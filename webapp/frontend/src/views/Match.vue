<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api/client'
import { useProfile, EXAMINEE_YEAR } from '@/composables/useProfile'
import { usePlanner, toSnapshot, candidateId } from '@/composables/usePlanner'
import type { MatchResponse, MatchCandidate, RiskLabel, SensitivityResponse } from '@/types'
import DataStatusBanner from '@/components/DataStatusBanner.vue'
import PlanBasket from '@/components/PlanBasket.vue'
import SchoolDrawer from '@/components/SchoolDrawer.vue'
import MajorDrawer from '@/components/MajorDrawer.vue'
import StepGuide from '@/components/StepGuide.vue'

const { profile } = useProfile()
const planner = usePlanner()

const meta = ref<any>(null)
const data = ref<MatchResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

// 档案摘要条：默认折叠为只读，点「修改」才展开表单
const editingProfile = ref(false)
// 院校详情抽屉
const drawerCode = ref<string | null>(null)
function openSchool(code: string) {
  drawerCode.value = code
}

// 专业详情抽屉（标准专业图文）
const drawerMajor = ref<string | null>(null)
function openMajor(catalogName: string | null) {
  if (catalogName) drawerMajor.value = catalogName
}

// 建议配比提示（教学性，非硬约束）
const RISK_HINT: Record<RiskLabel, string> = {
  保: '建议 ≥20%',
  稳: '建议 ~40%',
  冲: '建议 ~30%',
  高波动: '谨慎',
  数据不足: '仅参考',
}

// 风险档（决定 5 个 Tab 与默认展示顺序）：冲 → 稳 → 保 → 高波动 → 数据不足
const RISKS: { key: RiskLabel; label: string; type: string }[] = [
  { key: '冲', label: '冲', type: 'warning' },
  { key: '稳', label: '稳', type: 'primary' },
  { key: '保', label: '保', type: 'success' },
  { key: '高波动', label: '高波动', type: 'danger' },
  { key: '数据不足', label: '数据不足', type: 'info' },
]
const activeRisk = ref<RiskLabel>('冲')

// 筛选
const filters = ref({
  province: '' as string,
  city: '' as string,
  level: '' as string,
  nature: '' as string,
  type: '' as string,
  major_keyword: '' as string,
  has_both_years: false,
  exclude_flags: [] as string[], // D2a：排除含特殊报考标记的单元
})

// 再选科目候选（D2b）：3+1+2 模式从四科中选两门
const ELECTIVES = ['化学', '生物', '政治', '地理']
function onElectivesChange(v: string[]) {
  if (v.length > 2) profile.value.electives = v.slice(0, 2)
}

// 标记文案/颜色：从后端词表（meta.major_flags）取，前端不硬编码
function flagDef(flag: string) {
  return (meta.value?.major_flags || []).find((d: any) => d.flag === flag)
}
function flagLabel(flag: string) {
  return flagDef(flag)?.label || flag
}
function flagTagType(flag: string) {
  return flagDef(flag)?.severity === 'warn' ? 'warning' : 'info'
}
const page = ref(1)
const PAGE_SIZE = 30

// P5 学费代理过滤：「不接受高学费」勾选 → 自动并入排除标记（中外合作办学）
const TUITION_PROXY_FLAG = '中外合作'
const exclFlags = computed(() => {
  const excl = [...filters.value.exclude_flags]
  if (profile.value.tuition_cap && !excl.includes(TUITION_PROXY_FLAG)) {
    excl.push(TUITION_PROXY_FLAG)
  }
  return excl
})

const totalForActive = computed(() =>
  data.value ? data.value.totals[activeRisk.value] : 0,
)

// P1 备考期模式：估计位次区间（下界 = 乐观视角，上界 = 悲观主视角）
const isInterval = computed(() => profile.value.rank_mode === 'interval')
const intervalValid = computed(() => {
  const lo = profile.value.rank_lo
  const hi = profile.value.rank_hi
  return !!(lo && hi && lo > 0 && hi > 0 && lo <= hi)
})
// 试算锚点位次：区间模式取悲观上界
const sensRank = computed(() =>
  isInterval.value ? profile.value.rank_hi ?? null : profile.value.rank ?? null,
)

async function runMatch(resetPage = true) {
  if (resetPage) page.value = 1
  error.value = null
  sens.value = null // 条件变化后旧试算作废（A3）
  if (isInterval.value) {
    if (!intervalValid.value) {
      error.value = '请填写估计位次区间：上下界均为正整数，且下界 ≤ 上界。可在「我的定位」页用线差法估位。'
      data.value = null
      return
    }
  } else if (!profile.value.rank) {
    error.value = '请先在上方填写全省位次（必填），可同时填分数辅助校验；备考期可切换「估计位次区间」。'
    data.value = null
    return
  }
  loading.value = true
  try {
    data.value = await api.match({
      year: profile.value.year,
      category: profile.value.category,
      subject: profile.value.subject,
      batch: profile.value.batch,
      ...(isInterval.value
        ? { rank_lo: profile.value.rank_lo ?? undefined, rank_hi: profile.value.rank_hi ?? undefined }
        : { rank: profile.value.rank ?? undefined }),
      score: profile.value.score ?? undefined,
      province: filters.value.province || undefined,
      city: filters.value.city || undefined,
      level: filters.value.level || undefined,
      nature: filters.value.nature || undefined,
      type: filters.value.type || undefined,
      major_keyword: filters.value.major_keyword || undefined,
      has_both_years: filters.value.has_both_years || undefined,
      exclude_flags: exclFlags.value.join(',') || undefined,
      electives: profile.value.electives?.length
        ? profile.value.electives.join(',')
        : undefined,
      pref_sort: profile.value.pref_sort && profile.value.pref_sort !== 'certainty'
        ? profile.value.pref_sort
        : undefined,
      risk: activeRisk.value,
      page: page.value,
      page_size: PAGE_SIZE,
    })
    if (data.value?.error) error.value = data.value.error
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function onProfileSubmit() {
  editingProfile.value = false
  runMatch(true)
}
function onRiskTab(risk: RiskLabel) {
  if (risk === activeRisk.value) return
  activeRisk.value = risk
  runMatch(true)
}
function onFilterChange() {
  runMatch(true)
}
function onProvinceChange() {
  // 切换省份时清空已选城市（城市下拉随省份联动）
  filters.value.city = ''
  runMatch(true)
}
function onPageChange() {
  runMatch(false)
}

function riskType(r: RiskLabel) {
  return RISKS.find((x) => x.key === r)?.type || 'info'
}
function diffText(d: number | null) {
  if (d == null) return '—'
  if (d < 0) return `领先 ${Math.abs(d).toLocaleString()} 名`
  if (d > 0) return `落后 ${d.toLocaleString()} 名`
  return '持平'
}
function diffClass(d: number | null) {
  if (d == null) return ''
  if (d < 0) return 'diff--ahead'
  if (d > 0) return 'diff--behind'
  return 'diff--flat'
}

// ---------- A2/A3：分档可信度说明 + 位次敏感度试算 ----------
const noteOpen = ref<string[]>([])
const sens = ref<SensitivityResponse | null>(null)
const sensLoading = ref(false)

// 敏感度表的读法：直接引用「当前位次」行各格数字，用「你这个位次当年录不录」的白话解释
const sensExplain = computed(() => {
  const s = sens.value
  const cur = s?.scenarios?.find((x) => x.offset === 0)
  const r = s?.examinee?.rank ?? null
  if (!cur || !r) return null
  return { r, t: cur.totals }
})

// 风险档白话解释（chips 悬停提示）
function riskExplain(r: RiskLabel): string {
  switch (r) {
    case '保':
      return '历年最难的一年，你这个位次也录得上，且缓冲过了安全线：明年稍难也稳当'
    case '稳':
      return '历年你这个位次都录得上，但缓冲薄：门槛若上移有风险'
    case '冲':
      return '历年你这个位次都录不上（录取末位比你靠前）：需明年门槛下移才有机会'
    case '高波动':
      return '历年录取位次忽高忽低、跨度大，分档仅供参考'
    default:
      return '历史数据少于 2 年，仅供参考'
  }
}
function runSensitivity() {
  if (!sensRank.value) {
    ElMessage.warning('请先填写全省位次（或估计位次区间）')
    return
  }
  sensLoading.value = true
  api.matchSensitivity({
    year: profile.value.year,
    category: profile.value.category,
    subject: profile.value.subject,
    batch: profile.value.batch,
    rank: sensRank.value ?? undefined,
    score: profile.value.score ?? undefined,
    province: filters.value.province || undefined,
    city: filters.value.city || undefined,
    level: filters.value.level || undefined,
    nature: filters.value.nature || undefined,
    type: filters.value.type || undefined,
    major_keyword: filters.value.major_keyword || undefined,
    has_both_years: filters.value.has_both_years || undefined,
    exclude_flags: exclFlags.value.join(',') || undefined,
    electives: profile.value.electives?.length
      ? profile.value.electives.join(',')
      : undefined,
  }).then((r) => {
    sens.value = r
    if (r?.error) ElMessage.warning(r.error)
  }).catch((e) => {
    ElMessage.error((e as Error).message)
  }).finally(() => {
    sensLoading.value = false
  })
}

// 批次数据口径提示（D4）：让每条结果知道自己处在什么数据环境下
const batchContextText = computed(() => {
  const bc = data.value?.batch_context
  if (!bc) return ''
  const pubs = bc.publication
    .map((p) => `${p.year} ${p.stage}：${p.status}${p.official_published_at ? `（官方发布 ${String(p.official_published_at).slice(0, 10)}）` : ''}`)
    .join('；')
  return bc.score_kind_note + (pubs ? ` 历史录取年发布进度：${pubs}` : '')
})

const expandedRows = ref<Record<string, boolean>>({})
function rowKey(c: MatchCandidate) {
  return `${c.school_code}-${c.major_code || c.major_name}-${c.batch}`
}

// ---------- 收藏 / 对比 / 加入方案（Phase 3） ----------
function snap(row: MatchCandidate) {
  return toSnapshot(row, data.value?.data_version ?? null, data.value?.examinee.rank ?? null)
}
function onFav(row: MatchCandidate) {
  const fav = planner.isFavorite(candidateId(row))
  planner.toggleFavorite(snap(row))
  ElMessage.success(fav ? '已取消收藏' : '已收藏（含当前数据版本快照）')
}
function onCompare(row: MatchCandidate) {
  const err = planner.toggleCompare(snap(row))
  if (err) ElMessage.warning(err)
}
const planPicker = ref<{ visible: boolean; row: MatchCandidate | null }>({ visible: false, row: null })
const newPlanName = ref('')
function onAddToPlan(row: MatchCandidate) {
  planPicker.value = { visible: true, row }
}
function pickPlan(planId: string) {
  const row = planPicker.value.row
  if (!row) return
  const err = planner.addToPlan(planId, snap(row))
  err ? ElMessage.warning(err) : ElMessage.success('已加入方案')
  planPicker.value.visible = false
}
function createPlanAndAdd() {
  const row = planPicker.value.row
  if (!row) return
  const p = planner.createPlan(newPlanName.value.trim(), profile.value, data.value?.data_version ?? null)
  planner.addToPlan(p.id, snap(row))
  ElMessage.success(`已创建「${p.name}」并加入`)
  newPlanName.value = ''
  planPicker.value.visible = false
}

onMounted(async () => {
  meta.value = await api.meta().catch(() => null)
  if (profile.value.rank || (isInterval.value && intervalValid.value)) runMatch(true)
})
</script>

<template>
  <div class="page">
    <DataStatusBanner />

    <section class="hero">
      <StepGuide current="match" />
    </section>

    <!-- 考生档案：默认折叠为只读摘要条（与「我的定位」共享，无需重填） -->
    <div class="profile-bar" v-if="!editingProfile">
      <div class="profile-bar__summary">
        <span class="profile-bar__seg profile-bar__seg--year">{{ EXAMINEE_YEAR }} 考生</span>
        <span class="profile-bar__seg">{{ profile.category }}</span>
        <span class="profile-bar__seg">{{ profile.subject }}</span>
        <span class="profile-bar__seg">{{ profile.batch || '未选批次' }}</span>
        <span v-if="profile.electives?.length" class="profile-bar__seg">再选 {{ profile.electives.join('/') }}</span>
        <span v-if="isInterval" class="profile-bar__seg profile-bar__seg--key tnum">
          估计位次 {{ profile.rank_lo?.toLocaleString() ?? '未填' }} – {{ profile.rank_hi?.toLocaleString() ?? '未填' }}
        </span>
        <span v-else class="profile-bar__seg profile-bar__seg--key tnum">位次 {{ profile.rank?.toLocaleString() ?? '未填' }}</span>
        <span v-if="profile.tuition_cap" class="profile-bar__seg" style="background: var(--el-color-warning-light-9); color: var(--el-color-warning);">学费过滤开</span>
        <span class="profile-bar__ref">· 对比历史投档数据</span>
      </div>
      <el-button link type="primary" @click="editingProfile = true">修改</el-button>
    </div>

    <el-card v-else class="card" shadow="never">
      <template #header><div class="card__head"><span>修改考生档案</span>
        <span class="save-hint">自动保存到本机浏览器</span></div></template>
      <el-form :inline="false" label-width="96px" class="form">
        <div class="form__row">
          <el-form-item label="考生年份">
            <el-input :model-value="`${EXAMINEE_YEAR} 年（今年）`" disabled style="width: 150px" />
          </el-form-item>
          <el-form-item label="类别">
            <el-select v-model="profile.category" style="width: 140px">
              <el-option v-for="c in (meta?.categories || ['普通类'])" :key="c" :label="c" :value="c" />
            </el-select>
          </el-form-item>
          <el-form-item label="学科类">
            <el-select v-model="profile.subject" style="width: 160px">
              <el-option v-for="s in (meta?.subjects || ['物理学科类','历史学科类'])" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="目标批次">
            <el-select v-model="profile.batch" style="width: 160px" clearable>
              <el-option v-for="b in (meta?.batches || [])" :key="b" :label="b" :value="b" />
            </el-select>
          </el-form-item>
          <el-form-item label="再选科目">
            <el-select
              v-model="profile.electives"
              multiple
              collapse-tags
              clearable
              style="width: 200px"
              placeholder="选填，最多 2 门"
              @change="onElectivesChange"
            >
              <el-option v-for="s in ELECTIVES" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
        </div>
        <div class="form__row">
          <el-form-item label="位次类型">
            <el-radio-group v-model="profile.rank_mode">
              <el-radio value="exact">出分后·精确位次</el-radio>
              <el-radio value="interval">备考期·估计位次区间</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="!isInterval" label="全省位次" required>
            <el-input v-model.number="profile.rank" type="number" style="width: 170px" placeholder="必填" />
          </el-form-item>
          <template v-else>
            <el-form-item label="位次下界" required>
              <el-input v-model.number="profile.rank_lo" type="number" style="width: 150px" placeholder="更好，如 40000" />
            </el-form-item>
            <el-form-item label="位次上界" required>
              <el-input v-model.number="profile.rank_hi" type="number" style="width: 150px" placeholder="更差，如 50000" />
            </el-form-item>
          </template>
          <el-form-item label="高考分数">
            <el-input v-model.number="profile.score" type="number" style="width: 150px" placeholder="选填，仅记录" />
          </el-form-item>
          <el-button type="primary" :loading="loading" @click="onProfileSubmit">应用并匹配</el-button>
        </div>
      </el-form>
    </el-card>

    <!-- P5 偏好最小版：常显偏好条，即时生效（同档内重排 + 学费代理过滤，不改变分档） -->
    <div class="pref-bar">
      <span class="pref-bar__label">偏好</span>
      <el-radio-group v-model="profile.pref_sort" size="small" @change="runMatch(true)">
        <el-radio-button value="certainty">确定性优先</el-radio-button>
        <el-radio-button value="level">院校层次优先</el-radio-button>
        <el-radio-button value="city">城市分级优先</el-radio-button>
      </el-radio-group>
      <el-checkbox v-model="profile.tuition_cap" @change="runMatch(true)">
        学费 ≤2 万/年（自动排除中外合作办学等高学费项目）
      </el-checkbox>
      <span class="pref-bar__hint">仅影响同档内排序与过滤，不改变冲/稳/保判定</span>
    </div>

    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" class="card" />

    <template v-if="data">
      <!-- 风险档计数 -->
      <div class="risk-chips">
        <el-tooltip
          v-for="r in RISKS"
          :key="r.key"
          :content="riskExplain(r.key)"
          placement="bottom"
          :show-after="200"
        >
          <button
            class="chip"
            :class="['chip--' + r.type, { 'chip--active': activeRisk === r.key }]"
            @click="onRiskTab(r.key)"
          >
            <span class="chip__label">{{ r.label }}</span>
            <span class="chip__num">{{ data.totals[r.key] }}</span>
            <span class="chip__hint">{{ RISK_HINT[r.key] }}</span>
          </button>
        </el-tooltip>
      </div>

      <!-- P1 区间模式：乐观视角（位次下界）各档计数 -->
      <div v-if="data.interval && data.totals_lo" class="risk-chips risk-chips--lo">
        <span class="chips-cap">乐观视角（位次 {{ data.interval.lo.toLocaleString() }}）</span>
        <button
          v-for="r in RISKS"
          :key="'lo-' + r.key"
          class="chip chip--mini"
          :class="'chip--' + r.type"
          disabled
        >
          <span class="chip__label">{{ r.label }}</span>
          <span class="chip__num">{{ data.totals_lo[r.key] }}</span>
        </button>
        <span class="chips-cap chips-cap--note">上方主计数为悲观视角（位次 {{ data.interval.hi.toLocaleString() }}），表格分档亦按悲观视角</span>
      </div>

      <!-- 批次数据口径（D4）：每条结果所处的发布环境 -->
      <el-alert
        v-if="data.batch_context?.warning"
        type="warning"
        :title="data.batch_context.warning"
        show-icon
        :closable="false"
        class="card"
      />
      <el-alert
        v-else-if="batchContextText"
        type="info"
        :closable="false"
        class="card ctx-alert"
      >
        <template #title>数据口径：{{ data.batch_context?.score_kind }}（不含概率，仅门槛位次比较）</template>
        {{ batchContextText }}
      </el-alert>
      <p v-if="data.excluded_by_subject" class="subj-note">
        已按选科要求排除 {{ data.excluded_by_subject }} 个单元（首选不符 {{ data.excluded_first ?? 0 }}、再选不符 {{ data.excluded_re ?? 0 }}）；首选为投档硬约束，与是否填写再选无关。
      </p>
      <p v-else-if="data.subject_requirements_loaded && !profile.electives?.length" class="subj-note">
        2027 选科要求已收录：填写「再选科目」后，将自动排除不符合选科要求的单元。
      </p>

      <!-- 分档规则与位次敏感度：① 怎么判的 ② 位次若有偏差会怎样（A2/A3） -->
      <el-card v-if="data.classification_note" class="card" shadow="never">
        <template #header>
          <div class="card__head"><span>分档规则与位次敏感度</span></div>
        </template>

        <!-- ① 分档依据 -->
        <div class="sec">
          <div class="sec__head">
            <span class="sec__title">① 分档依据</span>
            <span class="sec__sub">冲/稳/保/高波动/数据不足 五档是怎么判的</span>
          </div>
          <p class="hint">
            本站拿「每个单元历年录取最低分对应的全省位次」与你的位次比较来分档（位次法），不输出录取概率。
            「保」档另要求缓冲足够：你的位次需优于「最难一年门槛 × {{ data.classification_note.safe_margin }}」（安全线）。
          </p>
          <el-collapse v-model="noteOpen">
            <el-collapse-item name="note">
              <template #title>查看每档具体怎么算 + 回测数据</template>
              <p class="note-line"><b>保</b>：历年哪怕最难的一年，你这个位次也录得上，且缓冲过了安全线（最难一年门槛 × {{ data.classification_note.safe_margin }}）——明年稍难也安全；</p>
              <p class="note-line"><b>稳</b>：历年你这个位次都录得上，但缓冲薄、没过安全线——门槛若上移有风险；</p>
              <p class="note-line"><b>冲</b>：历年你这个位次都录不上（当年录取末位比你靠前）——需明年门槛下移才有机会；</p>
              <p class="note-line"><b>高波动</b>：历年录取位次忽高忽低、摸不清规律——分档仅参考；</p>
              <p class="note-line"><b>数据不足</b>：历史数据少于 2 年——仅参考。</p>
              <p class="note-line"><b>回测检验</b>（{{ data.classification_note.backtest.pair }}）：{{ data.classification_note.backtest.margin_coverage }}。</p>
              <p class="note-line"><b>门槛跨年稳定性</b>：{{ data.classification_note.backtest.rel_delta }}。</p>
              <p class="note-line note-line--muted">{{ data.classification_note.disclaimer }}</p>
            </el-collapse-item>
          </el-collapse>
        </div>

        <el-divider class="sec-divider" />

        <!-- ② 位次敏感度试算 -->
        <div class="sec">
          <div class="sec__head">
            <span class="sec__title">② 位次敏感度试算</span>
            <el-button size="small" :loading="sensLoading" @click="runSensitivity">开始试算（±5% / ±10%）</el-button>
          </div>
          <p class="hint">
            什么是试算：位次是按分数在一分一段表里查的，但同一分数往往有很多人，
            表里只给累计人数，你在同分人群中的确切位置并不知道，所以你用的位次和真实位次之间有一个误差区间。
            这里用与①相同的分档规则（含安全线），把位次按 ±5% / ±10% 五种情景重新统计各档单元数，
            看「位次若有偏差，分档结果会怎么变」——用来检查你的志愿梯度是否留够；不是录取概率预测。
          </p>
        <div v-if="sens" class="sens">
          <el-alert v-if="sens.error" type="error" :title="sens.error" show-icon :closable="false" />
          <template v-else>
            <p class="hint sens-legend">
              表中数字是<b>单元个数</b>（一个「院校 + 专业」组合算一个单元），不是位次。
              「−10%」指位次数字变小 10%（排名更靠前、更好），「+10%」指位次数字变大 10%（排名更靠后、更差）。
            </p>
            <el-table :data="sens.scenarios" size="small" border style="width: 100%">
              <el-table-column label="情景" min-width="150">
                <template #default="{ row }">
                  <span :class="{ 'sens-cur': row.offset === 0 }">{{ row.label }}</span>
                </template>
              </el-table-column>
              <el-table-column label="位次" width="110" align="right">
                <template #default="{ row }"><span class="tnum">{{ row.rank.toLocaleString() }}</span></template>
              </el-table-column>
              <el-table-column v-for="r in RISKS" :key="r.key" :label="r.label" width="90" align="right">
                <template #default="{ row }">
                  <span class="tnum">{{ row.totals[r.key]?.toLocaleString() }}</span>
                </template>
              </el-table-column>
            </el-table>
            <div v-if="sensExplain" class="sens-explain">
              <p class="hint">
                <b>怎么看这张表</b>（以「当前位次」行为例，你的位次 {{ sensExplain.r.toLocaleString() }}）：
              </p>
              <p class="hint">
                · 「保」下的 <b>{{ sensExplain.t['保'].toLocaleString() }}</b> ＝ {{ sensExplain.t['保'].toLocaleString() }} 个单元「历年哪怕最难的一年，你这个位次也录得上」，且缓冲足够大（过了安全线）：明年就算变难一点，依旧安全；
              </p>
              <p class="hint">
                · 「稳」下的 <b>{{ sensExplain.t['稳'].toLocaleString() }}</b> ＝ {{ sensExplain.t['稳'].toLocaleString() }} 个单元「历年你这个位次都录得上，但缓冲薄」（没过安全线）：明年门槛若上移，这段领先可能被吃掉；
              </p>
              <p class="hint">
                · 「冲」下的 <b>{{ sensExplain.t['冲'].toLocaleString() }}</b> ＝ {{ sensExplain.t['冲'].toLocaleString() }} 个单元「历年你这个位次都录不上」（当年录取末位比你靠前）：只有明年门槛下移才有机会；
              </p>
              <p class="hint">
                · 「高波动」下的 <b>{{ sensExplain.t['高波动'].toLocaleString() }}</b> ＝ 历年录取位次忽高忽低、摸不清规律的单元，仅参考；「数据不足」下的 <b>{{ sensExplain.t['数据不足'].toLocaleString() }}</b> ＝ 历史数据少于 2 年的单元。
              </p>
              <p class="hint note-line--muted">
                安全线 ＝ 最难一年门槛 × {{ data?.classification_note?.safe_margin ?? 0.85 }}，是判「保」要求的缓冲；每个单元的具体安全线，在下方结果表展开该行见「保档安全边际线」。
              </p>
            </div>
            <p class="hint">{{ sens.note }}</p>
          </template>
        </div>
        </div>
      </el-card>

      <!-- 筛选器 -->
      <el-card class="card" shadow="never">
        <div class="filters wrap">
          <el-select v-model="filters.province" placeholder="省份" clearable class="f-sel" @change="onProvinceChange">
            <el-option v-for="f in data.facets.province" :key="f.value" :label="`${f.value} (${f.count})`" :value="f.value" />
          </el-select>
          <el-select v-model="filters.city" placeholder="城市" clearable class="f-sel" :disabled="!filters.province" @change="onFilterChange">
            <el-option v-for="f in data.facets.city" :key="f.value" :label="`${f.value} (${f.count})`" :value="f.value" />
          </el-select>
          <el-select v-model="filters.level" placeholder="层次" clearable class="f-sel" @change="onFilterChange">
            <el-option v-for="f in data.facets.level" :key="f.value" :label="`${f.value} (${f.count})`" :value="f.value" />
          </el-select>
          <el-select v-model="filters.nature" placeholder="性质" clearable class="f-sel" @change="onFilterChange">
            <el-option v-for="f in data.facets.nature" :key="f.value" :label="`${f.value} (${f.count})`" :value="f.value" />
          </el-select>
          <el-select v-model="filters.type" placeholder="类型" clearable class="f-sel" @change="onFilterChange">
            <el-option v-for="f in data.facets.type" :key="f.value" :label="`${f.value} (${f.count})`" :value="f.value" />
          </el-select>
          <el-input v-model="filters.major_keyword" placeholder="专业名关键词" clearable class="f-q" @keyup.enter="onFilterChange" @clear="onFilterChange" />
          <el-checkbox v-model="filters.has_both_years" @change="onFilterChange">仅两年均有数据</el-checkbox>
          <el-checkbox-group v-model="filters.exclude_flags" class="flag-excl" @change="onFilterChange">
            <el-tooltip
              v-for="d in (meta?.major_flags || [])"
              :key="d.flag"
              :content="d.note || d.label"
              placement="top"
            >
              <el-checkbox :value="d.flag">排除{{ d.label }}</el-checkbox>
            </el-tooltip>
          </el-checkbox-group>
          <span class="data-ver">数据版本：{{ data.data_version }}</span>
        </div>
      </el-card>

      <!-- 结果表 -->
      <el-card class="card" shadow="never" v-loading="loading">
        <div class="card__head">
          <span>{{ activeRisk }} · 共 {{ totalForActive.toLocaleString() }} 项</span>
        </div>
        <el-table :data="data.items" size="small" border :row-key="rowKey" :expand-row-keys="Object.keys(expandedRows)" @expand-change="(r:any)=>{const k=rowKey(r); expandedRows[k]=!expandedRows[k]}" style="width:100%">
          <el-table-column type="expand" fixed="left">
            <template #default="{ row }">
              <div class="yr">
                <span class="yr__t">历年最低位次：</span>
                <span v-for="y in row.yearly" :key="y.year" class="yr__item">
                  {{ y.year }}：<b class="tnum">{{ y.lowest_rank.toLocaleString() }}</b>
                </span>
                <span class="yr__m">（覆盖 {{ row.n_years }} 年）</span>
              </div>
              <div v-if="row.safe_line" class="yr">
                <span class="yr__t">保档安全边际线：</span>
                <b class="tnum">{{ row.safe_line.toLocaleString() }}</b>
                <span class="yr__m">
                  （最难年门槛 × {{ data?.classification_note?.safe_margin ?? 0.85 }}；位次优于此线才判「保」）
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="school_name" label="院校" min-width="170" show-overflow-tooltip fixed="left">
            <template #default="{ row }">
              <a class="school-link" @click.stop="openSchool(row.school_code)">{{ row.school_name }}</a>
            </template>
          </el-table-column>
          <el-table-column prop="major_name" label="专业" min-width="170" show-overflow-tooltip fixed="left">
            <template #default="{ row }">
              <a v-if="row.catalog_name" class="major-link" @click.stop="openMajor(row.catalog_name)">{{ row.major_name }}</a>
              <span v-else>{{ row.major_name }}</span>
              <el-tooltip
                v-for="f in (row.flags || [])"
                :key="f"
                :content="flagDef(f)?.note || flagLabel(f)"
                placement="top"
              >
                <el-tag :type="flagTagType(f)" size="small" effect="plain" class="flag-tag">{{ flagLabel(f) }}</el-tag>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="层次/性质/类型" min-width="150">
            <template #default="{ row }">
              <span class="tag">{{ row.level }}</span>
              <span class="tag">{{ row.nature }}</span>
              <span class="tag">{{ row.type }}</span>
            </template>
          </el-table-column>
          <el-table-column label="省份/城市" min-width="120">
            <template #default="{ row }">{{ row.province }}{{ row.city ? '·' + row.city : '' }}</template>
          </el-table-column>
          <el-table-column label="最难年 / 最近年位次" width="150" align="right">
            <template #header>
              <el-tooltip content="最难年＝历史最难一年的门槛位次（冲/稳/保的分档基准，保守口径）；最近年＝2026 年门槛。两者差距大＝门槛断崖变易，分档从严按最难年。" placement="top">
                <span class="th-help">最难年 / 最近年位次</span>
              </el-tooltip>
            </template>
            <template #default="{ row }"><span class="tnum">{{ row.best_rank?.toLocaleString() }} / {{ row.last_year_rank?.toLocaleString() ?? '—' }}</span></template>
          </el-table-column>
          <el-table-column label="最好/最差/中位" align="right" min-width="170">
            <template #header>
              <el-tooltip content="历年门槛位次：最好 = 历史最小位次（最难的一年）；最差 = 最大位次（最易的一年）；中位 = 中间值。跨度大说明门槛不稳定。" placement="top">
                <span class="th-help">最好/最差/中位</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span class="tnum">{{ row.best_rank.toLocaleString() }}</span> /
              <span class="tnum">{{ row.worst_rank.toLocaleString() }}</span> /
              <span class="tnum">{{ row.median_rank.toLocaleString() }}</span>
            </template>
          </el-table-column>
          <el-table-column label="跨度" width="90" align="right">
            <template #default="{ row }"><span class="tnum">{{ row.span.toLocaleString() }}</span></template>
          </el-table-column>
          <el-table-column label="本人位次差" width="130" align="center">
            <template #default="{ row }">
              <span :class="diffClass(row.rank_diff_last)">{{ diffText(row.rank_diff_last) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="依据" min-width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <span :class="['risk-dot','risk-dot--' + riskType(row.risk)]"></span>
              <el-tag v-if="row.risk === '保' && row.safe_band" size="small" effect="plain"
                :type="row.safe_band === '标准保底' ? 'success' : row.safe_band === '极稳垫底' ? 'info' : 'warning'">{{ row.safe_band }}</el-tag>
              <el-tag v-if="row.over_reach" size="small" type="danger" effect="plain">超冲</el-tag>
              <el-tag v-if="row.subject_req" size="small" effect="plain" type="info">选科 {{ row.subject_req }}</el-tag>
              <el-tooltip v-else-if="row.subject_status === 'school_missing'"
                content="该院校未出现在 2027 官方选科要求表中，2027 年可能不在辽招生，请重点核实" placement="top">
                <el-tag size="small" effect="plain" type="danger">院校未收录</el-tag>
              </el-tooltip>
              <el-tooltip v-else-if="row.subject_status === 'major_missing'"
                content="该院校在 2027 官方选科要求表中，但该专业未列出，2027 年可能停招或更名，请重点核实" placement="top">
                <el-tag size="small" effect="plain" type="warning">专业未收录</el-tag>
              </el-tooltip>
              <el-tooltip v-else-if="row.subject_match_level"
                content="已匹配官方选科表，该专业不提选科要求（任意首选/再选均可报）" placement="top">
                <el-tag size="small" effect="plain" type="success">已核验·不限</el-tag>
              </el-tooltip>
              <el-tag v-else-if="row.subject_unverified" size="small" effect="plain" type="warning">选科未核验</el-tag>
              {{ row.risk_reason }}
              <el-tooltip
                v-if="data.interval && row.risk_lo && row.risk_lo !== row.risk"
                content="若你的位次落在估计区间的乐观一端（下界），该单元会判为此档"
                placement="top"
              >
                <el-tag :type="riskType(row.risk_lo)" size="small" effect="plain" class="flag-tag">乐观 {{ row.risk_lo }}</el-tag>
              </el-tooltip>
              <el-tag v-if="row.warning" type="warning" size="small" effect="plain">数据不足</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="170" align="center" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="success" @click="onAddToPlan(row)">+方案</el-button>
              <el-button link size="small" :type="planner.isFavorite(candidateId(row)) ? 'warning' : 'default'" @click="onFav(row)">
                {{ planner.isFavorite(candidateId(row)) ? '★' : '☆' }}
              </el-button>
              <el-button link size="small" :type="planner.inCompare(candidateId(row)) ? 'primary' : 'default'" @click="onCompare(row)">对比</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pg">
          <el-pagination
            layout="prev, pager, next, total"
            :total="totalForActive"
            :page-size="PAGE_SIZE"
            v-model:current-page="page"
            @current-change="onPageChange"
          />
        </div>
        <p class="hint">
          说明：以投档最低分对应位次为门槛，用「位次法」与你的位次比较。
          位次数字越大 = 要求分数越低 = 越容易录。
          「保/稳/冲」为规则模型初步判定，<strong>不显示概率</strong>；高波动表示历年位次跨度大、不确定性高；数据不足表示历史年份少于 2 年，仅供参考。
        </p>
      </el-card>
    </template>

    <!-- 加入方案弹窗 -->
    <el-dialog v-model="planPicker.visible" title="加入志愿方案" width="420px">
      <template v-if="planner.plans.value.length">
        <p class="dlg-hint">选择已有方案：</p>
        <div class="plan-list">
          <el-button v-for="p in planner.plans.value" :key="p.id" class="plan-btn" @click="pickPlan(p.id)">
            {{ p.name }}<span class="plan-btn__n">（{{ p.entries.length }} 项）</span>
          </el-button>
        </div>
        <el-divider />
      </template>
      <p class="dlg-hint">或新建方案：</p>
      <div class="plan-new">
        <el-input v-model="newPlanName" placeholder="方案名，如「主方案」" style="width: 240px" @keyup.enter="createPlanAndAdd" />
        <el-button type="primary" @click="createPlanAndAdd">新建并加入</el-button>
      </div>
    </el-dialog>

    <!-- 常驻方案篮：攒志愿 → 去工作台整理 -->
    <PlanBasket />

    <!-- 院校详情抽屉：查看不离开匹配现场 -->
    <SchoolDrawer v-model:code="drawerCode" />
    <!-- 专业详情抽屉：与院校详情一致，右侧滑出标准专业图文 -->
    <MajorDrawer v-model:name="drawerMajor" />
  </div>
</template>

<style scoped>
.hero { margin-bottom: var(--space-5); }
.hero h1 { font-size: var(--text-2xl); }
.hero__sub { color: var(--color-text-secondary); max-width: 760px; margin-top: var(--space-2); }
.card { margin-bottom: var(--space-4); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
.card__head { font-weight: 600; display: flex; align-items: center; justify-content: space-between; }
.save-hint { font-size: var(--text-xs); color: var(--color-text-muted); font-weight: 400; }
.form__row { display: flex; flex-wrap: wrap; gap: var(--space-4); align-items: flex-end; }

/* 档案摘要条 */
.profile-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  padding: var(--space-2) var(--space-4);
  margin-bottom: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}
.profile-bar__summary { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2); }
.profile-bar__seg {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--color-bg);
}
.profile-bar__seg--key { background: var(--color-primary-soft); color: var(--color-primary); font-weight: 600; }
.profile-bar__seg--year { background: var(--color-text); color: #fff; font-weight: 600; }
.profile-bar__ref { font-size: var(--text-xs); color: var(--color-text-muted); }

.pref-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-4);
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, var(--el-border-color-lighter));
  border-radius: var(--radius-md, 8px);
}
.pref-bar__label { font-size: var(--text-sm); font-weight: 600; color: var(--color-text); }
.pref-bar__hint { font-size: var(--text-xs); color: var(--color-text-muted); margin-left: auto; }

.school-link { color: var(--color-primary); cursor: pointer; }
.school-link:hover { text-decoration: underline; }
.major-link { color: var(--color-primary); cursor: pointer; }
.major-link:hover { text-decoration: underline; }

.chip__hint { font-size: var(--text-xs); color: var(--color-text-muted); }
.risk-chips { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-4); }
.risk-chips--lo { align-items: center; }
.chips-cap { font-size: var(--text-xs); color: var(--color-text-secondary); font-weight: 600; }
.chips-cap--note { color: var(--color-text-muted); font-weight: 400; }
.chip--mini { padding: 2px var(--space-3); cursor: default; }
.chip {
  display: flex; align-items: center; gap: var(--space-2);
  padding: var(--space-2) var(--space-4); border-radius: 999px;
  border: 1px solid var(--color-border); background: #fff; cursor: pointer;
  font-size: var(--text-sm); transition: all .15s;
}
.chip__num { font-weight: 700; font-variant-numeric: tabular-nums; }
.chip--active { box-shadow: 0 0 0 2px var(--color-primary); }
.chip--success.chip--active { border-color: var(--el-color-success); box-shadow: 0 0 0 2px var(--el-color-success); }
.chip--primary.chip--active { border-color: var(--el-color-primary); box-shadow: 0 0 0 2px var(--el-color-primary); }
.chip--warning.chip--active { border-color: var(--el-color-warning); box-shadow: 0 0 0 2px var(--el-color-warning); }
.chip--danger.chip--active { border-color: var(--el-color-danger); box-shadow: 0 0 0 2px var(--el-color-danger); }
.chip--info.chip--active { border-color: var(--el-color-info); box-shadow: 0 0 0 2px var(--el-color-info); }
.filters { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-3); }
.filters.wrap { row-gap: var(--space-3); }
.f-sel { width: 150px; }
.f-q { width: 160px; }
.data-ver { margin-left: auto; color: var(--color-text-muted); font-size: var(--text-xs); }
.tag { display: inline-block; margin-right: 4px; padding: 0 6px; border-radius: 4px; background: var(--color-bg-subtle); font-size: var(--text-xs); color: var(--color-text-secondary); }
.yr { padding: var(--space-2) var(--space-3); font-size: var(--text-sm); color: var(--color-text-secondary); display: flex; flex-wrap: wrap; gap: var(--space-3); align-items: center; }
.yr__t { font-weight: 600; color: var(--color-text); }
.yr__m { color: var(--color-text-muted); }
.diff--ahead { color: var(--el-color-success); }
.diff--behind { color: var(--el-color-danger); }
.diff--flat { color: var(--color-text-muted); }
.risk-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.risk-dot--success { background: var(--el-color-success); }
.risk-dot--primary { background: var(--el-color-primary); }
.risk-dot--warning { background: var(--el-color-warning); }
.risk-dot--danger { background: var(--el-color-danger); }
.risk-dot--info { background: var(--el-color-info); }
.pg { display: flex; justify-content: flex-end; margin-top: var(--space-3); }
.ctx-alert { line-height: 1.7; }
.subj-note { margin: 0 0 var(--space-3); font-size: var(--text-sm); color: var(--color-text-secondary); }
.note-line { margin: 4px 0; font-size: var(--text-sm); color: var(--color-text-secondary); line-height: 1.7; }
.note-line b { color: var(--color-text); font-weight: 600; }
.note-line--muted { color: var(--color-text-muted); font-size: var(--text-xs); }
.sens { margin-top: var(--space-3); }
.sec__head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-2); }
.sec__title { font-weight: 700; }
.sec__sub { font-size: var(--text-xs); color: var(--color-text-muted); }
.sec-divider { margin: var(--space-4) 0; }
.sens-legend { margin: 0 0 var(--space-2); }
.sens-explain { margin-top: var(--space-2); }
.th-help { cursor: help; border-bottom: 1px dotted currentColor; }
.sens-cur { font-weight: 700; color: var(--color-primary); }
.flag-excl { display: inline-flex; flex-wrap: wrap; gap: var(--space-2); }
.flag-tag { margin-left: 4px; cursor: help; }
.hint { color: var(--color-text-muted); font-size: var(--text-xs); margin: var(--space-3) 0 0; line-height: 1.7; }
.dlg-hint { font-size: var(--text-sm); color: var(--color-text-secondary); margin: 0 0 var(--space-2); }
.plan-list { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.plan-btn__n { color: var(--color-text-muted); font-size: var(--text-xs); }
.plan-new { display: flex; gap: var(--space-2); }
</style>
