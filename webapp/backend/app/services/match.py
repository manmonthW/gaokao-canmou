"""普通类智能匹配服务（Phase 2 MVP）。

实现 spec §7 六步：
  1. 输入校验
  2. 资格/数据过滤（年份参考范围、类别/学科类/批次严格一致、常规≠征集、默认排最低位次空值）
  3. 构造招生候选单元 = 院校 + 专业 + 批次 + 志愿阶段（不按校聚合，避免掩盖同校专业位次差）
  4. 历史统计（覆盖年份、近一年位次、最好/最差/中位位次、跨度/波动、连续招生、断档）
  5. 风险分类（冲/稳/保/高波动/数据不足，阈值可配，待回测）
  6. 偏好排序（仅影响同档内展示顺序，不改资格与基础风险）

说明：
  - 当前库内「录取最低分」仅 373 行，远少于「投档最低分」(3.7 万行)，
    故 MVP 统一以**投档最低分**对应的 lowest_rank 作为门槛位次（代表进档门槛）。
    后续补录取分后，可在 step4 叠加录取分细化「稳/保」判定。
  - 历史跨 2025/2026 两年；考生位次与历史位次直接用「位次法」比较
    （R <= lowest_rank 表示考生位次优于该门槛，等价的分数更高）。
"""
from statistics import median
from typing import Optional

from app import db

# --------------------------- 可调阈值（经回测后再固化） ---------------------------
MATCH_CONFIG = {
    # 分类所需最少年份：<2 年判为「数据不足」
    "min_years": 2,
    # 高波动判定：相对波动(跨度/中位) >= 该值 且 绝对跨度 >= min_abs_span
    "high_vol_rel": 0.5,
    "high_vol_abs": 2000,
    # 断档判定：最差年份位次 > 中位 * break_multiplier
    "break_multiplier": 1.6,
}

RISK_ORDER = ["保", "稳", "冲", "高波动", "数据不足"]

# 再选科目全集（选科要求校验用，D2b）
_SUBJECTS = ["物理", "化学", "生物", "政治", "历史", "地理"]


def _first_choice(subject: str):
    """学科类 → 首选科目。"""
    if subject and "物理" in subject:
        return "物理"
    if subject and "历史" in subject:
        return "历史"
    return None


def _first_req_ok(first_req, subject):
    fc = _first_choice(subject)
    if not first_req or "不限" in first_req or "均可" in first_req:
        return True
    return bool(fc and fc in first_req)


def _re_req_ok(re_req, electives):
    """启发式校验再选要求（官方表头确定前的保守实现）：
    空/不限 → 通过；含「选 1/或」→ 任一命中；否则需全部命中。"""
    if not re_req or "不限" in re_req:
        return True
    tokens = [s for s in _SUBJECTS if s in re_req]
    if not tokens:
        return True
    if "选1" in re_req.replace(" ", "") or "或" in re_req:
        return any(t in electives for t in tokens)
    return all(t in electives for t in tokens)


async def get_data_version() -> Optional[str]:
    rel = await db.fetch_one(
        """SELECT version FROM data_releases
           WHERE status = 'published' ORDER BY published_at DESC LIMIT 1"""
    )
    return rel[0] if rel else None


def _build_unit_key(school_code, major_code, major_name, batch):
    mkey = major_code if major_code else major_name
    return (school_code, mkey, batch)


def _classify(unit: dict, R: int, cfg: dict):
    """返回 (risk, reason)。"""
    n = unit["n_years"]
    # 全部缺失最低位次：无法用位次法，降级为分数参考并标数据不足
    if n == 0:
        return "数据不足", "该单元最低位次缺失，仅可作分数参考，位次法不可用。"

    single = n < cfg["min_years"]  # 仅 1 年：仍按该年分类，但提示参考性有限
    best, worst, med = unit["best_rank"], unit["worst_rank"], unit["median_rank"]
    rel = (unit["span"] / med) if med else 0.0

    # 高波动优先（位次极不稳定，单独成档；至少 2 年才有意义）
    if not single and rel >= cfg["high_vol_rel"] and unit["span"] >= cfg["high_vol_abs"]:
        return (
            "高波动",
            f"历年位次跨度大（{best}～{worst}，相对波动 {rel:.0%}），结果不确定性高。",
        )

    if R <= best:
        base = "保"
        reason = f"你的位次 {R} 优于历史最易年份最低位次 {best}（领先 {best - R} 名），录取把握大。"
    elif R <= med:
        base = "稳"
        reason = f"你的位次 {R} 介于历史最易 {best} 与中位 {med} 之间，较稳。"
    elif R <= worst:
        base = "冲"
        reason = f"你的位次 {R} 介于中位 {med} 与历史最差 {worst} 之间，可冲刺。"
    else:
        base = "冲"
        reason = f"你的位次 {R} 高于历史最差位次 {worst}，属高风险冲刺。"

    if unit["break_detected"]:
        reason += " 注意：存在年份断档（位次大幅跳变），历史参考性下降。"
    if single:
        reason += "（仅 1 年投档数据，参考性有限）"
    return base, reason


def _build_candidate(unit: dict, R: int, cfg: dict):
    risk, reason = _classify(unit, R, cfg)
    last = unit["last_year_rank"]
    rank_diff_last = (R - last) if last is not None else None
    if risk == "数据不足":
        warning = "数据不足：最低位次缺失，仅可作分数参考。"
    elif unit["n_years"] < cfg["min_years"]:
        warning = f"数据不足：仅 {unit['n_years']} 年投档数据，参考性有限。"
    else:
        warning = None
    return {
        "school_code": unit["school_code"],
        "school_name": unit["school_name"],
        "major_code": unit["major_code"],
        "major_name": unit["major_name"],
        "catalog_name": unit.get("catalog_name"),
        "batch": unit["batch"],
        "province": unit["province"],
        "city": unit["city"],
        "level": unit["level"],
        "nature": unit["nature"],
        "type": unit["type"],
        "flags": unit["flags"],
        "n_years": unit["n_years"],
        "has_both_years": unit["has_both_years"],
        "best_rank": unit["best_rank"],
        "worst_rank": unit["worst_rank"],
        "median_rank": unit["median_rank"],
        "last_year": unit["last_year"],
        "last_year_rank": last,
        "last_year_score": unit.get("last_year_score"),
        "span": unit["span"],
        "relative_vol": round(unit["span"] / unit["median_rank"], 3)
        if unit["median_rank"] else None,
        "continuous": unit["continuous"],
        "break_detected": unit["break_detected"],
        "risk": risk,
        "risk_reason": reason,
        "rank_diff_last": rank_diff_last,
        "warning": warning,
        "yearly": [{"year": y, "lowest_rank": r} for y, r in unit["yearly"]],
    }


async def match(
    *,
    year: int,
    category: str,
    subject: str,
    batch: str,
    rank: Optional[int] = None,
    score: Optional[int] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    level: Optional[str] = None,
    nature: Optional[str] = None,
    type_: Optional[str] = None,
    major_keyword: Optional[str] = None,
    has_both_years: Optional[bool] = None,
    risk: Optional[str] = None,
    exclude_flags: Optional[list] = None,
    electives: Optional[list] = None,
    page: int = 1,
    page_size: int = 30,
    cfg: Optional[dict] = None,
):
    """普通类智能匹配主入口。"""
    cfg = cfg or MATCH_CONFIG

    # ---------- 第一步：输入校验 ----------
    if rank is None and score is not None:
        # 仅有分数：借定位服务反查位次
        from app.services import locate

        r = await locate.score_to_rank(year, category, subject, score)
        if r.get("found") and r.get("rank") is not None:
            rank = r["rank"]
        elif r.get("found") and r.get("rank_range"):
            rank = r["rank_range"][0]  # 取区间上界（更保守）
    if rank is None or rank <= 0:
        return {
            "error": "请提供有效位次（正整数），或有效的分数以便反查位次。",
            "examinee": {
                "year": year, "category": category, "subject": subject,
                "batch": batch, "score": score, "rank": rank,
            },
        }

    # ---------- 第二步：资格/数据过滤 ----------
    # 包含 lowest_rank 为空行（库内约 570 行）：这些归入「数据不足」档，
    # 按 roadmap 要求降级为「分数参考」并显式标注，而非直接丢弃。
    rows = await db.fetch_all(
        """SELECT a.year, a.school_code, a.school_name, a.major_code, a.major_name,
                  a.batch, a.lowest_rank, a.lowest_score, a.flags,
                  p.province, p.city, p.level, p.nature, p.type
           FROM admission_scores a
           LEFT JOIN school_profiles p ON a.school_code = p.code
           WHERE a.category = %s AND a.subject = %s AND a.batch = %s
             AND a.is_collection = FALSE
             AND a.score_kind = '投档最低分'
           ORDER BY a.school_code, a.major_name, a.batch, a.year""",
        (category, subject, batch),
    )

    # ---------- 第三步：构造候选单元 ----------
    units: dict = {}
    for (
        y, sc, sn, mc, mn, bt, lr, lscore, fl,
        prov, cty, lvl, nat, typ,
    ) in rows:
        key = _build_unit_key(sc, mc, mn, bt)
        u = units.get(key)
        if u is None:
            u = {
                "school_code": sc, "school_name": sn,
                "major_code": mc, "major_name": mn, "batch": bt,
                "province": prov, "city": cty, "level": lvl,
                "nature": nat, "type": typ,
                "years": [], "ranks": [], "yearly": [], "scores": {},
                "flags": set(),
            }
            units[key] = u
        u["flags"] |= set(fl or [])
        u["years"].append(y)
        if lscore is not None:
            u["scores"][y] = lscore
        if lr is not None:
            u["ranks"].append(lr)
            u["yearly"].append((y, lr))

    # ---------- 第四步：历史统计 ----------
    for u in units.values():
        yrs = sorted(set(u["years"]))
        ranks = sorted(u["ranks"])
        u["n_years"] = len(ranks)  # 有最低位次的年份数
        u["all_null"] = len(ranks) == 0  # 全部缺失最低位次
        if ranks:
            u["best_rank"] = ranks[0]
            u["worst_rank"] = ranks[-1]
            u["median_rank"] = int(median(ranks))
            u["span"] = ranks[-1] - ranks[0]
        else:
            u["best_rank"] = u["worst_rank"] = u["median_rank"] = u["span"] = None
        u["has_both_years"] = (2025 in yrs and 2026 in yrs)
        u["continuous"] = (yrs == list(range(yrs[0], yrs[0] + len(yrs))))
        u["break_detected"] = (
            len(ranks) >= 2
            and u["worst_rank"] > u["median_rank"] * cfg["break_multiplier"]
        )
        max_y = max(yrs)
        u["last_year"] = max_y
        u["last_year_rank"] = next((r for y, r in u["yearly"] if y == max_y), None)
        u["last_year_score"] = u["scores"].get(max_y)
        u["flags"] = sorted(u["flags"])
        u["yearly"].sort(key=lambda t: t[0])

    # ---------- 第四步（补充）：批量关联标准专业名 ----------
    # 把招生专业名（如"工科试验班(卓越计划)[计算机科学与...]"）映射到
    # major_catalog 里的标准专业名（如"计算机科学与技术"），供前端跳转专业详情。
    major_names = {u["major_name"] for u in units.values() if u["major_name"]}
    catalog_map: dict[str, str] = {}
    if major_names:
        # 一次性查库：标准专业名被招生专业名包含即视为命中
        rows = await db.fetch_all(
            """SELECT mc.name, a.major_name
               FROM major_catalog mc
               JOIN admission_scores a ON a.major_name ILIKE '%%' || mc.name || '%%'
               WHERE a.major_name = ANY(%s)""",
            (list(major_names),),
        )
        for std_name, adm_name in rows:
            # 同一招生名可能命中多个标准专业，取最长的（最具体）
            if adm_name not in catalog_map or len(std_name) > len(catalog_map[adm_name]):
                catalog_map[adm_name] = std_name
    for u in units.values():
        u["catalog_name"] = catalog_map.get(u["major_name"])

    # ---------- 第四步之后：构造候选 ----------
    candidates = [_build_candidate(u, rank, cfg) for u in units.values()]

    # ---------- 选科资格校验（D2b）：仅当该年选科要求已入库时启用 ----------
    excluded_by_subject = 0
    subjreq_loaded = False
    if electives:
        cnt = await db.fetch_one(
            "SELECT count(*) FROM subject_requirements WHERE year=%s", (year,))
        if cnt and cnt[0] > 0:
            subjreq_loaded = True
            req_rows = await db.fetch_all(
                """SELECT school_code, school_name, major_name, first_req, re_req
                   FROM subject_requirements WHERE year=%s""", (year,))
            # (school_code, major_name) 级优先；major_name 为空的行视为院校级兑底
            req_by_unit, req_by_school = {}, {}
            for sc, sn, mn, fr, rr in req_rows:
                if mn:
                    req_by_unit[(sc, mn)] = (fr, rr)
                else:
                    req_by_school.setdefault(sc, []).append((fr, rr))
            kept = []
            for c in candidates:
                req = req_by_unit.get((c["school_code"], c["major_name"]))
                reqs = [req] if req else req_by_school.get(c["school_code"], [])
                if not reqs:
                    # 无记录：不默认「可报」，显式标注未核验
                    c["subject_unverified"] = True
                    w = "选科要求未收录，请自行核对官方选科要求。"
                    c["warning"] = f"{c['warning']} {w}" if c["warning"] else w
                    kept.append(c)
                    continue
                ok = any(_first_req_ok(fr, subject) and _re_req_ok(rr, electives)
                         for fr, rr in reqs)
                if ok:
                    kept.append(c)
                else:
                    excluded_by_subject += 1
            candidates = kept

    # 应用偏好筛选（省/市/层次/性质/类型/专业关键词/两年均有/排除标记）
    def keep(c):
        if exclude_flags and set(exclude_flags) & set(c["flags"]):
            return False
        if province and c["province"] != province:
            return False
        if city and c["city"] != city:
            return False
        if level and c["level"] != level:
            return False
        if nature and c["nature"] != nature:
            return False
        if type_ and c["type"] != type_:
            return False
        if major_keyword and major_keyword not in (c["major_name"] or ""):
            return False
        if has_both_years is not None and c["has_both_years"] != has_both_years:
            return False
        return True

    filtered = [c for c in candidates if keep(c)]

    # 风险分档计数
    totals = {k: 0 for k in RISK_ORDER}
    for c in filtered:
        totals[c["risk"]] += 1
    totals["total"] = len(filtered)

    # 风险过滤前的匹配结果快照（供城市 facet 使用，只含实际出现的城市）
    matched_filtered = filtered

    # 按风险过滤（可选）
    if risk:
        filtered = [c for c in filtered if c["risk"] == risk]

    # 排序：风险优先（保>稳>冲>高波动>数据不足），同档内按位次差升序（最接近者靠前）
    filtered.sort(key=lambda c: (RISK_ORDER.index(c["risk"]),
                                 c["rank_diff_last"] if c["rank_diff_last"] is not None else 1 << 30))

    # 分页
    total = len(filtered)
    page = max(1, page)
    start = (page - 1) * page_size
    items = filtered[start:start + page_size]

    # 聚合 facet（供前端下拉）
    # - 省/层次/性质/类型 基于全量候选（保持下拉稳定可选）
    # - 城市基于"本次匹配结果"（风险过滤前的 filtered，即经考生位次/选科分类后的候选），
    #   因此城市下拉只显示本次结果中实际出现的城市，而非该省全部城市
    city_base = matched_filtered
    facets: dict = {"province": {}, "city": {}, "level": {}, "nature": {}, "type": {}}
    for c in candidates:
        for fkey in ("province", "level", "nature", "type"):
            v = c[fkey]
            if v is None:
                continue
            facets[fkey][v] = facets[fkey].get(v, 0) + 1
    for c in city_base:
        v = c["city"]
        if v is None:
            continue
        facets["city"][v] = facets["city"].get(v, 0) + 1
    facets = {k: sorted(v.items(), key=lambda kv: -kv[1]) for k, v in facets.items()}

    version = await get_data_version()

    # ---------- 批次发布状态上下文（D4）：让每条结果知道自己处在什么数据环境下 ----------
    pub = await db.fetch_all(
        """SELECT stage, status, note, official_published_at
           FROM admission_publication_status
           WHERE year=%s AND category=%s AND subject=%s AND batch=%s
           ORDER BY stage""",
        (year, category, subject, batch),
    )
    batch_context = {
        "batch": batch,
        "score_kind": "投档最低分",
        "score_kind_note": (
            "结果按「投档最低分」（进档门槛位次）统计。辽宁普通批以投档线发布为主，"
            "「录取最低分」仅提前批等批次发布；且「专业+学校」志愿无校内专业调剂，"
            "投档线与录取线差距小，可直接作为门槛参考。"),
        "publication": [
            {"stage": r[0], "status": r[1], "note": r[2],
             "official_published_at": str(r[3]) if r[3] else None}
            for r in pub
        ],
    }
    if not pub:
        batch_context["warning"] = (
            "该批次未登记发布状态，以上历史数据可能不完整，请结合省招考办官方公告核实。")

    return {
        "data_version": version,
        "examinee": {
            "year": year, "category": category, "subject": subject,
            "batch": batch, "score": score, "rank": rank,
            "electives": electives,
        },
        "totals": totals,
        "excluded_by_subject": excluded_by_subject,
        "subject_requirements_loaded": subjreq_loaded,
        "batch_context": batch_context,
        "facets": {k: [{"value": v, "count": c} for v, c in lst] for k, lst in facets.items()},
        "page": page,
        "page_size": page_size,
        "items": items,
    }
