#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""load_subject_requirements.py —— 选考科目要求加载（D2b，migration 0012）。

官方发布 2027 年在辽选科要求后，用本脚本灌入 subject_requirements：
  python3 etl/load_subject_requirements.py --file <xlsx/xls> --year 2027

约定（列名别名驱动，官方表头确定后一般零改动）：
  院校   : 院校名称 / 学校 / 高校名称 / 招生院校
  专业   : 专业名称 / 专业(类)名称 / 招生专业
  专业码 : 专业代码 / 招生代码
  单元码 : 招生单元代码 / 专业组代码 / 单元代码
  首选   : 首选科目 / 首选科目要求 / 首选要求
  再选   : 再选科目 / 再选科目要求 / 再选要求

幂等语义：按 --year 全量重灌（先删该年旧行与同名源文件），
未解析的行保留 raw_text 兜底。
"""
import argparse
import os
import sys

import psycopg2

from config import DSN
from readers import read_spreadsheet

ALIASES = {
    "school_name": {"院校名称", "学校", "学校名称", "高校名称", "招生院校"},
    "major_name": {"专业名称", "专业(类)名称", "专业（类）名称", "招生专业"},
    "major_code": {"专业代码", "招生代码"},
    "group_code": {"招生单元代码", "专业组代码", "单元代码"},
    "first_req": {"首选科目", "首选科目要求", "首选要求"},
    "re_req": {"再选科目", "再选科目要求", "再选要求"},
}


def _clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="选科要求文件（xlsx/xls）")
    ap.add_argument("--year", type=int, required=True)
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"文件不存在: {args.file}")
        return 1
    filename = os.path.basename(args.file)
    fmt = os.path.splitext(filename)[1].lstrip(".").lower()

    sheets = read_spreadsheet(args.file)

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    total = 0
    for sheet_name, rows in sheets:
        if not rows:
            continue
        header = [_clean(c) for c in rows[0]]
        colmap = {}
        for field, aliases in ALIASES.items():
            for idx, h in enumerate(header):
                if h in aliases:
                    colmap[field] = idx
                    break
        if "school_name" not in colmap or "first_req" not in colmap:
            print(f"[跳过 sheet {sheet_name}] 表头缺少必需列"
                  f"(院校/首选)，表头={header}")
            continue

        # 幂等：先删本年旧数据与同名源文件（以 note 标记识别选科要求文件）
        cur.execute("DELETE FROM subject_requirements WHERE year=%s", (args.year,))
        cur.execute("DELETE FROM source_files WHERE filename=%s AND year=%s "
                    "AND note LIKE '%%选考科目要求%%'", (filename, args.year))
        cur.execute(
            "INSERT INTO source_files (filename, fmt, year, status, note, loaded_at) "
            "VALUES (%s, %s, %s, 'loaded', %s, now()) RETURNING id",
            (filename, fmt, args.year,
             f"{args.year}年在辽选考科目要求 sheet={sheet_name}"))
        src_id = cur.fetchone()[0]

        n = 0
        for row in rows[1:]:
            def g(field):
                idx = colmap.get(field)
                return _clean(row[idx]) if idx is not None and idx < len(row) else None
            school = g("school_name")
            if not school:
                continue
            cur.execute(
                """INSERT INTO subject_requirements
                   (year, school_name, major_name, major_code, group_code,
                    first_req, re_req, raw_text, src_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (args.year, school, g("major_name"), g("major_code"),
                 g("group_code"), g("first_req"), g("re_req"),
                 " | ".join(str(c) for c in row if c is not None)[:2000],
                 src_id))
            n += 1
        total += n
        print(f"sheet [{sheet_name}]: 载入 {n} 行，列映射={colmap}")

    conn.commit()
    cur.execute("SELECT count(*) FROM subject_requirements WHERE year=%s",
                (args.year,))
    print(f"完成：{args.year} 年共 {cur.fetchone()[0]} 行")
    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
