"""定位服务：分数<->位次、省控线判断、个人定位摘要。

所有查询只读 admission_scores / score_rank / batch_control_line。
位次口径：cumulative_rank = 不低于该分数的人数（省排名）。
顶部分数桶以 is_top_bucket 标记，界面显示为「X 分及以上」。
"""
from app import db
from typing import Optional

_BATCH_TO_LINE = {"专科": "专科", "本科": "本科", "提前": "本科"}


def _line_type(batch: Optional[str]) -> Optional[str]:
    if not batch:
        return None
    for kw, lt in _BATCH_TO_LINE.items():
        if kw in batch:
            return lt
    return None


async def _load_rank_table(year, category, subject):
    """返回按分数降序的 (score, count, cumulative_rank, is_top_bucket, source) 列表。"""
    return await db.fetch_all(
        """SELECT score, count, cumulative_rank, is_top_bucket, source
           FROM score_rank
           WHERE year=%s AND category=%s AND subject=%s
           ORDER BY score DESC""",
        (year, category, subject),
    )


async def score_to_rank(year, category, subject, score):
    rows = await _load_rank_table(year, category, subject)
    if not rows:
        return {"found": False,
                "error": f"无一分一段数据：{year} {category} {subject}"}
    total = rows[-1][2]  # 最低分对应 max(cumulative_rank) = 总人数
    exact = next((r for r in rows if r[0] == score), None)
    if exact:
        s, cnt, cum, top, src = exact
        beat = (total - cum) / total if total else None
        return {
            "found": True,
            "score": s,
            "rank": cum,
            "rank_range": [cum - cnt + 1, cum],
            "same_score_count": cnt,
            "is_top_bucket": top,
            "total_candidates": total,
            "percentile": round(beat * 100, 2) if beat is not None else None,
            "source": src,
        }
    top = rows[0]
    if score >= top[0]:  # 高于顶部桶
        return {"found": True, "score": score, "is_top_bucket": True,
                "rank_upper": top[2],
                "note": f"位次约为 {top[2]} 及以上（含顶部区间）",
                "total_candidates": total, "source": top[4]}
    lower = next((r for r in rows if r[0] < score), None)
    # 取「紧邻更高」的分数（rows 降序，reversed 后取首个 > score 即最小更高分），
    # 以得到尽量紧的位次区间估计，而非取到表格顶端的宽松上界。
    higher = next((r for r in reversed(rows) if r[0] > score), None)
    if lower and higher:
        return {"found": True, "score": score,
                "rank_range": [higher[2] + 1, lower[2]],
                "note": "该分数在一分一段表中无直接对应行，给出区间估计",
                "total_candidates": total, "source": lower[4]}
    return {"found": True, "score": score, "below_table": True,
            "note": f"低于一分一段表最低分（{rows[-1][0]}），位次大于 {rows[-1][2]}",
            "total_candidates": total}


async def rank_to_score(year, category, subject, rank):
    if rank <= 0:
        return {"found": False, "error": "位次必须为正整数"}
    rows = await _load_rank_table(year, category, subject)
    if not rows:
        return {"found": False,
                "error": f"无一分一段数据：{year} {category} {subject}"}
    total = rows[-1][2]
    top = rows[0]
    if top[3] and rank <= top[2]:
        return {"found": True, "score": top[0],
                "score_note": f"{top[0]} 及以上", "is_top_bucket": True,
                "rank": rank, "total_candidates": total, "source": top[4]}
    for s, cnt, cum, _top_f, src in rows:
        if (cum - cnt + 1) <= rank <= cum:
            return {"found": True, "score": s, "rank": rank,
                    "count_in_bucket": cnt, "total_candidates": total,
                    "source": src}
    return {"found": True, "below_table": True,
            "note": f"位次 {rank} 超出一分一段表范围（总人数 {total}）",
            "total_candidates": total}


async def judge_line(year, category, subject, score, batch=None, line_type=None):
    lt = line_type or _line_type(batch)
    if not lt:
        return {"error": "无法确定要查的线，请传 batch 或 line_type"}
    row = await db.fetch_one(
        "SELECT score, note FROM batch_control_line "
        "WHERE year=%s AND category=%s AND subject=%s AND line_type=%s",
        (year, category, subject, lt))
    if not row:
        return {"error": f"无对应省控线：{year} {category} {subject} {lt}"}
    line, note = row
    res = {"primary": {"line_type": lt, "line": line,
                       "passed": score >= line, "gap": score - line}}
    if category == "普通类" and lt == "本科" and batch and "专科" not in batch:
        st = await db.fetch_one(
            "SELECT score FROM batch_control_line "
            "WHERE year=%s AND category=%s AND subject=%s AND line_type='特殊类型'",
            (year, category, subject))
        if st:
            res["special_type"] = {"line": st[0], "passed": score >= st[0],
                                   "gap": score - st[0]}
    if category in ("体育类", "艺术类"):
        res["note"] = ("仅判断文化课控制线；体育/艺术类还需满足相应专业控制线方可过线。"
                       + (f"（{note}）" if note else ""))
    return res


async def cross_year_scores(year, category, subject, rank):
    yrs = await db.fetch_all(
        "SELECT DISTINCT year FROM score_rank "
        "WHERE category=%s AND subject=%s AND year<>%s ORDER BY year",
        (category, subject, year))
    out = []
    for (yr,) in yrs:
        r = await rank_to_score(yr, category, subject, rank)
        if r.get("found") and "score" in r:
            out.append({"year": yr, "score": r["score"],
                        "score_note": r.get("score_note")})
    return out


async def line_rank(year, category, subject, line_type):
    """返回某年某控制线对应的位次（用于位次法过线参考）。"""
    row = await db.fetch_one(
        "SELECT score FROM batch_control_line "
        "WHERE year=%s AND category=%s AND subject=%s AND line_type=%s",
        (year, category, subject, line_type))
    if not row:
        return None
    line_score = row[0]
    r = await score_to_rank(year, category, subject, line_score)
    rk = r.get("rank")
    if rk is None and r.get("rank_range"):
        rk = r["rank_range"][1]  # 取区间下界位次（更靠后，过线参考更保守）
    if rk is None:
        rk = r.get("rank_upper")
    return {"year": year, "line_type": line_type,
            "line_score": line_score, "line_rank": rk}


async def rank_context(category, subject, rank, batch=None):
    """面向未来考生（如 2027）的「位次锚点」定位。

    考生所在年份是隐含且固定的；2025/2026 一律作为**历史参考年**，
    始终一起使用，不让用户在它们之间二选一。位次是唯一跨年可比的锚点。

    返回：
      - equivalents：该位次在各历史年份对应的分数（把抽象位次翻译成可理解的分数水平）
      - line_refs：以位次法给出各历史年份控制线的位次位置及领先/落后（历史参照，非绝对判定）
    """
    if rank is None or rank <= 0:
        return {"error": "请提供有效的全省位次（正整数）"}

    yrs = await db.fetch_all(
        "SELECT DISTINCT year FROM score_rank "
        "WHERE category=%s AND subject=%s ORDER BY year DESC",
        (category, subject))
    year_list = [r[0] for r in yrs]

    equivalents = []
    for yr in year_list:
        r = await rank_to_score(yr, category, subject, rank)
        if r.get("found") and "score" in r:
            equivalents.append({"year": yr, "score": r["score"],
                                "score_note": r.get("score_note"),
                                "below_table": bool(r.get("below_table"))})
        elif r.get("found"):
            equivalents.append({"year": yr, "score": None,
                                "note": r.get("note"),
                                "below_table": bool(r.get("below_table"))})

    line_refs = []
    lt = _line_type(batch)
    if lt:
        want = [lt]
        if category == "普通类" and lt == "本科" and batch and "专科" not in batch:
            want.append("特殊类型")
        for yr in year_list:
            for wlt in want:
                lr = await line_rank(yr, category, subject, wlt)
                if lr and lr["line_rank"]:
                    lr["passed_ref"] = rank <= lr["line_rank"]
                    lr["margin"] = lr["line_rank"] - rank  # 正=领先线该名次
                    line_refs.append(lr)

    note = None
    if category in ("体育类", "艺术类"):
        note = "体育/艺术类还需满足相应专业控制线，且录取规则特殊，此处仅作文化位次参照。"

    return {
        "category": category,
        "subject": subject,
        "batch": batch,
        "rank": rank,
        "reference_years": year_list,
        "equivalents": equivalents,
        "line_refs": line_refs,
        "note": note,
    }


async def personal_summary(year, category, subject, score=None, rank=None, batch=None):
    if not score and not rank:
        return {"error": "至少需要提供 score 或 rank 之一"}
    result = {"year": year, "category": category, "subject": subject}

    if score is not None:
        s2r = await score_to_rank(year, category, subject, score)
        result["by_score"] = s2r
        if s2r.get("found") and "rank" in s2r:
            rank = rank or s2r["rank"]
        elif s2r.get("found") and s2r.get("rank_range"):
            rank = rank or s2r["rank_range"][1]

    if rank is not None:
        if "by_score" not in result or not result["by_score"].get("found"):
            r2s = await rank_to_score(year, category, subject, rank)
            result["by_rank"] = r2s

    if rank is not None:
        result["cross_year"] = await cross_year_scores(year, category, subject, rank)

    if score is not None and batch:
        result["line"] = await judge_line(year, category, subject, score, batch=batch)

    return result
