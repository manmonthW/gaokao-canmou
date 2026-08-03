-- Phase 1 查询性能索引（spec 12.2）
-- 由 gaokao 拥有者执行；同时补齐只读角色对已建索引所属表的 SELECT。
CREATE INDEX IF NOT EXISTS idx_scores_school_code ON admission_scores(school_code);
CREATE INDEX IF NOT EXISTS idx_scores_ymcsb ON admission_scores(year, category, subject, batch, is_collection);
CREATE INDEX IF NOT EXISTS idx_scores_school_year ON admission_scores(school_code, year);
CREATE INDEX IF NOT EXISTS idx_scores_major_year ON admission_scores(major_name, year);
CREATE INDEX IF NOT EXISTS idx_src_year_cat ON source_files(year, category);

-- 确保只读角色可读取（gaokao 拥有者建的表/索引默认不含 SELECT 授权）
GRANT SELECT ON ALL TABLES IN SCHEMA public TO gaokao_web_ro;
