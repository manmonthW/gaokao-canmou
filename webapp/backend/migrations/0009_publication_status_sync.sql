-- 0009 批次发布状态与实际数据重新同步
-- 执行方式：以 gaokao 拥有者角色运行（须在既有迁移之后）
--   PGPASSWORD=gaokao123 psql -U gaokao -h localhost -d gaokao -f 0009_publication_status_sync.sql
--
-- 背景：0002_seed.sql 用 SELECT DISTINCT ... FROM admission_scores 生成发布状态，
--   但 load_2026_supplement.py 之后才灌入艺术/体育专科批与专科提前批等补充数据，
--   且该脚本历史上不维护 admission_publication_status，导致状态表停留在补充数据
--   入库前的快照，出现两类不一致：
--     (a) 遗漏：2026 体育类·历史学科类·专科批（征集）实际有 4 行数据，但状态表无此条；
--     (b) stage 缺失：艺术/体育专科批实际含"征集"行(is_collection=true)，
--         但状态表只登记了"常规"。
--
-- 本迁移：以当前 admission_scores 为准，把"实际已有数据"的组合补齐为"已完成"，
--   不覆盖人工标注的"待发布/已关闭"等非"已完成"状态（如 2026 普通类专科批待发布）。

BEGIN;

-- 对每个实际存在数据的 (year,category,subject,batch,stage) 组合，
-- 若状态表无记录则插入"已完成"；若已存在且当前为"已完成"则刷新时间；
-- 若已存在且为人工标注的其他状态（待发布/部分发布/已关闭），保持不变。
INSERT INTO admission_publication_status
  (year, category, subject, batch, stage, status, system_updated_at)
SELECT DISTINCT year, category, subject, batch,
       CASE WHEN is_collection THEN '征集' ELSE '常规' END AS stage,
       '已完成', now()
FROM admission_scores
ON CONFLICT (year, category, subject, batch, stage)
DO UPDATE SET
  -- 仅当既有状态本就是"已完成"时刷新时间戳；其他人工状态不动
  status = CASE
             WHEN admission_publication_status.status = '已完成' THEN '已完成'
             ELSE admission_publication_status.status
           END,
  system_updated_at = CASE
             WHEN admission_publication_status.status = '已完成' THEN now()
             ELSE admission_publication_status.system_updated_at
           END;

COMMIT;
