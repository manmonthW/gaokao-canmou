"""普通类智能匹配服务（Phase 2 MVP，A1–A4 算法层增强）。

实现 spec §7 六步：
  1. 输入校验
  2. 资格/数据过滤（年份参考范围、类别/学科类/批次严格一致、常规≠征集、默认排最低位次空值）
  3. 构造招生候选单元 = 院校 + 专业 + 批次 + 志愿阶段（不按校聚合，避免掩盖同校专业位次差）
  4. 历史统计（覆盖年份、近一年位次、最好/最差/中位位次、跨度/波动、连续招生、断档）
  5. 风险分类（冲/稳/保/高波动/数据不足；保档含回测固化的安全边际 margin）
  6. 偏好排序（仅影响同档内展示顺序，不改资格与基础风险）

A1–A4 算法层增强（2026-08-08，依据 first-principles-review.md §5.2）：
  - A1：「保」判据由 R<=best 收紧为 R <= best×safe_margin；margin=0.85 由
    2025→2026 回测定参（门槛年际比值 P10≈0.87，margin=0.85 时保档规则
    次年仍成立比例：物理 91.6% / 历史 92.4%，见 backtest_report.txt）；
    解释文案改为区间语言：分档是对明年的区间判断，不是对历史的事实陈述。
  - A2：回测报告固化（backtest_report.txt）+ classification_note 向用户公开分档依据。
  - A3：sensitivity() 位次 ±5%/±10% 敏感度一键试算（同一批单元对多个 R 重算）。
  - A4：has_both_years 与 n_years 口径统一（均基于有位次的年份）；
    本科提前批 A/B 段跨年别名在代码层归一（_normalize_batch，不改数据）。

说明：
  - 当前库内「录取最低分」仅 448 行且全在提前批，普通批官方只发投档线，
    故统一以**投档最低分**对应的 lowest_rank 作为门槛位次（代表进档门槛）。
  - 历史跨 2025/2026 两年；考生位次与历史位次直接用「位次法」比较
    （R <= lowest_rank 表示考生位次优于该门槛，等价的分数更高）。
"""
from statistics import median
from typing import Optional

from app import db

# --------------------------- 可调阈值（margin 已经 2025→2026 回测固化，其余阈值附回测依据） ---------------------------
MATCH_CONFIG = {
    # 分类所需最少年份：<2 年判为「数据不足」
    "min_years": 2,
    # 「保」档安全边际（A1）：R <= best × safe_margin 才判保。
    # margin=0.85 回测定参：门槛年际比值 P10≈0.87，margin=0.85 时次年门槛仍 >= best×0.85
    # 的比例为物理 91.6% / 历史 92.4%（backtest_report.txt）；
    # 调整本参数必须附回测报告（spec §7.4，A2 制度化）。
    "safe_margin": 0.85,
    # 高波动判定：相对波动(跨度/中位) >= 该值 且 绝对跨度 >= min_abs_span
    # （回测：跨年相对变动中位 6.2%/7.4%、P90 31%/28%、≥50% 占比 4.7%/3.5%，0.5 阈值隔离尾部）
    "high_vol_rel": 0.5,
    "high_vol_abs": 2000,
    # 断档判定：最差年份位次 > 中位 * break_multiplier
    "break_multiplier": 1.6,
    # ---- 冲稳保边界治理（第一性原理 + 行业经验收敛，docs/strategy-chong-wen-bao.md）----
    # 保底子档分界：best <= R×1.5 为标准保底（行业「低于你 10~15%」主力保底的扩展带），
    # (R×1.5, R×3] 为极稳垫底（稳妥型方案的垫底位），再深为过深。
    "safe_band_core": 1.5,
    # 过深保底：保护在 best≈2R 处饱和（回测：门槛需年际改善 >100% 才会滑到拒绝你，
    # 而年际变动 P90≈31%、≥50% 仅 4.7%），行业最深的「极稳」也只到 ~30%，
    # 故 best > R×3 标记 over_safe：不增加安全性，只消耗 112 志愿配额。
    "over_safe_ratio": 3,
    # 超冲：历史门槛好于考生位次 20% 以上（best < R×0.8）。行业冲刺带为
    # 高于自身 5~10%，0.8 作为可执行冲刺的上界，再远基本只消耗槽位。
    "over_reach_ratio": 0.8,
}

RISK_ORDER = ["保", "稳", "冲", "高波动", "数据不足"]

# P5 偏好最小版：同档内重排依据（仅改展示顺序，不改资格与分档）
CITY_TIER_ORDER = ["一线", "新一线", "二线", "三线", "四线", "五线"]
PREF_SORT_OPTIONS = {"certainty", "level", "city"}

# A4 批次别名归一（仅用于跨年单元合并，展示仍用原始批次名，不改数据）：
# 2026 本科提前批拆为 A/B 段后，与 2025「本科提前批」为同一批次概念。
BATCH_ALIASES = {"本科提前批A段": "本科提前批", "本科提前批B段": "本科提前批"}


def _normalize_batch(batch):
    return BATCH_ALIASES.get(batch, batch)


def _batch_variants(batch):
    """请求批次 + 归一到同一概念的所有别名段（A4，供 DB 过滤展开）。"""
    norm = _normalize_batch(batch)
    variants = {norm}
    for alias, n in BATCH_ALIASES.items():
        if n == norm:
            variants.add(alias)
    return sorted(variants)


# A2 分档可信度说明（数字固化自 backtest_report.txt，2026-08-08 回测）。
# 调整 MATCH_CONFIG 必须重跑回测并同步更新本说明（spec §7.4）。
CLASSIFICATION_NOTE = {
    "method": "位次法：拿每个单元历年录取最低分对应的全省位次，与你的位次比较，"
              "分成保/稳/冲/高波动/数据不足五档；分档是对明年门槛的区间判断，不是对历史的事实陈述。",
    "safe_margin": MATCH_CONFIG["safe_margin"],
    "backtest": {
        "pair": "用 2025 年数据判档、用 2026 年实际投档门槛检验（同单元跨年对照）",
        "margin_coverage": (
            "被判「保」的单元中，次年（2026）门槛实际没有越过安全线的比例："
            "物理学科类本科批 91.6%（7,027 个单元）、历史学科类本科批 92.4%（1,896 个单元）"
            "——即「保」的判定次年约九成依旧成立"),
        "rel_delta": (
            "录取位次年际变动：多数单元变动约 6–7%（中位数），九成单元变动在 30% 以内；"
            "变动 ≥50% 的仅 4.7%/3.5%，这类单元会被标为「高波动」"),
    },
    "disclaimer": "以上比例衡量的是门槛跨年是否稳定（即分档规则是否可靠），不是录取概率；本站不输出概率数字。",
}

# A3 敏感度试算偏移（负值 = 位次变好）
SENSITIVITY_OFFSETS = [
    (-0.10, "位次 -10%（偏好）"),
    (-0.05, "位次 -5%（偏好）"),
    (0.0, "当前位次"),
    (0.05, "位次 +5%（偏差）"),
    (0.10, "位次 +10%（偏差）"),
]

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
    # A4：批次别名归一，使 2025 本科提前批与 2026 A/B 段合并为同一单元
    return (school_code, mkey, _normalize_batch(batch))


def _over_safe(risk: str, best_rank, R: int, cfg: dict) -> bool:
    """过深保底：保档且历史最难年门槛超过考生位次 over_safe_ratio 倍。
    保护在 ~2R 处饱和，过深不增加安全性，只消耗志愿额度。"""
    return (risk == "保" and best_rank is not None and R > 0
            and best_rank > R * cfg["over_safe_ratio"])


def _over_reach(risk: str, best_rank, R: int, cfg: dict) -> bool:
    """超冲：冲档且历史门槛好于考生位次超过 (1-over_reach_ratio)，
    超出行业冲刺带（5~10%）过多，基本只消耗槽位。"""
    return (risk == "冲" and best_rank is not None and R > 0
            and best_rank < R * cfg["over_reach_ratio"])


def _safe_band(risk: str, best_rank, R: int, cfg: dict):
    """保档子档：标准保底（保护接近饱和且真会去读）/ 极稳垫底（少量跨档兑底）/
    过深保底（槽位浪费）；非保档返回 None。"""
    if risk != "保" or best_rank is None or R <= 0:
        return None
    if best_rank <= R * cfg["safe_band_core"]:
        return "标准保底"
    if best_rank <= R * cfg["over_safe_ratio"]:
        return "极稳垫底"
    return "过深保底"


def _classify(unit: dict, R: int, cfg: dict):
    """返回 (risk, reason)。区间语言：分档是对明年的区间判断，不是对历史的事实陈述（A1）。"""
    n = unit["n_years"]
    # 全部缺失最低位次：无法用位次法，降级为分数参考并标数据不足
    if n == 0:
        return "数据不足", "该单元最低位次缺失，仅可作分数参考，位次法不可用。"

    single = n < cfg["min_years"]  # 仅 1 年：仍按该年分类，但提示参考性有限
    best, worst, med = unit["best_rank"], unit["worst_rank"], unit["median_rank"]
    margin = cfg["safe_margin"]
    safe_line = int(best * margin)  # 保档门槛：历史最难年门槛再收紧 margin
    rel = (unit["span"] / med) if med else 0.0

    # 高波动优先（位次极不稳定，单独成档；至少 2 年才有意义）
    if not single and rel >= cfg["high_vol_rel"] and unit["span"] >= cfg["high_vol_abs"]:
        return (
            "高波动",
            f"历年位次跨度大（{best}～{worst}，相对波动 {rel:.0%}），结果不确定性高。",
        )

    if R <= safe_line:
        base = "保"
        reason = (
            f"你的位次 {R} 优于历史门槛区间 [{best}, {worst}] 的最严端 {best}，"
            f"且领先安全边际线 {safe_line} 达 {safe_line - R} 名。"
            f"明年门槛可能在历史区间附近移动，按回测该幅度大概率不越过此安全边际。")
    elif R <= best:
        base = "稳"
        reason = (
            f"你的位次 {R} 优于历史最难年门槛 {best}，但未越过安全边际线 {safe_line}；"
            f"门槛年际变动可能吃掉这段领先（回测口径），按「稳」对待。")
    elif R <= med:
        base = "稳"
        reason = (
            f"你的位次 {R} 落在历史门槛区间 [{best}, {worst}] 内、优于中位 {med}；"
            f"明年门槛若在区间内移动，录取机会较大。")
    elif R <= worst:
        base = "冲"
        reason = (
            f"你的位次 {R} 落在历史门槛区间 [{best}, {worst}] 内、劣于中位 {med}；"
            f"需明年门槛偏向区间宽松端才可进档，属可冲刺。")
    else:
        base = "冲"
        reason = (
            f"你的位次 {R} 位于历史门槛区间 [{best}, {worst}] 之外（落后最宽松端 {R - worst} 名），"
            f"仅当明年门槛大幅放宽时才有可能，属高风险冲刺。")

    # 断崖变易单元：最近年门槛明显宽于最难年 → 点明「去年宽松不作数」，
    # 解释为何「看起来领先很多却只判稳」
    if base == "稳":
        last = unit.get("last_year_rank")
        if last is not None and last > best * 1.3:
            reason += (f" 注意：最近年门槛 {last} 明显宽于历史最难年 {best}，去年宽松不代表明年；"
                       "若门槛回归难年水平，当前领先将不成立，故不能计「保」。")

    if unit["break_detected"]:
        reason += " 注意：存在年份断档（位次大幅跳变），历史参考性下降。"
    if single:
        reason += "（仅 1 年投档数据，参考性有限）"
    return base, reason


def _build_candidate(unit: dict, R: int, cfg: dict):
    risk, reason = _classify(unit, R, cfg)
    over_safe = _over_safe(risk, unit["best_rank"], R, cfg)
    over_reach = _over_reach(risk, unit["best_rank"], R, cfg)
    if over_safe:
        reason += (f"（注意：历史最难年门槛 {unit['best_rank']} 约为你的位次 {R} 的 "
                   f"{unit['best_rank'] // R} 倍——保护在 2 倍左右已饱和，过深不增加安全性，"
                   "只消耗志愿额度，请审慎占用槽位。）")
    if over_reach:
        reason += (f"（注意：历史门槛 {unit['best_rank']} 好于你的位次 {R} 超过 20%，差距过大，"
                   "需明年门槛大幅回落才有机会，基本只消耗槽位，建议仅作表头梦想位。）")
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
        # P5 同档内重排用：院校层次优先级（985>211>双一流>其他）与城市分级
        "school_tier": (0 if unit.get("is_985") else 1 if unit.get("is_211")
                        else 2 if unit.get("is_dfc") else 3),
        "city_tier": unit.get("city_tier"),
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
        # 冲稳保边界治理：过深保底/超冲标记 + 保档子档（展示与策略层，不改五档资格判定）
        "over_safe": over_safe,
        "over_reach": over_reach,
        "safe_band": _safe_band(risk, unit["best_rank"], R, cfg),
        "safe_line": int(unit["best_rank"] * cfg["safe_margin"]) if unit["best_rank"] else None,
        "rank_diff_last": rank_diff_last,
        "warning": warning,
        "yearly": [{"year": y, "lowest_rank": r} for y, r in unit["yearly"]],
    }


async def _resolve_rank(year, category, subject, rank, score):
    """仅有分数时借定位服务反查位次（区间取上界，更保守）。"""
    if rank is None and score is not None:
        from app.services import locate

        r = await locate.score_to_rank(year, category, subject, score)
        if r.get("found") and r.get("rank") is not None:
            rank = r["rank"]
        elif r.get("found") and r.get("rank_range"):
            rank = r["rank_range"][0]  # 取区间上界（更保守）
    return rank


async def _prepare_candidates(
    *, category, subject, batch, year, rank,
    province=None, city=None, level=None, nature=None, type_=None,
    major_keyword=None, has_both_years=None,
    exclude_flags=None, electives=None, cfg,
):
    """第 2–4 步 + 选科校验 + 偏好筛选：返回筛选后候选（match 与 sensitivity 共用，A3）。
    返回 (filtered, candidates_all, excluded_by_subject, subjreq_loaded)。"""
    # ---------- 第二步：资格/数据过滤 ----------
    # 包含 lowest_rank 为空行（库内约 570 行）：这些归入「数据不足」档，
    # 按 roadmap 要求降级为「分数参考」并显式标注，而非直接丢弃。
    rows = await db.fetch_all(
        """SELECT a.year, a.school_code, a.school_name, a.major_code, a.major_name,
                  a.batch, a.lowest_rank, a.lowest_score, a.flags,
                  p.province, p.city, p.level, p.nature, p.type,
                  p.is_985, p.is_211, p.is_dfc, ct.tier
           FROM admission_scores a
           LEFT JOIN school_profiles p ON a.school_code = p.code
           LEFT JOIN cities ct ON p.city = ct.city
           WHERE a.category = %s AND a.subject = %s AND a.batch = ANY(%s)
             AND a.is_collection = FALSE
             AND a.score_kind = '投档最低分'
           ORDER BY a.school_code, a.major_name, a.batch, a.year""",
        (category, subject, _batch_variants(batch)),
    )

    # ---------- 第三步：构造候选单元 ----------
    units: dict = {}
    for (
        y, sc, sn, mc, mn, bt, lr, lscore, fl,
        prov, cty, lvl, nat, typ,
        is985, is211, isdfc, ctier,
    ) in rows:
        key = _build_unit_key(sc, mc, mn, bt)
        u = units.get(key)
        if u is None:
            # 跨年合并单元的批次名：优先用用户请求的批次名，避免展示成某年的别名段
            u = {
                "school_code": sc, "school_name": sn,
                "major_code": mc, "major_name": mn,
                "batch": batch if _normalize_batch(bt) == _normalize_batch(batch) else bt,
                "province": prov, "city": cty, "level": lvl,
                "nature": nat, "type": typ,
                "is_985": is985, "is_211": is211, "is_dfc": isdfc,
                "city_tier": ctier,
                "years": [], "ranks": [], "yearly": [], "scores": {},
                "rank_years": set(),
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
            u["rank_years"].add(y)  # A4：有位次的年份（与 n_years 同源）

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
        # A4 口径统一：has_both_years 与 n_years 均基于「有最低位次的年份」，
        # 避免某年位次缺失时 has_both_years=True 但 n_years=1 的展示矛盾。
        u["has_both_years"] = (2025 in u["rank_years"] and 2026 in u["rank_years"])
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
    return filtered, candidates, excluded_by_subject, subjreq_loaded


def _risk_at(c: dict, R: int, cfg: dict):
    """同一候选在另一考生位次下重新分档（A3 试算 / P1 区间模式共用）。"""
    u = {"n_years": c["n_years"], "best_rank": c["best_rank"],
         "worst_rank": c["worst_rank"], "median_rank": c["median_rank"],
         "span": c["span"], "break_detected": c["break_detected"]}
    return _classify(u, R, cfg)


def _pref_sort_key(c: dict, pref_sort: Optional[str]):
    """P5 排序键：风险档优先不变；同档内按偏好重排。
    接近度 = |位次差|（不带符号）：带符号 diff 在保档恒负、冲档恒正，
    升序会让保档最深的垫底校排在最前，与「最接近匹配」直觉相反。
    certainty（默认）＝最接近匹配原则：同档内门槛最贴近你位次的单元靠前
    （保档即「最好的保底」，冲档即「最现实的冲刺」），同距离时院校层次高者靠前；
    level＝院校层次优先（985>211>双一流），接近度为次键；
    city＝城市分级优先（一线→五线），接近度为次键。"""
    diff = c["rank_diff_last"] if c["rank_diff_last"] is not None else 1 << 30
    near = abs(diff)
    head = RISK_ORDER.index(c["risk"])
    tier = c.get("school_tier", 9)
    if pref_sort == "level":
        return (head, tier, near)
    if pref_sort == "city":
        t = c.get("city_tier")
        tidx = CITY_TIER_ORDER.index(t) if t in CITY_TIER_ORDER else 99
        return (head, tidx, near)
    return (head, near, tier, diff)


def _totals_at_rank(candidates, R: int, cfg: dict):
    """同一候选集在不同考生位次下重新分档计数（A3 敏感度一键试算）。"""
    totals = {k: 0 for k in RISK_ORDER}
    for c in candidates:
        risk, _ = _risk_at(c, R, cfg)
        totals[risk] += 1
    totals["total"] = len(candidates)
    return totals


async def sensitivity(
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
    exclude_flags: Optional[list] = None,
    electives: Optional[list] = None,
    cfg: Optional[dict] = None,
):
    """A3 敏感度一键试算：位次 ±5%/±10% 时同一候选集的分档变化。"""
    cfg = cfg or MATCH_CONFIG
    rank = await _resolve_rank(year, category, subject, rank, score)
    if rank is None or rank <= 0:
        return {"error": "请提供有效位次（正整数），或有效的分数以便反查位次。"}
    filtered, _, excluded_by_subject, subjreq_loaded = await _prepare_candidates(
        category=category, subject=subject, batch=batch, year=year, rank=rank,
        province=province, city=city, level=level, nature=nature, type_=type_,
        major_keyword=major_keyword, has_both_years=has_both_years,
        exclude_flags=exclude_flags, electives=electives, cfg=cfg,
    )
    scenarios = []
    for off, label in SENSITIVITY_OFFSETS:
        R2 = max(1, int(round(rank * (1 + off))))
        scenarios.append({
            "label": label, "offset": off, "rank": R2,
            "totals": _totals_at_rank(filtered, R2, cfg),
        })
    return {
        "examinee": {"year": year, "category": category, "subject": subject,
                     "batch": batch, "score": score, "rank": rank},
        "excluded_by_subject": excluded_by_subject,
        "subject_requirements_loaded": subjreq_loaded,
        "scenarios": scenarios,
        "note": ("试算基于同一候选集与分档规则（含安全边际），仅改变考生位次，"
                 "用于展示分档边界对位次的敏感度，不是录取概率预测。"),
    }


async def match(
    *,
    year: int,
    category: str,
    subject: str,
    batch: str,
    rank: Optional[int] = None,
    score: Optional[int] = None,
    rank_lo: Optional[int] = None,
    rank_hi: Optional[int] = None,
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
    pref_sort: Optional[str] = None,
    page: int = 1,
    page_size: int = 30,
    cfg: Optional[dict] = None,
):
    """普通类智能匹配主入口。P1：rank_lo/rank_hi 给定时按区间模式（备考期估位）；
    P5：pref_sort 只影响同档内展示顺序（certainty/level/city）。"""
    cfg = cfg or MATCH_CONFIG
    if pref_sort and pref_sort not in PREF_SORT_OPTIONS:
        pref_sort = None

    # ---------- P1 备考期模式：位次区间 → 乐观/悲观双档 ----------
    # lo（位次数字小＝更好）为乐观情景，hi 为悲观情景；主判定用 hi（保守）。
    interval = None
    if rank_lo is not None or rank_hi is not None:
        if (rank_lo is None or rank_hi is None or rank_lo <= 0 or rank_hi <= 0
                or rank_lo > rank_hi):
            return {
                "error": "位次区间无效：请同时填写上下界（正整数），且下界 ≤ 上界。",
                "examinee": {"year": year, "category": category, "subject": subject,
                             "batch": batch, "score": score, "rank": rank},
            }
        interval = {"lo": rank_lo, "hi": rank_hi}
        rank = rank_hi

    # ---------- 第一步：输入校验 ----------
    rank = await _resolve_rank(year, category, subject, rank, score)
    if rank is None or rank <= 0:
        return {
            "error": "请提供有效位次（正整数），或有效的分数以便反查位次。",
            "examinee": {
                "year": year, "category": category, "subject": subject,
                "batch": batch, "score": score, "rank": rank,
            },
        }

    # ---------- 第 2–4 步 + 选科校验 + 偏好筛选（与 sensitivity 共用，A3） ----------
    filtered, candidates, excluded_by_subject, subjreq_loaded = await _prepare_candidates(
        category=category, subject=subject, batch=batch, year=year, rank=rank,
        province=province, city=city, level=level, nature=nature, type_=type_,
        major_keyword=major_keyword, has_both_years=has_both_years,
        exclude_flags=exclude_flags, electives=electives, cfg=cfg,
    )

    # 风险分档计数
    totals = {k: 0 for k in RISK_ORDER}
    for c in filtered:
        totals[c["risk"]] += 1
    totals["total"] = len(filtered)
    # P1 区间模式：乐观情景（下界 lo）的分档计数
    totals_lo = _totals_at_rank(filtered, interval["lo"], cfg) if interval else None

    # 风险过滤前的匹配结果快照（供城市 facet 使用，只含实际出现的城市）
    matched_filtered = filtered

    # 按风险过滤（可选）
    if risk:
        filtered = [c for c in filtered if c["risk"] == risk]

    # 排序：风险优先（保>稳>冲>高波动>数据不足）；同档内默认按位次差升序，
    # P5 偏好重排：level＝院校层次优先，city＝城市分级优先
    filtered.sort(key=lambda c: _pref_sort_key(c, pref_sort))

    # 分页
    total = len(filtered)
    page = max(1, page)
    start = (page - 1) * page_size
    items = filtered[start:start + page_size]
    # P1 区间模式：每条结果附乐观情景分档（主判定为悲观 hi）
    if interval:
        for c in items:
            c["risk_lo"], c["risk_reason_lo"] = _risk_at(c, interval["lo"], cfg)

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
    # 发布登记描述的是「用于对比的历史录取年」（登记表只有 2025/2026 录取年的进度），
    # 考生年（如 2027）本身尚未录取、无登记，不能拿考生年去查；
    # 先取本批次库内实际存在的历史录取年，再按这些年份取发布进度。
    # 同时做别名展开（A4）：2026 提前批登记在 A/B 段名下，
    # 合并视图查「本科提前批」时也能取到发布登记，避免「未登记」误报。
    hist_years = await db.fetch_all(
        """SELECT DISTINCT year FROM admission_scores
           WHERE category=%s AND subject=%s AND batch = ANY(%s)
             AND is_collection = FALSE AND score_kind = '投档最低分'
           ORDER BY year""",
        (category, subject, _batch_variants(batch)),
    )
    years = [r[0] for r in hist_years]
    pub = await db.fetch_all(
        """SELECT DISTINCT year, stage, status, note, official_published_at
           FROM admission_publication_status
           WHERE year = ANY(%s) AND category=%s AND subject=%s AND batch = ANY(%s)
           ORDER BY year, stage""",
        (years, category, subject, _batch_variants(batch)),
    )
    batch_context = {
        "batch": batch,
        "score_kind": "投档最低分",
        "score_kind_note": (
            "结果按「投档最低分」（进档门槛位次）统计。辽宁普通批以投档线发布为主，"
            "「录取最低分」仅提前批等批次发布；且「专业+学校」志愿无校内专业调剂，"
            "投档线与录取线差距小，可直接作为门槛参考。"),
        "publication": [
            {"year": r[0], "stage": r[1], "status": r[2], "note": r[3],
             "official_published_at": str(r[4]) if r[4] else None}
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
            "rank_lo": interval["lo"] if interval else None,
            "rank_hi": interval["hi"] if interval else None,
            "electives": electives,
        },
        "interval": interval,
        "totals": totals,
        "totals_lo": totals_lo,
        "excluded_by_subject": excluded_by_subject,
        "subject_requirements_loaded": subjreq_loaded,
        "classification_note": CLASSIFICATION_NOTE,
        "batch_context": batch_context,
        "facets": {k: [{"value": v, "count": c} for v, c in lst] for k, lst in facets.items()},
        "page": page,
        "page_size": page_size,
        "items": items,
    }
