<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api/client'
import { useProfile } from '@/composables/useProfile'
import { usePlanner, STRATEGY_BASELINES } from '@/composables/usePlanner'
import type { CandidateSnapshot, PlanEntry, PlanStrategy, RiskLabel, VolunteerPlan } from '@/types'
import DataStatusBanner from '@/components/DataStatusBanner.vue'
import StepGuide from '@/components/StepGuide.vue'

const { profile } = useProfile()
const planner = usePlanner()
const { favorites, compareIds, plans } = planner

const activeTab = ref<'fav' | 'compare' | 'plans'>('plans')

// 元数据：仅用于列头/文案里的年份动态渲染（年度接入免改文案）
const meta = ref<any>(null)
onMounted(async () => {
  meta.value = await api.meta().catch(() => null)
})

const RISK_TYPE: Record<RiskLabel, string> = {
  保: 'success', 稳: 'primary', 冲: 'warning', 高波动: 'danger', 数据不足: 'info',
}
// P2a 覆盖曲线点位配色（与体检配比条同色系）
const RISK_COLOR: Record<RiskLabel, string> = {
  保: 'var(--color-match)', 稳: 'var(--color-safe)', 冲: 'var(--color-reach)',
  高波动: 'var(--color-volatile)', 数据不足: 'var(--color-insufficient)',
}

// ---------- 面向普通用户的悬浮说明（覆盖曲线画图逻辑 / 策略基线） ----------
const CURVE_TIP = '这张图怎么画：① 每个点＝一个志愿，点的高度＝该院校+专业「历史最难年」的投档门槛位次（历年数据里录取最难的一年，取保守口径）；② 虚线＝你的位次：线上方＝最难年门槛也比你好，属冲击区；紧贴线下方＝稳档区（最可能录取）；远低于线＝保底区；③ 点的颜色是最终档位判定（还会综合考虑波动、数据完整度等），高度只是判定依据之一，所以个别「稳」的点略高于线是正常的（最难年够不着、但历史中位够得着）；④ 健康的志愿表曲线应按 冲→稳→保 单调下沉，尾部全是保档；⑤ 年份切换只改纵轴口径（看「如果只信这一年，每个志愿站在哪」），不改变分档——分档仍以最难年+安全边际为准。'
const STRATEGY_TIPS: Record<PlanStrategy, string> = {
  冲击: '冲击型：冲约36% / 稳29% / 保35%。愿意用更多冲刺槽位博更好学校，但保底安全垫不缩水；适合能接受「用滑到更低一档的可能、换更好学校机会」的考生。',
  均衡: '均衡型：冲20% / 稳50% / 保30%。稳档占一半作主体，兼顾「博好学校」和「不滑档」，是最常见的建议比例。',
  稳妥: '稳妥型：冲10% / 稳55% / 保35%。冲刺只留一成梦想位，九成放在稳+保；适合「宁可学校低一点、也不冒滑档风险」的考生。',
}

function fmt(n: number | null | undefined) {
  return n == null ? '—' : n.toLocaleString()
}
function diffText(d: number | null) {
  if (d == null) return '—'
  if (d < 0) return `领先 ${Math.abs(d).toLocaleString()}`
  if (d > 0) return `落后 ${d.toLocaleString()}`
  return '持平'
}

// ---------- 收藏 ----------
const favRiskFilter = ref<RiskLabel | ''>('')
const favFiltered = computed(() =>
  favRiskFilter.value ? favorites.value.filter((f) => f.risk === favRiskFilter.value) : favorites.value,
)

// ---------- 对比 ----------
const compareList = computed(() => planner.compareItems())
const COMPARE_ROWS: { label: string; get: (c: CandidateSnapshot) => string }[] = [
  { label: '风险档', get: (c) => c.risk },
  { label: '批次', get: (c) => c.batch },
  { label: '省份/城市', get: (c) => `${c.province || '—'}${c.city ? '·' + c.city : ''}` },
  { label: '层次/性质/类型', get: (c) => [c.level, c.nature, c.type].filter(Boolean).join(' / ') || '—' },
  { label: '最近年位次', get: (c) => fmt(c.last_year_rank) },
  { label: '近一年最低分', get: (c) => (c.last_year_score != null ? String(c.last_year_score) : '—') },
  { label: '最好 / 最差 / 中位', get: (c) => `${fmt(c.best_rank)} / ${fmt(c.worst_rank)} / ${fmt(c.median_rank)}` },
  { label: '位次跨度（波动）', get: (c) => `${fmt(c.span)}${c.relative_vol != null ? `（${Math.round(c.relative_vol * 100)}%）` : ''}` },
  { label: '覆盖年份', get: (c) => `${c.n_years} 年` },
  { label: '本人位次差', get: (c) => diffText(c.rank_diff_last) },
  { label: '判定依据', get: (c) => c.risk_reason },
  { label: '数据版本', get: (c) => c.data_version || '—' },
]

// ---------- 方案 ----------
const activePlanId = ref<string>(plans.value[0]?.id || '')
const activePlan = computed<VolunteerPlan | null>(
  () => plans.value.find((p) => p.id === activePlanId.value) || null,
)
const analysis = computed(() => (activePlan.value ? planner.analyzePlan(activePlan.value) : null))
// 体检/模板的策略基线选择（旧方案无 strategy 时默认均衡型）
const planStrategy = computed<PlanStrategy>({
  get: () => activePlan.value?.strategy ?? '均衡',
  set: (v) => { if (activePlan.value) activePlan.value.strategy = v },
})

// ---------- P2a 整表覆盖曲线：横轴=志愿序号，纵轴=历史门槛位次，叠加考生位次（区间）水平线 ----------
// 第一性原理设计：决策相关的不是位次绝对差，而是与「你的位次」的比值
// （1k→2k 名的难度差 ≫ 120k→121k 名），故 y 轴用 log₁₀：
// 冲在虚线上方、稳紧贴线下（最可能录取）、保沉底，三档天然分层
function smoothPath(pts: { x: number; y: number }[]): string {
  if (pts.length < 2) return ''
  let d = `M${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] ?? p2
    d += ` C${(p1.x + (p2.x - p0.x) / 6).toFixed(1)},${(p1.y + (p2.y - p0.y) / 6).toFixed(1)}`
      + ` ${(p2.x - (p3.x - p1.x) / 6).toFixed(1)},${(p2.y - (p3.y - p1.y) / 6).toFixed(1)}`
      + ` ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`
  }
  return d
}
// ---------- 分年视图 / 三年叠加：纵轴口径切换（分档不变，仍以最难年为基准） ----------
type CurveMode = 'hardest' | 'overlay' | number
const curveYear = ref<CurveMode>('hardest')
const availableYears = computed(() => {
  const ys = new Set<number>()
  for (const e of activePlan.value?.entries ?? []) for (const t of e.yearly ?? []) ys.add(t.year)
  return [...ys].sort((a, b) => b - a)
})
const curveMode = computed<CurveMode>(() => {
  const m = curveYear.value
  return typeof m === 'number' && !availableYears.value.includes(m) ? 'hardest' : m
})
// 叠加细线调色板（按年份升序：蓝/橙/绿，未来新增年份循环取色）
const OVERLAY_COLORS = ['#409eff', '#e6a23c', '#67c23a', '#909399', '#f56c6c']

const curveHeadNote = computed(() => {
  const mode = curveMode.value
  if (typeof mode === 'number') {
    const p = activePlan.value
    const k = p ? p.entries.filter((e) => (e.yearly ?? []).some((t) => t.year === mode && t.lowest_rank != null)).length : 0
    return `纵轴＝${mode} 年投档门槛位次（对数）；空心点＝该志愿当年无数据（有数据 ${k}/${p?.entries.length ?? 0}）；分档颜色仍为最终判定`
  }
  if (mode === 'overlay') return '粗线＝最难年口径（分档基准），细线为各年门槛，看年际跳动'
  return '纵轴＝最难年门槛位次（对数，分档基准）：冲在虚线上方、稳紧贴线下（最可能录取）、保沉底；整体应单调下沉'
})
const curveNote = computed(() => {
  const p = activePlan.value
  const mode = curveMode.value
  if (!p || p.entries.length < 2 || typeof mode !== 'number') return null
  const k = p.entries.filter((e) => (e.yearly ?? []).some((t) => t.year === mode && t.lowest_rank != null)).length
  return k < 2 ? `${mode} 年数据不足（${k}/${p.entries.length} 个志愿有该年门槛位次），无法成线，请切换其他年份或最难年。` : null
})

const curve = computed(() => {
  const p = activePlan.value
  if (!p || p.entries.length < 2) return null
  const mode = curveMode.value
  const yearRank = (e: PlanEntry, yr: number) =>
    (e.yearly ?? []).find((t) => t.year === yr)?.lowest_rank ?? null
  const all = p.entries.map((e, i) => ({
    i: i + 1,
    // 分年模式取该年门槛；最难年/叠加模式维持原保守口径
    y: typeof mode === 'number' ? yearRank(e, mode) : e.best_rank ?? e.last_year_rank ?? e.worst_rank,
    last: e.last_year_rank, risk: e.risk as RiskLabel, over: !!e.over_safe, far: !!e.over_reach,
    name: `${e.school_name}·${e.major_name}`,
  }))
  const pts = all.filter((d): d is typeof d & { y: number } => Number.isFinite(d.y))
  if (pts.length < 2) return null
  const gaps = typeof mode === 'number' ? all.filter((d) => !Number.isFinite(d.y)) : []
  const ex = p.examinee
  const exHi = ex.rank ?? ex.rank_hi ?? null // 精确位次或区间上界（悲观）
  const exLo = ex.rank_mode === 'interval' ? ex.rank_lo ?? null : null // 区间下界（乐观）
  const vals = [...pts.map((d) => d.y)]
  if (exHi != null) vals.push(exHi)
  if (exLo != null) vals.push(exLo)
  // 叠加模式：各年门槛均纳入纵轴范围，防细线越界
  if (mode === 'overlay') {
    for (const e of p.entries) for (const t of e.yearly ?? []) if (t.lowest_rank != null) vals.push(t.lowest_rank)
  }
  const finiteVals = vals.filter((v) => Number.isFinite(v))
  if (finiteVals.length < 1) return null
  const minV = Math.max(1, Math.min(...finiteVals) * 0.8)
  const maxV = Math.max(...finiteVals) * 1.25
  const lgMin = Math.log10(minV)
  const lgSpan = Math.max(0.1, Math.log10(maxV) - lgMin)
  const W = 760, H = 320, padL = 70, padR = 16, padT = 18, padB = 34
  const n = p.entries.length
  const x = (i: number) => padL + ((i - 1) / Math.max(1, n - 1)) * (W - padL - padR)
  const y = (v: number) => padT + ((Math.log10(Math.max(1, v)) - lgMin) / lgSpan) * (H - padT - padB)
  const fy = (v: number | null | undefined) => {
    if (v == null || !Number.isFinite(v)) return null
    const yy = y(v)
    return Number.isFinite(yy) ? +yy.toFixed(1) : null
  }
  const xy = pts.map((d) => ({ x: x(d.i), y: y(d.y) }))
  const line = smoothPath(xy)
  const bottom = H - padB
  const area = `${line} L${xy[xy.length - 1].x.toFixed(1)},${bottom} L${xy[0].x.toFixed(1)},${bottom} Z`
  // 叠加细线：每年一条（只连接有值点，缺值跨过）
  const overlays = mode === 'overlay'
    ? [...availableYears.value].sort((a, b) => a - b).map((yr, idx) => ({
        year: yr,
        color: OVERLAY_COLORS[idx % OVERLAY_COLORS.length],
        d: smoothPath(p.entries
          .map((e, i) => ({ i: i + 1, v: yearRank(e, yr) }))
          .filter((o): o is { i: number; v: number } => Number.isFinite(o.v))
          .map((o) => ({ x: x(o.i), y: y(o.v) }))),
      })).filter((o) => o.d)
    : []
  // 对数刻度：1/2/5×10^k 取样，≥1万 显示为「N万」（跳过非有限值，防 NaN 属性）
  const ticks: { y: string; label: string }[] = []
  for (let e = Math.floor(Math.log10(minV)); e <= Math.ceil(Math.log10(maxV)); e++) {
    for (const m of [1, 2, 5]) {
      const v = m * 10 ** e
      const ty = fy(v)
      if (v >= minV && v <= maxV && ty != null) {
        ticks.push({
          y: String(ty),
          label: v >= 10000 && v % 10000 === 0 ? `${v / 10000}万` : v.toLocaleString(),
        })
      }
    }
  }
  const ticksShown = ticks.length > 7 ? ticks.filter((_, i) => i % 2 === 0) : ticks
  // 稳档带：你的位次线 → 稳簇底部，即「最可能录取区间」
  let wenBand: { top: number; height: number } | null = null
  const wenYs = pts.filter((d) => d.risk === '稳').map((d) => y(d.y)).filter(Number.isFinite)
  if (wenYs.length) {
    const anchorY = exHi != null ? y(exHi) : Math.min(...wenYs)
    if (Number.isFinite(anchorY)) {
      const top = Math.max(padT, Math.min(anchorY, ...wenYs) - 8)
      wenBand = { top: +top.toFixed(1), height: +Math.max(18, Math.max(...wenYs) - top + 10).toFixed(1) }
    }
  }
  // 横轴序号刻度：不多则全显，多则抽样并保证末位
  const step = n <= 16 ? 1 : Math.ceil(n / 12)
  const xTicks: { x: number; label: number }[] = []
  for (let i = 1; i <= n; i += step) xTicks.push({ x: +x(i).toFixed(1), label: i })
  if ((n - 1) % step !== 0) xTicks.push({ x: +x(n).toFixed(1), label: n })
  return {
    W, H, padL, right: W - padR, bottom, line, area, ticks: ticksShown, xTicks, wenBand,
    circles: pts.map((d) => ({ cx: +x(d.i).toFixed(1), cy: +y(d.y).toFixed(1), risk: d.risk, over: d.over, far: d.far, label: typeof mode === 'number' ? `第 ${d.i} 位 ${d.name}（${mode} 年门槛 ${d.y.toLocaleString()}）` : `第 ${d.i} 位 ${d.name}（最难年 ${d.y.toLocaleString()}${d.last != null && d.last !== d.y ? ` / 最近年 ${d.last.toLocaleString()}` : ''}${d.over ? ' · 过深保底：保护已饱和' : d.far ? ' · 超冲：差距过大' : ''}）` })),
    gaps: gaps.map((d) => ({ cx: +x(d.i).toFixed(1), label: `第 ${d.i} 位 ${d.name}（${mode} 年无数据）` })),
    overlays,
    axisTitle: typeof mode === 'number' ? `${mode} 年门槛位次(对数)` : '最难年门槛位次(对数)',
    exY: fy(exHi), exHi,
    exLoY: fy(exLo), exLo,
  }
})

const newPlanName = ref('')
function createPlan() {
  const p = planner.createPlan(newPlanName.value.trim(), profile.value, favorites.value[0]?.data_version ?? null)
  activePlanId.value = p.id
  newPlanName.value = ''
}
async function deletePlan(p: VolunteerPlan) {
  try {
    await ElMessageBox.confirm(`确定删除方案「${p.name}」？（不可恢复）`, '删除方案', { type: 'warning' })
  } catch {
    return
  }
  planner.removePlan(p.id)
  if (activePlanId.value === p.id) activePlanId.value = plans.value[0]?.id || ''
}
function onToggleCompare(snap: CandidateSnapshot) {
  const err = planner.toggleCompare(snap)
  if (err) ElMessage.warning(err)
}
function addFavToPlan(snapId: string) {
  if (!activePlan.value) {
    ElMessage.warning('请先创建/选择一个方案')
    activeTab.value = 'plans'
    return
  }
  const snap = favorites.value.find((f) => f.id === snapId)
  if (!snap) return
  const err = planner.addToPlan(activePlan.value.id, snap)
  err ? ElMessage.warning(err) : ElMessage.success(`已加入「${activePlan.value.name}」`)
}

// ---------- P2c 梯度模板：从收藏池按所选策略基线（冲/稳/保）一键生成骨架 ----------
const tplStrategy = ref<PlanStrategy>('均衡')
function generateTemplate() {
  const pool = favorites.value
  if (pool.length < 3) {
    ElMessage.warning('收藏太少：先到「智能匹配」收藏一批候选（建议冲/稳/保都有一些），再一键生成梯度模板')
    return
  }
  const total = Math.min(112, Math.max(10, pool.length))
  const base = STRATEGY_BASELINES[tplStrategy.value]
  const want: Record<string, number> = { 冲: Math.round(total * base.冲), 稳: Math.round(total * base.稳), 保: 0 }
  want['保'] = Math.max(1, total - want['冲'] - want['稳'])
  const p = planner.createPlan(`梯度模板（${base.label}）${new Date().toISOString().slice(0, 10)}`, profile.value, pool[0]?.data_version ?? null)
  p.strategy = tplStrategy.value
  const added: string[] = []
  for (const r of ['冲', '稳', '保'] as RiskLabel[]) {
    // 同档内按门槛位次升序（从贴近你位次的一侧逐步变易，形成梯度）
    let poolR = pool.filter((f) => f.risk === r)
    if (r === '保') { const eff = poolR.filter((f) => !f.over_safe); if (eff.length) poolR = eff }   // 保池优先有效保底
    if (r === '冲') { const eff = poolR.filter((f) => !f.over_reach); if (eff.length) poolR = eff }  // 冲池剔除超冲梦想位
    const cands = poolR
      .sort((a, b) => (a.last_year_rank ?? 1e9) - (b.last_year_rank ?? 1e9))
      .slice(0, want[r])
    for (const c of cands) planner.addToPlan(p.id, c)
    added.push(`${r} ${cands.length}/${want[r]}`)
  }
  activePlanId.value = p.id
  activeTab.value = 'plans'
  ElMessage.success(`已生成「${p.name}」：${added.join('、')}（收藏不足处按现有数量加入，可继续补充至 112 个）`)
}

// ---------- P4 录取结果自愿回填（录取结束后，匿名可用） ----------
const fbVisible = ref(false)
const fbLoading = ref(false)
const fbOutcome = ref<'admitted' | 'slipped' | 'unknown'>('admitted')
const fbOrder = ref<number | null>(null)
const fbNote = ref('')
const fbSummary = ref<{ total: number; by_outcome: Record<string, number> } | null>(null)
// 录取志愿自动带出该位次条目的院校/专业/档位（真实标签集的关键字段）
const fbEntry = computed(() => {
  const p = activePlan.value
  if (!p || !fbOrder.value || fbOrder.value < 1) return null
  return p.entries[fbOrder.value - 1] ?? null
})
async function openFeedback() {
  if (!activePlan.value || !activePlan.value.entries.length) {
    ElMessage.warning('请先选择包含志愿的方案')
    return
  }
  fbSummary.value = await api.feedbackSummary().catch(() => null)
  fbVisible.value = true
}
async function submitFeedback() {
  const p = activePlan.value
  if (!p) return
  if (fbOutcome.value === 'admitted' && (!fbOrder.value || fbOrder.value < 1 || fbOrder.value > p.entries.length)) {
    ElMessage.warning(`请填写实际被第几志愿录取（1–${p.entries.length}）`)
    return
  }
  fbLoading.value = true
  try {
    const e = fbEntry.value
    const r = await api.submitFeedback({
      examinee_year: p.examinee.year,
      category: p.examinee.category,
      subject: p.examinee.subject,
      batch: p.examinee.batch,
      examinee_rank: p.examinee.rank ?? p.examinee.rank_hi ?? null,
      plan_total: p.entries.length,
      outcome: fbOutcome.value,
      admitted_order: fbOutcome.value === 'admitted' ? fbOrder.value : null,
      admitted_risk: fbOutcome.value === 'admitted' ? e?.risk ?? null : null,
      admitted_school: fbOutcome.value === 'admitted' ? e?.school_name ?? null : null,
      admitted_major: fbOutcome.value === 'admitted' ? e?.major_name ?? null : null,
      note: fbNote.value.trim() || null,
    })
    if (r?.error) {
      ElMessage.warning(r.error)
      return
    }
    fbVisible.value = false
    fbOrder.value = null
    fbNote.value = ''
    ElMessage.success('感谢回填！你的真实录取结果将用于校准分档规则（匿名汇总）。')
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    fbLoading.value = false
  }
}

// ---------- 导出 ----------
const exporting = ref(false)
// 数值净化：v-model.number 清空输入会留下空字符串（localStorage 快照可能带脏值），
// 非有限数值一律转 null，避免后端 float/int 解析 422
const num = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null
async function exportPlan(p: VolunteerPlan) {
  if (!p.entries.length) {
    ElMessage.warning('方案为空，无可导出内容')
    return
  }
  exporting.value = true
  try {
    const blob = await api.exportPlan({
      plan_name: p.name,
      note: p.note,
      data_version: p.data_version,
      created_at: p.created_at,
      examinee: {
        year: p.examinee.year, category: p.examinee.category,
        subject: p.examinee.subject, batch: p.examinee.batch,
        score: num(p.examinee.score), rank: num(p.examinee.rank),
      },
      items: p.entries.map((e) => ({
        risk: e.risk,
        school_code: e.school_code, school_name: e.school_name,
        major_code: e.major_code, major_name: e.major_name,
        last_year: num(e.last_year), last_year_score: num(e.last_year_score),
        last_year_rank: num(e.last_year_rank), rank_diff_last: num(e.rank_diff_last),
        level: e.level, city: e.city, flags: e.flags || [], note: e.note,
      })),
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${p.name}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已导出 xlsx（列对齐辽宁「专业+学校」平行志愿）')
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div class="page">
    <DataStatusBanner />

    <StepGuide current="workbench" />

    <!-- 方案体检：置顶显眼位置（change 7） -->
    <el-card v-if="activePlan && activePlan.entries.length && analysis" class="checkup" shadow="never"
             :class="analysis.ok ? 'checkup--ok' : 'checkup--warn'">
      <div class="checkup__head">
        <div>
          <span class="checkup__title">方案体检 · {{ activePlan.name }}</span>
          <span class="checkup__total">共 {{ analysis.total }} 个志愿</span>
        </div>
        <el-button v-if="analysis.ok" type="primary" :loading="exporting" @click="exportPlan(activePlan)">
          方案健康 · 导出志愿表 →
        </el-button>
        <span v-else class="checkup__badge">{{ analysis.issues }} 项待优化</span>
      </div>

      <!-- 冲稳保配比条 -->
      <div class="ratio">
        <template v-for="r in (['冲','稳','保','高波动','数据不足'] as RiskLabel[])" :key="r">
          <div
            v-if="analysis.counts[r]"
            class="ratio__seg"
            :class="'ratio__seg--' + RISK_TYPE[r]"
            :style="{ flexGrow: analysis.counts[r] }"
            :title="`${r} ${analysis.counts[r]}`"
          >{{ r }}{{ analysis.counts[r] }}</div>
        </template>
      </div>

      <ul class="checkup__list" :class="{ 'checkup__list--ok': analysis.ok }">
        <li v-for="(w, i) in analysis.warnings" :key="i">{{ w }}</li>
      </ul>
    </el-card>

    <el-tabs v-model="activeTab">
      <!-- ============ 收藏 ============ -->
      <el-tab-pane :label="`收藏（${favorites.length}）`" name="fav">
        <el-card class="card" shadow="never">
          <div class="toolbar">
            <el-radio-group v-model="favRiskFilter" size="small">
              <el-radio-button label="">全部</el-radio-button>
              <el-radio-button v-for="r in (['保','稳','冲','高波动','数据不足'] as RiskLabel[])" :key="r" :label="r">{{ r }}</el-radio-button>
            </el-radio-group>
            <span class="muted" v-if="activePlan">加入目标方案：{{ activePlan.name }}</span>
          </div>
          <el-empty v-if="!favFiltered.length" description="暂无收藏。到「智能匹配」结果里点 ☆ 收藏候选。" />
          <el-table v-else :data="favFiltered" size="small" border>
            <el-table-column label="档位" width="90" align="center">
              <template #default="{ row }"><el-tag :type="RISK_TYPE[row.risk as RiskLabel] as any" size="small">{{ row.risk }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="school_name" label="院校" min-width="160" show-overflow-tooltip />
            <el-table-column prop="major_name" label="专业" min-width="160" show-overflow-tooltip />
            <el-table-column label="城市" width="110">
              <template #default="{ row }">{{ row.province }}{{ row.city ? '·' + row.city : '' }}</template>
            </el-table-column>
            <el-table-column :label="`近年最低位次${meta?.last_year ? '（' + meta.last_year + '）' : ''}`" width="130" align="right">
              <template #default="{ row }"><span class="tnum">{{ fmt(row.last_year_rank) }}</span></template>
            </el-table-column>
            <el-table-column label="位次差" width="110" align="center">
              <template #default="{ row }">{{ diffText(row.rank_diff_last) }}</template>
            </el-table-column>
            <el-table-column prop="saved_at" label="收藏时间" width="160" />
            <el-table-column label="操作" width="190" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link size="small" :type="planner.inCompare(row.id) ? 'primary' : 'default'" @click="onToggleCompare(row)">对比</el-button>
                <el-button link size="small" type="success" @click="addFavToPlan(row.id)">+方案</el-button>
                <el-button link size="small" type="danger" @click="planner.removeFavorite(row.id)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- ============ 对比中心 ============ -->
      <el-tab-pane :label="`对比中心（${compareIds.length}/5）`" name="compare">
        <el-card class="card" shadow="never">
          <el-empty v-if="compareList.length < 2" description="从「收藏」或「智能匹配」加入 2–5 项后同屏对比。" />
          <template v-else>
            <div class="toolbar">
              <span class="muted">同屏对比 {{ compareList.length }} 项（位次 / 波动 / 层次 / 城市 / 依据）</span>
              <el-button size="small" @click="planner.clearCompare()">清空对比</el-button>
            </div>
            <div class="cmp-wrap">
              <table class="cmp">
                <thead>
                  <tr>
                    <th class="cmp__attr">对比项</th>
                    <th v-for="c in compareList" :key="c.id">
                      <div class="cmp__school">{{ c.school_name }}</div>
                      <div class="cmp__major">{{ c.major_name }}</div>
                      <el-button link size="small" type="danger" @click="planner.toggleCompare(c)">移除</el-button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="r in COMPARE_ROWS" :key="r.label">
                    <td class="cmp__attr">{{ r.label }}</td>
                    <td v-for="c in compareList" :key="c.id" :class="{ 'cmp__risk': r.label === '风险档' }">
                      <el-tag v-if="r.label === '风险档'" :type="RISK_TYPE[c.risk] as any" size="small">{{ c.risk }}</el-tag>
                      <template v-else>{{ r.get(c) }}</template>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </el-card>
      </el-tab-pane>

      <!-- ============ 我的方案 ============ -->
      <el-tab-pane :label="`我的方案（${plans.length}）`" name="plans">
        <el-card class="card" shadow="never">
          <div class="toolbar">
            <el-select v-model="activePlanId" placeholder="选择方案" style="width: 220px">
              <el-option v-for="p in plans" :key="p.id" :label="`${p.name}（${p.entries.length}）`" :value="p.id" />
            </el-select>
            <el-input v-model="newPlanName" placeholder="新方案名" style="width: 180px" @keyup.enter="createPlan" />
            <el-button @click="createPlan">新建方案</el-button>
            <el-tooltip content="一键梯度模板按此策略基线决定冲/稳/保配比；各型含义见下方「策略基线」悬浮说明" placement="top" popper-class="wb-tip">
              <el-select v-model="tplStrategy" size="small" style="width: 104px">
                <el-option value="冲击" label="冲击型" />
                <el-option value="均衡" label="均衡型" />
                <el-option value="稳妥" label="稳妥型" />
              </el-select>
            </el-tooltip>
            <el-tooltip content="从收藏池按所选策略基线（冲/稳/保配比）一键生成骨架方案（教学性模板，需自行补全至 112 个）" placement="top">
              <el-button type="success" plain @click="generateTemplate">一键梯度模板</el-button>
            </el-tooltip>
            <template v-if="activePlan">
              <el-button type="warning" plain @click="planner.sortPlanByGradient(activePlan.id)">按冲→稳→保重排</el-button>
              <el-button type="primary" :loading="exporting" @click="exportPlan(activePlan)">导出志愿表 xlsx</el-button>
              <el-button type="danger" plain @click="deletePlan(activePlan)">删除方案</el-button>
              <el-tooltip content="录取结束后自愿回填「实际被第几志愿录取」；匿名可用，仅用于校准分档规则" placement="top">
                <el-button type="info" plain @click="openFeedback">回填录取结果</el-button>
              </el-tooltip>
            </template>
          </div>

          <template v-if="activePlan">
            <div class="plan-meta">
              考生：{{ activePlan.examinee.year }} 年 {{ activePlan.examinee.subject }} {{ activePlan.examinee.batch }}，
              位次 {{ fmt(activePlan.examinee.rank) }} ·
              创建于 {{ activePlan.created_at }} · 数据版本 {{ activePlan.data_version || '—' }}
            </div>
            <div class="plan-meta">
              <el-tooltip content="三个数字是「冲/稳/保」建议占比：任何类型保底都恒定在 35% 左右（防滑档安全垫），只有冲的比例随风险偏好变化。该基线用于方案体检配比校验与一键梯度模板。" placement="top" popper-class="wb-tip">
                <span class="help-q">策略基线？</span>
              </el-tooltip>
              <el-radio-group v-model="planStrategy" size="small">
                <el-tooltip :content="STRATEGY_TIPS['冲击']" placement="top" popper-class="wb-tip">
                  <el-radio-button value="冲击">冲击型 36/29/35</el-radio-button>
                </el-tooltip>
                <el-tooltip :content="STRATEGY_TIPS['均衡']" placement="top" popper-class="wb-tip">
                  <el-radio-button value="均衡">均衡型 20/50/30</el-radio-button>
                </el-tooltip>
                <el-tooltip :content="STRATEGY_TIPS['稳妥']" placement="top" popper-class="wb-tip">
                  <el-radio-button value="稳妥">稳妥型 10/55/35</el-radio-button>
                </el-tooltip>
              </el-radio-group>
              <span class="muted">用于方案体检配比校验与一键梯度模板（悬停各型查看含义）</span>
            </div>

            <!-- P2a 整表覆盖曲线：志愿序号 × 历史门槛位次，叠加考生位次（区间）水平线 -->
            <el-card v-if="curve || curveNote" class="card curve-card" shadow="never">
              <template #header>
                <div class="card__head card__head--curve">
                  <span class="curve-title">整表覆盖曲线
                    <el-tooltip :content="CURVE_TIP" placement="top" popper-class="wb-tip">
                      <span class="help-q">这图怎么画？</span>
                    </el-tooltip></span>
                  <el-radio-group v-model="curveYear" size="small" class="curve-mode">
                    <el-radio-button value="hardest">最难年</el-radio-button>
                    <el-radio-button v-for="yr in availableYears" :key="yr" :value="yr">{{ yr }}</el-radio-button>
                    <el-radio-button value="overlay">三年叠加</el-radio-button>
                  </el-radio-group>
                  <span class="muted">{{ curveHeadNote }}</span>
                </div>
              </template>
              <svg v-if="curve" :viewBox="`0 0 ${curve.W} ${curve.H}`" class="curve" role="img" aria-label="志愿表覆盖曲线">
                <defs>
                  <linearGradient id="curveArea" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="var(--color-primary)" stop-opacity="0.20" />
                    <stop offset="100%" stop-color="var(--color-primary)" stop-opacity="0.02" />
                  </linearGradient>
                </defs>
                <!-- 分区着色：你的位次之上=冲击区，之下=保底区 -->
                <template v-if="curve.exY != null">
                  <rect :x="curve.padL" :y="curve.padT" :width="curve.right - curve.padL" :height="Math.max(0, +curve.exY - curve.padT)" class="curve__zone curve__zone--reach" />
                  <rect :x="curve.padL" :y="curve.exY" :width="curve.right - curve.padL" :height="Math.max(0, curve.bottom - +curve.exY)" class="curve__zone curve__zone--safe" />
                  <text v-if="+curve.exY - curve.padT > 26" :x="curve.padL + 8" :y="curve.padT + 15" class="curve__zone-label curve__zone-label--reach">冲击区 · 门槛比你好</text>
                  <text v-if="curve.bottom - +curve.exY > 26" :x="curve.padL + 8" :y="curve.bottom - 8" class="curve__zone-label curve__zone-label--safe">保底区 · 远低于你的位次</text>
                </template>
                <!-- 稳档带：最可能录取区间 -->
                <template v-if="curve.wenBand">
                  <rect :x="curve.padL" :y="curve.wenBand.top" :width="curve.right - curve.padL" :height="curve.wenBand.height" class="curve__wen" />
                  <text :x="curve.right - 6" :y="curve.wenBand.top + curve.wenBand.height - 6" text-anchor="end" class="curve__wen-label">稳档带 · 最可能录取区间</text>
                </template>
                <text :x="curve.padL - 8" :y="curve.padT - 6" text-anchor="end" class="curve__tick">{{ curve.axisTitle }}</text>
                <!-- 横向网格刻度（位次值，越小越难） -->
                <g v-for="(t, i) in curve.ticks" :key="'g' + i">
                  <line :x1="curve.padL" :x2="curve.right" :y1="t.y" :y2="t.y" class="curve__grid" />
                  <text :x="curve.padL - 8" :y="+t.y + 3" text-anchor="end" class="curve__tick">{{ t.label }}</text>
                </g>
                <!-- 渐变面积 + 平滑曲线 -->
                <path :d="curve.area" fill="url(#curveArea)" />
                <path :d="curve.line" fill="none" stroke="var(--color-primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.85" />
                <!-- 三年叠加细线 + 右上角图例 -->
                <template v-if="curve.overlays.length">
                  <path v-for="o in curve.overlays" :key="'ov' + o.year" :d="o.d" fill="none" :stroke="o.color" stroke-width="1.5" stroke-dasharray="5 4" opacity="0.85" />
                  <g v-for="(o, i) in curve.overlays" :key="'ovl' + o.year">
                    <line :x1="curve.right - 158 + i * 54" :x2="curve.right - 144 + i * 54" :y1="curve.padT + 8" :y2="curve.padT + 8" :stroke="o.color" stroke-width="2" />
                    <text :x="curve.right - 140 + i * 54" :y="curve.padT + 11" class="curve__tick">{{ o.year }}</text>
                  </g>
                </template>
                <!-- 考生位次水平线（区间模式画两条） -->
                <template v-if="curve.exY != null">
                  <line :x1="curve.padL" :x2="curve.right" :y1="curve.exY" :y2="curve.exY" class="curve__me" />
                  <text :x="curve.right - 2" :y="+curve.exY - 5" text-anchor="end" class="curve__me-label">你的位次 {{ (curve.exHi as number).toLocaleString() }}{{ curve.exLoY != null ? '（上界）' : '' }}</text>
                </template>
                <template v-if="curve.exLoY != null">
                  <line :x1="curve.padL" :x2="curve.right" :y1="curve.exLoY" :y2="curve.exLoY" class="curve__me curve__me--lo" />
                  <text :x="curve.right - 2" :y="+curve.exLoY - 5" text-anchor="end" class="curve__me-label curve__me-label--lo">下界 {{ (curve.exLo as number).toLocaleString() }}</text>
                </template>
                <!-- 门槛位次点：按档位着色，悬停放大 -->
                <circle
                  v-for="(c, i) in curve.circles"
                  :key="'c' + i"
                  :cx="c.cx" :cy="c.cy" r="4.5"
                  :fill="RISK_COLOR[c.risk]"
                  :class="['curve__dot', c.over && 'curve__dot--over', c.far && 'curve__dot--far']"
                >
                  <title>{{ c.label }}</title>
                </circle>
                <!-- 分年视图：当年无数据的志愿在底部画空心点 -->
                <circle
                  v-for="(g, i) in curve.gaps"
                  :key="'gap' + i"
                  :cx="g.cx" :cy="curve.bottom - 6" r="3.5"
                  class="curve__gap"
                >
                  <title>{{ g.label }}</title>
                </circle>
                <!-- 横轴：序号刻度 -->
                <line :x1="curve.padL" :x2="curve.right" :y1="curve.bottom" :y2="curve.bottom" class="curve__axis" />
                <text v-for="t in curve.xTicks" :key="'x' + t.label" :x="t.x" :y="curve.bottom + 15" text-anchor="middle" class="curve__tick">{{ t.label }}</text>
                <text :x="(curve.W + curve.padL) / 2" :y="curve.H - 4" text-anchor="middle" class="curve__tick">志愿序号 →</text>
              </svg>
              <div v-if="!curve && curveNote" class="curve-note">{{ curveNote }}</div>
              <div v-if="curve" class="curve-legend">
                <span v-for="r in (['冲', '稳', '保', '高波动', '数据不足'] as RiskLabel[])" :key="r" class="curve-legend__item">
                  <i class="curve-legend__dot" :style="{ background: RISK_COLOR[r] }"></i>{{ r }}
                </span>
                <span class="curve-legend__item"><i class="curve-legend__dash"></i>你的位次</span>
                <span v-if="curve.wenBand" class="curve-legend__item"><i class="curve-legend__zone curve-legend__zone--wen"></i>稳档带（最可能录取）</span>
                <span v-if="curve.exY != null" class="curve-legend__item"><i class="curve-legend__zone curve-legend__zone--reach"></i>冲击区</span>
                <span v-if="curve.exY != null" class="curve-legend__item"><i class="curve-legend__zone curve-legend__zone--safe"></i>保底区</span>
                <span v-for="o in curve.overlays" :key="'lg' + o.year" class="curve-legend__item"><i class="curve-legend__line" :style="{ color: o.color }"></i>{{ o.year }} 门槛</span>
                <span v-if="curve.gaps.length" class="curve-legend__item"><i class="curve-legend__gapdot"></i>当年无数据</span>
                <span class="curve-legend__hint">悬停圆点查看明细</span>
              </div>
            </el-card>

            <!-- 梯度分析已提升到顶部「方案体检」卡，此处仅保留志愿明细表 -->
            <el-empty v-if="!activePlan.entries.length" description="方案为空：从「智能匹配」或「收藏」加入志愿。" />
            <el-table v-else :data="activePlan.entries" size="small" border>
              <el-table-column type="index" label="序号" width="60" align="center" />
              <el-table-column label="档位" width="90" align="center">
                <template #default="{ row }"><el-tag :type="RISK_TYPE[row.risk as RiskLabel] as any" size="small">{{ row.risk }}</el-tag></template>
              </el-table-column>
              <el-table-column prop="school_name" label="院校" min-width="150" show-overflow-tooltip />
              <el-table-column prop="major_name" label="专业" min-width="150" show-overflow-tooltip />
              <el-table-column :label="`${meta?.last_year ?? ''}最低分/位次`" width="150" align="right">
                <template #default="{ row }">
                  <span class="tnum">{{ row.last_year_score ?? '—' }}</span> /
                  <span class="tnum">{{ fmt(row.last_year_rank) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="位次差" width="110" align="center">
                <template #default="{ row }">{{ diffText(row.rank_diff_last) }}</template>
              </el-table-column>
              <el-table-column label="城市" width="100">
                <template #default="{ row }">{{ row.city || '—' }}</template>
              </el-table-column>
              <el-table-column label="备注" min-width="140">
                <template #default="{ row }"><el-input v-model="row.note" size="small" placeholder="备注" /></template>
              </el-table-column>
              <el-table-column label="排序/操作" width="160" align="center" fixed="right">
                <template #default="{ $index, row }">
                  <el-button link size="small" :disabled="$index === 0" @click="planner.moveEntry(activePlan!.id, $index, -1)">↑</el-button>
                  <el-button link size="small" :disabled="$index === activePlan!.entries.length - 1" @click="planner.moveEntry(activePlan!.id, $index, 1)">↓</el-button>
                  <el-button link size="small" type="danger" @click="planner.removeFromPlan(activePlan!.id, row.id)">移除</el-button>
                </template>
              </el-table-column>
            </el-table>

            <p class="hint">
              导出列对齐辽宁「专业+学校」平行志愿：序号 / 档位 / 院校代码 / 院校名称 / 专业代码 / 专业名称 /
              往年最低分 / 往年最低位次 / 位次差 / 层次 / 城市。条目保存加入时的数据版本快照；
              本表仅供参考，最终以省招考部门及院校官方发布为准。
            </p>
          </template>
          <el-empty v-else description="暂无方案：输入方案名点「新建方案」。" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- P4 录取结果自愿回填（匿名可用，真实标签集） -->
    <el-dialog v-model="fbVisible" title="回填录取结果（自愿·匿名）" width="480px">
      <p class="muted">
        录取结束后，告诉我们实际结果即可；不要求登录，不收集身份信息。
        这些真实标签将用于校准冲/稳/保分档规则，让后来者受益。
        <template v-if="fbSummary?.total">目前已有 {{ fbSummary.total }} 人回填。</template>
      </p>
      <el-form label-width="110px">
        <el-form-item label="录取结果">
          <el-radio-group v-model="fbOutcome">
            <el-radio value="admitted">已被录取</el-radio>
            <el-radio value="slipped">滑档（本批未录取）</el-radio>
            <el-radio value="unknown">暂不确定</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="fbOutcome === 'admitted' && activePlan">
          <el-form-item label="被第几志愿录取">
            <el-input v-model.number="fbOrder" type="number" style="width: 140px" :placeholder="`1–${activePlan.entries.length}`" />
          </el-form-item>
          <p v-if="fbEntry" class="muted">
            对应志愿：{{ fbEntry.school_name }} · {{ fbEntry.major_name }}（档位：{{ fbEntry.risk }}）
          </p>
        </template>
        <el-form-item label="备注（选填）">
          <el-input v-model="fbNote" maxlength="500" placeholder="如：录取位次与预期差异、征集志愿情况等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fbVisible = false">取消</el-button>
        <el-button type="primary" :loading="fbLoading" @click="submitFeedback">提交回填</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.hero { margin-bottom: var(--space-5); }
.hero h1 { font-size: var(--text-2xl); }
.hero__sub { color: var(--color-text-secondary); max-width: 780px; margin-top: var(--space-2); }
.card { margin-bottom: var(--space-4); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }

/* 方案体检卡（置顶） */
.checkup {
  margin-bottom: var(--space-5);
  border-radius: var(--radius-lg);
  border-width: 1px;
  border-style: solid;
}
.checkup--ok { border-color: var(--color-match); background: var(--color-match-soft); }
.checkup--warn { border-color: var(--color-reach); background: var(--color-reach-soft); }
.checkup__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}
.checkup__title { font-weight: 700; font-size: var(--text-lg); color: var(--color-text); }
.checkup__total { margin-left: var(--space-3); color: var(--color-text-muted); font-size: var(--text-sm); }
.checkup__badge {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-reach);
  padding: var(--space-1) var(--space-3);
  border-radius: 999px;
  background: #fff;
}
.ratio {
  display: flex;
  gap: 3px;
  height: 28px;
  margin-bottom: var(--space-3);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.ratio__seg {
  display: grid;
  place-items: center;
  min-width: 44px;
  color: #fff;
  font-size: var(--text-xs);
  font-weight: 600;
  white-space: nowrap;
}
.ratio__seg--success { background: var(--color-match); }
.ratio__seg--primary { background: var(--color-safe); }
.ratio__seg--warning { background: var(--color-reach); }
.ratio__seg--danger { background: var(--color-volatile); }
.ratio__seg--info { background: var(--color-insufficient); }
.checkup__list {
  margin: 0;
  padding-left: 1.2em;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: 1.9;
}
.checkup__list--ok { color: var(--color-match); font-weight: 500; }
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-3); margin-bottom: var(--space-4); }
.muted { color: var(--color-text-muted); font-size: var(--text-xs); }
.plan-meta { color: var(--color-text-secondary); font-size: var(--text-sm); margin-bottom: var(--space-3); }
.analysis { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); margin-bottom: var(--space-4); background: var(--color-bg-subtle); }
.analysis__chips { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); margin-bottom: var(--space-2); }
.analysis__warn { margin: 0; padding-left: 1.2em; font-size: var(--text-sm); color: var(--color-text-secondary); line-height: 1.8; }
.cmp-wrap { overflow-x: auto; }
.cmp { border-collapse: collapse; width: 100%; font-size: var(--text-sm); }
.cmp th, .cmp td { border: 1px solid var(--color-border); padding: var(--space-2) var(--space-3); text-align: left; vertical-align: top; min-width: 160px; }
.cmp thead th { background: var(--color-bg-subtle); }
.cmp__attr { width: 140px; min-width: 140px !important; font-weight: 600; color: var(--color-text-secondary); background: var(--color-bg-subtle); }
.cmp__school { font-weight: 600; }
.cmp__major { color: var(--color-text-secondary); font-size: var(--text-xs); margin: 2px 0 4px; }
.hint { color: var(--color-text-muted); font-size: var(--text-xs); margin: var(--space-3) 0 0; line-height: 1.7; }
.card__head { font-weight: 600; display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }

/* P2a 覆盖曲线 */
.curve-card { background: linear-gradient(180deg, #fff 0%, var(--color-bg-subtle) 100%); }
.curve { width: 100%; height: auto; display: block; }
.curve__grid { stroke: var(--color-border, #e6e8ee); stroke-dasharray: 3 5; }
.curve__axis { stroke: var(--color-border, #d8dbe2); }
.curve__tick { font-size: 10px; fill: var(--color-text-muted); }
.curve__zone--reach { fill: var(--el-color-warning-light-9); opacity: 0.35; }
.curve__zone--safe { fill: var(--el-color-success-light-9); opacity: 0.4; }
.curve__zone-label { font-size: 10px; font-weight: 600; letter-spacing: 0.5px; }
.curve__zone-label--reach { fill: var(--el-color-warning); }
.curve__zone-label--safe { fill: var(--el-color-success); }
.curve__me { stroke: var(--color-primary); stroke-width: 1.5; stroke-dasharray: 6 4; }
.curve__me--lo { stroke: var(--color-match); }
.curve__me-label { font-size: 10px; fill: var(--color-primary); font-weight: 700; paint-order: stroke; stroke: #fff; stroke-width: 3px; }
.curve__me-label--lo { fill: var(--color-match); }
.curve__dot { stroke: #fff; stroke-width: 1.5; transition: r 0.15s ease; cursor: pointer; }
.curve__dot--over { opacity: 0.45; }
.curve__dot--far { stroke: var(--color-text-muted, #999); stroke-dasharray: 2 2; opacity: 0.6; }
.curve__dot:hover { r: 7; }
.curve-legend { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-3); margin-top: var(--space-2); font-size: var(--text-xs); color: var(--color-text-secondary); }
.curve-legend__item { display: inline-flex; align-items: center; gap: 6px; }
.curve-legend__dot { width: 8px; height: 8px; border-radius: 50%; }
.curve-legend__dash { width: 18px; border-top: 2px dashed var(--color-primary); }
.curve-legend__zone { width: 14px; height: 10px; border-radius: 2px; }
.curve-legend__zone--reach { background: var(--el-color-warning-light-9); }
.curve-legend__zone--safe { background: var(--el-color-success-light-9); }
.curve__wen { fill: var(--el-color-primary-light-9); opacity: 0.7; }
.curve__wen-label { font-size: 10px; font-weight: 700; fill: var(--color-primary); paint-order: stroke; stroke: #fff; stroke-width: 3px; }
.curve-legend__zone--wen { background: var(--el-color-primary-light-9); }
.curve-legend__hint { margin-left: auto; color: var(--color-text-muted); }
/* 分年视图 / 三年叠加 */
.card__head--curve { flex-wrap: wrap; }
.curve-mode { flex: none; }
.curve__gap { fill: #fff; stroke: var(--color-text-muted, #999); stroke-width: 1.5; stroke-dasharray: 2 2; }
.curve-note { color: var(--color-text-muted); font-size: var(--text-xs); padding: var(--space-2) 0; }
.curve-legend__line { width: 18px; border-top: 2px dashed currentColor; }
.curve-legend__gapdot { width: 8px; height: 8px; border-radius: 50%; border: 1.5px dashed var(--color-text-muted, #999); background: #fff; box-sizing: border-box; }
</style>

<style>
/* 悬浮说明 popper 挂载在 body，需全局样式 */
.wb-tip { max-width: 460px; line-height: 1.7; }
.help-q {
  color: var(--color-primary);
  font-size: var(--text-xs);
  font-weight: 400;
  cursor: help;
  border-bottom: 1px dashed var(--color-primary);
  margin-left: var(--space-2);
}
.curve-title { display: inline-flex; align-items: baseline; }
</style>
