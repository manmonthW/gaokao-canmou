-- 0007_phase1_enrich.sql
-- 第一期：院校+专业核心字段补全
-- A1: 院校标识码/主管单位/所在地/办学层次
-- A2: 院校层级标签（985/211/双一流/小985/小211/部委直属）
-- A3: 保研资格
ALTER TABLE school_profiles
  ADD COLUMN IF NOT EXISTS school_id_code TEXT,          -- 学校标识码（教育部）
  ADD COLUMN IF NOT EXISTS has_postgrad_recommend BOOLEAN DEFAULT FALSE, -- 保研资格
  ADD COLUMN IF NOT EXISTS tags TEXT;                    -- 层级标签聚合（如 985;211;双一流）

-- B7: 专业标准字典（教育部本科专业目录）
CREATE TABLE IF NOT EXISTS major_catalog (
    id            BIGSERIAL PRIMARY KEY,
    code          TEXT NOT NULL,        -- 专业代码（6位）
    name          TEXT NOT NULL,        -- 专业名称
    category      TEXT,                 -- 专业类（如 经济学类）
    discipline    TEXT,                 -- 门类（如 经济学）
    year          SMALLINT,             -- 目录年份（2025/2026）
    UNIQUE (code, year)
);
CREATE INDEX IF NOT EXISTS idx_mc_name ON major_catalog(name);
CREATE INDEX IF NOT EXISTS idx_mc_code ON major_catalog(code);
GRANT SELECT ON major_catalog TO gaokao_web_ro;
GRANT USAGE, SELECT ON SEQUENCE major_catalog_id_seq TO gaokao_web_ro;
GRANT SELECT ON school_profiles TO gaokao_web_ro;
