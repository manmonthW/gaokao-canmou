#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""load_subject_requirements.py —— 选考科目要求加载（D2b，migration 0012）。

官方《2027 年拟在辽招生普通高校专业选考科目要求》三表（bk 本科 / zk 专科 /
jx 军校）为合并单列文本：
  院校代码 | 院校名称 | 招生专业代码 | 招生专业名称 | [层次] | 选考科目要求
亦兼容首选/再选分列的早期表头约定。

用法（分文件多次运行，互不清空）：
  python3 etl/load_subject_requirements.py --file 2026allmaterial/2027lnzsxkap0407bk.xlsx --year 2027
  python3 etl/load_subject_requirements.py --file 2026allmaterial/2027lnzsxkap0407zk.xlsx --year 2027
  python3 etl/load_subject_requirements.py --file 2026allmaterial/2027lnzsxkap0407jx.xlsx --year 2027

解析约定：
  - 「不提科目要求」→ first_req=不限, re_req=NULL；
  - 文本中的 物理/历史 归首选（3+1+2 首选科目），其余归再选；
  - re_req 保留官方原文但剔除首选科目字样，避免匹配层把首选科目重复计入再选校验；
  - 幂等：按 (filename, year, note) 删除旧 source_files 及其 subject_requirements 行。
"""
import argparse
import os
import sys

import psycopg2

from config import DSN
from readers import read_spreadsheet

ALIASES = {
    "school_code": {"院校代码", "学校代码", "招生院校代码"},
    "school_name": {"院校名称", "学校", "学校名称", "高校名称", "招生院校"},
    "major_name": {"专业名称", "专业(类)名称", "专业（类）名称", "招生专业", "招生专业名称"},
    "major_code": {"专业代码", "招生代码", "招生专业代码"},
    "group_code": {"招生单元代码", "专业组代码", "单元代码"},
    "first_req": {"首选科目", "首选科目要求", "首选要求"},
    "re_req": {"再选科目", "再选科目要求", "再选要求"},
    "req_text": {"选考科目要求"},
}

_SUBJECTS = ["思想政治", "物理", "化学", "生物", "历史", "地理"]
_FIRST_SUBJECTS = {"物理", "历史"}


def _clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _parse_req(text):
    """官方合并文本 → (first_req, re_req)。"""
    if not text:
        return None, None
    t = str(text).strip()
    if "不提" in t or "不限" in t:
        return "不限", None
    tokens = [s for s in _SUBJECTS if s in t]
    firsts = [s for s in tokens if s in _FIRST_SUBJECTS]
    res = [s for s in tokens if s not in _FIRST_SUBJECTS]
    first_req = ",".join(firsts) if firsts else "不限"
    if not res:
        return first_req, None
    rest = t
    for s in firsts:
        rest = rest.replace(s, "", 1)
    rest = rest.lstrip(",，、;； ").strip()
    return first_req, rest or None


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

    # 幂等：仅删同文件旧数据（先取 src id 再删子表），多文件可分次灌入
    cur.execute(
        "SELECT id FROM source_files WHERE filename=%s AND year=%s "
        "AND note LIKE '%%选考科目要求%%'", (filename, args.year))
    old_ids = [r[0] for r in cur.fetchall()]
    if old_ids:
        cur.execute("DELETE FROM subject_requirements WHERE src_id = ANY(%s)",
                    (old_ids,))
        cur.execute("DELETE FROM source_files WHERE id = ANY(%s)", (old_ids,))

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
        if "school_name" not in colmap or \
                ("first_req" not in colmap and "req_text" not in colmap):
            print(f"[跳过 sheet {sheet_name}] 表头缺少必需列"
                  f"(院校/选科要求)，表头={header}")
            continue

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
            fr, rr = g("first_req"), g("re_req")
            if fr is None and "req_text" in colmap:
                fr, rr = _parse_req(g("req_text"))
            cur.execute(
                """INSERT INTO subject_requirements
                   (year, school_code, school_name, major_name, major_code,
                    group_code, first_req, re_req, raw_text, src_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (args.year, g("school_code"), school, g("major_name"),
                 g("major_code"), g("group_code"), fr, rr,
                 " | ".join(str(c) for c in row if c is not None)[:2000],
                 src_id))
            n += 1
        total += n
        print(f"sheet [{sheet_name}]: 载入 {n} 行，列映射={colmap}")

    conn.commit()
    cur.execute("SELECT count(*) FROM subject_requirements WHERE year=%s",
                (args.year,))
    print(f"完成：本文件 {total} 行；{args.year} 年累计 {cur.fetchone()[0]} 行")
    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
