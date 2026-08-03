-- 0005 院校官网与简介：在 school_profiles 扩展 website / intro / enriched_at
-- 以 superuser(postgres) 执行（web 角色 gaokao_web_ro 只读，无 ALTER 权限）
ALTER TABLE school_profiles ADD COLUMN IF NOT EXISTS website text;
ALTER TABLE school_profiles ADD COLUMN IF NOT EXISTS intro text;
ALTER TABLE school_profiles ADD COLUMN IF NOT EXISTS enriched_at timestamptz;

COMMENT ON COLUMN school_profiles.website IS '院校官方主页 URL';
COMMENT ON COLUMN school_profiles.intro IS '面向考生的简洁学校简介（2-4 句，由官网/权威来源整理）';
COMMENT ON COLUMN school_profiles.enriched_at IS '官网/简介补充时间，NULL 表示尚未补充；可用于进度跟踪';

-- 进度视图：已补充 / 未补充 计数
-- SELECT count(*) FILTER (WHERE enriched_at IS NOT NULL) AS done,
--        count(*) FILTER (WHERE enriched_at IS NULL)     AS todo
-- FROM school_profiles;
