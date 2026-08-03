"""P2-b: 判断考生是否过线（基于 batch_control_line 省控线）。

用法（命令行快速演示）:
  python3 etl/check_line.py --year 2025 --subject 物理学科类 --category 普通类 --score 500 --batch 本科批
  python3 etl/check_line.py --year 2026 --subject 历史学科类 --category 普通类 --score 442 --batch 本科批

作为模块:
  from check_line import judge
  judge(year=2025, subject="物理学科类", category="普通类", score=500, batch="本科批")
  -> {"primary": {"line_type":"本科","line":437,"passed":True,"gap":63},
      "special_type": {"line":515,"passed":False,"gap":-15},   # 仅普通类本科/提前批附带
      "note": "..."}
"""
import argparse
import psycopg2
from config import DSN


def _line(conn, year, category, subject, line_type):
    cur = conn.cursor()
    cur.execute(
        "SELECT score, note FROM batch_control_line "
        "WHERE year=%s AND category=%s AND subject=%s AND line_type=%s;",
        (year, category, subject, line_type))
    row = cur.fetchone()
    cur.close()
    return (row[0], row[1]) if row else (None, None)


def _batch_to_line_type(batch):
    if batch is None:
        return None
    if "专科" in batch:
        return "专科"
    if "本科" in batch or "提前" in batch:
        return "本科"
    return None


def judge(conn, year, subject, category, score, batch=None, line_type=None):
    """返回过线判断结果。

    - 普通类：primary 取 batch 对应线（本科/专科）；若 batch 为本科/提前批，
      额外给出 special_type（特控线）是否过线，便于“能否报特殊类型”。
    - 体育/艺术类：primary 取文化课控制线；note 提示还需满足专业控制线。
    """
    lt = line_type or _batch_to_line_type(batch)
    if lt is None:
        return {"error": "无法确定要查的线，请传 batch 或 line_type"}

    line, note = _line(conn, year, category, subject, lt)
    if line is None:
        return {"error": f"无对应省控线: {year} {category} {subject} {lt}"}

    passed = score >= line
    result = {
        "primary": {
            "line_type": lt,
            "line": line,
            "passed": passed,
            "gap": score - line,
        }
    }
    if category == "普通类" and lt in ("本科",) and batch and "专科" not in batch:
        st, _ = _line(conn, year, category, subject, "特殊类型")
        if st is not None:
            result["special_type"] = {
                "line": st,
                "passed": score >= st,
                "gap": score - st,
            }
    if category in ("体育类", "艺术类"):
        result["note"] = "仅判断文化课控制线；体育/艺术类还需满足相应专业控制线方可过线。"
    return result


def _cli():
    p = argparse.ArgumentParser()
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--category", required=True)
    p.add_argument("--score", type=int, required=True)
    p.add_argument("--batch")
    p.add_argument("--line-type")
    args = p.parse_args()
    conn = psycopg2.connect(DSN)
    try:
        res = judge(conn, args.year, args.subject, args.category,
                    args.score, batch=args.batch, line_type=args.line_type)
        print(res)
    finally:
        conn.close()


if __name__ == "__main__":
    _cli()
