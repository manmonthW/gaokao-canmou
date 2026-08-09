// API 基址：默认走 vite 代理的相对路径；可用 VITE_API_BASE 覆盖为完整 origin（如 http://127.0.0.1:8000）
const ORIGIN = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')
const PREFIX = '/api/v1'

// 当前登录 token（由 useAuth 设置/清除）。放在模块级，getJson 自动带上。
let _token: string | null = null
export function setAuthToken(t: string | null) {
  _token = t
}
function authHeaders(): Record<string, string> {
  return _token ? { Authorization: `Bearer ${_token}` } : {}
}

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${ORIGIN}${PREFIX}${path}`, { headers: authHeaders() })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`请求 ${path} 失败：HTTP ${res.status}${body ? ' ' + body.slice(0, 120) : ''}`)
  }
  return (await res.json()) as T
}

async function sendJson<T>(method: string, path: string, payload: unknown): Promise<T> {
  const res = await fetch(`${ORIGIN}${PREFIX}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const j = await res.json()
      if (j?.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch {
      /* ignore */
    }
    throw new Error(msg)
  }
  return (await res.json()) as T
}

export function buildQuery(params: Record<string, unknown>): string {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    usp.append(k, String(v))
  }
  const s = usp.toString()
  return s ? '?' + s : ''
}

import type {
  DataStatusResponse,
  EstimateRankResponse,
  MetaResponse,
  LocateSummary,
  SchoolSummary,
  MajorSearchItem,
  CatalogDiscipline,
  CatalogCategory,
  MajorCatalogItem,
  MajorDetail,
  SchoolDetail,
  SchoolMajorRecord,
  ControlLine,
  PagedScoreRank,
  PagedRecords,
  SourceFile,
  PublicationStatus,
  CollectionReference,
  SubjectReqSummary,
  PagedSubjectReqs,
  GuidesResponse,
  MatchResponse,
  SensitivityResponse,
  RankContext,
  AuthUser,
  AuthResult,
  HotSchoolCategory,
  HotSchool,
  DataStatusMatrix,
} from '@/types'

export const api = {
  dataStatus: () => getJson<DataStatusResponse>('/data-status'),
  dataStatusMatrix: () => getJson<DataStatusMatrix>('/data-status/matrix'),
  meta: () => getJson<MetaResponse>('/meta'),
  locateSummary: (p: Record<string, unknown>) =>
    getJson<LocateSummary>(`/locate/summary${buildQuery(p)}`),
  rankContext: (p: Record<string, unknown>) =>
    getJson<RankContext>(`/locate/rank-context${buildQuery(p)}`),
  estimateRank: (p: Record<string, unknown>) =>
    getJson<EstimateRankResponse>(`/locate/estimate-rank${buildQuery(p)}`),
  searchSchools: (q: string, limit = 20) =>
    getJson<SchoolSummary[]>(`/search/schools${buildQuery({ q, limit })}`),
  searchMajors: (p: Record<string, unknown>) =>
    getJson<MajorSearchItem[]>(`/search/majors${buildQuery(p)}`),
  // ---- 专业字典（标准专业浏览 + 在辽招生关联）----
  catalogDisciplines: () =>
    getJson<CatalogDiscipline[]>('/major-catalog/disciplines'),
  catalogCategories: (discipline?: string) =>
    getJson<CatalogCategory[]>(
      `/major-catalog/categories${buildQuery({ discipline: discipline || undefined })}`,
    ),
  catalogSearch: (p: Record<string, unknown>) =>
    getJson<MajorCatalogItem[]>(`/major-catalog/search${buildQuery(p)}`),
  catalogDetail: (name: string) =>
    getJson<MajorDetail>(`/major-catalog/detail${buildQuery({ name })}`),
  hotImageUrl: (name: string) =>
    `${ORIGIN}${PREFIX}/major-catalog/hot-image${buildQuery({ name })}`,
  school: (code: string) => getJson<SchoolDetail>(`/schools/${code}`),
  schoolMajor: (code: string, p: Record<string, unknown>) =>
    getJson<SchoolMajorRecord[]>(`/schools/${code}/major${buildQuery(p)}`),
  controlLines: (p: Record<string, unknown>) =>
    getJson<ControlLine[]>(`/datacenter/control-lines${buildQuery(p)}`),
  scoreRank: (p: Record<string, unknown>) =>
    getJson<PagedScoreRank>(`/datacenter/score-rank${buildQuery(p)}`),
  records: (p: Record<string, unknown>) =>
    getJson<PagedRecords>(`/datacenter/records${buildQuery(p)}`),
  sourceFiles: () => getJson<SourceFile[]>('/datacenter/source-files'),
  publicationStatus: () => getJson<PublicationStatus[]>('/datacenter/publication-status'),
  // P6 往年征集参考（最坏情况安全网，不参与智能匹配）
  collectionReference: (p: Record<string, unknown>) =>
    getJson<CollectionReference>(`/datacenter/collection-reference${buildQuery(p)}`),
  // 选科要求三表（官方 2027 选考科目要求）
  subjectReqSummary: () =>
    getJson<SubjectReqSummary>('/datacenter/subject-requirements/summary'),
  subjectReqs: (p: Record<string, unknown>) =>
    getJson<PagedSubjectReqs>(`/datacenter/subject-requirements${buildQuery(p)}`),
  // 报考说明（官方招考文件在线阅读）
  guides: () => getJson<GuidesResponse>('/guides'),
  guidePdfUrl: (id: string) => `${ORIGIN}${PREFIX}/guides/${encodeURIComponent(id)}/pdf`,
  match: (p: Record<string, unknown>) =>
    getJson<MatchResponse>(`/match${buildQuery(p)}`),
  matchSensitivity: (p: Record<string, unknown>) =>
    getJson<SensitivityResponse>(`/match/sensitivity${buildQuery(p)}`),
  // ---- 热门大学介绍 ----
  hotSchoolCategories: () =>
    getJson<{ categories: HotSchoolCategory[]; total: number }>('/hot-schools/categories'),
  hotSchools: (category?: string) =>
    getJson<{ schools: HotSchool[]; count: number }>(
      `/hot-schools${buildQuery({ category: category || undefined })}`,
    ),
  hotSchoolImageUrl: (name: string) =>
    `${ORIGIN}${PREFIX}/hot-schools/${encodeURIComponent(name)}/image`,
  // ---- 认证与用户数据 ----
  register: (payload: { email: string; username: string; password: string }) =>
    sendJson<AuthResult>('POST', '/auth/register', payload),
  login: (payload: { login: string; password: string }) =>
    sendJson<AuthResult>('POST', '/auth/login', payload),
  me: () => getJson<AuthUser>('/auth/me'),
  getUserData: () => getJson<{ data: Record<string, unknown> }>('/user/data'),
  putUserData: (data: Record<string, unknown>) =>
    sendJson<{ ok: boolean }>('PUT', '/user/data', { data }),
  // ---- P4 录取结果自愿回填（匿名可用） ----
  submitFeedback: (payload: Record<string, unknown>) =>
    sendJson<{ ok?: boolean; id?: number; error?: string }>('POST', '/feedback', payload),
  feedbackSummary: () =>
    getJson<{ total: number; by_outcome: Record<string, number>; by_admitted_risk: Record<string, number> }>('/feedback/summary'),
  /** 导出志愿方案 xlsx，返回 Blob */
  exportPlan: async (payload: unknown): Promise<Blob> => {
    const res = await fetch(`${ORIGIN}${PREFIX}/plan/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const body = await res.text().catch(() => '')
      throw new Error(`导出失败：HTTP ${res.status}${body ? ' ' + body.slice(0, 120) : ''}`)
    }
    return await res.blob()
  },
}
