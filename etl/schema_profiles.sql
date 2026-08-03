-- 院校画像 + 城市画像 扩展表（独立 migration，不删除已有表）
-- 运行: PGPASSWORD=gaokao123 psql -U gaokao -h localhost -d gaokao -f schema_profiles.sql

-- 7) 城市画像（地理位置深度维度，按"去重城市"调研一次，被多所院校复用）
--    来源: brightgems/china_city_dataset(城市分级/地理大区) + Wikidata(地区GDP) + 规则推导(城市群/沿海)
CREATE TABLE IF NOT EXISTS cities (
  city      TEXT PRIMARY KEY,           -- 归一化城市名(去"市/地区/自治州"等后缀), 如 大连
  province  TEXT,                       -- 省份
  region    TEXT,                       -- 地理大区(华北/东北/华东/华南/华中/西北/西南)
  tier      TEXT,                       -- 城市分级(一线/新一线/二线/三线/四线/五线)
  gdp       NUMERIC,                    -- 地区生产总值(亿元)
  gdp_year  SMALLINT,                   -- GDP 对应年份
  cluster   TEXT,                       -- 所属城市群(长三角/珠三角/京津冀/成渝/长江中游…)
  coastal   BOOLEAN,                    -- 是否沿海城市
  note      TEXT
);
CREATE INDEX IF NOT EXISTS idx_cities_prov ON cities(province);

-- 8) 院校画像（省份/层次/性质/类型 + 城市引用）
--    来源: 教育部《2025全国高等学校名单》Excel(省份/城市/主管/层次/性质)
--          + 校名启发式(类型) + 官方名单(985/211/双一流) + Wikidata/软科(建校年/优势)
CREATE TABLE IF NOT EXISTS school_profiles (
  code        TEXT PRIMARY KEY REFERENCES schools(code),
  name        TEXT,
  city        TEXT REFERENCES cities(city),   -- 归一化城市名
  province    TEXT,
  affiliation TEXT,                   -- 主管部门(教育部/省属/市属/部委…)
  level       TEXT,                   -- 本科 / 高职专科
  nature      TEXT,                   -- 公办 / 民办 / 独立学院 / 中外合作办学
  type        TEXT,                   -- 综合/理工/师范/医药/财经/农林/政法/语言/民族/艺术/体育/军事/职业技术
  is_985      BOOLEAN DEFAULT FALSE,
  is_211      BOOLEAN DEFAULT FALSE,
  is_dfc      BOOLEAN DEFAULT FALSE,  -- 双一流
  established INTEGER,                -- 建校年
  strength    TEXT,                   -- 优势学科/特色
  school_style TEXT,                  -- 办学风格标签
  employment_region TEXT,            -- 就业集中地
  rank_ref    TEXT,                   -- 参考排名(软科/校友会)
  note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_sp_prov ON school_profiles(province);
CREATE INDEX IF NOT EXISTS idx_sp_level ON school_profiles(level);
CREATE INDEX IF NOT EXISTS idx_sp_type ON school_profiles(type);
CREATE INDEX IF NOT EXISTS idx_sp_nature ON school_profiles(nature);
CREATE INDEX IF NOT EXISTS idx_sp_dfc ON school_profiles(is_dfc);
