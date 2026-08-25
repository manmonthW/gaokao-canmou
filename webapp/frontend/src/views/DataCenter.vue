<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import type {
  DataStatusMatrix, CollectionReference, SubjectReqSummary, PagedSubjectReqs,
  PagedMajorTrend, MarketDriftRow,
} from '@/types'

const route = useRoute()
const meta = ref<any>(null)

const active = ref<string>('lines')
const loading = ref(false)
const error = ref<string | null>(null)

// 省控线
const lineFilters = ref({ year: 2025, category: '普通类', subject: '物理学科类' })
const lines = ref<any[]>([])

// 一分一段
const rankFilters = ref({ year: 2025, category: '普通类', subject: '物理学科类' })
const rankData = ref<any>(null)
const rankPage = ref(1)

// 原始记录
const recFilters = ref({
  year: null as number | null,
  category: '' as string,
  subject: '' as string,
  batch: '' as string,
  is_collection: null as boolean | null,
  school: '' as string,
  major: '' as string,
})
const recData = ref<any>(null)
const recPage = ref(1)

// 批次发布状态
const pubStatus = ref<any[]>([])

// 发布矩阵（D4）：官方发布状态 × 库内记录数，暴露时效性缺口
const matrix = ref<DataStatusMatrix | null>(null)

// 往年征集参考（P6）：滑档后真实存在的安全网，独立入口、明确标注，不参与智能匹配
const collFilters = ref({
  category: '普通类',
  subject: '物理学科类',
  batch: '',
  rank: null as number | null,
})
const collData = ref<CollectionReference | null>(null)

// 专业冷热趋势（0017）：默认看本科批——那是主战场，且专科批「样本不足」占比更高
const trendFilters = ref({ subject: '', batch: '本科批', label: '', q: '' })
const trendData = ref<PagedMajorTrend | null>(null)
const trendMarket = ref<MarketDriftRow[]>([])

// 选科要求三表（D2b）：官方 2027 选考科目要求原样浏览，不参与任何计算
const XK_TABLE_LABEL: Record<string, string> = { bk: '本科', zk: '专科', jx: '军校' }
const XK_NOTE = '官方《拟在辽招生普通高校专业选考科目要求》三表：bk 本科 / zk 专科 / jx 军校；「不限」即不提科目要求。'
const xkFilters = ref({ year: null as number | null, table: '', school: '', major: '', first_req: '' })
const xkData = ref<PagedSubjectReqs | null>(null)
const xkSummary = ref<SubjectReqSummary | null>(null)
const xkPage = ref(1)
const xkYears = computed(() =>
  [...new Set((xkSummary.value?.items || []).map((i) => i.year))].sort((a, b) => b - a))

async function guard(fn: () => Promise<void>) {
  loading.value = true
  error.value = null
  try {
    await fn()
  } catch (e: any) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function loadLines() {
  return guard(async () => {
    lines.value = await api.controlLines({
      year: lineFilters.value.year,
      category: lineFilters.value.category,
      subject: lineFilters.value.subject,
    })
  })
}
function loadRank() {
  return guard(async () => {
    rankData.value = await api.scoreRank({
      year: rankFilters.value.year,
      category: rankFilters.value.category,
      subject: rankFilters.value.subject,
      page: rankPage.value,
      page_size: 50,
    })
  })
}
function loadRec() {
  return guard(async () => {
    recData.value = await api.records({
      year: recFilters.value.year ?? undefined,
      category: recFilters.value.category || undefined,
      subject: recFilters.value.subject || undefined,
      batch: recFilters.value.batch || undefined,
      is_collection: recFilters.value.is_collection ?? undefined,
      school: recFilters.value.school || undefined,
      major: recFilters.value.major || undefined,
      page: recPage.value,
      page_size: 50,
    })
  })
}
function loadPub() {
  return guard(async () => { pubStatus.value = await api.publicationStatus() })
}
function loadMatrix() {
  return guard(async () => { matrix.value = await api.dataStatusMatrix() })
}
function loadColl() {
  return guard(async () => {
    collData.value = await api.collectionReference({
      category: collFilters.value.category,
      subject: collFilters.value.subject || undefined,
      batch: collFilters.value.batch || undefined,
      rank: collFilters.value.rank || undefined,
    })
  })
}
function loadXkSummary() {
  return guard(async () => { xkSummary.value = await api.subjectReqSummary() })
}
function loadXk() {
  return guard(async () => {
    xkData.value = await api.subjectReqs({
      year: xkFilters.value.year ?? undefined,
      table: xkFilters.value.table || undefined,
      school: xkFilters.value.school || undefined,
      major: xkFilters.value.major || undefined,
      first_req: xkFilters.value.first_req || undefined,
      page: xkPage.value,
      page_size: 50,
    })
  })
}

function onTab(tab: string) {
  if (tab === 'lines' && !lines.value.length) loadLines()
  if (tab === 'rank' && !rankData.value) loadRank()
  if (tab === 'records') loadRec()
  if (tab === 'pub' && !pubStatus.value.length) loadPub()
  if (tab === 'matrix' && !matrix.value) loadMatrix()
  if (tab === 'collection' && !collData.value) loadColl()
  if (tab === 'xk') {
    if (!xkSummary.value) loadXkSummary()
    if (!xkData.value) loadXk()
  }
  if (tab === 'trend') {
    if (!trendMarket.value.length) loadTrendMarket()
    if (!trendData.value) loadTrend(1)
  }
}

function loadTrend(page = 1) {
  return guard(async () => {
    const f = trendFilters.value
    trendData.value = await api.majorTrendTable({
      subject: f.subject || undefined,
      batch: f.batch || undefined,
      label: f.label || undefined,
      q: f.q || undefined,
      page,
      page_size: 50,
    })
  })
}

function loadTrendMarket() {
  return guard(async () => {
    trendMarket.value = await api.majorTrendMarket()
  })
}

// 原始记录：批次下拉按已选科类联动（数据驱动，来自 meta.batches_by_category）。
// 未选科类时展示全部批次；已选科类时仅展示该科类实际存在的批次，
// 避免把跨科类共享的批次值（如「专科批」）误导性地暴露给其他科类。
const recBatchOptions = computed<string[]>(() => {
  const cat = recFilters.value.category
  const map = meta.value?.batches_by_category
  if (cat && map && map[cat]) return map[cat]
  return meta.value?.batches || []
})

// 切换科类时，若当前已选批次不属于新科类，则清空，避免残留导致空结果。
function onRecCategoryChange() {
  const opts = recBatchOptions.value
  if (recFilters.value.batch && !opts.includes(recFilters.value.batch)) {
    recFilters.value.batch = ''
  }
  onRecFilter()
}

// 征集参考：批次下拉同样按已选类别联动（逻辑与原始记录一致）
const collBatchOptions = computed<string[]>(() => {
  const cat = collFilters.value.category
  const map = meta.value?.batches_by_category
  if (cat && map && map[cat]) return map[cat]
  return meta.value?.batches || []
})
function onCollCategoryChange() {
  const opts = collBatchOptions.value
  if (collFilters.value.batch && !opts.includes(collFilters.value.batch)) {
    collFilters.value.batch = ''
  }
  loadColl()
}

onMounted(async () => {
  meta.value = await api.meta().catch(() => null)
  // 从专业搜索跳转：预填专业名并切到记录页
  if (route.query.major) {
    recFilters.value.major = route.query.major as string
    active.value = 'records'
    loadRec()
  } else {
    loadLines()
  }
})

watch(rankPage, () => { if (active.value === 'rank') loadRank() })
watch(recPage, () => { if (active.value === 'records') loadRec() })
watch(xkPage, () => { if (active.value === 'xk') loadXk() })

function onRankFilter() { rankPage.value = 1; loadRank() }
function onRecFilter() { recPage.value = 1; loadRec() }
function onXkFilter() { xkPage.value = 1; loadXk() }
</script>

<template>
  <div class="page">
    <div class="lib-eyebrow"><span class="lib-eyebrow__dot"></span>资料库 · 原始数据</div>
    <h1 class="page__title">数据中心</h1>
    <p class="page__sub">省控线、一分一段表、原始录取记录、批次发布状态与 2027 选科要求。这里是原始数据溯源，一般决策看前面「定位 → 匹配 → 工作台」三步即可。</p>

    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" class="card" />

    <el-tabs v-model="active" class="tabs" @tab-change="(n: any) => onTab(n)" v-loading="loading">
      <!-- 省控线 -->
      <el-tab-pane label="省控线" name="lines">
        <div class="filters">
          <el-select v-model="lineFilters.year" class="f-sel" @change="loadLines">
            <el-option v-for="y in (meta?.years || [])" :key="y" :label="y" :value="y" />
          </el-select>
          <el-select v-model="lineFilters.category" class="f-sel" @change="loadLines">
            <el-option v-for="c in (meta?.categories || [])" :key="c" :label="c" :value="c" />
          </el-select>
          <el-select v-model="lineFilters.subject" class="f-sel" @change="loadLines">
            <el-option v-for="s in (meta?.subjects || [])" :key="s" :label="s" :value="s" />
          </el-select>
        </div>
        <el-table :data="lines" size="small" border fit>
          <el-table-column prop="year" label="年份" width="90" />
          <el-table-column prop="category" label="类别" width="100" />
          <el-table-column prop="subject" label="学科类" width="120" />
          <el-table-column prop="line_type" label="线类型" width="160" />
          <el-table-column prop="score" label="分数" width="100" align="right">
            <template #default="{ row }"><span class="tnum">{{ row.score }}</span></template>
          </el-table-column>
          <el-table-column prop="note" label="说明" min-width="160" show-overflow-tooltip />
        </el-table>
      </el-tab-pane>

      <!-- 一分一段 -->
      <el-tab-pane label="一分一段" name="rank">
        <div class="filters">
          <el-select v-model="rankFilters.year" class="f-sel" @change="onRankFilter()">
            <el-option v-for="y in (meta?.years || [])" :key="y" :label="y" :value="y" />
          </el-select>
          <el-select v-model="rankFilters.category" class="f-sel" @change="onRankFilter()">
            <el-option v-for="c in (meta?.categories || [])" :key="c" :label="c" :value="c" />
          </el-select>
          <el-select v-model="rankFilters.subject" class="f-sel" @change="onRankFilter()">
            <el-option v-for="s in (meta?.subjects || [])" :key="s" :label="s" :value="s" />
          </el-select>
          <el-pagination
            v-if="rankData"
            layout="prev, pager, next, total"
            :total="rankData.total"
            :page-size="rankData.page_size"
            v-model:current-page="rankPage"
            class="pg"
          />
        </div>
        <el-table v-if="rankData" :data="rankData.items" size="small" border fit>
          <el-table-column prop="score" label="分数" width="100">
            <template #default="{ row }">
              <span class="tnum">{{ row.score }}</span>
              <el-tag v-if="row.is_top_bucket" size="small" type="success" effect="plain">及以上</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="count" label="本分人数" width="110" align="right">
            <template #default="{ row }"><span class="tnum">{{ row.count }}</span></template>
          </el-table-column>
          <el-table-column prop="cumulative_rank" label="累计人数（位次）" align="right">
            <template #default="{ row }"><span class="tnum">{{ row.cumulative_rank.toLocaleString() }}</span></template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 原始记录 -->
      <el-tab-pane label="原始录取记录" name="records">
        <div class="filters wrap">
          <el-select v-model="recFilters.year" placeholder="年份" aria-label="年份" clearable class="f-sel" @change="onRecFilter()">
            <el-option v-for="y in (meta?.years || [])" :key="y" :label="y" :value="y" />
          </el-select>
          <el-select v-model="recFilters.category" placeholder="类别" aria-label="类别" clearable class="f-sel" @change="onRecCategoryChange()">
            <el-option v-for="c in (meta?.categories || [])" :key="c" :label="c" :value="c" />
          </el-select>
          <el-select v-model="recFilters.subject" placeholder="学科类" aria-label="学科类" clearable class="f-sel" @change="onRecFilter()">
            <el-option v-for="s in (meta?.subjects || [])" :key="s" :label="s" :value="s" />
          </el-select>
          <el-select v-model="recFilters.batch" placeholder="批次" aria-label="批次" clearable class="f-sel" @change="onRecFilter()">
            <el-option v-for="b in recBatchOptions" :key="b" :label="b" :value="b" />
          </el-select>
          <el-select v-model="recFilters.is_collection" placeholder="志愿类型" aria-label="志愿类型" clearable class="f-sel" @change="onRecFilter()">
            <el-option label="常规" :value="false" />
            <el-option label="征集" :value="true" />
          </el-select>
          <el-input v-model="recFilters.school" placeholder="院校名" aria-label="院校名" clearable class="f-q" @keyup.enter="onRecFilter()" />
          <el-input v-model="recFilters.major" placeholder="专业名" aria-label="专业名" clearable class="f-q" @keyup.enter="onRecFilter()" />
          <el-button @click="onRecFilter()">查询</el-button>
          <el-pagination
            v-if="recData"
            layout="prev, pager, next, total"
            :total="recData.total"
            :page-size="recData.page_size"
            v-model:current-page="recPage"
            class="pg"
          />
        </div>
        <div v-if="recData && !recData.items.length" class="empty">无匹配记录，请调整筛选条件。</div>
        <el-table v-if="recData && recData.items.length" :data="recData.items" size="small" border fit>
          <el-table-column prop="year" label="年" width="70" />
          <el-table-column prop="category" label="类别" width="90" />
          <el-table-column prop="subject" label="学科类" width="110" />
          <el-table-column prop="batch" label="批次" width="120" />
          <el-table-column label="征集" width="60" align="center">
            <template #default="{ row }"><el-tag v-if="row.is_collection" size="small" type="warning" effect="plain">征</el-tag></template>
          </el-table-column>
          <el-table-column prop="school_name" label="院校" min-width="140" show-overflow-tooltip />
          <el-table-column prop="major_name" label="专业" min-width="140" show-overflow-tooltip />
          <el-table-column prop="score_kind" label="类型" width="100" />
          <el-table-column prop="lowest_score" label="最低分" width="80" align="right">
            <template #default="{ row }"><span class="tnum" v-if="row.lowest_score != null">{{ row.lowest_score }}</span></template>
          </el-table-column>
          <el-table-column prop="lowest_rank" label="最低位次" width="90" align="right">
            <template #default="{ row }"><span class="tnum" v-if="row.lowest_rank != null">{{ row.lowest_rank.toLocaleString() }}</span></template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 批次发布状态 -->
      <el-tab-pane label="批次发布状态" name="pub">
        <el-table :data="pubStatus" size="small" border fit>
          <el-table-column prop="year" label="年份" width="80" />
          <el-table-column prop="category" label="类别" width="90" />
          <el-table-column prop="subject" label="学科类" width="110" />
          <el-table-column prop="batch" label="批次" width="130" />
          <el-table-column prop="stage" label="阶段" width="90" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag
                :type="row.status === '已完成' ? 'success' : row.status === '待发布' ? 'warning' : 'info'"
                effect="light"
              >{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="official_published_at" label="官方发布" width="170" />
          <el-table-column prop="system_updated_at" label="系统更新" width="170" />
          <el-table-column prop="note" label="备注" min-width="160" show-overflow-tooltip />
        </el-table>
      </el-tab-pane>

      <!-- 发布矩阵（D4）：官方发布 × 库内记录，缺口一目了然 -->
      <el-tab-pane label="发布矩阵" name="matrix">
        <p class="matrix-note">
          每个批次的官方发布状态与库内已入库记录数对照：
          <el-tag type="danger" size="small" effect="light">缺口</el-tag>
          表示官方已发布/部分发布但库内尚无数据，结果可能不完整。
        </p>
        <el-table
          v-if="matrix"
          :data="matrix.matrix"
          size="small"
          border
          fit
          :row-class-name="(r: any) => (r.row.gap ? 'matrix-gap' : '')"
        >
          <el-table-column prop="year" label="年份" width="80" />
          <el-table-column prop="category" label="类别" width="90" />
          <el-table-column prop="subject" label="学科类" width="110" />
          <el-table-column prop="batch" label="批次" width="130" />
          <el-table-column prop="stage" label="阶段" width="80" />
          <el-table-column label="发布状态" width="100">
            <template #default="{ row }">
              <el-tag
                :type="row.status === '已完成' ? 'success' : row.status === '待发布' ? 'warning' : 'info'"
                effect="light"
              >{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="official_published_at" label="官方发布" width="170" />
          <el-table-column label="库内记录" width="100" align="right">
            <template #default="{ row }">
              <span class="tnum">{{ row.records.toLocaleString() }}</span>
              <el-tag v-if="row.gap" type="danger" size="small" effect="light">缺口</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="note" label="备注" min-width="160" show-overflow-tooltip />
        </el-table>
        <template v-if="matrix?.unregistered.length">
          <h3 class="matrix-sub">库内有数据但未登记发布状态的批次（登记遗漏）</h3>
          <el-table :data="matrix.unregistered" size="small" border fit>
            <el-table-column prop="year" label="年份" width="80" />
            <el-table-column prop="category" label="类别" width="90" />
            <el-table-column prop="subject" label="学科类" width="110" />
            <el-table-column prop="batch" label="批次" width="130" />
            <el-table-column prop="records" label="库内记录" width="100" align="right">
              <template #default="{ row }"><span class="tnum">{{ row.records.toLocaleString() }}</span></template>
            </el-table-column>
          </el-table>
        </template>
      </el-tab-pane>

      <!-- 往年征集参考（P6）：最坏情况安全网，明确标注不参与匹配 -->
      <el-tab-pane label="往年征集参考" name="collection">
        <el-alert
          v-if="collData"
          type="warning"
          :title="collData.note"
          show-icon
          :closable="false"
          class="coll-alert"
        />
        <div class="filters wrap">
          <el-select v-model="collFilters.category" class="f-sel" @change="onCollCategoryChange()">
            <el-option v-for="c in (meta?.categories || [])" :key="c" :label="c" :value="c" />
          </el-select>
          <el-select v-model="collFilters.subject" placeholder="学科类" aria-label="学科类" clearable class="f-sel" @change="loadColl()">
            <el-option v-for="s in (meta?.subjects || [])" :key="s" :label="s" :value="s" />
          </el-select>
          <el-select v-model="collFilters.batch" placeholder="批次" aria-label="批次" clearable class="f-sel" @change="loadColl()">
            <el-option v-for="b in collBatchOptions" :key="b" :label="b" :value="b" />
          </el-select>
          <el-input
            v-model.number="collFilters.rank"
            type="number"
            :min="1"
            placeholder="你的位次（可选）"
            aria-label="你的位次"
            clearable
            class="f-q"
            @keyup.enter="loadColl()"
          />
          <el-button type="primary" @click="loadColl()">查询</el-button>
        </div>
        <p v-if="collData?.band" class="coll-band">
          位次带：<span class="tnum">{{ collData.band.lo.toLocaleString() }}</span> –
          <span class="tnum">{{ collData.band.hi.toLocaleString() }}</span>（你的位次 ±30%），
          共 {{ collData.items.length }} 条征集记录（最多展示 400 条）
        </p>
        <div v-if="collData && !collData.items.length" class="empty">该条件下无征集记录：往年此范围内没有院校专业进入征集，或尚未入库。</div>
        <el-table v-if="collData && collData.items.length" :data="collData.items" size="small" border fit>
          <el-table-column prop="year" label="年份" width="80" />
          <el-table-column prop="batch" label="批次" width="130" />
          <el-table-column prop="school_name" label="院校" min-width="150" show-overflow-tooltip />
          <el-table-column prop="major_name" label="专业" min-width="150" show-overflow-tooltip />
          <el-table-column prop="score_kind" label="类型" width="90" />
          <el-table-column prop="lowest_score" label="最低分" width="90" align="right">
            <template #default="{ row }"><span class="tnum" v-if="row.lowest_score != null">{{ row.lowest_score }}</span></template>
          </el-table-column>
          <el-table-column prop="lowest_rank" label="最低位次" width="100" align="right">
            <template #default="{ row }"><span class="tnum" v-if="row.lowest_rank != null">{{ row.lowest_rank.toLocaleString() }}</span></template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 专业冷热趋势（migration 0017）：方法、阈值、自检与全量表，对应「可解释可溯源」原则 -->
      <el-tab-pane label="专业冷热趋势" name="trend">
        <el-alert type="info" :closable="false" show-icon class="coll-alert"
          title="趋势说明的是「历史最难年还值不值得当参考」，不是报考建议。三年数据只给出两个年段，不用于预测明年门槛；不覆盖艺术类、体育类与提前批（含公费师范/公安/军校）。" />

        <div class="tr-method">
          <h4 class="tr-h">怎么算出来的</h4>
          <ol class="tr-ol">
            <li><b>位次先百分位化</b>：门槛位次 ÷ 当年该学科类考生总数。辽宁 2025 历史类考生比 2024 年多 29.3%，同一个位次在两年里含金量完全不同，直接比会得出错误结论。</li>
            <li><b>同单元跨年配对</b>：以「院校 + 规范化专业名 + 批次」为身份逐年对照。<b>不用省内专业代码</b>——它是逐年重排的顺序号，按代码归并会把不同专业接成一条时间线。</li>
            <li><b>扣掉全省大盘漂移</b>：每个「学科类 × 批次 × 年段」取全部配对单元变动的中位数作基准，只谈超出基准的部分。不扣的话几乎所有专业都会被误判成在变松。</li>
            <li><b>阈值由数据自己给</b>：把该格子全部单元的超额漂移打散，随机抽 n 个算中位数、重复 2 万次得到零分布，取双侧 95% 分位作为该 n 下的显著性门槛。开设院校越少，阈值越高——避免小专业被噪声误判成趋势。</li>
            <li><b>趋势 vs 大小年看方向一致性</b>：两个年段同向且都显著才算「连降/连升两年」；一升一降是「大小年波动」；只有一段显著是「近一年跳变」。</li>
          </ol>
          <p class="tr-p">
            <b>自检</b>：把专业标签随机打乱后用同一套判据重跑，529 个可判定专业中被判「持续趋势」的有
            <b>0 个</b>；真实数据是 320 个可判定专业中 61 个（19%）。信号与噪声分离干净。
          </p>
          <p class="tr-p tr-p--muted">
            局限：① 三年只有两个年段，趋势判断置信度有限；② 招生计划人数尚未入库，只能用「在辽招生单元数」做供给代理；
            ③ 2024–2026 的选科要求变化无法核查；④ 结论只适用于辽宁。
          </p>
        </div>

        <div v-if="trendMarket.length" class="tr-method">
          <h4 class="tr-h">全省大盘漂移基准（趋势口径的分母）</h4>
          <el-table :data="trendMarket" size="small" border fit>
            <el-table-column prop="subject" label="学科类" width="110" />
            <el-table-column prop="batch" label="批次" width="90" />
            <el-table-column label="年段" width="120">
              <template #default="{ row }">{{ row.year_from }} → {{ row.year_to }}</template>
            </el-table-column>
            <el-table-column label="整体门槛变动" min-width="140" align="right">
              <template #default="{ row }">
                <span class="tnum">{{ ((Math.exp(row.drift_log) - 1) * 100).toFixed(1) }}%</span>
                <span class="tr-m">（正 = 整体变松）</span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="filters wrap">
          <el-select v-model="trendFilters.subject" placeholder="学科类" aria-label="学科类" clearable class="f-sel" @change="loadTrend(1)">
            <el-option label="物理学科类" value="物理学科类" />
            <el-option label="历史学科类" value="历史学科类" />
          </el-select>
          <el-select v-model="trendFilters.batch" placeholder="批次" aria-label="批次" clearable class="f-sel" @change="loadTrend(1)">
            <el-option label="本科批" value="本科批" />
            <el-option label="专科批" value="专科批" />
          </el-select>
          <el-select v-model="trendFilters.label" placeholder="趋势标签" aria-label="趋势标签" clearable class="f-sel" @change="loadTrend(1)">
            <el-option v-for="d in (meta?.trend_dictionary || [])" :key="d.label" :label="d.display" :value="d.label" />
          </el-select>
          <el-input v-model="trendFilters.q" placeholder="专业名关键词" aria-label="专业名关键词" clearable class="f-q" @keyup.enter="loadTrend(1)" />
          <el-button type="primary" @click="loadTrend(1)">查询</el-button>
        </div>

        <div v-if="trendData?.unavailable" class="empty">趋势数据尚未入库（需执行 migration 0017 + etl/load_major_trend.py）。</div>
        <el-table v-else-if="trendData" :data="trendData.items" size="small" border fit>
          <el-table-column prop="major_key" label="专业" min-width="150" show-overflow-tooltip />
          <el-table-column prop="subject" label="学科类" width="100" />
          <el-table-column prop="batch" label="批次" width="85" />
          <el-table-column label="趋势" width="140">
            <template #default="{ row }">
              {{ (meta?.trend_dictionary || []).find((d) => d.label === row.label)?.display || row.label }}
            </template>
          </el-table-column>
          <el-table-column label="等效分变化" width="150" align="right">
            <template #default="{ row }">
              <span v-if="row.eq_score_delta != null" class="tnum">
                {{ row.eq_score_delta > 0 ? '+' : '' }}{{ row.eq_score_delta }} 分
              </span>
              <span v-if="row.eq_score_delta_market != null" class="tr-m">
                （大盘 {{ row.eq_score_delta_market > 0 ? '+' : '' }}{{ row.eq_score_delta_market }}）
              </span>
            </template>
          </el-table-column>
          <el-table-column label="院校数" width="80" align="right">
            <template #default="{ row }"><span class="tnum">{{ row.n_pairs_2 ?? row.n_pairs_1 ?? '—' }}</span></template>
          </el-table-column>
          <el-table-column label="同向率" width="85" align="right">
            <template #default="{ row }">
              <span v-if="row.concord_2 != null" class="tnum">{{ Math.round(row.concord_2 * 100) }}%</span>
            </template>
          </el-table-column>
          <el-table-column label="在辽招生单元" min-width="140" align="right">
            <template #default="{ row }">
              <span class="tnum">{{ row.units[2024] }} → {{ row.units[2025] }} → {{ row.units[2026] }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-if="trendData && trendData.total > trendData.page_size"
          class="pager"
          layout="prev, pager, next, total"
          :current-page="trendData.page"
          :page-size="trendData.page_size"
          :total="trendData.total"
          @current-change="loadTrend"
        />
      </el-tab-pane>

      <!-- 选科要求三表（D2b）：官方 2027 选考科目要求原样浏览 -->
      <el-tab-pane label="选科要求" name="xk">
        <el-alert
          type="info"
          show-icon
          :closable="false"
          class="xk-alert"
          :title="xkSummary?.note || XK_NOTE"
        />
        <div v-if="xkSummary?.items.length" class="xk-sum">
          <span v-for="it in xkSummary.items" :key="`${it.year}-${it.table}`" class="xk-sum__chip">
            {{ it.year }} {{ XK_TABLE_LABEL[it.table] || it.table }}：
            <span class="tnum">{{ it.rows.toLocaleString() }}</span> 行 ·
            <span class="tnum">{{ it.schools.toLocaleString() }}</span> 所院校
          </span>
        </div>
        <div class="filters wrap">
          <el-select v-model="xkFilters.year" placeholder="年份" aria-label="年份" clearable class="f-sel" @change="onXkFilter()">
            <el-option v-for="y in xkYears" :key="y" :label="y" :value="y" />
          </el-select>
          <el-select v-model="xkFilters.table" placeholder="表类型" aria-label="表类型" clearable class="f-sel" @change="onXkFilter()">
            <el-option label="本科（bk）" value="bk" />
            <el-option label="专科（zk）" value="zk" />
            <el-option label="军校（jx）" value="jx" />
          </el-select>
          <el-select v-model="xkFilters.first_req" placeholder="首选要求" aria-label="首选要求" clearable class="f-sel" @change="onXkFilter()">
            <el-option label="物理" value="物理" />
            <el-option label="历史" value="历史" />
            <el-option label="不限" value="不限" />
          </el-select>
          <el-input v-model="xkFilters.school" placeholder="院校名" aria-label="院校名" clearable class="f-q" @keyup.enter="onXkFilter()" />
          <el-input v-model="xkFilters.major" placeholder="专业名" aria-label="专业名" clearable class="f-q" @keyup.enter="onXkFilter()" />
          <el-button @click="onXkFilter()">查询</el-button>
          <el-pagination
            v-if="xkData"
            layout="prev, pager, next, total"
            :total="xkData.total"
            :page-size="xkData.page_size"
            v-model:current-page="xkPage"
            class="pg"
          />
        </div>
        <div v-if="xkData && !xkData.items.length" class="empty">无符合条件的选科要求记录，请调整筛选。</div>
        <el-table v-if="xkData && xkData.items.length" :data="xkData.items" size="small" border fit>
          <el-table-column label="表" width="70">
            <template #default="{ row }">{{ XK_TABLE_LABEL[row.table] || '—' }}</template>
          </el-table-column>
          <el-table-column prop="school_code" label="院校代码" width="90" />
          <el-table-column prop="school_name" label="院校" min-width="140" show-overflow-tooltip />
          <el-table-column prop="major_code" label="专业代码" width="90" />
          <el-table-column prop="major_name" label="专业（类）" min-width="160" show-overflow-tooltip />
          <el-table-column label="首选要求" width="100">
            <template #default="{ row }">
              <el-tag
                size="small"
                effect="plain"
                :type="row.first_req === '不限' ? 'success' : row.first_req === '历史' ? 'warning' : ''"
              >{{ row.first_req || '—' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="再选要求" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.re_req">{{ row.re_req }}</span>
              <span v-else class="dim">无要求</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.tr-method { margin-bottom: var(--space-4); }
.tr-h { font-size: var(--text-sm); font-weight: 600; margin: 0 0 var(--space-2); color: var(--color-text); }
.tr-ol { margin: 0 0 var(--space-2); padding-left: 1.3em; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.8; }
.tr-p { margin: 0 0 var(--space-2); color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.7; }
.tr-p--muted { color: var(--color-text-muted); font-size: var(--text-xs); }
.tr-m { font-size: var(--text-xs); color: var(--color-text-muted); margin-left: 4px; }

.lib-eyebrow { display: inline-flex; align-items: center; gap: var(--space-2); font-size: var(--text-xs); color: var(--color-text-muted); margin-bottom: var(--space-2); }
.lib-eyebrow__dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-text-muted); }
.page__title { font-size: var(--text-2xl); }
.page__sub { color: var(--color-text-secondary); margin: var(--space-2) 0 var(--space-4); }
.card { margin-bottom: var(--space-4); }
.filters { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-3); margin-bottom: var(--space-4); }
.filters.wrap { row-gap: var(--space-3); }
.f-sel { width: 140px; }
.f-q { width: 160px; }
.pg { margin-left: auto; }
.tabs :deep(.el-tabs__content) { padding-top: var(--space-2); }
.matrix-note { color: var(--color-text-secondary); font-size: var(--text-sm); margin: 0 0 var(--space-3); }
.matrix-sub { margin: var(--space-5) 0 var(--space-2); font-size: var(--text-base); }
.coll-alert { margin-bottom: var(--space-4); }
.coll-band { color: var(--color-text-secondary); font-size: var(--text-sm); margin: 0 0 var(--space-3); }
.xk-alert { margin-bottom: var(--space-4); }
.xk-sum { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-3); }
.xk-sum__chip { font-size: var(--text-xs); color: var(--color-text-secondary); border: 1px solid var(--color-border, #e3e8ef); border-radius: 999px; padding: 3px 10px; }
.dim { color: var(--color-text-muted); }
:deep(.matrix-gap) td { background: var(--el-color-danger-light-9) !important; }
.empty { padding: var(--space-8); text-align: center; color: var(--color-text-muted); }

/* 移动端优先（PRODUCT.md 硬要求）：筛选栏改单列堆叠 */
@media (max-width: 640px) {
  .filters { flex-direction: column; align-items: stretch; }
  .f-sel, .f-q { width: 100%; }
  .pg { margin-left: 0; }
}
</style>
