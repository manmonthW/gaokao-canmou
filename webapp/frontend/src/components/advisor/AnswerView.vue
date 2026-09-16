<script setup lang="ts">
import type { AdvisorAnswer, AdvisorEvidence } from '@/types'

defineProps<{ answer: AdvisorAnswer; evidence: AdvisorEvidence[] }>()

const toolNames: Record<string, string> = {
  locate_rank: '位次定位',
  search_candidates: '候选检索',
  get_unit_detail: '录取单元详情',
  get_school_profile: '院校资料',
  get_major_info: '专业资料',
  check_subject_req: '选科要求',
  rank_sensitivity: '位次敏感度',
}

function evidenceById(items: AdvisorEvidence[], eid: string) {
  return items.find((item) => item.eid === eid)
}
</script>

<template>
  <article class="answer">
    <p class="answer__summary">{{ answer.summary }}</p>

    <section v-for="section in answer.sections" :key="section.title" class="answer__section">
      <h3>{{ section.title }}</h3>
      <p>{{ section.body }}</p>
      <div v-if="section.evidence_ids.length" class="evidence-row">
        <el-popover v-for="eid in section.evidence_ids" :key="eid" width="340" trigger="click">
          <template #reference><button type="button" class="evidence-chip">{{ eid }}</button></template>
          <template v-if="evidenceById(evidence, eid)">
            <strong>{{ toolNames[evidenceById(evidence, eid)!.tool] || evidenceById(evidence, eid)!.tool }}</strong>
            <pre>{{ JSON.stringify(evidenceById(evidence, eid)!.data, null, 2) }}</pre>
          </template>
          <span v-else>该证据未随结果返回。</span>
        </el-popover>
      </div>
    </section>

    <section v-if="answer.recommended_units.length" class="answer__section">
      <h3>参考单元</h3>
      <div class="unit-list">
        <div v-for="unit in answer.recommended_units" :key="`${unit.school}-${unit.major}`" class="unit">
          <div><strong>{{ unit.school }}</strong><span>{{ unit.major }}</span></div>
          <span v-if="unit.risk" :class="['risk-tag', `risk-tag--${unit.risk === '冲' ? 'reach' : unit.risk === '稳' ? 'match' : unit.risk === '保' ? 'safe' : 'insufficient'}`]">{{ unit.risk }}</span>
          <small v-if="unit.rank_last">最近年最低位次 {{ unit.rank_last.toLocaleString() }}</small>
        </div>
      </div>
    </section>

    <section v-if="answer.caveats.length" class="answer__section answer__section--caveat">
      <h3>请特别留意</h3>
      <ul><li v-for="item in answer.caveats" :key="item">{{ item }}</li></ul>
    </section>

    <div v-if="answer.follow_ups.length" class="follow-ups">
      <span>还可以继续问：</span><span v-for="item in answer.follow_ups" :key="item">{{ item }}</span>
    </div>
    <p class="disclaimer">{{ answer.disclaimer || '以上基于历年投档数据的参考分析，不代表录取承诺，请以辽宁省招考办及院校官方信息为准。' }}</p>
  </article>
</template>

<style scoped>
.answer { display: grid; gap: var(--space-5); }
.answer__summary { margin: 0; padding: var(--space-4); border-left: 4px solid var(--color-primary); background: var(--color-primary-soft); color: var(--color-text); font-size: var(--text-base); line-height: 1.7; }
.answer__section { display: grid; gap: var(--space-2); }
.answer__section h3 { margin: 0; font-size: var(--text-base); }
.answer__section p, .answer__section ul { margin: 0; color: var(--color-text-secondary); line-height: 1.7; white-space: pre-wrap; }
.answer__section--caveat { padding: var(--space-4); background: var(--color-reach-soft); border-radius: var(--radius-md); }
.evidence-row { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.evidence-chip { border: 1px solid var(--color-primary); border-radius: 999px; padding: 2px 8px; color: var(--color-primary); background: white; cursor: pointer; }
pre { max-height: 260px; overflow: auto; padding: var(--space-3); background: var(--color-bg-subtle); white-space: pre-wrap; font-size: 12px; }
.unit-list { display: grid; gap: var(--space-2); }
.unit { display: grid; grid-template-columns: 1fr auto; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.unit strong, .unit span { margin-right: var(--space-2); }
.unit small { grid-column: 1 / -1; color: var(--color-text-muted); }
.follow-ups { display: flex; flex-wrap: wrap; gap: var(--space-2); color: var(--color-text-muted); font-size: var(--text-sm); }
.follow-ups span:not(:first-child) { padding: 4px 8px; background: var(--color-bg-subtle); border-radius: 999px; }
.disclaimer { margin: 0; padding-top: var(--space-3); border-top: 1px solid var(--color-border); color: var(--color-text-muted); font-size: var(--text-xs); line-height: 1.6; }
</style>
