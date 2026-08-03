-- 0006_major_profiles.sql
-- 专业级属性表：补齐 admission_scores 缺失的选科/学制/学费/计划数/硕博/学科水平
-- 维度：院校代码 + 专业代码 + 年份 + 科类(历史/物理学科类)
CREATE TABLE IF NOT EXISTS major_profiles (
    id            BIGSERIAL PRIMARY KEY,
    school_code   TEXT NOT NULL,
    major_code    TEXT,
    major_name    TEXT NOT NULL,
    year          SMALLINT NOT NULL,
    category      TEXT,                       -- 科类：物理学科类 / 历史学科类
    subject_req   TEXT,                       -- 选考科目要求（如 物理,化学(2门须选考) / 不提科目要求）
    length        TEXT,                       -- 学制（如 四年 / 5年）
    tuition       INTEGER,                    -- 学费 元/年（解析自备注或计划表）
    plan_count    INTEGER,                    -- 辽宁招生计划数（分专业）
    plan_count_hist INTEGER,                  -- 历史学科类计划数（youzy 来源）
    plan_count_phys INTEGER,                  -- 物理学科类计划数（youzy 来源）
    has_master    BOOLEAN,                    -- 该校/该专业相关硕士点
    has_doctor    BOOLEAN,                    -- 博士点
    discipline_level TEXT,                    -- 学科水平（如 A- / B+ / 无）
    source        TEXT,                       -- 数据来源标记（dxsbb/youzy/school_official/...）
    raw_note      TEXT,                       -- 原始专业备注（含学费说明等）
    enriched_at   TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE (school_code, major_code, major_name, year, category)
);
CREATE INDEX IF NOT EXISTS idx_mp_school ON major_profiles(school_code);
CREATE INDEX IF NOT EXISTS idx_mp_major ON major_profiles(major_name);
CREATE INDEX IF NOT EXISTS idx_mp_school_year ON major_profiles(school_code, year);

-- 只读角色授权
GRANT SELECT ON major_profiles TO gaokao_web_ro;
GRANT USAGE, SELECT ON SEQUENCE major_profiles_id_seq TO gaokao_web_ro;
