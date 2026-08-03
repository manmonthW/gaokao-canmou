-- 0010 批次命名统一：2025「提前批」→「专科提前批」（方案 A）
-- 执行方式：以 gaokao 拥有者角色运行（须在既有迁移之后）
--   PGPASSWORD=gaokao123 psql -U gaokao -h localhost -d gaokao -f 0010_batch_naming_unify.sql
--
-- 背景与依据（文件名溯源）：
--   2025「提前批」(128 行) 来源文件为 2025gklqtqpzk*（tqpzk=提前批·专科）与
--   2025gklqzktqzj*（zk·tq·zj=专科提前征集），确认其语义为「专科提前批」，
--   与 2026 的「专科提前批」为同一概念的不同叫法。故重命名对齐。
--
--   2025「本科提前批」(330 行) 保持不变：2025 官方未细分 A/B 段，
--   不强行拆分以免污染数据真实性（方案 A，不采纳拆段的方案 B）。
--
-- 安全性核查（迁移前已验证）：
--   - 2025 现无「专科提前批」行，重命名无冲突；
--   - admission_scores 唯一键为 (src_id,school_code,major_code,major_name,subject,score_kind)，
--     不含 batch，改 batch 不触发唯一约束冲突；
--   - source_files 4 行、publication_status 4 行、data_releases 1 行受影响。

BEGIN;

UPDATE admission_scores
SET batch = '专科提前批'
WHERE year = 2025 AND batch = '提前批';

UPDATE source_files
SET batch = '专科提前批'
WHERE year = 2025 AND batch = '提前批';

UPDATE admission_publication_status
SET batch = '专科提前批', system_updated_at = now()
WHERE year = 2025 AND batch = '提前批';

-- data_releases.covered_batches 数组内的「提前批」替换为「专科提前批」
UPDATE data_releases
SET covered_batches = array_replace(covered_batches, '提前批', '专科提前批')
WHERE '提前批' = ANY(covered_batches);

COMMIT;
