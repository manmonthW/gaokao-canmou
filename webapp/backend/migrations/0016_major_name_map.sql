-- 0016 招生专业名 → 标准专业映射预计算 + 匹配主查询复合索引
-- 执行方式：以 gaokao 拥有者角色运行（须在 0015 之后）
--   psql -U gaokao -h localhost -d gaokao -f 0016_major_name_map.sql
--
-- 背景：
--   /match 每次请求都用 major_name ILIKE '%' || mc.name || '%' 把招生专业名
--   映射到 major_catalog 标准专业名（供专业详情跳转与实力关联）。双侧通配
--   无索引可走，几千个招生名 × 737 标准名 = 千万级 ILIKE，是 /match 最大头。
--   映射只依赖 admission_scores 与 major_catalog 两张静态表，一年只在年度
--   投档入库时变化一次 —— 与 0015 同套路：ETL 预计算，读路径精确匹配。
--
-- 设计决策：
--   - 口径与 match.py 原实时查询一致：招生名被标准名包含即命中，
--     多个命中取名字最长的（最具体）；ETL 用 DISTINCT ON 一次算完。
--   - 顺带补 (category, subject, batch, is_collection, score_kind) 复合索引：
--     既有 idx_scores_ymcsb 首列是 year，而匹配主查询不带 year，用不上。

BEGIN;

CREATE TABLE IF NOT EXISTS major_name_map (
  admission_name TEXT PRIMARY KEY,   -- admission_scores 招生专业名（原始名）
  catalog_name   TEXT NOT NULL       -- major_catalog 标准专业名（最长命中）
);

COMMENT ON TABLE major_name_map IS
  '招生专业名→标准专业名映射预计算表，由 etl/load_major_name_map.py 全量重建；年度投档入库后须重跑';

-- 匹配主查询过滤列复合索引（不带 year 的查询路径）
CREATE INDEX IF NOT EXISTS idx_scores_cat_subj_batch
  ON admission_scores(category, subject, batch, is_collection, score_kind);

-- ---------- 只读 Web 角色授权（模式同 0006/0011/0014/0015）----------
GRANT SELECT ON major_name_map TO gaokao_web_ro;

COMMIT;
