-- 0008 source_files 去重 + 幂等约束 + loaded_at 回填
-- 执行方式：以 gaokao 拥有者角色运行（须在既有迁移之后）
--   PGPASSWORD=gaokao123 psql -U gaokao -h localhost -d gaokao -f 0008_source_files_dedup.sql
--
-- 背景：load_2026_supplement.py 使用 INSERT ... ON CONFLICT DO NOTHING，
--   但 source_files 从未建立唯一约束，冲突永不触发，导致每次运行都新增行。
--   实测 source_files 有 235 行 / 65 个唯一文件名（单文件最高 69 次重复）。
--   每个重复 source_files 行与其 admission_scores 行是 1:1 关系，
--   raw_texts 不引用任何重复行（已核实）。admission_scores 本身无重复。
--
-- 本迁移：
--   1) 每个 filename 保留最小 id 为 canonical，其余重复行的 admission_scores.src_id
--      重指向 canonical，然后删除多余 source_files 行；
--   2) 回填 loaded_at（现有行为 NULL，统一设为 now()，仅补空值）；
--   3) 建立复合唯一约束（filename + 语义维度），支撑脚本幂等 upsert；
--   语义维度选 (filename, year, category, batch, subject, is_collection)，
--   比单列 filename 更安全：允许同名文件承载不同科类/批次/科目/志愿阶段语义。

BEGIN;

-- ---------- 1) 去重：重指向子表 src_id 到 canonical，再删多余父行 ----------
-- 计算每个 (filename, year, category, batch, subject, is_collection) 分组的 canonical（最小 id）
CREATE TEMP TABLE _sf_canon ON COMMIT DROP AS
SELECT id AS dup_id,
       min(id) OVER (
         PARTITION BY filename, year, category, batch, subject, is_collection
       ) AS canon_id
FROM source_files;

-- 把 admission_scores 中指向重复行的 src_id 重指向 canonical
UPDATE admission_scores a
SET src_id = c.canon_id
FROM _sf_canon c
WHERE a.src_id = c.dup_id
  AND c.dup_id <> c.canon_id;

-- 把 raw_texts 中指向重复行的 src_id 重指向 canonical（防御性，实测当前为 0 行）
UPDATE raw_texts r
SET src_id = c.canon_id
FROM _sf_canon c
WHERE r.src_id = c.dup_id
  AND c.dup_id <> c.canon_id;

-- 删除多余的 source_files 行（非 canonical）
DELETE FROM source_files sf
USING _sf_canon c
WHERE sf.id = c.dup_id
  AND c.dup_id <> c.canon_id;

-- ---------- 2) 回填 loaded_at（仅补空值）----------
UPDATE source_files
SET loaded_at = now()
WHERE loaded_at IS NULL;

-- ---------- 3) 建立复合唯一约束（幂等 upsert 依据）----------
-- 使用唯一索引而非表约束，便于 ON CONFLICT 指定；NULL 语义：
-- Postgres 默认多个 NULL 不冲突，为使含 NULL 维度的行也能去重/幂等，
-- 采用 COALESCE 归一后的表达式索引。
CREATE UNIQUE INDEX IF NOT EXISTS uq_source_files_semantic
  ON source_files (
    filename,
    COALESCE(year, -1),
    COALESCE(category, ''),
    COALESCE(batch, ''),
    COALESCE(subject, ''),
    COALESCE(is_collection, FALSE)
  );

COMMIT;
