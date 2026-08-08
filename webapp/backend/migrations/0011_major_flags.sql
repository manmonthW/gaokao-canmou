-- 0011 专业级报考标记（D2a）：中外合作/定向/预科/民族班/异地校区
-- 执行方式：以 gaokao 拥有者角色运行（须在 0010 之后）
--   psql -U gaokao -h localhost -d gaokao -f 0011_major_flags.sql
--
-- 设计说明（docs/first-principles-review.md 建议 D2a）：
--   - 标记挂在录取记录行（admission_scores.flags），因为「是否中外合作/定向」
--     是专业（招生条目）级属性，不是院校级；匹配按单元聚合时取两年并集。
--   - 标记由 etl/load_major_flags.py 基于关键词规则幂等重算，
--     规则迭代后可全量刷新，不依赖增量状态。
--   - 「高收费」暂不入表：缺少学费数据支撑，避免无依据打标（见 D2b 备注）。

BEGIN;

ALTER TABLE admission_scores
  ADD COLUMN IF NOT EXISTS flags TEXT[] NOT NULL DEFAULT '{}';

-- GIN 索引：支持 flags && ARRAY[...] / @> 过滤
CREATE INDEX IF NOT EXISTS idx_scores_flags ON admission_scores USING GIN (flags);

-- 标记词表：前端筛选与文案的统一来源
CREATE TABLE IF NOT EXISTS flag_dictionary (
  flag       TEXT PRIMARY KEY,
  label      TEXT NOT NULL,
  severity   TEXT NOT NULL DEFAULT 'notice'
               CHECK (severity IN ('notice', 'warn', 'block')),
  note       TEXT
);

INSERT INTO flag_dictionary (flag, label, severity, note) VALUES
  ('中外合作',   '中外合作办学', 'warn', '学费通常显著高于普通专业，录取规则与培养模式特殊，报考前请确认费用与毕业要求'),
  ('少数民族预科', '少数民族预科', 'warn', '仅面向符合少数民族预科报考条件的考生，培养年限与转入规则特殊'),
  ('定向',       '定向就业',     'warn', '录取后通常需签订定向就业协议，毕业去向受限，报考前请确认协议内容'),
  ('民族班',     '民族班',       'warn', '面向特定民族考生招生，报考条件特殊'),
  ('异地校区',   '异地校区',     'notice', '培养地点与校本部不同，请确认校区所在城市与办学安排')
ON CONFLICT (flag) DO UPDATE
  SET label = EXCLUDED.label,
      severity = EXCLUDED.severity,
      note = EXCLUDED.note;

-- 只读 Web 角色授权（沿用 0003 模式）
GRANT SELECT ON flag_dictionary TO gaokao_web_ro;

COMMIT;
