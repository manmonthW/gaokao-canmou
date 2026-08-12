#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ews_gen_clean_sql.py —— 基于 EWS dump 生成文字清洗单事务 SQL（本地不连 EWS 库）

输入：/tmp/ews_hot_profiles.csv（EWS 容器库 major_hot_profiles 的 CSV dump）
规则：复用 clean_major_hot_text.transform()（与本地清洗完全同一套规则+人工修正）
输出：/tmp/ews_clean_text.sql —— BEGIN/COMMIT 单事务：
  1) major_hot_profiles 逐行 UPDATE（只含变化字段，NULL 显式置空）
  2) major_catalog 补 3 条（ON CONFLICT DO NOTHING，幂等）
用法：
  python3 etl/ews_gen_clean_sql.py            # 生成 + 打印审计摘要
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clean_major_hot_text as c

SRC = "/tmp/ews_hot_profiles.csv"
OUT = "/tmp/ews_clean_text.sql"

CATALOG_MISSING = [
    ("080911TK", "网络空间安全", "计算机类", "工学"),
    ("100202TK", "麻醉学", "临床医学类", "医学"),
    ("100203TK", "医学影像学", "临床医学类", "医学"),
]


def q(v):
    """SQL 单引号转义；None → NULL。"""
    if v is None:
        return "NULL"
    return "'" + v.replace("'", "''") + "'"


def main():
    rows = []
    with open(SRC, encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        for r in rd:
            row = {k: (v if v != "" else None) for k, v in r.items()}
            rows.append(row)

    n_null = {f: 0 for f in c.FIELDS}
    n_rep = 0
    updates = []
    for row in rows:
        changed = c.transform(row)
        if not changed:
            continue
        for f, v in changed.items():
            if v is None and row[f] is not None:
                n_null[f] += 1
            elif v is not None and row[f] is not None:
                n_rep += 1
        updates.append((row["name"], changed))

    print(f"EWS dump {len(rows)} 行，需变更 {len(updates)} 行")
    print("置 NULL 统计（按字段）:")
    for f in c.FIELDS:
        if n_null[f]:
            print(f"  {f:20s} {n_null[f]}")
    print(f"文本替换/折行合并: {n_rep} 处")
    print("\ncareer 变更审计:")
    for name, ch in updates:
        if "career" in ch:
            ov = c.OVERRIDES.get(name, {}).get("career", "__NO__")
            reason = "OVERRIDE" if ov != "__NO__" else "RULE"
            print(f"  [{reason}] {name}: -> {ch['career']!r}")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("-- EWS 专业介绍文字清洗（与本地 clean_major_hot_text.py 同规则，单事务）\n")
        f.write("BEGIN;\n")
        for name, changed in updates:
            sets = ", ".join(f"{fld}={q(v)}" for fld, v in changed.items())
            f.write(f"UPDATE major_hot_profiles SET {sets} WHERE name={q(name)};\n")
        for code, name, category, discipline in CATALOG_MISSING:
            f.write(
                "INSERT INTO major_catalog (code, name, category, discipline, year) "
                f"VALUES ({q(code)}, {q(name)}, {q(category)}, {q(discipline)}, 2026) "
                "ON CONFLICT (code, year) DO NOTHING;\n")
        f.write("COMMIT;\n")
    print(f"\nSQL 已生成: {OUT}（UPDATE {len(updates)} 条 + INSERT {len(CATALOG_MISSING)} 条）")


if __name__ == "__main__":
    main()
