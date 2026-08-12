// 全站共享类型：后端响应结构（与 webapp/backend/app 各 service 返回对齐）

export interface ReleaseInfo {
  version: string
  data_as_of: string
  covered_years: number[]
  covered_categories: string[]
  covered_batches: string[]
  status: string
  publisher?: string | null
  published_at?: string | null
  quality_summary?: string | null
}

export interface PendingBatch {
  year: number
  category: string
  subject: string
  batch: string
  stage: string
  status: string
  note?: string | null
}

export interface CoverageRow {
  year: number
  category: string
  count: number
}

export interface DataStatusResponse {
  release: ReleaseInfo | null
  pending_batches: PendingBatch[]
  coverage: CoverageRow[]
}

export interface MetaResponse {
  years: number[]
  /** 考生年（最新数据年+1），前端 EXAMINEE_YEAR 常量仅兜底 */
  examinee_year?: number
  /** 最新数据年（如 2026） */
  last_year?: number
  /** 全部历史数据年（同 years，语义别名） */
  history_years?: number[]
  categories: string[]
  subjects: string[]
  batches: string[]
  batches_by_category: Record<string, string[]>
  score_kinds: string[]
  provinces: string[]
  levels: string[]
  natures: string[]
  types: string[]
  flags: string[]
  major_flags: MajorFlagDef[]
  /** 院校/专业实力标签词表（任务 #9，migration 0014）；旧后端无此键时为 undefined */
  strength_dictionary?: StrengthTagDef[]
}

/** 专业级报考标记词表（D2a）：后端 flag_dictionary */
export interface MajorFlagDef {
  flag: string
  label: string
  severity: 'notice' | 'warn' | 'block'
  note: string | null
}

/** 实力标签词表（任务 #9）：后端 strength_dictionary，标签文案与来源口径说明的唯一权威来源 */
export interface StrengthTagDef {
  tag: string
  label: string
  /** 分类：eval4 四轮学科评估 / eval5 五轮学科评估（非官方汇总） / dfc2022 双一流学科 / swyc 一流专业 / ruanke 软科（第三方） / meta 聚合类 */
  kind: string
  third_party: boolean
  source_note: string | null
  display_order: number
}

/** 专业实力条目（任务 #9）：source ∈ swyc_national / swyc_provincial / ruanke */
export interface MajorStrengthItem {
  major_name: string
  source: string
  /** 第三方评级档位（如 A+/B+）；官方名单为 null */
  tier: string | null
  data_year: number | null
}

// ------------------------------ 定位服务 ------------------------------

export interface ScoreToRank {
  found: boolean
  score?: number
  rank?: number
  rank_range?: [number, number]
  same_score_count?: number
  is_top_bucket?: boolean
  total_candidates?: number
  percentile?: number | null
  source?: string
  rank_upper?: number
  note?: string
  below_table?: boolean
  error?: string
}

export interface RankToScore {
  found: boolean
  score?: number
  score_note?: string
  is_top_bucket?: boolean
  rank?: number
  count_in_bucket?: number
  total_candidates?: number
  source?: string
  below_table?: boolean
  note?: string
  error?: string
}

export interface CrossYearItem {
  year: number
  score: number
  score_note?: string
}

// 位次锚点定位（面向未来考生，无 year）
export interface RankEquivalent {
  year: number
  score: number | null
  score_note?: string
  note?: string
  below_table?: boolean
}

export interface RankLineRef {
  year: number
  line_type: string
  line_score: number
  line_rank: number
  passed_ref: boolean
  margin: number
}

export interface RankContext {
  category: string
  subject: string
  batch: string | null
  rank: number
  reference_years: number[]
  equivalents: RankEquivalent[]
  line_refs: RankLineRef[]
  note: string | null
  error?: string
}

export interface LineJudgement {
  primary: { line_type: string; line: number; passed: boolean; gap: number }
  special_type?: { line: number; passed: boolean; gap: number }
  note?: string
  error?: string
}

export interface LocateSummary {
  year: number
  category: string
  subject: string
  by_score?: ScoreToRank
  by_rank?: RankToScore
  cross_year?: CrossYearItem[]
  line?: LineJudgement
  error?: string
}

// ------------------------------ 搜索/详情 ------------------------------

export interface SchoolSummary {
  code: string
  name: string
  province: string | null
  city: string | null
  level: string | null
  nature: string | null
  type: string | null
  is_985: boolean | null
  is_211: boolean | null
  is_dfc: boolean | null
  postgrad_rate: number | null   // 保研率（%，最新年口径）；null=无资格/缺失
}

export interface MajorSearchItem {
  major_name: string
  school_count: number
  lowest_score_range: [number | null, number | null]
  lowest_rank_range: [number | null, number | null]
  record_count: number
}

export interface CatalogDiscipline {
  discipline: string
  count: number
}

export interface CatalogCategory {
  category: string
  discipline: string
  count: number
}

export interface MajorCatalogItem {
  code: string
  name: string
  category: string
  discipline: string
  school_count: number
  lowest_score_range: [number | null, number | null]
  lowest_rank_range: [number | null, number | null]
  has_admission: boolean
}

export interface HotProfile {
  degree: string | null
  length: number | null
  gender_ratio: string | null
  introduction: string | null
  subject_req: string | null
  career: string | null
  training_goal: string | null
  discipline_req: string | null
  main_courses: string | null
  postgrad_dir: string | null
  employment_dir: string | null
  hot_schools: string[]
  image_path: string | null
  has_image: boolean
}

export interface MajorEval5 {
  discipline: string | null
  grades: Record<string, string[]>
}

export interface MajorDetail {
  code: string
  name: string
  category: string
  discipline: string
  hot_profile: HotProfile | null
  eval5: MajorEval5
}

export interface CityProfile {
  city: string
  province: string
  region: string | null
  tier: string | null
  gdp: number | null
  gdp_year: number | null
  cluster: string | null
  coastal: boolean | null
  note: string | null
}

export interface YearlySummary {
  year: number
  category: string
  subject: string
  records: number
  major_count: number
  lowest_score_range: [number | null, number | null]
  lowest_rank_range: [number | null, number | null]
}

export interface SchoolMajorBrief {
  major_name: string
  major_code: string | null
  years: number
  last_year: number
  records: number
}

export interface SchoolProfile {
  province: string | null
  city: string | null
  affiliation: string | null
  level: string | null
  nature: string | null
  type: string | null
  is_985: boolean | null
  is_211: boolean | null
  is_dfc: boolean | null
  established: number | null
  strength: string | null
  school_style: string | null
  employment_region: string | null
  rank_ref: string | null
  note: string | null
  website: string | null
  intro: string | null
  postgrad_rate: number | null   // 保研率（%，最新年口径）；null=无资格/缺失
}

/** 学科评估/一流学科记录（任务 #9）：source ∈ eval4_official / eval5_a / dfc2022 */
export interface StrengthDiscipline {
  school_code?: string | null
  discipline_name: string
  source: string
  data_year: number | null
  /** 评级（如 A+/A/A-）；双一流名单无评级为 null */
  grade: string | null
  official: boolean
  verify_status: string | null
}

/** 专业实力记录（任务 #9）：source ∈ swyc_national / swyc_provincial / ruanke */
export interface StrengthMajor {
  school_name?: string | null
  major_name: string
  major_code: string | null
  source: string
  data_year: number | null
  /** 入选批次（双万计划 2019-2021 三批；排名类为 null） */
  batch: number | null
  /** 第三方排名名次；官方名单为 null */
  rank: number | null
  /** 第三方评级档位；官方名单为 null */
  tier: string | null
  note: string | null
}

/** 院校学科实力聚合（任务 #9）：GET /schools/{code} 附加字段 与 GET /schools/{code}/strength */
export interface SchoolStrength {
  disciplines: StrengthDiscipline[]
  majors: StrengthMajor[]
  strength_tags: string[]
}

export interface SchoolDetail {
  code: string
  name: string
  profile: SchoolProfile | null
  city: CityProfile | null
  yearly_summary: YearlySummary[]
  majors: SchoolMajorBrief[]
  /** 学科实力聚合（任务 #9）；旧后端无此键时为 undefined，空数据时各列表为空数组 */
  strength?: SchoolStrength
}

export interface SchoolMajorRecord {
  year: number
  category: string
  subject: string
  batch: string
  is_collection: boolean
  score_kind: string | null
  lowest_score: number | null
  lowest_rank: number | null
  tiebreak_1: number | null
  source_file: string | null
  source_note: string | null
  source_status: string | null
}

// ------------------------------ 数据中心 ------------------------------

export interface ControlLine {
  year: number
  category: string
  subject: string
  line_type: string
  score: number
  note: string | null
}

export interface ScoreRankRow {
  score: number
  count: number
  cumulative_rank: number
  is_top_bucket: boolean
  source: string
}

export interface PagedScoreRank {
  total: number
  page: number
  page_size: number
  items: ScoreRankRow[]
}

export interface AdmissionRecord {
  year: number
  category: string
  subject: string
  batch: string
  is_collection: boolean
  score_kind: string | null
  school_code: string
  school_name: string
  major_code: string | null
  major_name: string
  lowest_score: number | null
  lowest_rank: number | null
  src_id: number | null
}

export interface PagedRecords {
  total: number
  page: number
  page_size: number
  items: AdmissionRecord[]
}

export interface SourceFile {
  id: number
  filename: string
  fmt: string | null
  year: number | null
  category: string | null
  batch: string | null
  is_collection: boolean | null
  subject: string | null
  status: string | null
  note: string | null
  loaded_at: string | null
}

export interface PublicationStatus {
  year: number
  category: string
  subject: string | null
  batch: string
  stage: string
  status: string
  official_published_at: string | null
  system_updated_at: string | null
  source_url: string | null
  note: string | null
}

// ------------------------------ 往年征集参考（P6） ------------------------------

export interface CollectionItem {
  year: number
  batch: string
  school_name: string
  major_name: string | null
  score_kind: string | null
  lowest_score: number | null
  lowest_rank: number | null
}

export interface CollectionReference {
  category: string
  subject: string | null
  batch: string | null
  rank: number | null
  band: { lo: number; hi: number } | null
  items: CollectionItem[]
  note: string
}

// ------------------------------ 选科要求三表（D2b / 数据中心） ------------------------------

/** 表类型：bk 本科 / zk 专科 / jx 军校 */
export type XkTable = 'bk' | 'zk' | 'jx'

export interface SubjectReqSummaryItem {
  year: number
  table: XkTable
  filename: string
  rows: number
  schools: number
}

export interface SubjectReqSummary {
  items: SubjectReqSummaryItem[]
  note: string
}

export interface SubjectReqItem {
  year: number
  table: XkTable | null
  school_code: string | null
  school_name: string
  major_code: string | null
  major_name: string | null
  group_code: string | null
  first_req: string | null
  re_req: string | null
}

export interface PagedSubjectReqs {
  total: number
  page: number
  page_size: number
  items: SubjectReqItem[]
}

// ------------------------------ 报考说明（官方招考文件） ------------------------------

export interface GuideItem {
  id: string
  title: string
  filename: string
  summary: string
  points: string[]
  tag: string
  size_bytes: number | null
  available: boolean
}

export interface GuideGroup {
  key: string
  title: string
  desc: string
  items: GuideItem[]
}

export interface GuidesResponse {
  groups: GuideGroup[]
  total: number
  note: string
}

// ------------------------------ 选科组合专业覆盖率（定位页联动） ------------------------------

export interface SubjectCombo {
  id: string
  first: string          // 首选：物理 / 历史
  electives: string[]    // 再选两门（排序后）
  coverage: number       // 专业覆盖率（%，全国通用参考值）
  image: string
  available: boolean
}

export interface SubjectCombosResponse {
  items: SubjectCombo[]
  overview_image: string
  overview_available: boolean
  note: string
}

// ------------------------------ 智能匹配（Phase 2） ------------------------------

export type RiskLabel = '保' | '稳' | '冲' | '高波动' | '数据不足'

export interface MatchYearly {
  year: number
  lowest_rank: number
}

export interface MatchCandidate {
  school_code: string
  school_name: string
  major_code: string | null
  major_name: string | null
  catalog_name: string | null
  batch: string
  province: string | null
  city: string | null
  level: string | null
  nature: string | null
  type: string | null
  /** 院校牌子标签：true 时前端在院校名后展示 985/211 徽章 */
  is_985?: boolean | null
  is_211?: boolean | null
  n_years: number
  has_both_years: boolean
  best_rank: number
  worst_rank: number
  median_rank: number
  last_year: number
  last_year_rank: number | null
  last_year_score: number | null
  span: number
  relative_vol: number | null
  continuous: boolean
  break_detected: boolean
  risk: RiskLabel
  risk_reason: string
  /** P1 区间模式：乐观情景（位次下界）分档与依据 */
  risk_lo?: RiskLabel | null
  risk_reason_lo?: string | null
  /** 保档安全边际线 = 最难年门槛 × safe_margin（A1，回测固化） */
  safe_line: number | null
  /** 过深保底：门槛 > 考生位次×3，保护已饱和，不增加安全性只消耗槽位 */
  over_safe?: boolean
  /** 超冲：历史门槛好于考生位次超过 20%，基本只消耗槽位 */
  over_reach?: boolean
  /** 保档子档：标准保底 / 极稳垫底 / 过深保底 */
  safe_band?: '标准保底' | '极稳垫底' | '过深保底' | null
  rank_diff_last: number | null
  warning: string | null
  flags: string[]
  subject_unverified?: boolean
  /** 2027 官方选科要求展示串（再选原文/首选），无要求为 null */
  subject_req?: string | null
  /** 选科匹配层级：exact 精确 / norm 归一 / base 基础名 / enum 枚举反查 / school 院校级 */
  subject_match_level?: 'exact' | 'norm' | 'base' | 'enum' | 'school' | null
  /** 未收录拆分：major_missing 专业未收录（学校在表）/ school_missing 院校未收录 */
  subject_status?: 'major_missing' | 'school_missing'
  yearly: MatchYearly[]
  /** 院校级实力标签（任务 #9，值域=strength_dictionary.tag）；空数组=暂无收录 */
  strength_tags?: string[]
  /** 专业实力（任务 #9）：国/省一流专业、软科评级等；空数组=暂无收录 */
  major_strength?: MajorStrengthItem[]
}

export interface MatchFacetItem {
  value: string
  count: number
}

export interface MatchTotals {
  total: number
  保: number
  稳: number
  冲: number
  高波动: number
  数据不足: number
}

export interface MatchExaminee {
  year: number
  category: string
  subject: string
  batch: string
  score: number | null
  rank: number | null
  electives?: string[] | null
}

/** 批次发布状态上下文（D4）：告诉用户本批数据的口径与发布进度 */
export interface BatchContext {
  batch: string
  score_kind: string
  score_kind_note: string
  publication: {
    year: number
    stage: string
    status: string
    note: string | null
    official_published_at: string | null
  }[]
  warning?: string
}

export interface MatchResponse {
  data_version: string | null
  examinee: MatchExaminee
  totals: MatchTotals
  /** P1 区间模式：乐观情景分档计数（主 totals 为悲观上界） */
  totals_lo?: MatchTotals | null
  interval?: { lo: number; hi: number } | null
  facets: {
    province: MatchFacetItem[]
    city: MatchFacetItem[]
    level: MatchFacetItem[]
    nature: MatchFacetItem[]
    type: MatchFacetItem[]
  }
  page: number
  page_size: number
  items: MatchCandidate[]
  batch_context?: BatchContext
  classification_note?: ClassificationNote
  excluded_by_subject?: number
  /** 首选不符排除数（无条件生效） */
  excluded_first?: number
  /** 再选不符排除数（填了再选才生效） */
  excluded_re?: number
  subject_requirements_loaded?: boolean
  error?: string
}

/** 分档可信度说明（A2）：向用户公开分档方法与回测依据 */
export interface ClassificationNote {
  method: string
  safe_margin: number
  backtest: {
    pair: string
    margin_coverage: string
    rel_delta: string
  }
  disclaimer: string
}

/** 位次敏感度试算响应（A3） */
export interface SensitivityResponse {
  examinee: MatchExaminee
  excluded_by_subject: number
  excluded_first?: number
  excluded_re?: number
  subject_requirements_loaded: boolean
  scenarios: {
    label: string
    offset: number
    rank: number
    totals: MatchTotals
  }[]
  note: string
  error?: string
}

/** 工作台快照刷新响应（「刷新到最新数据」：年度接入后旧方案补新年数据） */
export interface RefreshSnapshotsResponse {
  data_version: string | null
  items: MatchCandidate[]
  error?: string
}

/** P1 线差法估位响应（备考期） */
export interface EstimateRankResponse {
  category: string
  subject: string
  batch: string
  score: number
  mock_line: number
  line_diff: number
  line_type: string
  per_year: {
    year: number
    line: number
    est_score: number
    rank?: number
    rank_range?: [number, number]
    note?: string
  }[]
  suggested_interval: { lo: number; hi: number } | null
  note: string
  error?: string
}

export interface ExamineeProfile {
  year: number
  category: string
  subject: string
  batch: string
  score: number | null
  rank: number | null
  /** 再选科目（D2b，可选）：如 ['化学','生物']；2027 选科要求入库后参与资格校验 */
  electives?: string[]
  /** P1 备考期：exact=精确位次；interval=估计位次区间 */
  rank_mode?: 'exact' | 'interval'
  rank_lo?: number | null
  rank_hi?: number | null
  /** P5 偏好最小版：同档内排序依据 */
  pref_sort?: 'certainty' | 'level' | 'city' | 'major'
  /** P5 偏好最小版：不能接受高学费（中外合作等代理标记） */
  tuition_cap?: boolean
}

// ------------------------------ 认证 ------------------------------

export interface AuthUser {
  id: number
  email: string
  username: string
}

export interface AuthResult {
  token: string
  user: AuthUser
}

// ------------------------------ 决策工作台（Phase 3） ------------------------------

/** 候选快照：收藏 / 对比 / 方案条目共用（创建时冻结数据版本与风险） */
export interface CandidateSnapshot {
  id: string // school_code|major_key|batch
  risk: RiskLabel
  risk_reason: string
  school_code: string
  school_name: string
  major_code: string | null
  major_name: string | null
  catalog_name: string | null
  batch: string
  province: string | null
  city: string | null
  level: string | null
  nature: string | null
  type: string | null
  n_years: number
  best_rank: number | null
  worst_rank: number | null
  median_rank: number | null
  span: number | null
  relative_vol: number | null
  last_year: number
  last_year_rank: number | null
  last_year_score: number | null
  rank_diff_last: number | null
  yearly: MatchYearly[]
  flags?: string[]
  over_safe?: boolean
  over_reach?: boolean
  safe_band?: '标准保底' | '极稳垫底' | '过深保底' | null
  data_version: string | null
  examinee_rank: number | null
  saved_at: string
}

export interface PlanEntry extends CandidateSnapshot {
  note: string
}

export type PlanStrategy = '冲击' | '均衡' | '稳妥'

export interface VolunteerPlan {
  id: string
  name: string
  note: string
  created_at: string
  data_version: string | null
  examinee: ExamineeProfile
  entries: PlanEntry[]
  /** 冲稳保配比基线（体检与模板用）：冲击 36/29/35、均衡 20/50/30、稳妥 10/55/35 */
  strategy?: PlanStrategy
}

// ---- 热门大学介绍（每日一校卡片）----
export interface HotSchoolCategory {
  category: string
  count: number
}

export interface HotSchool {
  code: string | null
  name: string
  categories: string[]
  established: number | null
  location: string | null
  nature: string | null
  school_type: string | null
  upgrade_rate: string | null
  grad_recommend_rate: string | null
  master_points: number | null
  doctor_points: number | null
  ranking: string | null
  ranking_items: { source: string; rank: number | null; year: string | null }[]
  intro: string | null
  discipline_eval: string | null
  features: string | null
  honors: string | null
  faculty: string | null
  has_image: boolean
}

// ------------------------------ 发布状态矩阵（D4） ------------------------------
export interface MatrixRow {
  year: number
  category: string
  subject: string
  batch: string
  stage: string
  status: string
  note: string | null
  official_published_at: string | null
  records: number
  gap: boolean
}

export interface DataStatusMatrix {
  matrix: MatrixRow[]
  unregistered: { year: number; category: string; subject: string; batch: string; records: number }[]
}
