"""P1: 由一分一段表(score_rank)反查“最低位次”补录入库，支撑位次版匹配。

逻辑：
- 给 admission_scores 增加 lowest_rank 列（若不存在）。
- 对每行有 lowest_score 的记录，按 (year, subject, category) 在 score_rank 中
  找到 <= floor(lowest_score) 的最大整数分对应的 cumulative_rank（即“>=该分人数”=省位次）。
- 仅当能在 score_rank 命中（lowest_score 落在表分数区间内）才写入，
  越界（如脏数据 70 分、或艺术类综合分超表范围）保持 NULL，避免伪排名。
- 幂等：重复运行只更新，不会重复插入。

运行: python3 etl/backfill_lowest_rank.py
"""
import psycopg2
from config import DSN


def backfill(conn):
    with conn:
        with conn.cursor() as cur:
            # 1) 加列（幂等）
            cur.execute(
                "ALTER TABLE admission_scores ADD COLUMN IF NOT EXISTS lowest_rank INTEGER;")

            # 2) 反查更新：LATERAL 取 <= floor(lowest_score) 的最大分对应累计位次
            cur.execute(
                """
                UPDATE admission_scores a
                SET lowest_rank = sub.rank
                FROM (
                    SELECT a2.id,
                           (SELECT s.cumulative_rank
                              FROM score_rank s
                             WHERE s.year = a2.year
                               AND s.subject = a2.subject
                               AND s.category = a2.category
                               AND s.score <= floor(a2.lowest_score)
                             ORDER BY s.score DESC
                             LIMIT 1) AS rank
                    FROM admission_scores a2
                    WHERE a2.lowest_score IS NOT NULL
                      AND a2.subject IN ('物理学科类', '历史学科类')
                      AND a2.category IN ('普通类', '体育类', '艺术类')
                ) sub
                WHERE a.id = sub.id AND sub.rank IS NOT NULL;
                """
            )
            updated = cur.rowcount

            # 3) 统计
            cur.execute(
                "SELECT count(*) FROM admission_scores WHERE lowest_rank IS NOT NULL;")
            have_rank = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM admission_scores WHERE lowest_score IS NOT NULL;")
            have_score = cur.fetchone()[0]
            return updated, have_score, have_rank


def spot_check(conn):
    """抽样验证：选几个已知锚点比对。"""
    cur = conn.cursor()
    # 2025 物理 普通类 606 -> 已知 11742
    cur.execute(
        """SELECT school_name, lowest_score, lowest_rank
           FROM admission_scores
           WHERE year=2025 AND subject='物理学科类' AND category='普通类'
             AND lowest_score=606 LIMIT 3;""")
    print("  抽样(2025物理普通类 606分 应≈11742):")
    for r in cur.fetchall():
        print(f"    {r[0]} score={r[1]} rank={r[2]}")
    cur.close()


def main():
    conn = psycopg2.connect(DSN)
    try:
        updated, have_score, have_rank = backfill(conn)
        print(f"P1 完成: 本次更新 {updated} 行 | 有 lowest_score 共 {have_score} 行 | "
              f"已反查到位次 {have_rank} 行")
        spot_check(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
