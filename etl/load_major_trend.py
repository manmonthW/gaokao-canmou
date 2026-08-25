#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""load_major_trend.py —— major_trend / major_trend_alias 全量重建（migration 0017）

背景：
  专业冷热趋势的计算要跑 2 万次置换重抽样，是典型的预计算场景；口径一年只在
  年度投档入库时变一次。计算内核在 etl/major_trend_core.py，与只读研究脚本
  webapp/scripts/major_trend.py 共用同一份实现，保证线上口径与研究口径不漂移。

不碰 major_trend_context：那张表是人工撰写的社会背景解读，由人维护，ETL 不得覆盖。

幂等：单事务内 DELETE + INSERT，可任意重跑；
时机：每年投档数据入库（etl/load*.py + backfill_lowest_rank.py）完成后重跑一次。
"""
import json
import sys
import time
from collections import defaultdict

import numpy as np
import psycopg2
from psycopg2.extras import execute_values

from config import DSN
import major_trend_core as core

SEED = 20260825          # 固定随机种子：置换阈值可复现，重跑结果稳定


def compute():
    """连库取数并算出 (专业层行, 别名行)。只读，不写。"""
    conn = psycopg2.connect(DSN)
    try:
        cur = conn.cursor()
        bases, rows = core.load(cur)
        tbl = core.load_score_tables(cur)
    finally:
        conn.close()

    units, pairs, market = core.build_pairs(rows)
    rng = np.random.default_rng(SEED)
    thr = {k: core.perm_thresholds([p["e"] for p in lst], rng)
           for k, lst in pairs.items()}
    agg = core.aggregate(pairs, thr)
    sup = core.supply_table(rows)
    eq_major, eq_market = core.equivalent_scores(units, tbl)

    trend_rows = []
    for (subject, batch, major_key), steps in agg.items():
        a, b = steps.get(core.STEPS[0]), steps.get(core.STEPS[1])
        lab, reason = core.label(a, b)
        s = sup[(subject, batch, major_key)]
        tiers = core.tier_breakdown(b["pairs"]) if b else {}
        trend_rows.append((
            subject, batch, major_key, lab, reason,
            a["n"] if a else None, a["E"] if a else None,
            a["T"] if a else None, a["sig"] if a else None,
            a["concord"] if a else None,
            b["n"] if b else None, b["E"] if b else None,
            b["T"] if b else None, b["sig"] if b else None,
            b["concord"] if b else None,
            (a["E"] + b["E"]) if (a and b) else None,
            s.get(2024, 0), s.get(2025, 0), s.get(2026, 0),
            json.dumps({t: {"n": n, "e": round(v, 5)} for t, (n, v) in tiers.items()},
                       ensure_ascii=False),
            eq_major.get((subject, batch, major_key)),
            eq_market.get((subject, batch)),
        ))

    # 别名：招生专业名 → 归一专业。后端据此精确匹配，无需自己实现归一规则。
    alias = {}
    for r in rows:
        alias[(r["subject"], r["batch"], r["major_name"])] = r["major_key"]
    have = {(t[0], t[1], t[2]) for t in trend_rows}
    alias_rows = [(su, ba, nm, mk) for (su, ba, nm), mk in alias.items()
                  if (su, ba, mk) in have]
    market_rows = [(su, ba, y1, y2, m)
                   for (su, ba, (y1, y2)), m in market.items()]
    return trend_rows, alias_rows, market_rows


TREND_COLS = """subject, batch, major_key, label, label_reason,
                n_pairs_1, excess_1, thr_1, sig_1, concord_1,
                n_pairs_2, excess_2, thr_2, sig_2, concord_2,
                excess_total, units_2024, units_2025, units_2026,
                tier_split, eq_score_delta, eq_score_delta_market"""


def main():
    t0 = time.time()
    trend_rows, alias_rows, market_rows = compute()
    if not trend_rows:
        sys.exit("未算出任何趋势行——请先确认投档数据与一分一段表已入库")

    conn = psycopg2.connect(DSN)
    try:
        with conn:                       # 成功即提交，异常即回滚
            cur = conn.cursor()
            cur.execute("DELETE FROM major_trend_alias")
            cur.execute("DELETE FROM major_trend_market")
            cur.execute("DELETE FROM major_trend")
            execute_values(
                cur, f"INSERT INTO major_trend ({TREND_COLS}) VALUES %s", trend_rows)
            execute_values(
                cur,
                "INSERT INTO major_trend_alias (subject, batch, admission_name, major_key)"
                " VALUES %s", alias_rows)
            execute_values(
                cur,
                "INSERT INTO major_trend_market"
                " (subject, batch, year_from, year_to, drift_log) VALUES %s",
                market_rows)

            cur.execute("SELECT label, count(*) FROM major_trend GROUP BY label ORDER BY 2 DESC")
            dist = cur.fetchall()
            cur.execute("SELECT count(*) FROM major_trend_alias")
            n_alias = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM major_trend_context")
            n_ctx = cur.fetchone()[0]
    finally:
        conn.close()

    print(f"major_trend {len(trend_rows)} 行、major_trend_alias {n_alias} 行；"
          f"社会背景 major_trend_context {n_ctx} 行（人工维护，本脚本不动）")
    print("标签分布：" + "  ".join(f"{k} {v}" for k, v in dist))
    print(f"全省大盘漂移基准 major_trend_market {len(market_rows)} 行：")
    for su, ba, y1, y2, m in sorted(market_rows):
        print(f"  {su} {ba} {y1}→{y2}: {m:+.4f}")
    print(f"耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
