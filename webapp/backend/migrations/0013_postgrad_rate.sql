-- 0013 保研率数值增强：school_profiles.postgrad_recommend_rate
-- 执行方式：以 gaokao 拥有者角色运行（须在 0012 之后）
--   psql -U gaokao -h localhost -d gaokao -f 0013_postgrad_rate.sql
--
-- 背景：0007 阶段已有 has_postgrad_recommend 布尔（A3：367 所保研资格名单），
--   本迁移补入保研率数值，来源《全国367所具有保研资格院校保研率》PDF
--   （最新年 2021 推免率口径），由 etl/load_baoyan_rate.py 灌入。
-- 语义：NULL = 无保研资格或数据缺失；数值 = 最新年推免率（%）。
-- 不新增表，无需新增 GRANT（gaokao_web_ro 已有 school_profiles SELECT 权限）。

BEGIN;

ALTER TABLE school_profiles
  ADD COLUMN IF NOT EXISTS postgrad_recommend_rate NUMERIC(5,2);

COMMENT ON COLUMN school_profiles.postgrad_recommend_rate IS
  '保研率/推免率（%），最新年口径（2021），来源《全国367所具有保研资格院校保研率》PDF；NULL=无资格或缺失';

COMMIT;
