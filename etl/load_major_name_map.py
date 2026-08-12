#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
load_major_name_map.py —— 招生专业名 → 标准专业映射预计算表全量重建

背景：/match 每次请求都要把招生专业名（如"工科试验班(卓越计划)[计算机科学
与技术]"）映射到 major_catalog 标准专业名，原实现用双侧通配 ILIKE 实时关联，
千万级字符串比对，是智能匹配接口最大耗时项。映射只依赖两张静态表，
一年只在年度投档入库时变化一次，故预计算进 major_name_map（migration 0016）。

口径（与原 match.py 实时查询一致）：
- 招生名被标准名包含（ILIKE '%标准名%'）即命中；
- 多个命中时取名字最长的标准名（最具体）。

幂等：单事务内 DELETE + INSERT，可任意重跑；
时机：每年投档数据入库（etl/load*.py）完成后重跑一次即可。
"""
import time

import psycopg2

from config import DSN

MAP_SQL = """
INSERT INTO major_name_map (admission_name, catalog_name)
SELECT DISTINCT ON (a.major_name) a.major_name, mc.name
FROM (SELECT DISTINCT major_name
      FROM admission_scores
      WHERE major_name IS NOT NULL AND major_name <> '') a
JOIN major_catalog mc
  ON a.major_name ILIKE '%' || mc.name || '%'
ORDER BY a.major_name, length(mc.name) DESC, mc.name
"""


def main():
    conn = psycopg2.connect(DSN)
    try:
        with conn:
            cur = conn.cursor()
            t0 = time.time()
            cur.execute("DELETE FROM major_name_map")
            cur.execute(MAP_SQL)
            cur.execute("SELECT count(*) FROM major_name_map")
            mapped = cur.fetchone()[0]
            cur.execute(
                "SELECT count(DISTINCT major_name) FROM admission_scores "
                "WHERE major_name IS NOT NULL AND major_name <> ''"
            )
            total = cur.fetchone()[0]
            print(
                f"major_name_map 重建完成: {total} 个招生名中 {mapped} 个"
                f"映射到标准专业（覆盖率 {mapped / total:.1%}），"
                f"耗时 {time.time() - t0:.1f}s"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
