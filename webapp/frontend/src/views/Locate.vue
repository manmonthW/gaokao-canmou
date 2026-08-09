<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/api/client'
import { useProfile, EXAMINEE_YEAR } from '@/composables/useProfile'
import type { RankContext, EstimateRankResponse, SubjectCombosResponse, SubjectCombo } from '@/types'
import DataStatusBanner from '@/components/DataStatusBanner.vue'
import StepGuide from '@/components/StepGuide.vue'

const router = useRouter()
const { profile } = useProfile()

const meta = ref<any>(null)
const result = ref<RankContext | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

// 再选科目（与匹配页同一档案，最多 2 门）
const ELECTIVES = ['化学', '生物', '政治', '地理']
function onElectivesChange(v: string[]) {
  if (v.length > 2) profile.value.electives = v.slice(0, 2)
}

// ---------- 选科组合专业覆盖率联动（全国通用参考值，非辽宁专属口径） ----------
const combos = ref<SubjectCombosResponse | null>(null)
const comboDialog = ref(false)
const comboView = ref<{ title: string; cid: string } | null>(null)
const myCombo = computed<SubjectCombo | null>(() => {
  const list = combos.value?.items || []
  const first = profile.value.subject?.includes('物理') ? '物理'
    : profile.value.subject?.includes('历史') ? '历史' : null
  const els = [...(profile.value.electives || [])].sort()
  if (!first || els.length !== 2) return null
  return list.find((c) => c.first === first &&
    c.electives.length === 2 &&
    [...c.electives].sort().join('+') === els.join('+')) || null
})
function openComboDetail(c: SubjectCombo) {
  comboView.value = { title: `${c.first} + ${c.electives.join(' + ')} · 专业覆盖率 ≈ ${c.coverage}%`, cid: c.id }
  comboDialog.value = true
}
function openComboOverview() {
  comboView.value = { title: '12 种选科组合专业覆盖率总览', cid: 'overview' }
  comboDialog.value = true
}

onMounted(async () => {
  meta.value = await api.meta().catch(() => null)
  combos.value = await api.subjectCombos().catch(() => null)
})

async function onSubmit() {
  error.value = null
  result.value = null
  const isInterval = profile.value.rank_mode === 'interval'
  if (isInterval) {
    if (!profile.value.rank_lo || !profile.value.rank_hi ||
        profile.value.rank_lo <= 0 || profile.value.rank_hi <= 0 ||
        profile.value.rank_lo > profile.value.rank_hi) {
      error.value = '请填写估计位次区间：上下界均为正整数，且下界 ≤ 上界。'
      return
    }
  } else if (!profile.value.rank || profile.value.rank <= 0) {
    error.value = '请填写你的全省位次（正整数）——它是本工具的定位锚点；备考期可切换「估计位次区间」或用下方线差法估算。'
    return
  }
  loading.value = true
  try {
    result.value = await api.rankContext({
      category: profile.value.category,
      subject: profile.value.subject,
      rank: isInterval ? profile.value.rank_hi : profile.value.rank,
      batch: profile.value.batch || undefined,
    })
    if (result.value?.error) error.value = result.value.error
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

// ---------- P1 备考期：线差法估位（模考分 → 线差 → 历史同年线差对应位次） ----------
const est = ref<EstimateRankResponse | null>(null)
const estLoading = ref(false)
const estScore = ref<number | null>(null)
const estLine = ref<number | null>(null)
async function runEstimate() {
  error.value = null
  est.value = null
  estLoading.value = true
  try {
    est.value = await api.estimateRank({
      category: profile.value.category,
      subject: profile.value.subject,
      batch: profile.value.batch || '本科批',
      score: estScore.value ?? undefined,
      mock_line: estLine.value ?? undefined,
    })
    if (est.value?.error) error.value = est.value.error
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    estLoading.value = false
  }
}
function applyEstimate() {
  const s = est.value?.suggested_interval
  if (!s) return
  profile.value.rank_mode = 'interval'
  profile.value.rank_lo = s.lo
  profile.value.rank_hi = s.hi
  ElMessage.success(`已采用估计位次区间 ${s.lo.toLocaleString()} – ${s.hi.toLocaleString()}`)
}

function goMatch() {
  router.push('/match')
}

const refYearsText = computed(() => {
  if (result.value?.reference_years?.length) {
    return [...result.value.reference_years].sort().join(' / ')
  }
  // 兜底：取 /meta 全部历史数据年（年度接入免改文案）
  const ys = meta.value?.history_years as number[] | undefined
  return ys?.length ? ys.join(' / ') : '2024 / 2025 / 2026'
})
</script>

<template>
  <div class="page">
    <DataStatusBanner />

    <StepGuide current="locate" />

    <el-card class="card" shadow="never">
      <el-form :inline="false" label-width="96px" class="form">
        <div class="form__row">
          <el-form-item label="考生年份">
            <el-input :model-value="`${EXAMINEE_YEAR} 年（预报）`" disabled style="width: 160px" />
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
              <el-option v-for="e in ELECTIVES" :key="e" :label="e" :value="e" />
            </el-select>
            <span style="margin-left: 8px; font-size: 12px; color: #909399;">
              2027 选科要求已入库：首选不符无条件排除，填再选后再选不符也排除
            </span>
          </el-form-item>
        </div>
        <!-- 选科组合覆盖率联动：首选 + 两门再选齐备时显示 -->
        <div v-if="combos" class="combo-row">
          <template v-if="myCombo">
            <span class="combo-pill" @click="openComboDetail(myCombo)">
              你的组合 <b>{{ myCombo.first }} + {{ myCombo.electives.join(' + ') }}</b>
              · 专业覆盖率 ≈ <b class="tnum">{{ myCombo.coverage }}%</b>
              <span class="combo-pill__view">看组合分析 →</span>
            </span>
          </template>
          <span v-else class="combo-hint">
            选好学科类与两门再选科目后，可查看该组合的专业覆盖率
          </span>
          <el-link v-if="combos.overview_available" type="primary" :underline="false" @click="openComboOverview">
            12 种组合覆盖率总览
          </el-link>
          <span class="combo-note">{{ combos.note }}</span>
        </div>
        <div class="form__row">
          <el-form-item label="位次类型">
            <el-radio-group v-model="profile.rank_mode">
              <el-radio value="exact">出分后·精确位次</el-radio>
              <el-radio value="interval">备考期·估计位次区间</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="profile.rank_mode !== 'interval'" label="全省位次" required>
            <el-input v-model.number="profile.rank" type="number" style="width: 180px" placeholder="必填，如 13601" />
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
            <el-input v-model.number="profile.score" type="number" style="width: 160px" placeholder="选填，仅记录" />
          </el-form-item>
          <el-button type="primary" :loading="loading" @click="onSubmit">定位</el-button>
        </div>
        <p class="save-hint">
          出分后官方一分一段表会同时给出你的分数与省位次。请以<strong>位次</strong>为准；分数仅用于记录与导出，不参与换算。
          档案自动保存到本机，下一步「智能匹配」直接沿用。
        </p>
      </el-form>
    </el-card>

    <!-- P1 备考期：线差法估位工具 -->
    <el-card class="card" shadow="never">
      <template #header>
        <div class="card__head"><span>备考期·线差法估位（还没有高考位次？用模考成绩估算）</span></div>
      </template>
      <div class="form__row">
        <el-form-item label="模考分数">
          <el-input v-model.number="estScore" type="number" style="width: 140px" placeholder="如 580" />
        </el-form-item>
        <el-form-item label="模考批次线">
          <el-input v-model.number="estLine" type="number" style="width: 180px" placeholder="如学校划定的模考本科线 470" />
        </el-form-item>
        <el-button :loading="estLoading" @click="runEstimate">估算位次</el-button>
      </div>
      <template v-if="est && !est.error">
        <el-table :data="est.per_year" size="small" border class="est-table">
          <el-table-column prop="year" label="参考年" width="90" />
          <el-table-column prop="line" label="当年本科线" width="110" align="right" />
          <el-table-column prop="est_score" label="估计分（线+线差）" width="150" align="right" />
          <el-table-column label="对应位次" min-width="180" align="right">
            <template #default="{ row }">
              <span v-if="row.rank_range" class="tnum">
                {{ row.rank_range[0].toLocaleString() }} – {{ row.rank_range[1].toLocaleString() }}
              </span>
              <span v-else>{{ row.note || '—' }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-alert
          v-if="est.suggested_interval"
          type="warning"
          :closable="false"
          class="est-alert"
          :title="`此为估算：建议估计位次区间 ${est.suggested_interval.lo.toLocaleString()} – ${est.suggested_interval.hi.toLocaleString()}（已外扩 ±10% 覆盖模考误差）`"
        />
        <p class="hint">{{ est.note }}</p>
        <el-button v-if="est.suggested_interval" type="primary" @click="applyEstimate">
          采用该区间作为我的估计位次 →
        </el-button>
      </template>
    </el-card>

    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" class="card" />

    <template v-if="result && !result.error">
      <!-- 重点：位次的历史含义（主角） -->
      <div class="highlight">
        <div class="highlight__lead">
          <span class="highlight__k">你的全省位次</span>
          <span class="highlight__rank tnum">{{ result.rank.toLocaleString() }}</span>
          <span class="highlight__k">{{ profile.subject }} · {{ profile.category }}</span>
        </div>
        <div class="highlight__eq">
          <span class="highlight__eq-label">相当于历史参考年的分数水平：</span>
          <div class="eq-cards">
            <div v-for="e in result.equivalents" :key="e.year" class="eq-card">
              <span class="eq-card__year">{{ e.year }}</span>
              <span class="eq-card__score tnum" v-if="e.score != null">
                ≈ {{ e.score }} 分<span v-if="e.score_note" class="eq-card__note">（{{ e.score_note }}）</span>
              </span>
              <span class="eq-card__score eq-card__score--na" v-else>超出该年一分一段表</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 明确的下一步召唤 -->
      <div class="next-cta">
        <div class="next-cta__text">
          <b>定位完成。</b>下一步：看看哪些院校专业适合你的位次（冲 / 稳 / 保）。
        </div>
        <el-button type="primary" size="large" @click="goMatch">进入智能匹配 →</el-button>
      </div>

      <!-- 过线参考（位次法，历史参照） -->
      <el-card v-if="result.line_refs && result.line_refs.length" class="card" shadow="never">
        <template #header>
          <div class="card__head">
            <span>过线参考（历史参照）</span>
          </div>
        </template>
        <el-table :data="result.line_refs" size="small" border>
          <el-table-column prop="year" label="参考年" width="90" />
          <el-table-column prop="line_type" label="控制线" width="120">
            <template #default="{ row }">{{ row.line_type === '本科' ? '本科线' : row.line_type === '特殊类型' ? '特殊类型线' : row.line_type + '线' }}</template>
          </el-table-column>
          <el-table-column label="当年线分/对应位次" min-width="180" align="right">
            <template #default="{ row }">
              <span class="tnum">{{ row.line_score }} 分</span> ·
              <span class="tnum">约第 {{ row.line_rank.toLocaleString() }} 名</span>
            </template>
          </el-table-column>
          <el-table-column label="你的位置" min-width="180" align="center">
            <template #default="{ row }">
              <el-tag :type="row.passed_ref ? 'success' : 'info'" effect="light">
                {{ row.passed_ref ? '优于该线' : '低于该线' }}
              </el-tag>
              <span class="line-margin tnum" :class="row.margin >= 0 ? 'ahead' : 'behind'">
                {{ row.margin >= 0 ? '领先' : '落后' }} {{ Math.abs(row.margin).toLocaleString() }} 名
              </span>
            </template>
          </el-table-column>
        </el-table>
        <p class="hint">
          说明：以位次法与 {{ refYearsText }} 各年控制线对应位次比较，仅作<strong>历史参照</strong>；
          {{ EXAMINEE_YEAR }} 年实际控制线与分数尺度以辽宁省招考部门官方发布为准。
          <template v-if="result.note"> {{ result.note }}</template>
        </p>
      </el-card>
    </template>

    <!-- 空状态引导：操作流程图 -->
    <el-card v-if="!result || result.error" class="card tip" shadow="never">
      <template #header><div class="card__head"><span>三步完成一份志愿草案</span></div></template>
      <div class="flow">
        <div class="flow-step">
          <div class="flow-badge" style="--c: var(--color-primary); --c-soft: var(--color-primary-soft)">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s-7-5.5-9-10a5 5 0 0 1 9-3 5 5 0 0 1 9 3c-2 4.5-9 10-9 10z"/></svg>
          </div>
          <div class="flow-body">
            <div class="flow-step-title">1 · 我的定位（当前）</div>
            <div class="flow-step-desc">选类别、学科类与目标批次，填入你的<strong>全省位次</strong>，点「定位」。</div>
          </div>
        </div>

        <div class="flow-arrow" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </div>

        <div class="flow-step">
          <div class="flow-badge" style="--c: var(--color-reach); --c-soft: var(--color-reach-soft)">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17l6-6-6-6M12 19h8"/></svg>
          </div>
          <div class="flow-body">
            <div class="flow-step-title">2 · 智能匹配</div>
            <div class="flow-step-desc">系统按位次法给出冲 / 稳 / 保候选，把中意的加入方案。</div>
          </div>
        </div>

        <div class="flow-arrow" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </div>

        <div class="flow-step">
          <div class="flow-badge" style="--c: var(--color-match); --c-soft: var(--color-match-soft)">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
          </div>
          <div class="flow-body">
            <div class="flow-step-title">3 · 决策工作台</div>
            <div class="flow-step-desc">整理梯度、体检方案、导出志愿表。</div>
          </div>
        </div>
      </div>

      <div class="flow-foot">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/></svg>
        <span>本工具以 <b>{{ refYearsText }}</b> 已完成录取的数据作为历史参考，服务于 <b>{{ EXAMINEE_YEAR }}</b> 年考生。随时可用右上角 <b>「资料库」</b> 查院校、查专业、看省控线与一分一段表。</span>
      </div>
    </el-card>

    <!-- 选科组合分析图弹窗 -->
    <el-dialog v-model="comboDialog" :title="comboView?.title || ''" width="min(920px, 94vw)" top="5vh">
      <img
        v-if="comboView"
        :src="api.subjectComboImageUrl(comboView.cid)"
        :alt="comboView.title"
        class="combo-img"
      />
      <p class="hint">覆盖率为全国通用参考值（第三方整理），非辽宁省专属口径；实际可报范围以「智能匹配」的 2027 官方选科要求核验为准。</p>
    </el-dialog>
  </div>
</template>

<style scoped>
.hero { margin-bottom: var(--space-5); }
.hero h1 { font-size: var(--text-2xl); }
.hero__sub { color: var(--color-text-secondary); max-width: 760px; margin-top: var(--space-2); }
.card { margin-bottom: var(--space-4); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
.form__row { display: flex; flex-wrap: wrap; gap: var(--space-4); align-items: flex-end; }
.save-hint { font-size: var(--text-xs); color: var(--color-text-muted); margin: var(--space-2) 0 0; line-height: 1.7; }
/* 选科组合覆盖率联动 */
.combo-row { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-3); margin: var(--space-1) 0 0; }
.combo-pill {
  display: inline-flex; align-items: center; gap: var(--space-2);
  padding: 6px 14px; border-radius: 999px; cursor: pointer;
  background: var(--color-primary-soft); border: 1px solid var(--color-border);
  font-size: var(--text-sm); color: var(--color-text-secondary);
}
.combo-pill b { color: var(--color-primary); }
.combo-pill__view { font-size: var(--text-xs); color: var(--color-primary); }
.combo-hint { font-size: var(--text-xs); color: var(--color-text-muted); }
.combo-note { font-size: var(--text-xs); color: var(--color-text-muted); }
.combo-img { width: 100%; border-radius: var(--radius-md); border: 1px solid var(--color-border); }
.card__head { font-weight: 600; }

/* 位次历史含义（主角卡） */
.highlight {
  padding: var(--space-5);
  border-radius: var(--radius-lg);
  background: var(--color-primary-soft);
  border: 1px solid var(--color-border);
  margin-bottom: var(--space-4);
}
.highlight__lead { display: flex; align-items: baseline; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-4); }
.highlight__k { font-size: var(--text-sm); color: var(--color-text-muted); }
.highlight__rank { font-size: 40px; font-weight: 800; color: var(--color-primary); line-height: 1; }
.highlight__eq-label { font-size: var(--text-sm); color: var(--color-text-secondary); }
.eq-cards { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-top: var(--space-3); }
.eq-card {
  display: flex; flex-direction: column; gap: var(--space-1);
  padding: var(--space-3) var(--space-5);
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: var(--radius-md); min-width: 160px;
}
.eq-card__year { font-size: var(--text-xs); color: var(--color-text-muted); }
.eq-card__score { font-size: var(--text-xl); font-weight: 700; color: var(--color-text); }
.eq-card__score--na { font-size: var(--text-sm); font-weight: 400; color: var(--color-text-muted); }
.eq-card__note { font-size: var(--text-sm); font-weight: 400; color: var(--color-text-muted); }

/* 下一步召唤 */
.next-cta {
  display: flex; align-items: center; justify-content: space-between; gap: var(--space-4);
  flex-wrap: wrap; padding: var(--space-4) var(--space-5); margin-bottom: var(--space-4);
  border-radius: var(--radius-lg); border: 1px dashed var(--color-primary); background: var(--color-surface);
}
.next-cta__text { color: var(--color-text-secondary); font-size: var(--text-base); }

.line-margin { margin-left: var(--space-2); font-size: var(--text-sm); }
.line-margin.ahead { color: var(--color-match); }
.line-margin.behind { color: var(--color-text-muted); }
.hint { color: var(--color-text-muted); font-size: var(--text-xs); margin: var(--space-3) 0 0; line-height: 1.7; }
/* 操作流程图 */
.flow {
  display: flex;
  align-items: stretch;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.flow-step {
  flex: 1 1 200px;
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}
.flow-badge {
  flex: 0 0 auto;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--c);
  background: var(--c-soft);
}
.flow-body { min-width: 0; }
.flow-step-title {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-1);
}
.flow-step-desc {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: 1.7;
}
.flow-arrow {
  flex: 0 0 auto;
  align-self: center;
  color: var(--color-border-strong);
  display: flex;
}
.flow-foot {
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  color: var(--color-text-muted);
  font-size: var(--text-sm);
  line-height: 1.7;
}
.flow-foot svg { flex: 0 0 auto; margin-top: 2px; color: var(--color-primary); }
.flow-foot b { color: var(--color-text-secondary); }

@media (max-width: 720px) {
  .flow { flex-direction: column; }
  .flow-step { flex: 1 1 auto; }
  .flow-arrow { transform: rotate(90deg); align-self: center; padding: var(--space-1) 0; }
}
</style>
