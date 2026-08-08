-- 0012 选考科目要求（D2b 骨架）：2027 年各专业在辽选科要求
-- 执行方式：以 gaokao 拥有者角色运行（须在 0011 之后）
--   psql -U gaokao -h localhost -d gaokao -f 0012_subject_requirements.sql
--
-- 设计说明（docs/first-principles-review.md 建议 D2b）：
--   - 3+1+2 模式：首选（物理/历史）决定学科类，再选两科常被专业要求约束。
--   - 本表先建骨架，数据待辽宁官方发布 2027 选科要求后由
--     etl/load_subject_requirements.py 灌入（复用 source_files 溯源）。
--   - 匹配语义（先行约定）：有记录且不满足 → 硬过滤并计入 excluded_by_subject；
--     无记录 → 不排除但标注 subject_unverified（数据未核验不默认「可报」）。
--   - re_req 保留官方原文（如「化学(必选)」「化学,生物(2选1)」），
--     结构化解析在加载层处理，避免建表期过度设计。

BEGIN;

CREATE TABLE IF NOT EXISTS subject_requirements (
  id          BIGSERIAL PRIMARY KEY,
  year        SMALLINT NOT NULL,
  school_code TEXT,
  school_name TEXT NOT NULL,
  major_name  TEXT,                    -- 专业组口径时可为空
  major_code  TEXT,
  group_code  TEXT,                    -- 招生单元/专业组（预留）
  first_req   TEXT,                    -- 首选要求：物理 / 历史 / 不限
  re_req      TEXT,                    -- 再选要求（官方原文）
  raw_text    TEXT,                    -- 原始行兜底
  src_id      BIGINT REFERENCES source_files(id),
  loaded_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subjreq_ysc
  ON subject_requirements(year, school_code);
CREATE INDEX IF NOT EXISTS idx_subjreq_name
  ON subject_requirements(school_name, major_name);

-- 只读 Web 角色授权
GRANT SELECT ON subject_requirements TO gaokao_web_ro;

COMMIT;
