#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_xk3.py —— 院校别名候选生成（只读）：
对零命中学校，用「去掉 大学/学院 尾词后核心相似度 >=0.85」的严格规则
生成候选别名对，人工核对后固化进匹配层。
"""
import difflib
from collections import defaultdict

import psycopg2

from config import DSN

YEAR = 2027
POOL_YEARS = (2025, 2026)
_TAILS = ("职业技术大学", "职业大学", "学院", "大学")


def core(s):
    t = (s or "").strip()
    for w in _TAILS:
        if t.endswith(w):
            return t[: -len(w)], w
    return t, ""


def main():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT school_name FROM subject_requirements WHERE year=%s",
                (YEAR,))
    off_schools = sorted({r[0].strip() for r in cur.fetchall()})
    cur.execute("""SELECT DISTINCT school_name FROM admission_scores
                   WHERE year IN %s""", (POOL_YEARS,))
    adm_schools = sorted({r[0].strip() for r in cur.fetchall()})
    cur.execute("""SELECT school_name, count(*) FROM admission_scores
                   WHERE year IN %s GROUP BY school_name""", (POOL_YEARS,))
    adm_cnt = dict(cur.fetchall())
    conn.close()

    off_set = set(off_schools)
    zero = [s for s in adm_schools if s not in off_set]
    print(f"零命中学校 {len(zero)} 所\n")
    print(f"{'投档库学校名':<28} {'单元数':>5}  候选官方名(核心相似度)")
    for s in zero:
        c1, t1 = core(s)
        cands = []
        for o in off_schools:
            c2, t2 = core(o)
            if not c1 or not c2:
                continue
            r = difflib.SequenceMatcher(None, c1, c2).ratio()
            if r >= 0.85:
                cands.append((r, o))
        cands.sort(reverse=True)
        n = adm_cnt.get(s, 0)
        desc = "、".join(f"{o}({r:.2f})" for r, o in cands[:3]) or "—"
        print(f"{s:<28} {n:>5}  {desc}")


if __name__ == "__main__":
    main()
