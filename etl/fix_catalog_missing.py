#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_catalog_missing.py —— 补回 major_catalog 中 PDF 解析丢失的 3 个专业（幂等）

背景：major_catalog 由 load_material_phase1.py B7（普通高等学校本科专业目录
2026.pdf 解析）写入，共 737 条。核对发现 major_hot_profiles 里 3 个热门专业
不在目录中（详情页 /major-catalog/detail 因 JOIN major_catalog 返回 null）：

  080911TK 网络空间安全（计算机类/工学）—— 位于 080910T 与 080912T 之间，PDF 解析漏行
  100202TK 麻醉学（临床医学类/医学）—— 紧随 100201K 临床医学，PDF 解析漏行
  100203TK 医学影像学（临床医学类/医学）—— 同上

编码/类别依据教育部《普通高等学校本科专业目录（2026年）》。
用法：
  python3 etl/fix_catalog_missing.py            # 仅打印缺失项
  python3 etl/fix_catalog_missing.py --apply    # 幂等补入（ON CONFLICT DO NOTHING）
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psycopg2
from config import DSN

MISSING = [
    ("080911TK", "网络空间安全", "计算机类", "工学"),
    ("100202TK", "麻醉学", "临床医学类", "医学"),
    ("100203TK", "医学影像学", "临床医学类", "医学"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    todo = []
    for code, name, category, discipline in MISSING:
        cur.execute("SELECT 1 FROM major_catalog WHERE code=%s AND year=2026", (code,))
        if cur.fetchone():
            print(f"已存在，跳过: {code} {name}")
        else:
            todo.append((code, name, category, discipline))
    if not todo:
        print("无需补入（幂等）")
        conn.close()
        return
    print(f"缺失待补: {len(todo)} 条")
    for code, name, category, discipline in todo:
        print(f"  {code} {name}（{category}/{discipline}）")
    if args.apply:
        for code, name, category, discipline in todo:
            cur.execute(
                """INSERT INTO major_catalog (code, name, category, discipline, year)
                   VALUES (%s,%s,%s,%s,2026)
                   ON CONFLICT (code, year) DO NOTHING""",
                (code, name, category, discipline),
            )
        conn.commit()
        print(f"已补入 {len(todo)} 条")
    else:
        print("（加 --apply 写库）")
    conn.close()


if __name__ == "__main__":
    main()
