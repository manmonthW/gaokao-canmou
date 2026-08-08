<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import type { DataStatusMatrix } from '@/types'

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

function onTab(tab: string) {
  if (tab === 'lines' && !lines.value.length) loadLines()
  if (tab === 'rank' && !rankData.value) loadRank()
  if (tab === 'records') loadRec()
  if (tab === 'pub' && !pubStatus.value.length) loadPub()
  if (tab === 'matrix' && !matrix.value) loadMatrix()
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

function onRankFilter() { rankPage.value = 1; loadRank() }
function onRecFilter() { recPage.value = 1; loadRec() }
</script>

<template>
  <div class="page">
    <div class="lib-eyebrow"><span class="lib-eyebrow__dot"></span>资料库 · 原始数据</div>
    <h1 class="page__title">数据中心</h1>
    <p class="page__sub">省控线、一分一段表、原始录取记录与批次发布状态。这里是原始数据溯源，一般决策看前面「定位 → 匹配 → 工作台」三步即可。</p>

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
          <el-select v-model="recFilters.year" placeholder="年份" clearable class="f-sel" @change="onRecFilter()">
            <el-option v-for="y in (meta?.years || [])" :key="y" :label="y" :value="y" />
          </el-select>
          <el-select v-model="recFilters.category" placeholder="类别" clearable class="f-sel" @change="onRecCategoryChange()">
            <el-option v-for="c in (meta?.categories || [])" :key="c" :label="c" :value="c" />
          </el-select>
          <el-select v-model="recFilters.subject" placeholder="学科类" clearable class="f-sel" @change="onRecFilter()">
            <el-option v-for="s in (meta?.subjects || [])" :key="s" :label="s" :value="s" />
          </el-select>
          <el-select v-model="recFilters.batch" placeholder="批次" clearable class="f-sel" @change="onRecFilter()">
            <el-option v-for="b in recBatchOptions" :key="b" :label="b" :value="b" />
          </el-select>
          <el-select v-model="recFilters.is_collection" placeholder="志愿类型" clearable class="f-sel" @change="onRecFilter()">
            <el-option label="常规" :value="false" />
            <el-option label="征集" :value="true" />
          </el-select>
          <el-input v-model="recFilters.school" placeholder="院校名" clearable class="f-q" @keyup.enter="onRecFilter()" />
          <el-input v-model="recFilters.major" placeholder="专业名" clearable class="f-q" @keyup.enter="onRecFilter()" />
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
    </el-tabs>
  </div>
</template>

<style scoped>
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
:deep(.matrix-gap) td { background: var(--el-color-danger-light-9) !important; }
.empty { padding: var(--space-8); text-align: center; color: var(--color-text-muted); }
</style>
