#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""smoke_xk_layers.py —— 选科分层匹配冒烟（只读）。

直接导入生产代码 webapp/backend/app/services/match.py 的
build_req_indexes / lookup_reqs，对真实库回归验证：
1. 固定用例：太原理工·化学(试验班) 由未核验转已核验（base 层）；
   石家庄铁道·人工智能 保持「未收录」；吉林化工大学（别名）可核验。
2. 全池覆盖率：2025/2026 投档单元 vs 2027 官方表，分层命中分布，
   总覆盖率应 >= 88%（audit_xk 审计口径）。
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "webapp", "backend"))

import psycopg2

from app.services.match import build_req_indexes, lookup_reqs
from config import DSN

YEAR = 2027
POOL_YEARS = (2025, 2026)


def main():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute("""SELECT school_code, school_name, major_name, first_req, re_req
                   FROM subject_requirements WHERE year=%s""", (YEAR,))
    idx = build_req_indexes(cur.fetchall())
    cur.execute("""SELECT DISTINCT school_name, major_name FROM admission_scores
                   WHERE year IN %s""", (POOL_YEARS,))
    units = cur.fetchall()
    conn.close()

    # ---- 固定用例 ----
    reqs, level, known = lookup_reqs(idx, "太原理工大学", "化学(试验班)")
    assert reqs, "太原理工·化学(试验班) 应命中（base 层剥括号）"
    print(f"[OK] 太原理工大学|化学(试验班) -> level={level} reqs={reqs}")

    reqs, level, known = lookup_reqs(idx, "石家庄铁道大学", "人工智能")
    assert not reqs, "石家庄铁道·人工智能 应保持未收录（审计定稿）"
    status = "major_missing" if known else "school_missing"
    print(f"[OK] 石家庄铁道大学|人工智能 -> 未收录 status={status}")

    cur_alias = [(m) for (sn, m) in units if sn == "吉林化工大学"]
    hit = sum(1 for m in cur_alias if lookup_reqs(idx, "吉林化工大学", m)[0])
    assert hit > 0, "吉林化工大学（别名→吉林化工学院）应有单元核验成功"
    print(f"[OK] 吉林化工大学（别名）单元 {len(cur_alias)} 个，核验成功 {hit}")

    # ---- 全池分层命中分布 ----
    dist = Counter()
    status_dist = Counter()
    for sn, mn in units:
        reqs, level, known = lookup_reqs(idx, sn, mn)
        if reqs:
            dist[level] += 1
        else:
            dist["未收录"] += 1
            status_dist["major_missing" if known else "school_missing"] += 1
    total = len(units)
    verified = total - dist["未收录"]
    print(f"\n全池 {total} 单元：核验 {verified} ({verified/total:.1%})")
    for k in ["exact", "norm", "base", "enum", "school", "未收录"]:
        n = dist[k]
        print(f"  {k:<8} {n:>6} ({n/total:.1%})")
    print("未收录拆分:", dict(status_dist))
    assert verified / total >= 0.88, f"总覆盖率低于 88%：{verified/total:.1%}"
    print("\nSMOKE OK")


if __name__ == "__main__":
    main()
