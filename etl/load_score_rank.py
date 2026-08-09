#!/usr/bin/env python3
"""将辽宁高考「成绩统计表(一分一段表)」加载进 PostgreSQL 的 score_rank 表。

数据来源：etl/score_rank_pdf/{2024,2025,2026}/*.pdf
（沈阳本地宝镜像辽宁招生考试之窗官方发布，文字版 PDF，由 parse_score_rank 解析）。
重算累计位次由 count 累加得到，已规避水印污染。

用法:
  python3 etl/load_score_rank.py           # 建表 + 全量载入 (幂等, 先清后插)
  python3 etl/load_score_rank.py --dry-run # 仅打印校验，不落库
"""
import os, sys, argparse
import psycopg2

import parse_score_rank as pr
from config import DSN

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS score_rank (
  id              BIGSERIAL PRIMARY KEY,
  year            SMALLINT NOT NULL,
  subject         TEXT NOT NULL,   -- 物理学科类 / 历史学科类
  category        TEXT NOT NULL,   -- 普通类 / 体育类 / 艺术类
  score           INTEGER NOT NULL,-- 分数 (顶部桶取整数, 如 708 表示 >=708)
  count           INTEGER NOT NULL,-- 该分数人数
  cumulative_rank INTEGER NOT NULL,-- 累计人数 (>=该分人数, 即省排名)
  is_top_bucket   BOOLEAN DEFAULT FALSE, -- 是否 "XX及以上" 顶部桶
  source          TEXT,            -- 来源 PDF 文件名 (溯源)
  UNIQUE (year, subject, category, score)
);
CREATE INDEX IF NOT EXISTS idx_rank_ysc ON score_rank(year, subject, category, score);
CREATE INDEX IF NOT EXISTS idx_rank_year ON score_rank(year);
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    recs = pr.build_records()
    print(f"解析得到 {len(recs)} 条记录")

    if args.dry_run:
        return

    conn = psycopg2.connect(DSN)
    try:
        cur = conn.cursor()
        cur.execute(CREATE_SQL)
        cur.execute("TRUNCATE TABLE score_rank")
        cur.executemany(
            "INSERT INTO score_rank "
            "(year, subject, category, score, count, cumulative_rank, is_top_bucket, source) "
            "VALUES (%(year)s,%(subject)s,%(category)s,%(score)s,%(count)s,"
            "%(cumulative_rank)s,%(is_top_bucket)s,%(source)s)",
            recs,
        )
        conn.commit()
        cur.execute("SELECT count(*) FROM score_rank")
        print("score_rank 已载入:", cur.fetchone()[0], "行")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
