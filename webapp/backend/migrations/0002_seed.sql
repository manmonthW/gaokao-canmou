-- Phase 0 数据可信化：固化质量与发布状态
-- 执行方式：以 gaokao 拥有者角色运行（须在 0001 之后）
--   PGPASSWORD=gaokao123 psql -U gaokao -h localhost -d gaokao -f 0002_seed.sql

-- 1) 固化一个已发布的数据版本
INSERT INTO data_releases
  (version, data_as_of, covered_years, covered_categories, covered_batches,
   status, publisher, published_at, quality_summary)
VALUES
  ('2026.1', now(), ARRAY[2025,2026],
   ARRAY['普通类','艺术类','体育类'],
   ARRAY['本科批','专科批','提前批','本科提前批A段','本科提前批B段'],
   'published', 'etl', now(),
   '辽宁 2025–2026 录取数据；位次回填 37173/37743（约 98.5%）；'
   '常规/征集已隔离；2026 普通类专科批（物理/历史）尚未入库，标记待发布。')
ON CONFLICT (version) DO NOTHING;

-- 2) 按现有录取数据生成“已完成”批次发布状态
INSERT INTO admission_publication_status
  (year, category, subject, batch, stage, status, system_updated_at)
SELECT DISTINCT year, category, subject, batch,
       CASE WHEN is_collection THEN '征集' ELSE '常规' END,
       '已完成', now()
FROM admission_scores
ON CONFLICT (year, category, subject, batch, stage) DO NOTHING;

-- 3) 明确标记 2026 普通类专科批（常规）尚未发布/入库
--    当前 admission_scores 中 2026 普通类专科批无记录，应显示为“待发布”而非零结果。
INSERT INTO admission_publication_status
  (year, category, subject, batch, stage, status, note, system_updated_at)
VALUES
  (2026,'普通类','物理学科类','专科批','常规','待发布',
   '2026 录取周期尚未完整发布或入库', now()),
  (2026,'普通类','历史学科类','专科批','常规','待发布',
   '2026 录取周期尚未完整发布或入库', now())
ON CONFLICT (year, category, subject, batch, stage)
  DO UPDATE SET status = EXCLUDED.status,
                note   = EXCLUDED.note,
                system_updated_at = now();
