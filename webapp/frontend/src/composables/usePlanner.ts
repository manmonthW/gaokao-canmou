import { ref, watch } from 'vue'
import type {
  CandidateSnapshot,
  ExamineeProfile,
  MatchCandidate,
  PlanEntry,
  VolunteerPlan,
} from '@/types'

/**
 * 决策工作台状态（Phase 3）：收藏 / 对比 / 多志愿方案。
 * MVP 匿名本地保存（spec §9.3）；快照在加入时冻结（数据版本 + 风险 + 本人位次），
 * 防止后续数据更新导致用户无法理解结果变化（spec §5.2.6）。
 */

const FAV_KEY = 'ln-zhiyuan-favorites'
const CMP_KEY = 'ln-zhiyuan-compare'
const PLAN_KEY = 'ln-zhiyuan-plans'

export const COMPARE_MAX = 5

function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

function persist(key: string, v: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(v))
  } catch {
    /* 隐私模式等写入失败忽略 */
  }
}

// ---- 全局单例状态 ----
const favorites = ref<CandidateSnapshot[]>(loadJson(FAV_KEY, []))
const compareIds = ref<string[]>(loadJson(CMP_KEY, []))
const plans = ref<VolunteerPlan[]>(loadJson(PLAN_KEY, []))

watch(favorites, (v) => { persist(FAV_KEY, v); notifyChange() }, { deep: true })
watch(compareIds, (v) => { persist(CMP_KEY, v); notifyChange() }, { deep: true })
watch(plans, (v) => { persist(PLAN_KEY, v); notifyChange() }, { deep: true })

// 云端数据恢复后（登录/启动），从 localStorage 重新载入内存态
if (typeof window !== 'undefined') {
  window.addEventListener('ln-userdata-restored', () => {
    favorites.value = loadJson(FAV_KEY, [])
    compareIds.value = loadJson(CMP_KEY, [])
    plans.value = loadJson(PLAN_KEY, [])
  })
  // 退出登录：清空收藏/对比/方案
  window.addEventListener('ln-userdata-cleared', () => {
    favorites.value = []
    compareIds.value = []
    plans.value = []
  })
}

// 惰性获取 scheduleSync（登录后本地变更防抖同步到服务端），避免循环依赖
let _scheduleSync: (() => void) | null = null
function notifyChange() {
  if (_scheduleSync) return _scheduleSync()
  import('./useAuth').then(({ useAuth }) => {
    _scheduleSync = useAuth().scheduleSync
    _scheduleSync()
  })
}

export function candidateId(c: { school_code: string; major_code: string | null; major_name: string | null; batch: string }): string {
  return `${c.school_code}|${c.major_code || c.major_name}|${c.batch}`
}

export function toSnapshot(
  c: MatchCandidate,
  dataVersion: string | null,
  examineeRank: number | null,
): CandidateSnapshot {
  return {
    id: candidateId(c),
    risk: c.risk,
    risk_reason: c.risk_reason,
    school_code: c.school_code,
    school_name: c.school_name,
    major_code: c.major_code,
    major_name: c.major_name,
    batch: c.batch,
    province: c.province,
    city: c.city,
    level: c.level,
    nature: c.nature,
    type: c.type,
    n_years: c.n_years,
    best_rank: c.best_rank,
    worst_rank: c.worst_rank,
    median_rank: c.median_rank,
    span: c.span,
    relative_vol: c.relative_vol,
    last_year: c.last_year,
    last_year_rank: c.last_year_rank,
    last_year_score: c.last_year_score ?? null,
    rank_diff_last: c.rank_diff_last,
    yearly: c.yearly,
    flags: c.flags ?? [],
    data_version: dataVersion,
    examinee_rank: examineeRank,
    saved_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
  }
}

function uid(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7)
}

export function usePlanner() {
  // ---------- 收藏 ----------
  function isFavorite(id: string) {
    return favorites.value.some((f) => f.id === id)
  }
  function addFavorite(snap: CandidateSnapshot) {
    if (!isFavorite(snap.id)) favorites.value.push(snap)
  }
  function removeFavorite(id: string) {
    favorites.value = favorites.value.filter((f) => f.id !== id)
    compareIds.value = compareIds.value.filter((c) => c !== id)
  }
  function toggleFavorite(snap: CandidateSnapshot) {
    isFavorite(snap.id) ? removeFavorite(snap.id) : addFavorite(snap)
  }

  // ---------- 对比（最多 COMPARE_MAX 项；加入对比自动收藏以保留快照） ----------
  function inCompare(id: string) {
    return compareIds.value.includes(id)
  }
  function toggleCompare(snap: CandidateSnapshot): string | null {
    if (inCompare(snap.id)) {
      compareIds.value = compareIds.value.filter((c) => c !== snap.id)
      return null
    }
    if (compareIds.value.length >= COMPARE_MAX) {
      return `对比最多 ${COMPARE_MAX} 项，请先移除一项`
    }
    addFavorite(snap)
    compareIds.value.push(snap.id)
    return null
  }
  function compareItems(): CandidateSnapshot[] {
    return compareIds.value
      .map((id) => favorites.value.find((f) => f.id === id))
      .filter((x): x is CandidateSnapshot => !!x)
  }
  function clearCompare() {
    compareIds.value = []
  }

  // ---------- 方案 ----------
  function createPlan(name: string, examinee: ExamineeProfile, dataVersion: string | null, note = ''): VolunteerPlan {
    const p: VolunteerPlan = {
      id: uid(),
      name: name || `方案 ${plans.value.length + 1}`,
      note,
      created_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
      data_version: dataVersion,
      examinee: { ...examinee },
      entries: [],
    }
    plans.value.push(p)
    return p
  }
  function removePlan(id: string) {
    plans.value = plans.value.filter((p) => p.id !== id)
  }
  function addToPlan(planId: string, snap: CandidateSnapshot): string | null {
    const p = plans.value.find((x) => x.id === planId)
    if (!p) return '方案不存在'
    if (p.entries.some((e) => e.id === snap.id)) return '该志愿已在方案中'
    p.entries.push({ ...snap, note: '' })
    return null
  }
  function removeFromPlan(planId: string, entryId: string) {
    const p = plans.value.find((x) => x.id === planId)
    if (p) p.entries = p.entries.filter((e) => e.id !== entryId)
  }
  function moveEntry(planId: string, index: number, dir: -1 | 1) {
    const p = plans.value.find((x) => x.id === planId)
    if (!p) return
    const j = index + dir
    if (j < 0 || j >= p.entries.length) return
    const arr = p.entries
    ;[arr[index], arr[j]] = [arr[j], arr[index]]
  }
  /** 按冲→稳→保→高波动→数据不足重排（梯度排序） */
  function sortPlanByGradient(planId: string) {
    const p = plans.value.find((x) => x.id === planId)
    if (!p) return
    const order = ['冲', '稳', '保', '高波动', '数据不足']
    p.entries = [...p.entries].sort((a, b) => {
      const d = order.indexOf(a.risk) - order.indexOf(b.risk)
      if (d !== 0) return d
      return (a.last_year_rank ?? 1e9) - (b.last_year_rank ?? 1e9)
    })
  }

  /** 梯度/健康度分析：风险结构、数据缺失、重复、版本一致性 */
  function analyzePlan(p: VolunteerPlan) {
    const counts: Record<string, number> = { 冲: 0, 稳: 0, 保: 0, 高波动: 0, 数据不足: 0 }
    const seen = new Map<string, number>()
    let missing = 0
    let versionMismatch = 0
    const flagged: string[] = []
    for (const e of p.entries) {
      counts[e.risk] = (counts[e.risk] || 0) + 1
      const key = `${e.school_code}|${e.major_code || e.major_name}`
      seen.set(key, (seen.get(key) || 0) + 1)
      if (e.last_year_rank == null) missing++
      if (p.data_version && e.data_version && e.data_version !== p.data_version) versionMismatch++
      if (e.flags && e.flags.length) flagged.push(`${e.school_name}·${e.major_name}（${e.flags.join('、')}）`)
    }
    const dup = [...seen.values()].filter((n) => n > 1).length
    const total = p.entries.length
    // problems 只收集“真正的问题”；warnings 供展示（无问题时给正向反馈）
    const problems: string[] = []
    if (total === 0) {
      return {
        counts,
        total,
        warnings: ['方案为空：请从「智能匹配」或「收藏」中加入志愿。'],
        ok: false,
        issues: 0,
      }
    }
    if (counts['冲'] / total > 0.5) problems.push(`「冲」占比 ${Math.round((counts['冲'] / total) * 100)}%（>50%），风险过度集中，建议增加稳/保志愿。`)
    if (counts['保'] === 0) problems.push('没有「保」档志愿，存在滑档风险，建议至少配置 2–3 个保底。')
    if (counts['稳'] === 0 && total >= 5) problems.push('没有「稳」档志愿，梯度断层，建议补充。')
    if (counts['高波动'] / total > 0.3) problems.push('「高波动」志愿占比偏高，结果不确定性大。')
    if (missing > 0) problems.push(`${missing} 个志愿缺少最低位次数据（仅分数参考），判定可靠性有限。`)
    if (dup > 0) problems.push(`存在 ${dup} 组重复的「院校+专业」，请检查是否误加。`)
    if (versionMismatch > 0) problems.push(`${versionMismatch} 个志愿的数据版本与方案创建时不一致，建议重新匹配后确认。`)
    if (flagged.length > 0) problems.push(
      `${flagged.length} 个志愿含特殊报考标记，需逐项核实学费/协议/报考条件后再保留：` +
      flagged.slice(0, 5).join('；') + (flagged.length > 5 ? ` 等 ${flagged.length} 项` : '') + '。')
    if (total > 112) problems.push('志愿数超过辽宁本科批 112 个上限。')
    const ok = problems.length === 0
    const warnings = ok ? ['梯度结构良好：冲稳保配置合理，无重复与数据缺失。'] : problems
    return { counts, total, warnings, ok, issues: problems.length }
  }

  return {
    favorites, compareIds, plans,
    isFavorite, addFavorite, removeFavorite, toggleFavorite,
    inCompare, toggleCompare, compareItems, clearCompare,
    createPlan, removePlan, addToPlan, removeFromPlan, moveEntry,
    sortPlanByGradient, analyzePlan,
  }
}
