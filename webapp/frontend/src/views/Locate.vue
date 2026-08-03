<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import { useProfile, EXAMINEE_YEAR } from '@/composables/useProfile'
import type { RankContext } from '@/types'
import DataStatusBanner from '@/components/DataStatusBanner.vue'
import StepGuide from '@/components/StepGuide.vue'

const router = useRouter()
const { profile } = useProfile()

const meta = ref<any>(null)
const result = ref<RankContext | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

onMounted(async () => {
  meta.value = await api.meta().catch(() => null)
})

async function onSubmit() {
  error.value = null
  result.value = null
  if (!profile.value.rank || profile.value.rank <= 0) {
    error.value = '请填写你的全省位次（正整数）——它是本工具的定位锚点。'
    return
  }
  loading.value = true
  try {
    result.value = await api.rankContext({
      category: profile.value.category,
      subject: profile.value.subject,
      rank: profile.value.rank,
      batch: profile.value.batch || undefined,
    })
    if (result.value?.error) error.value = result.value.error
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function goMatch() {
  router.push('/match')
}

const refYearsText = computed(() =>
  result.value?.reference_years?.length
    ? result.value.reference_years.join(' / ')
    : '2025 / 2026',
)
</script>

<template>
  <div class="page">
    <DataStatusBanner />

    <StepGuide current="locate" />

    <el-card class="card" shadow="never">
      <el-form :inline="false" label-width="96px" class="form">
        <div class="form__row">
          <el-form-item label="考生年份">
            <el-input :model-value="`${EXAMINEE_YEAR} 年（今年）`" disabled style="width: 160px" />
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
        </div>
        <div class="form__row">
          <el-form-item label="全省位次" required>
            <el-input v-model.number="profile.rank" type="number" style="width: 180px" placeholder="必填，如 13601" />
          </el-form-item>
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

    <!-- 空状态引导 -->
    <el-card v-if="!result || result.error" class="card tip" shadow="never">
      <template #header><div class="card__head"><span>三步完成一份志愿草案</span></div></template>
      <ol class="tip__list">
        <li><b>我的定位（当前）：</b>选类别、学科类与目标批次，填入你的<strong>全省位次</strong>，点「定位」。</li>
        <li><b>智能匹配：</b>系统按位次法给出冲 / 稳 / 保候选，把中意的加入方案。</li>
        <li><b>决策工作台：</b>整理梯度、体检方案、导出志愿表。</li>
      </ol>
      <p class="tip__foot">
        本工具以 {{ refYearsText }} 已完成录取的数据作为历史参考，服务于 {{ EXAMINEE_YEAR }} 年考生。
        随时可用右上角「资料库」查院校、查专业、看省控线与一分一段表。
      </p>
    </el-card>
  </div>
</template>

<style scoped>
.hero { margin-bottom: var(--space-5); }
.hero h1 { font-size: var(--text-2xl); }
.hero__sub { color: var(--color-text-secondary); max-width: 760px; margin-top: var(--space-2); }
.card { margin-bottom: var(--space-4); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
.form__row { display: flex; flex-wrap: wrap; gap: var(--space-4); align-items: flex-end; }
.save-hint { font-size: var(--text-xs); color: var(--color-text-muted); margin: var(--space-2) 0 0; line-height: 1.7; }
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
.tip__list { margin: 0; padding-left: var(--space-5); color: var(--color-text-secondary); line-height: 2; }
.tip__foot { color: var(--color-text-muted); font-size: var(--text-sm); margin: var(--space-3) 0 0; line-height: 1.7; }
</style>
