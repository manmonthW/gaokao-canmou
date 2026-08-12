-- 0015 专业字典「在辽招生概览」预计算表
-- 执行方式：以 gaokao 拥有者角色运行（须在 0014 之后）
--   psql -U gaokao -h localhost -d gaokao -f 0015_major_admission_summary.sql
--
-- 背景：
--   /major-catalog/search 原先每次请求都用
--     admission_scores.major_name ILIKE '%' || mc.name || '%'
--   做 737 个标准专业 × 约 6.7 万条分数的全表关联，双侧通配无法走索引，
--   单次请求约 25 秒；专业查询页每次打开都要跑一遍（取热门专业入口）。
--
-- 设计决策：
--   - 分数数据一年只在年度投档入库时变化一次，是典型的预计算场景：
--     ILIKE 重聚合只在 ETL 阶段跑一次（etl/load_major_summary.py，幂等全量重建），
--     读路径改为本表直连，毫秒级。
--   - 主键 (code, name) 对齐 major_catalog；标准专业目录若有增删，重跑 ETL 即可。
--   - built_at 记录最近一次重建时间，便于排查数据新鲜度。

BEGIN;

CREATE TABLE IF NOT EXISTS major_admission_summary (
  code         TEXT NOT NULL,                -- major_catalog 标准专业代码
  name         TEXT NOT NULL,                -- major_catalog 标准专业名称
  school_count INTEGER NOT NULL DEFAULT 0,   -- 在辽招该专业的院校数（模糊关联口径）
  min_score    NUMERIC,                      -- 历年最低分区间下限
  max_score    NUMERIC,                      -- 历年最低分区间上限
  min_rank     INTEGER,                      -- 历年最低位次区间下限
  max_rank     INTEGER,                      -- 历年最低位次区间上限
  built_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (code, name)
);

COMMENT ON TABLE major_admission_summary IS
  '专业字典在辽招生概览预计算表，由 etl/load_major_summary.py 全量重建；年度投档入库后须重跑';

-- ---------- 只读 Web 角色授权（模式同 0006/0011/0014）----------
GRANT SELECT ON major_admission_summary TO gaokao_web_ro;

COMMIT;
