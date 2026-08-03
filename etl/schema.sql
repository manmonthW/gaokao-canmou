-- ============================================================================
-- ⚠️ 已废弃（DEPRECATED）—— 请勿用于建库/重建库
-- ----------------------------------------------------------------------------
-- 本文件仅保留早期 ETL 阶段的表结构，已严重滞后于真实库（真实库含 14 张表：
-- data_releases / admission_publication_status / school_profiles / cities /
-- major_catalog / major_profiles / major_hot_profiles / school_hot_profiles
-- 等，本文件均未包含）。
--
-- 唯一权威真相源：webapp/backend/migrations/0000_*.sql ~ 0009_*.sql（按序执行）。
-- 重建库请以 migrations 为准，切勿运行本文件（会 DROP 并残缺重建核心表）。
--
-- 保留原因：作为字段语义的历史注释参考（tiebreak_1~7、score_kind、lowest_rank
-- 等列的说明在此较完整）。如需修改结构，请新增 migration，不要改本文件。
-- ============================================================================

-- 辽宁高考录取最低分数据库 schema（历史版本，已废弃）
-- 【已废弃】原运行方式（请勿再执行）:
--   PGPASSWORD=gaokao123 psql -U gaokao -h localhost -d gaokao -f schema.sql

DROP TABLE IF EXISTS admission_scores CASCADE;
DROP TABLE IF EXISTS raw_texts CASCADE;
DROP TABLE IF EXISTS schools CASCADE;
DROP TABLE IF EXISTS source_files CASCADE;

-- 1) 文件溯源：保证“无遗漏”可审计
CREATE TABLE source_files (
  id            BIGSERIAL PRIMARY KEY,
  filename      TEXT NOT NULL,
  fmt           TEXT,                 -- xlsx / xls / pdf
  year          SMALLINT,
  category      TEXT,                 -- 普通类 / 艺术类 / 体育类
  batch         TEXT,                 -- 本科批 / 专科批 / 本科提前批A段 ...
  is_collection BOOLEAN DEFAULT FALSE,-- 是否征集志愿
  subject       TEXT,                 -- 物理学科类 / 历史学科类
  sheet         TEXT,
  status        TEXT DEFAULT 'pending', -- loaded / encrypted / error
  note          TEXT,
  loaded_at     TIMESTAMPTZ
);

-- 2) 院校维度
CREATE TABLE schools (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL
);
CREATE INDEX idx_schools_name ON schools(name);

-- 3) 核心事实表：投档/录取最低分
CREATE TABLE admission_scores (
  id            BIGSERIAL PRIMARY KEY,
  src_id        BIGINT REFERENCES source_files(id),
  year          SMALLINT NOT NULL,
  category      TEXT NOT NULL,
  batch         TEXT,                   -- PDF OCR 元数据可能缺失，允许为空
  is_collection BOOLEAN DEFAULT FALSE,
  subject       TEXT,                   -- 同上
  school_code   TEXT REFERENCES schools(code),
  school_name   TEXT NOT NULL,
  major_code    TEXT,                 -- 提前批A段为 NULL
  major_name    TEXT,
  score_kind    TEXT,                 -- 投档最低分 / 录取最低分
  lowest_score  NUMERIC(7,2),
  tiebreak_1    NUMERIC(7,2),         -- 同分排序项(一)~(七)
  tiebreak_2    NUMERIC(7,2),
  tiebreak_3    NUMERIC(7,2),
  tiebreak_4    NUMERIC(7,2),
  tiebreak_5    NUMERIC(7,2),
  tiebreak_6    NUMERIC(7,2),
  tiebreak_7    NUMERIC(7,2),
  lowest_rank   INTEGER,              -- 由 score_rank 反查：投档/录取最低分对应的省位次(>=该分人数)
  raw_row       JSONB,                -- 原始行兜底，绝不丢字段
  UNIQUE (src_id, school_code, major_code, subject, score_kind)
);
CREATE INDEX idx_scores_ycb  ON admission_scores(year, category, batch);
CREATE INDEX idx_scores_schl ON admission_scores(school_name);
CREATE INDEX idx_scores_maj  ON admission_scores(major_name);

-- 4) 原始文本存档：PDF / 无法结构化的兜底，确保无遗漏
CREATE TABLE raw_texts (
  id      BIGSERIAL PRIMARY KEY,
  src_id  BIGINT REFERENCES source_files(id),
  page    INT,
  content TEXT
);

-- 5) 一分一段表（成绩统计表）：分数 <-> 省排名换算基石
--    来源：辽宁招生考试之窗官方发布，沈阳本地宝(bendibao)镜像文字版 PDF，
--          经 etl/parse_score_rank.py 解析、etl/load_score_rank.py 载入。
--    累计人数 = 自最高分起 count 累加（">=该分人数" = 省排名），
--    不直接采用 PDF 内被水印污染的"累计"列，改由 count 重算以消除个别坏值。
CREATE TABLE IF NOT EXISTS score_rank (
  id              BIGSERIAL PRIMARY KEY,
  year            SMALLINT NOT NULL,
  subject         TEXT NOT NULL,   -- 物理学科类 / 历史学科类
  category        TEXT NOT NULL,   -- 普通类 / 体育类 / 艺术类
  score           INTEGER NOT NULL,-- 分数（顶部桶取整数，如 708 表示 >=708）
  count           INTEGER NOT NULL,-- 该分数人数
  cumulative_rank INTEGER NOT NULL,-- 累计人数（>=该分人数，即省排名）
  is_top_bucket   BOOLEAN DEFAULT FALSE, -- 是否 "XX及以上" 顶部桶
  source          TEXT,            -- 来源 PDF 文件名（溯源）
  UNIQUE (year, subject, category, score)
);
CREATE INDEX IF NOT EXISTS idx_rank_ysc ON score_rank(year, subject, category, score);
CREATE INDEX IF NOT EXISTS idx_rank_year ON score_rank(year);

-- 6) 批次录取控制分数线（省控线）：判断考生是否过线的基准
--    来源：辽宁招生考试之窗/辽宁省教育厅 官方发布，经 etl/load_control_line.py 载入。
--    line_type: 特殊类型(特控线) / 本科 / 专科 / 本科_舞蹈表导音乐表演 / 本科_戏曲
--    注：体育类、艺术类此处仅存“文化课控制线”，专业控制线需另行满足（judge 会提示）。
CREATE TABLE IF NOT EXISTS batch_control_line (
  id        BIGSERIAL PRIMARY KEY,
  year      SMALLINT NOT NULL,
  category  TEXT NOT NULL,   -- 普通类 / 体育类 / 艺术类
  subject   TEXT NOT NULL,   -- 物理学科类 / 历史学科类
  line_type TEXT NOT NULL,   -- 特殊类型 / 本科 / 专科 / 本科_舞蹈表导音乐表演 / 本科_戏曲
  score     INTEGER NOT NULL,
  note      TEXT,
  UNIQUE (year, category, subject, line_type)
);
CREATE INDEX IF NOT EXISTS idx_bcl_ysc ON batch_control_line(year, category, subject, line_type);

