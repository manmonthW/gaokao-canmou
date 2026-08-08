#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""load_major_flags.py —— 专业级报考标记打标（D2a，migration 0011）。

对 admission_scores.flags 做全量幂等重算：
  - 中外合作   : major_name 含「中外合作办学」（库内仅此形态，不用宽泛的「合作」）
  - 定向       : major_name 含「定向」（含「水利定向班定向就业XX」）
  - 少数民族预科: major_name 含「预科班」（覆盖少数民族预科班/边防军人子女预科班）
  - 民族班     : major_name 含「(民族班)」——绝不匹配裸「民族」，
                 否则「民族学」「中国少数民族语言文学」「民族器乐」会误报
  - 异地校区   : school_name 形如 X(威海)/X(深圳)/X分校 等，
                 且「去掉括号/分校后缀的母体校名」在库内存在——
                 以此排除「香港中文大学(深圳)」这类独立法人高校（母体不在库内）

运行:
  python3 etl/load_major_flags.py --dry-run   # 只统计+打印样例，不写库（先走这步人工确认）
  python3 etl/load_major_flags.py             # 全量重算写库（幂等）
"""
import argparse
import re
import sys
from collections import Counter, defaultdict

import psycopg2
import psycopg2.extras

from config import DSN

# 括号校区城市白名单（先验：这些括号形态在库内真实出现过）
_CAMPUS_CITIES = "威海|深圳|盘锦|烟台|秦皇岛|宁波|苏州|温州|汕头|珠海|嘉兴|泰安"
RE_CAMPUS = re.compile(r"[（(]（?(?:%s)(?:校区)?[)）]）?" % _CAMPUS_CITIES)
RE_BRANCH = re.compile(r"分校$")


def parent_name(school: str):
    """返回「母体校名」：去括号/去分校后缀；无法解析返回 None。"""
    m = RE_CAMPUS.search(school)
    if m:
        return (school[:m.start()] + school[m.end():]).strip() or None
    if RE_BRANCH.search(school):
        return RE_BRANCH.sub("", school).strip() or None
    return None


def compute_flags(major_name, school_name, parents_known):
    """parents_known: 已确认母体在库内的「母体校名」集合。"""
    flags = []
    mn = major_name or ""
    sn = school_name or ""
    if "中外合作办学" in mn:
        flags.append("中外合作")
    if "定向" in mn:
        flags.append("定向")
    if "预科班" in mn:
        flags.append("少数民族预科")
    if "(民族班)" in mn or "（民族班）" in mn:
        flags.append("民族班")
    p = parent_name(sn)
    if p and p in parents_known:
        flags.append("异地校区")
    return flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只统计与打印样例，不写库")
    ap.add_argument("--samples", type=int, default=8, help="每个标记打印的样例数")
    args = ap.parse_args()

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    # 已知校名集合（母体存在性判断）
    cur.execute("SELECT DISTINCT name FROM schools")
    known = {r[0] for r in cur.fetchall()}

    cur.execute("SELECT id, school_name, major_name FROM admission_scores")
    rows = cur.fetchall()

    flag_rows = defaultdict(list)   # flag -> [(school, major), ...]
    combos = Counter()
    updates = []
    for rid, sn, mn in rows:
        fs = compute_flags(mn, sn, known)
        if fs:
            combos[tuple(sorted(fs))] += 1
            for f in fs:
                flag_rows[f].append((sn, mn))
            updates.append((sorted(fs), rid))

    total_flagged = len(updates)
    print(f"总记录 {len(rows)} 行 | 命中任一标记 {total_flagged} 行")
    for f in sorted(flag_rows):
        print(f"  [{f}] {len(flag_rows[f])} 行，样例:")
        for sn, mn in flag_rows[f][:args.samples]:
            print(f"      {sn} | {mn}")
    if combos:
        print("标记组合分布:")
        for combo, n in combos.most_common():
            print(f"  {'+'.join(combo)}: {n}")

    if args.dry_run:
        print("\n[dry-run] 未写库。确认样例无误后去掉 --dry-run 重跑。")
        return

    psycopg2.extras.execute_batch(
        cur, "UPDATE admission_scores SET flags=%s WHERE id=%s", updates,
        page_size=2000)
    # 未命中的行归零（保证幂等全量重算语义：规则迭代后旧标不残留）
    cur.execute("UPDATE admission_scores SET flags='{}' WHERE flags <> '{}' AND id NOT IN "
                "(SELECT unnest(%s::bigint[]))", ([u[1] for u in updates] or [0],))
    conn.commit()
    cur.execute("SELECT count(*) FROM admission_scores WHERE flags <> '{}'")
    print(f"写库完成：flags 非空 {cur.fetchone()[0]} 行")
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
