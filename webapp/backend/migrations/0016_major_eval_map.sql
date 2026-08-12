-- 0016 本科专业 → 第五轮学科评估学科 映射表
-- 执行方式：以 gaokao 拥有者角色运行（须在 0014 之后，依赖 school_disciplines）
--   psql -U gaokao -h localhost -d gaokao -f 0016_major_eval_map.sql
--
-- 背景：
--   专业查询页（major_catalog）按「本科专业」浏览，而第五轮学科评估是按
--   「研究生一级学科」口径。两者命名不完全一致（如「金融学」对应「应用经济学」学科）。
--   本表建立 本科专业名 → 学科评估学科名 的映射，供专业详情页关联展示该专业
--   对应的第五轮学科评估 A 类结果（院校+等级）。
--
-- 数据由 etl/build_major_eval_map.py 生成并写入，规则：
--   1) 同名直接映射（major_catalog.name = school_disciplines.discipline_name）
--   2) 专业类(category) → 学科 映射（如 金融学类 → 应用经济学）
-- 重跑该 ETL 即可刷新映射，无需改本迁移。

BEGIN;

CREATE TABLE IF NOT EXISTS major_eval_map (
  major_name     TEXT NOT NULL,
  eval_discipline TEXT NOT NULL,
  map_type       TEXT NOT NULL DEFAULT 'category'
                 CHECK (map_type IN ('exact', 'category')),
  PRIMARY KEY (major_name, eval_discipline)
);

CREATE INDEX IF NOT EXISTS idx_mem_eval ON major_eval_map(eval_discipline);

COMMIT;
