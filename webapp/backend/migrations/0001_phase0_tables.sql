-- Phase 0 数据可信化：发布版本 + 批次发布状态
-- 执行方式：以 gaokao 拥有者角色运行
--   PGPASSWORD=gaokao123 psql -U gaokao -h localhost -d gaokao -f 0001_phase0_tables.sql

-- 1) 数据发布版本：网站只读经过审核的稳定版本
CREATE TABLE IF NOT EXISTS data_releases (
  id               BIGSERIAL PRIMARY KEY,
  version          TEXT UNIQUE NOT NULL,
  data_as_of       TIMESTAMPTZ NOT NULL DEFAULT now(),
  covered_years    SMALLINT[] NOT NULL DEFAULT '{}',
  covered_categories TEXT[] NOT NULL DEFAULT '{}',
  covered_batches  TEXT[] NOT NULL DEFAULT '{}',
  status           TEXT NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft','validating','published','rolled_back')),
  publisher        TEXT,
  published_at     TIMESTAMPTZ,
  quality_summary  TEXT
);
CREATE INDEX IF NOT EXISTS idx_releases_status ON data_releases(status);

-- 2) 批次发布状态：区分“没有数据”与“尚未发布”
CREATE TABLE IF NOT EXISTS admission_publication_status (
  id                   BIGSERIAL PRIMARY KEY,
  year                 SMALLINT NOT NULL,
  category             TEXT NOT NULL,
  subject              TEXT NOT NULL,
  batch                TEXT NOT NULL,
  stage                TEXT NOT NULL DEFAULT '常规'
                         CHECK (stage IN ('常规','征集')),
  status               TEXT NOT NULL
                         CHECK (status IN ('待发布','部分发布','已完成','已关闭')),
  official_published_at TIMESTAMPTZ,
  system_updated_at    TIMESTAMPTZ DEFAULT now(),
  source_url           TEXT,
  note                 TEXT,
  UNIQUE (year, category, subject, batch, stage)
);
CREATE INDEX IF NOT EXISTS idx_pub_status_year ON admission_publication_status(year);
CREATE INDEX IF NOT EXISTS idx_pub_status_lookup
  ON admission_publication_status(year, category, subject, batch, stage);
