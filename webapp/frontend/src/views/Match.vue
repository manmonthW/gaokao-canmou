<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api/client'
import { useProfile, EXAMINEE_YEAR } from '@/composables/useProfile'
import { usePlanner, toSnapshot, candidateId } from '@/composables/usePlanner'
import type { MatchResponse, MatchCandidate, RiskLabel } from '@/types'
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

const totalForActive = computed(() =>
  data.value ? data.value.totals[activeRisk.value] : 0,
)

async function runMatch(resetPage = true) {
  if (resetPage) page.value = 1
  error.value = null
  if (!profile.value.rank) {
    error.value = '请先在上方填写全省位次（必填），可同时填分数辅助校验。'
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
      rank: profile.value.rank ?? undefined,
      score: profile.value.score ?? undefined,
      province: filters.value.province || undefined,
      city: filters.value.city || undefined,
      level: filters.value.level || undefined,
      nature: filters.value.nature || undefined,
      type: filters.value.type || undefined,
      major_keyword: filters.value.major_keyword || undefined,
      has_both_years: filters.value.has_both_years || undefined,
      exclude_flags: filters.value.exclude_flags.join(',') || undefined,
      electives: profile.value.electives?.length
        ? profile.value.electives.join(',')
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

// 批次数据口径提示（D4）：让每条结果知道自己处在什么数据环境下
const batchContextText = computed(() => {
  const bc = data.value?.batch_context
  if (!bc) return ''
  const pubs = bc.publication
    .map((p) => `${p.stage}：${p.status}${p.official_published_at ? `（官方发布 ${String(p.official_published_at).slice(0, 10)}）` : ''}`)
    .join('；')
  return bc.score_kind_note + (pubs ? ` 本批发布进度：${pubs}` : '')
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
  if (profile.value.rank) runMatch(true)
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
        <span class="profile-bar__seg profile-bar__seg--key tnum">位次 {{ profile.rank?.toLocaleString() ?? '未填' }}</span>
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
          <el-form-item label="全省位次" required>
            <el-input v-model.number="profile.rank" type="number" style="width: 170px" placeholder="必填" />
          </el-form-item>
          <el-form-item label="高考分数">
            <el-input v-model.number="profile.score" type="number" style="width: 150px" placeholder="选填，仅记录" />
          </el-form-item>
          <el-button type="primary" :loading="loading" @click="onProfileSubmit">应用并匹配</el-button>
        </div>
      </el-form>
    </el-card>

    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" class="card" />

    <template v-if="data">
      <!-- 风险档计数 -->
      <div class="risk-chips">
        <button
          v-for="r in RISKS"
          :key="r.key"
          class="chip"
          :class="['chip--' + r.type, { 'chip--active': activeRisk === r.key }]"
          @click="onRiskTab(r.key)"
        >
          <span class="chip__label">{{ r.label }}</span>
          <span class="chip__num">{{ data.totals[r.key] }}</span>
          <span class="chip__hint">{{ RISK_HINT[r.key] }}</span>
        </button>
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
        已按再选科目排除 {{ data.excluded_by_subject }} 个不符合选科要求的单元。
      </p>

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
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="yr">
                <span class="yr__t">历年最低位次：</span>
                <span v-for="y in row.yearly" :key="y.year" class="yr__item">
                  {{ y.year }}：<b class="tnum">{{ y.lowest_rank.toLocaleString() }}</b>
                </span>
                <span class="yr__m">（覆盖 {{ row.n_years }} 年）</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="school_name" label="院校" min-width="170" show-overflow-tooltip>
            <template #default="{ row }">
              <a class="school-link" @click.stop="openSchool(row.school_code)">{{ row.school_name }}</a>
            </template>
          </el-table-column>
          <el-table-column prop="major_name" label="专业" min-width="170" show-overflow-tooltip>
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
          <el-table-column label="近年最低位次（2026）" width="130" align="right">
            <template #default="{ row }"><span class="tnum">{{ row.last_year_rank?.toLocaleString() }}</span></template>
          </el-table-column>
          <el-table-column label="最好/最差/中位" align="right" min-width="170">
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
              {{ row.risk_reason }}
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

.school-link { color: var(--color-primary); cursor: pointer; }
.school-link:hover { text-decoration: underline; }
.major-link { color: var(--color-primary); cursor: pointer; }
.major-link:hover { text-decoration: underline; }

.chip__hint { font-size: var(--text-xs); color: var(--color-text-muted); }
.risk-chips { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-4); }
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
.flag-excl { display: inline-flex; flex-wrap: wrap; gap: var(--space-2); }
.flag-tag { margin-left: 4px; cursor: help; }
.hint { color: var(--color-text-muted); font-size: var(--text-xs); margin: var(--space-3) 0 0; line-height: 1.7; }
.dlg-hint { font-size: var(--text-sm); color: var(--color-text-secondary); margin: 0 0 var(--space-2); }
.plan-list { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.plan-btn__n { color: var(--color-text-muted); font-size: var(--text-xs); }
.plan-new { display: flex; gap: var(--space-2); }
</style>
