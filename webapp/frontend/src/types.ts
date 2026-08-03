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

export interface MajorDetail {
  code: string
  name: string
  category: string
  discipline: string
  hot_profile: HotProfile | null
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
}

export interface SchoolDetail {
  code: string
  name: string
  profile: SchoolProfile | null
  city: CityProfile | null
  yearly_summary: YearlySummary[]
  majors: SchoolMajorBrief[]
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
  rank_diff_last: number | null
  warning: string | null
  yearly: MatchYearly[]
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
}

export interface MatchResponse {
  data_version: string | null
  examinee: MatchExaminee
  totals: MatchTotals
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
  error?: string
}

export interface ExamineeProfile {
  year: number
  category: string
  subject: string
  batch: string
  score: number | null
  rank: number | null
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
  data_version: string | null
  examinee_rank: number | null
  saved_at: string
}

export interface PlanEntry extends CandidateSnapshot {
  note: string
}

export interface VolunteerPlan {
  id: string
  name: string
  note: string
  created_at: string
  data_version: string | null
  examinee: ExamineeProfile
  entries: PlanEntry[]
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
