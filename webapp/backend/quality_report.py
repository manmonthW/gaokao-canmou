"""Phase 0 质量检查报告：从数据库统计生成可读的质量与发布状态报告。

用法（在 backend 目录，已配置 .env）：
  python3 quality_report.py            # 打印并写入 ../docs/quality-report.md
  python3 quality_report.py --print-only
"""
import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv
import psycopg2

load_dotenv()
DSN = os.environ.get("GAOKAO_DSN")
if not DSN:
    sys.exit("GAOKAO_DSN 未设置：请在 backend/.env 配置只读连接串")


def q(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def build_report(conn):
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"# 数据质量与发布状态报告\n")
    lines.append(f"> 生成时间：{now}  \n> 数据源：PostgreSQL `gaokao`（只读）\n")

    # 1) 当前发布版本
    rel = q(conn, """SELECT version, data_as_of, covered_years, status, quality_summary
                     FROM data_releases WHERE status='published'
                     ORDER BY published_at DESC LIMIT 1""")
    lines.append("## 1. 当前数据版本")
    if rel:
        r = rel[0]
        lines.append(f"- 版本：**{r[0]}**（{r[3]}），数据截止 {r[1]}")
        lines.append(f"- 覆盖年份：{r[2]}")
        lines.append(f"- 说明：{r[4]}")
    else:
        lines.append("- ⚠ 无已发布版本")

    # 2) 录取记录规模
    total = q(conn, "SELECT count(*) FROM admission_scores")[0][0]
    lines.append("\n## 2. 录取记录规模")
    lines.append(f"- 总计：**{total:,}** 条")
    rows = q(conn, "SELECT year, category, count(*) FROM admission_scores "
                  "GROUP BY year, category ORDER BY year, category")
    lines.append("\n| 年份 | 科类 | 记录数 |")
    lines.append("|---|---|---:|")
    for y, c, n in rows:
        lines.append(f"| {y} | {c} | {n:,} |")

    # 3) 位次回填率
    lines.append("\n## 3. 最低位次回填率")
    rows = q(conn, """SELECT year,
                       count(*) FILTER (WHERE lowest_rank IS NOT NULL) AS has_rank,
                       count(*) AS total
                FROM admission_scores GROUP BY year ORDER BY year""")
    lines.append("\n| 年份 | 有最低位次 | 总计 | 回填率 |")
    lines.append("|---|---:|---:|---:|")
    for y, h, t in rows:
        rate = h / t * 100 if t else 0
        lines.append(f"| {y} | {h:,} | {t:,} | {rate:.1f}% |")

    # 4) 常规/征集隔离验证
    lines.append("\n## 4. 常规与征集隔离")
    rows = q(conn, """SELECT is_collection, count(*)
                      FROM admission_scores GROUP BY is_collection ORDER BY is_collection""")
    for col, n in rows:
        label = "常规志愿" if not col else "征集志愿"
        lines.append(f"- {label}：{n:,} 条")

    # 5) 待发布/部分发布批次
    lines.append("\n## 5. 批次发布状态（待发布 / 部分发布）")
    pend = q(conn, """SELECT year, category, subject, batch, stage, status, note
                      FROM admission_publication_status
                      WHERE status IN ('待发布','部分发布')
                      ORDER BY year, category, subject, batch""")
    if pend:
        lines.append("\n| 年份 | 科类 | 学科类 | 批次 | 阶段 | 状态 | 备注 |")
        lines.append("|---|---|---|---|---|---|---|")
        for y, c, s, b, st, stat, note in pend:
            lines.append(f"| {y} | {c} | {s} | {b} | {st} | {stat} | {note or ''} |")
    else:
        lines.append("- 全部批次已完成发布")

    # 6) 院校画像关联率
    lines.append("\n## 6. 院校画像关联")
    sp = q(conn, "SELECT count(*) FROM school_profiles")[0][0]
    sch = q(conn, "SELECT count(*) FROM schools")[0][0]
    lines.append(f"- 院校总数：{sch:,}，已关联画像：{sp:,}"
                 f"（关联率 {sp/sch*100:.1f}%）")

    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print-only", action="store_true")
    args = ap.parse_args()
    conn = psycopg2.connect(DSN)
    try:
        report = build_report(conn)
    finally:
        conn.close()

    if args.print_only:
        print(report)
        return

    out_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "quality-report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"\n[已写入] {os.path.abspath(out_path)}")


if __name__ == "__main__":
    main()
