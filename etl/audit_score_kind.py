#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_score_kind.py —— score_kind（投档/录取）口径审计（D3，只读）。

目的：搞清「录取最低分仅 373 行」是数据现实还是解析遗漏：
  1) score_kind × 年份 × 类别 全局分布；
  2) 每个源文件的 score_kind 构成（混合文件单独列出）；
  3) 录取最低分覆盖的批次清单；
  4) 文件名含「投档/录取」暗示词但 score_kind 不符的疑似错分类文件。

只读脚本，不写库。运行: python3 etl/audit_score_kind.py
"""
import psycopg2

from config import DSN


def main():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    print("=" * 70)
    print("1) score_kind × year × category 分布")
    cur.execute(
        """SELECT score_kind, year, category, count(*)
           FROM admission_scores GROUP BY 1,2,3
           ORDER BY 1 NULLS LAST, 2, 3""")
    for k, y, c, n in cur.fetchall():
        print(f"   {k or '(空)'} | {y} | {c}: {n}")

    print("\n2) 每文件 score_kind 构成（仅列多口径/含录取分的文件）")
    cur.execute(
        """SELECT sf.filename, a.score_kind, count(*)
           FROM admission_scores a JOIN source_files sf ON a.src_id=sf.id
           GROUP BY 1,2 ORDER BY 1""")
    per_file = {}
    for fn, k, n in cur.fetchall():
        per_file.setdefault(fn, {})[k or "(空)"] = n
    for fn, kinds in sorted(per_file.items()):
        if len(kinds) > 1 or any(k == "录取最低分" for k in kinds):
            detail = ", ".join(f"{k}:{v}" for k, v in sorted(kinds.items()))
            print(f"   {fn} -> {detail}")

    print("\n3) 录取最低分覆盖的批次")
    cur.execute(
        """SELECT year, category, batch, count(*)
           FROM admission_scores WHERE score_kind='录取最低分'
           GROUP BY 1,2,3 ORDER BY 1,2,3""")
    rows = cur.fetchall()
    if not rows:
        print("   （无录取最低分记录）")
    for y, c, b, n in rows:
        print(f"   {y} | {c} | {b}: {n}")

    print("\n4) 疑似错分类：文件名暗示与实际 score_kind 不符")
    cur.execute(
        """SELECT sf.filename, a.score_kind, count(*)
           FROM admission_scores a JOIN source_files sf ON a.src_id=sf.id
           WHERE (sf.filename LIKE '%toudang%' AND a.score_kind='录取最低分')
              OR (sf.note LIKE '%录取%' AND a.score_kind='投档最低分')
           GROUP BY 1,2""")
    found = cur.fetchall()
    if not found:
        print("   （未发现明显错分类；文件名无统一「投档/录取」暗示词，"
              "结论以第 1/2/3 节分布为准）")
    for fn, k, n in found:
        print(f"   {fn} | {k}: {n}")

    print("\n结论指引：若第 1 节录取分占比极低且第 2 节无混合文件，"
          "则「录取分稀缺」为官方发布口径的现实（辽宁以投档线为主发布），"
          "D3 应转为叙事优化而非补数。")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
