"""位次版“冲稳保”匹配（面向下一年考生，如 2027）。

关键逻辑修正：
- 考生是“下一年”的（如 2027），此时既没有 2027 的一分一段表(score_rank)，
  也没有 2027 的录取数据(admission_scores)。
- 因此：考生**直接提供自己年份的省位次**（来自该年官方一分一段表），
  我们拿它去对比**往年（如 2026、2025）院校实际录取的 lowest_rank**。
- 位次口径一致（“全省第几名”），天然跨年可比，这正是位次版优于分数版之处。

分档（考生位次 vs 院校参考位次 ref_rank）：
    保 (safe)   : 考生位次 <= ref_rank * safe_ratio      (明显更靠前)
    稳 (match)  : ref_rank*safe_ratio < 考生位次 <= ref_rank*reach_ratio
    冲 (reach)  : 考生位次 >  ref_rank * reach_ratio      (排名更靠后，有风险)
  位次数值越小越好；考生位次 > 院校位次 表示考生排得更靠后(更难进)。

参考年份聚合：同一院校(校+专业+批次)在多个参考年都有录取位次时，
  取“最近一年”的 lowest_rank 作为 ref_rank 用于分档，并保留各年位次供查看稳定性。

用法:
  # 2027 考生（必须提供 --rank，因 2027 一分一段表尚未入库）
  python3 etl/match_rank.py --student-year 2027 --subject 物理学科类 --category 普通类 --rank 12512 --batch 本科批

  # 历史年份考生（可用 --score 由同年 score_rank 反查位次，便于回测）
  python3 etl/match_rank.py --student-year 2026 --subject 物理学科类 --category 普通类 --score 606 --batch 本科批
"""
import argparse
import psycopg2
from config import DSN


def student_rank(conn, student_year, subject, category, score=None, rank=None):
    """考生省位次。

    - 若调用方直接给 rank（如下一年考生自查的一分一段表位次），优先使用。
    - 否则尝试用 student_year 的 score_rank 由 score 反查（仅当该年表已入库，
      如 2025/2026；2027 尚未入库，必须显式传 --rank）。
    """
    if rank is not None:
        return rank
    if score is None:
        return None
    cur = conn.cursor()
    cur.execute(
        """SELECT cumulative_rank FROM score_rank s
           WHERE s.year=%s AND s.subject=%s AND s.category=%s
             AND s.score <= floor(%s)
           ORDER BY s.score DESC LIMIT 1;""",
        (student_year, subject, category, score))
    row = cur.fetchone()
    cur.close()
    return row[0] if row else None


def _default_ref_years(student_year):
    return [student_year - 1, student_year - 2]


def match(conn, student_year, subject, category,
          student_rank_arg=None, score=None,
          ref_years=None, batch=None, score_kind="投档最低分",
          safe_ratio=0.85, reach_ratio=1.10, limit_per=20):
    if ref_years is None:
        ref_years = _default_ref_years(student_year)

    srank = student_rank(conn, student_year, subject, category,
                         score=score, rank=student_rank_arg)
    if srank is None:
        return {"error": "缺少考生位次：下一年考生请通过 --rank 提供当年省位次；"
                         "历史年份可用 --score 由同年一分一段表反查。"}

    cur = conn.cursor()
    sql = """SELECT school_name, major_name, batch, year, lowest_score, lowest_rank
             FROM admission_scores
             WHERE year = ANY(%s) AND subject=%s AND category=%s
               AND lowest_rank IS NOT NULL AND score_kind=%s"""
    params = [ref_years, subject, category, score_kind]
    if batch:
        sql += " AND batch=%s"
        params.append(batch)
    sql += " ORDER BY year, lowest_rank;"
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()

    # 聚合：同一 (校,专业,批次) 跨参考年 -> 取最近一年的位次为 ref_rank
    groups = {}
    for school, major, bat, yr, low_score, low_rank in rows:
        key = (school, major, bat)
        g = groups.setdefault(key, {"school": school, "major": major, "batch": bat,
                                    "years": {}})
        g["years"][yr] = {"lowest_score": low_score, "lowest_rank": low_rank}
    if not groups:
        return {"error": f"参考年份 {ref_years} 无匹配录取数据 "
                         f"({subject} {category})。"}

    buckets = {"冲": [], "稳": [], "保": []}
    for key, g in groups.items():
        ref_yr = max(g["years"])            # 最近一年
        ref = g["years"][ref_yr]
        ref_rank = ref["lowest_rank"]
        gap = srank - ref_rank
        if srank <= ref_rank * safe_ratio:
            label = "保"
        elif srank <= ref_rank * reach_ratio:
            label = "稳"
        else:
            label = "冲"
        # 各年位次串，便于看稳定性
        yr_detail = " ".join(
            f"{y}:{g['years'][y]['lowest_rank']}" for y in sorted(g["years"]))
        buckets[label].append({
            "school": g["school"], "major": g["major"], "batch": g["batch"],
            "ref_year": ref_yr, "lowest_score": ref["lowest_score"],
            "lowest_rank": ref_rank, "gap": gap, "years": yr_detail,
        })
    for k in buckets:
        buckets[k].sort(key=lambda r: abs(r["gap"]))

    return {
        "student_year": student_year,
        "student_rank": srank,
        "ref_years": ref_years,
        "score_kind": score_kind,
        "counts": {k: len(v) for k, v in buckets.items()},
        "冲": buckets["冲"][:limit_per],
        "稳": buckets["稳"][:limit_per],
        "保": buckets["保"][:limit_per],
    }


def _print(res):
    if "error" in res:
        print("⚠", res["error"])
        return
    print(f"考生年份: {res['student_year']}  省位次: {res['student_rank']}  "
          f"(参考录取年份: {res['ref_years']}, 依据 {res['score_kind']})")
    print(f"档位数量: 冲={res['counts']['冲']}  稳={res['counts']['稳']}  "
          f"保={res['counts']['保']}\n")
    for label in ("冲", "稳", "保"):
        print(f"===== {label} ({res['counts'][label]} 所，显示前 {len(res[label])}) =====")
        for r in res[label]:
            major = f" / {r['major']}" if r["major"] else ""
            print(f"  {r['school']}{major}  [{r['batch']}]  "
                  f"参考年{r['ref_year']}最低分={r['lowest_score']} 最低位次={r['lowest_rank']}  "
                  f"位次差={r['gap']:+d}  | 各年位次 {r['years']}")
        print()


def _cli():
    p = argparse.ArgumentParser()
    p.add_argument("--student-year", type=int, required=True, help="考生高考年份(如下一年 2027)")
    p.add_argument("--subject", required=True)
    p.add_argument("--category", required=True)
    p.add_argument("--rank", type=int, help="考生当年省位次(下一年考生必填)")
    p.add_argument("--score", type=int, help="考生分数(历史年份可由同年一分一段表反查位次)")
    p.add_argument("--ref-years", type=int, nargs="+", help="参考录取年份, 默认 [year-1, year-2]")
    p.add_argument("--batch")
    p.add_argument("--score-kind", default="投档最低分")
    p.add_argument("--limit", type=int, default=15)
    args = p.parse_args()
    conn = psycopg2.connect(DSN)
    try:
        res = match(conn, args.student_year, args.subject, args.category,
                    student_rank_arg=args.rank, score=args.score,
                    ref_years=args.ref_years, batch=args.batch,
                    score_kind=args.score_kind, limit_per=args.limit)
        _print(res)
    finally:
        conn.close()


if __name__ == "__main__":
    _cli()
