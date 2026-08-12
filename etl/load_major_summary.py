#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
load_major_summary.py —— 专业字典「在辽招生概览」预计算表全量重建

背景：专业查询页每次打开都要对 737 个标准专业 × 约 6.7 万条分数做
major_name ILIKE '%标准名%' 双侧通配聚合（无索引可走，约 25s/次）。
分数数据一年只在年度投档入库时变化一次，故把聚合预计算进
major_admission_summary（migration 0015），读路径直连本表。

幂等：单事务内 DELETE + INSERT，可任意重跑；
时机：每年投档数据入库（etl/load*.py）完成后重跑一次即可。
"""
import time

import psycopg2

from config import DSN

AGGREGATE_SQL = """
INSERT INTO major_admission_summary
    (code, name, school_count, min_score, max_score, min_rank, max_rank)
SELECT mc.code, mc.name,
       count(DISTINCT a.school_code) FILTER (WHERE a.school_code IS NOT NULL),
       min(a.lowest_score) FILTER (WHERE a.school_code IS NOT NULL),
       max(a.lowest_score) FILTER (WHERE a.school_code IS NOT NULL),
       min(a.lowest_rank)  FILTER (WHERE a.school_code IS NOT NULL),
       max(a.lowest_rank)  FILTER (WHERE a.school_code IS NOT NULL)
FROM major_catalog mc
LEFT JOIN admission_scores a
       ON a.major_name ILIKE '%' || mc.name || '%'
GROUP BY mc.code, mc.name
"""


def main():
    conn = psycopg2.connect(DSN)
    try:
        with conn:
            cur = conn.cursor()
            t0 = time.time()
            cur.execute("DELETE FROM major_admission_summary")
            cur.execute(AGGREGATE_SQL)
            cur.execute(
                "SELECT count(*), count(*) FILTER (WHERE school_count > 0) "
                "FROM major_admission_summary"
            )
            total, hit = cur.fetchone()
            print(
                f"major_admission_summary 重建完成: {total} 个专业, "
                f"其中 {hit} 个在辽有招生记录, 耗时 {time.time() - t0:.1f}s"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
