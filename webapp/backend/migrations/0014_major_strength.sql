-- 0014 院校学科实力与专业强度数据（一期建表）
-- 执行方式：以 gaokao 拥有者角色运行（须在 0013 之后）
--   psql -U gaokao -h localhost -d gaokao -f 0014_major_strength.sql
--
-- 内容：
--   1) school_disciplines  院校学科评估/一流学科建设记录（学科粒度）
--   2) major_strengths     一流专业建设点与第三方专业评级（专业粒度）
--   3) strength_dictionary 实力标签词表（前端展示与筛选的统一来源，模式同 0011 flag_dictionary）
--   4) school_profiles.strength_tags TEXT[] + GIN 索引（院校级聚合标签，供列表页直出）
--
-- 设计决策：
--   - 不回填 major_profiles 既有预留列（discipline_level 等）：
--     学科评估/一流专业是「院校-学科」「院校-专业」实力口径，与 major_profiles
--     的「招生条目」粒度不匹配；且 etl/load_major_profiles.py 仍在运行，
--     全量重写该表，手工回填会被覆盖。本迁移只建新表，互不干扰。
--   - school_disciplines.school_code / major_strengths.major_code 可空：
--     部分原始素材（如图片 OCR、第三方榜单）未含代码，允许先入库后解析；
--     院校代码与「院校名称 + 数据年份」联合唯一，不依赖代码去重。
--   - verify_status 预留人工复核流转（pending/verified/disputed），
--     review_note/image_ref/src_file_id 支撑溯源到原始素材。

BEGIN;

-- ---------- 1) school_disciplines：院校学科实力记录 ----------
-- 一条记录 = 某校某学科在某来源某年份的一个评级结果。
-- source 取值：
--   eval4_official  教育部第四轮学科评估（2017 公布，官方）
--   eval5_a         第五轮学科评估 A 类结果（非官方，来自各校喜报/汇总版）
--   dfc2022         第二轮「双一流」建设学科名单（2022 公布，官方）
CREATE TABLE IF NOT EXISTS school_disciplines (
  id              SERIAL PRIMARY KEY,
  school_code     TEXT,                       -- 院校代码（可空 = 原始素材未解析出代码）
  school_name     TEXT NOT NULL,
  discipline_name TEXT NOT NULL,              -- 学科名称（如 计算机科学与技术）
  source          TEXT NOT NULL
                  CHECK (source IN ('eval4_official', 'eval5_a', 'dfc2022')),
  data_year       SMALLINT NOT NULL,          -- 数据所属年份（如 2017/2023/2022）
  grade           TEXT,                       -- 评级（如 A+ / A / A-；双一流名单无评级为 NULL）
  official        BOOLEAN NOT NULL,           -- 是否官方发布口径
  verify_status   TEXT NOT NULL DEFAULT 'pending'
                  CHECK (verify_status IN ('pending', 'verified', 'disputed')),
  review_note     TEXT,                       -- 人工复核备注
  image_ref       TEXT,                       -- 原始素材图片/文件引用（溯源）
  src_file_id     BIGINT REFERENCES source_files(id),
  UNIQUE (source, data_year, school_name, discipline_name)
);
CREATE INDEX IF NOT EXISTS idx_sd_school_code ON school_disciplines(school_code);
CREATE INDEX IF NOT EXISTS idx_sd_source_year ON school_disciplines(source, data_year);
CREATE INDEX IF NOT EXISTS idx_sd_discipline  ON school_disciplines(discipline_name);

-- ---------- 2) major_strengths：专业实力记录 ----------
-- 一条记录 = 某校某专业在某来源某年份的一个入选/评级结果。
-- source 取值：
--   swyc_national   国家级一流本科专业建设点（教育部「双万计划」，官方）
--   swyc_provincial 省级一流本科专业建设点（官方）
--   ruanke          软科中国大学专业排名评级（第三方，仅供参考）
CREATE TABLE IF NOT EXISTS major_strengths (
  id          SERIAL PRIMARY KEY,
  school_code TEXT,                           -- 院校代码（可空 = 原始素材未解析出代码）
  school_name TEXT NOT NULL,
  major_name  TEXT NOT NULL,
  major_code  TEXT,                           -- 专业代码（可空，二期解析预留）
  source      TEXT NOT NULL
              CHECK (source IN ('swyc_national', 'swyc_provincial', 'ruanke')),
  data_year   SMALLINT NOT NULL,              -- 数据所属年份（批次公布年/排名年）
  batch       SMALLINT,                       -- 入选批次（双万计划 2019-2021 三批；排名类为 NULL）
  rank        INT,                            -- 第三方排名名次（官方名单为 NULL）
  tier        TEXT,                           -- 第三方评级档位（如 A+ / A / B+；官方名单为 NULL）
  note        TEXT,                           -- 原始备注
  src_file_id BIGINT REFERENCES source_files(id),
  UNIQUE (source, data_year, school_name, major_name)
);
CREATE INDEX IF NOT EXISTS idx_ms_school_code ON major_strengths(school_code);
CREATE INDEX IF NOT EXISTS idx_ms_major_name  ON major_strengths(major_name);
CREATE INDEX IF NOT EXISTS idx_ms_code_year   ON major_strengths(major_code, data_year);

-- ---------- 3) strength_dictionary：实力标签词表 ----------
-- 模式同 0011 flag_dictionary：前端标签展示/筛选文案的唯一权威来源。
-- 每条 label/source_note 用平实语言写清楚，外行能直接看懂。
CREATE TABLE IF NOT EXISTS strength_dictionary (
  tag           TEXT PRIMARY KEY,             -- 标签键（入 school_profiles.strength_tags 的值）
  label         TEXT NOT NULL,                -- 前端展示文案
  kind          TEXT NOT NULL,                -- 分类：eval4/eval5/dfc2022/swyc/ruanke/meta
  third_party   BOOLEAN NOT NULL DEFAULT FALSE, -- 是否第三方来源（前端需加免责提示）
  source_note   TEXT,                         -- 来源与口径说明（平实语言）
  display_order INT NOT NULL DEFAULT 0        -- 展示排序（小者靠前）
);

INSERT INTO strength_dictionary (tag, label, kind, third_party, source_note, display_order) VALUES
  ('四轮A+', '四轮学科评估 A+', 'eval4', FALSE,
   '教育部第四轮学科评估（2017 年公布，官方）中该学科获评 A+，为全国前 2% 或前 2 名，是官方认可的最顶尖学科水平', 1),
  ('四轮A',  '四轮学科评估 A',  'eval4', FALSE,
   '教育部第四轮学科评估（2017 年公布，官方）中该学科获评 A，为全国前 2%～5%，属官方认可的顶尖学科水平', 2),
  ('四轮A-', '四轮学科评估 A-', 'eval4', FALSE,
   '教育部第四轮学科评估（2017 年公布，官方）中该学科获评 A-，为全国前 5%～10%，属官方认可的优势学科', 3),
  ('五轮A+', '五轮学科评估 A+', 'eval5', FALSE,
   '第五轮学科评估 A+ 结果，来自各校公开发布的喜报与汇总（非官方·A类汇总版），官方未集中公布完整名单，供参考', 4),
  ('五轮A',  '五轮学科评估 A',  'eval5', FALSE,
   '第五轮学科评估 A 结果，来自各校公开发布的喜报与汇总（非官方·A类汇总版），官方未集中公布完整名单，供参考', 5),
  ('五轮A-', '五轮学科评估 A-', 'eval5', FALSE,
   '第五轮学科评估 A- 结果，来自各校公开发布的喜报与汇总（非官方·A类汇总版），官方未集中公布完整名单，供参考', 6),
  ('双一流学科', '双一流建设学科', 'dfc2022', FALSE,
   '入选第二轮「双一流」建设学科名单（2022 年公布，教育部官方），代表国家重点支持建设的高水平学科', 7),
  ('国一流专业', '国家级一流本科专业', 'swyc', FALSE,
   '入选教育部「双万计划」国家级一流本科专业建设点（2019-2021 年三批公布，官方），代表该专业办学水平获国家认可', 8),
  ('省一流专业', '省级一流本科专业', 'swyc', FALSE,
   '入选「双万计划」省级一流本科专业建设点（2019-2021 年三批公布，官方），代表该专业办学水平获省级认可', 9),
  ('软科评级', '软科专业评级', 'ruanke', TRUE,
   '来自软科中国大学专业排名（第三方·仅供参考），非官方评价，评级与名次仅作报考参考', 10),
  ('多源印证', '多源实力印证', 'meta', FALSE,
   '该校该方向的实力获得两个及以上独立来源的共同印证（如学科评估 + 一流专业），可信度更高', 11)
ON CONFLICT (tag) DO UPDATE
  SET label         = EXCLUDED.label,
      kind          = EXCLUDED.kind,
      third_party   = EXCLUDED.third_party,
      source_note   = EXCLUDED.source_note,
      display_order = EXCLUDED.display_order;

-- ---------- 4) school_profiles.strength_tags：院校级聚合标签 ----------
-- 值为 strength_dictionary.tag，由后续 ETL 从三张明细表聚合重算（幂等全量刷新）。
ALTER TABLE school_profiles
  ADD COLUMN IF NOT EXISTS strength_tags TEXT[] NOT NULL DEFAULT '{}';

-- GIN 索引：支持 strength_tags && ARRAY[...] / @> 过滤（模式同 0011 flags）
CREATE INDEX IF NOT EXISTS idx_profiles_strength_tags
  ON school_profiles USING GIN (strength_tags);

COMMENT ON COLUMN school_profiles.strength_tags IS
  '院校级实力标签数组（值域=strength_dictionary.tag），由明细表聚合重算，空数组=暂无收录';

-- ---------- 5) 只读 Web 角色授权（模式同 0006/0011）----------
GRANT SELECT ON school_disciplines TO gaokao_web_ro;
GRANT USAGE, SELECT ON SEQUENCE school_disciplines_id_seq TO gaokao_web_ro;

GRANT SELECT ON major_strengths TO gaokao_web_ro;
GRANT USAGE, SELECT ON SEQUENCE major_strengths_id_seq TO gaokao_web_ro;

GRANT SELECT ON strength_dictionary TO gaokao_web_ro;

COMMIT;
