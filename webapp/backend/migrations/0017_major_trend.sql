-- 0017 专业冷热趋势（2024–2026）预计算表
-- 执行方式：以 gaokao 拥有者角色运行（须在 0016 之后）
--   psql -U gaokao -h localhost -d gaokao -f 0017_major_trend.sql
--
-- 背景：
--   研究结论见 docs/major-trend-2024-2026.md。核心事实是「门槛的年际移动不都是
--   无方向的波动」——本科批 320 个可判定专业中 61 个（19%）两年连续同向，
--   临床医学两年相对全省松动 41.9%。而匹配算法把「历史最难年」当保守锚点，
--   对这类专业系统性失真。本表把趋势结论落库，供匹配页/专业页解释与提示。
--
-- 设计决策：
--   - 与 0015/0016 同套路：口径固定、一年只在年度投档入库时变一次，属预计算场景；
--     置换检验要跑 2 万次重抽样，绝不能放在读路径上。
--   - 拆三张表而非一张宽表，各自解决一个问题：
--       major_trend         专业层结论（分析口径，键 = 学科类×批次×归一专业）
--       major_trend_alias   招生专业名 → 归一专业（让后端零归一化逻辑，见下）
--       major_trend_context 社会背景解读（人工撰写，强制标注来源与日期）
--   - alias 表的存在理由：本科批走 major_name_map→major_catalog、专科批走去括号
--     原始名，这套归一规则只写在 etl/major_trend_core.py 一处。若让后端自己再实现
--     一遍，Python 与 ETL 两处必然漂移。后端直接按招生专业名精确匹配即可。
--   - 趋势键带 subject：docs §3.4 已证明法学/会计学/金融学在物理类与历史类结论相反，
--     跨学科类合并会得出错误结论，故不做合并。

BEGIN;

-- ---------- 1) 专业层结论 ----------
CREATE TABLE IF NOT EXISTS major_trend (
  subject         TEXT NOT NULL,          -- 物理学科类 / 历史学科类
  batch           TEXT NOT NULL,          -- 本科批 / 专科批
  major_key       TEXT NOT NULL,          -- 归一专业名（本科=标准专业目录名，专科=去括号招生名）
  label           TEXT NOT NULL           -- 内部标签，前端文案映射见 major_trend_core.LABEL_DISPLAY
                    CHECK (label IN ('持续降温','持续升温','趋势（内部分化）',
                                     '单年跳变','震荡/大小年','平稳','样本不足')),
  label_reason    TEXT,                   -- 判定依据一句话（可直接展示）
  n_pairs_1       INTEGER,                -- 2024→2025 段配对单元数
  excess_1        NUMERIC(10,5),          -- 2024→2025 段超额漂移（对数，正=相对全省变松）
  thr_1           NUMERIC(10,5),          -- 该 n 下的置换阈值 T(n)
  sig_1           BOOLEAN,                -- |excess_1| > thr_1
  concord_1       NUMERIC(5,3),           -- 单元同向率
  n_pairs_2       INTEGER,                -- 2025→2026 段，下同
  excess_2        NUMERIC(10,5),
  thr_2           NUMERIC(10,5),
  sig_2           BOOLEAN,
  concord_2       NUMERIC(5,3),
  excess_total    NUMERIC(10,5),          -- 两段合计
  units_2024      INTEGER NOT NULL DEFAULT 0,   -- 在辽招生单元数（招生计划缺失时的供给代理）
  units_2025      INTEGER NOT NULL DEFAULT 0,
  units_2026      INTEGER NOT NULL DEFAULT 0,
  tier_split      JSONB,                  -- 院校层次分化 {"985":{"n":16,"e":0.217}, ...}
  eq_score_delta       NUMERIC(6,1),      -- 等效分变化（2024→2026，2026 分数尺；负=门槛降了多少分）
  eq_score_delta_market NUMERIC(6,1),     -- 同期全省大盘等效分变化——必须与上一列并列展示
  built_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (subject, batch, major_key)
);

CREATE INDEX IF NOT EXISTS idx_major_trend_key ON major_trend(major_key);
CREATE INDEX IF NOT EXISTS idx_major_trend_label ON major_trend(label);

COMMENT ON TABLE major_trend IS
  '专业冷热趋势结论，由 etl/load_major_trend.py 全量重建；年度投档入库后须重跑';
COMMENT ON COLUMN major_trend.excess_1 IS
  '超额漂移＝该专业门槛百分位对数变动 减去 当年当格全省中位变动。正号=相对全省变松，'
  '与用户直觉相反，前端一律用 eq_score_delta 作一线数字，不要直接展示本列';
COMMENT ON COLUMN major_trend.units_2026 IS
  '招生单元数，供给代理。「平稳」标签必须与本列同屏展示：人工智能门槛平稳但供给 +67%（强需求'
  '吃下扩招），土木工程门槛平稳但供给 −28%（靠缩招撑住），只看标签会误导';

-- ---------- 2) 招生专业名 → 归一专业 ----------
CREATE TABLE IF NOT EXISTS major_trend_alias (
  subject        TEXT NOT NULL,
  batch          TEXT NOT NULL,
  admission_name TEXT NOT NULL,           -- admission_scores.major_name 原样
  major_key      TEXT NOT NULL,           -- 对应 major_trend.major_key
  PRIMARY KEY (subject, batch, admission_name)
);

CREATE INDEX IF NOT EXISTS idx_major_trend_alias_key
  ON major_trend_alias(subject, batch, major_key);

COMMENT ON TABLE major_trend_alias IS
  '招生专业名→归一专业映射，由 etl/load_major_trend.py 全量重建；'
  '存在的意义是让后端零归一化逻辑，避免 ETL 与服务端两处实现漂移';

-- ---------- 3) 社会背景解读（人工撰写） ----------
CREATE TABLE IF NOT EXISTS major_trend_context (
  major_key    TEXT NOT NULL,
  subject      TEXT NOT NULL DEFAULT '',  -- 空串 = 该专业两个学科类通用
  note         TEXT NOT NULL,             -- 一到两句背景，须是可核查的事实陈述
  source_name  TEXT NOT NULL,             -- 来源媒体/机构名
  source_url   TEXT NOT NULL,             -- 来源链接
  published_on DATE NOT NULL,             -- 来源发布日期
  curated_by   TEXT,                      -- 撰写人
  curated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (major_key, subject)
);

COMMENT ON TABLE major_trend_context IS
  '专业趋势的社会背景解读，人工撰写、非本站数据。source_name/source_url/published_on '
  '三列 NOT NULL 就是「强制标注来源」的技术保证——无来源则写不进来，前端也就不会渲染';

-- ---------- 4) 全省大盘漂移基准 ----------
CREATE TABLE IF NOT EXISTS major_trend_market (
  subject    TEXT NOT NULL,
  batch      TEXT NOT NULL,
  year_from  SMALLINT NOT NULL,
  year_to    SMALLINT NOT NULL,
  drift_log  NUMERIC(10,5) NOT NULL,   -- 该格子全部配对单元门槛百分位对数变动的中位数
  PRIMARY KEY (subject, batch, year_from, year_to)
);

COMMENT ON TABLE major_trend_market IS
  '全省大盘门槛漂移基准，由 etl/load_major_trend.py 全量重建。用途有二：'
  '① 专业级超额漂移就是「该专业变动 − 本表基准」；'
  '② 前端历年门槛曲线叠加的基准线——让用户一眼看出「是全省都这样，还是这个专业自己在动」';

-- ---------- 只读 Web 角色授权（模式同 0006/0011/0014/0015/0016）----------
GRANT SELECT ON major_trend TO gaokao_web_ro;
GRANT SELECT ON major_trend_alias TO gaokao_web_ro;
GRANT SELECT ON major_trend_context TO gaokao_web_ro;
GRANT SELECT ON major_trend_market TO gaokao_web_ro;

-- 补 0016_major_eval_map.sql 遗漏的授权：该文件建表后未授权只读角色，
-- 导致 major_catalog.get_major_eval5() 与 match 的 eval5 关联在 web 角色下取不到数据。
GRANT SELECT ON major_eval_map TO gaokao_web_ro;

COMMIT;
