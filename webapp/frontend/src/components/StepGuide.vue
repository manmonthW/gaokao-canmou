<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useJourney } from '@/composables/useJourney'
import { EXAMINEE_YEAR } from '@/composables/useProfile'

/**
 * 主线步骤向导：醒目、可交互，替代原来页面顶部的纯灰字说明。
 * - 三步做成大卡片，当前步高亮、已完成打勾、可点击跳转；
 * - 顶部一句大标题告诉用户「现在该做什么」；
 * - 右侧主行动按钮引导进入下一步（如「去选学校 →」）。
 */
const props = defineProps<{ current: 'locate' | 'match' | 'workbench' }>()
const router = useRouter()
const j = useJourney()

interface StepDef {
  key: 'locate' | 'match' | 'workbench'
  index: number
  to: string
  title: string
  desc: string
  done: boolean
  warn: boolean
  summary: string
}

const steps = computed<StepDef[]>(() => [
  {
    key: 'locate', index: 1, to: '/',
    title: '我的定位', desc: '填入全省位次，看它相当于往年多少分',
    done: j.locateDone.value, warn: false, summary: j.locateSummary.value,
  },
  {
    key: 'match', index: 2, to: '/match',
    title: '智能匹配', desc: '按位次挑出冲 / 稳 / 保的院校专业',
    done: j.matchStarted.value, warn: false, summary: j.matchSummary.value,
  },
  {
    key: 'workbench', index: 3, to: '/workbench',
    title: '决策工作台', desc: '体检梯度、排序并导出志愿表',
    done: j.planStats.value.entries > 0, warn: j.workbenchWarn.value,
    summary: j.workbenchSummary.value,
  },
])

// 当前步的引导语与主行动
const lead = computed(() => {
  switch (props.current) {
    case 'locate':
      return j.locateDone.value
        ? { title: '定位完成，下一步去选学校', hint: `你是 ${EXAMINEE_YEAR} 年考生，位次已记录。`, cta: '去智能匹配选学校 →', to: '/match', show: true }
        : { title: `第 1 步 · 先告诉我你的全省位次`, hint: '位次是跨年可比的锚点，本工具全部基于位次法。填好后点「定位」。', cta: '', to: '', show: false }
    case 'match':
      if (!j.locateDone.value)
        return { title: '请先完成第 1 步：我的定位', hint: '智能匹配需要你的全省位次。', cta: '← 回到我的定位', to: '/', show: true }
      return { title: '第 2 步 · 挑出适合你的院校专业', hint: '在下方冲 / 稳 / 保里挑选，点「+方案」加入。挑好后去工作台整理。', cta: j.favCount.value ? '去决策工作台整理 →' : '', to: '/workbench', show: !!j.favCount.value }
    case 'workbench':
      return { title: '第 3 步 · 整理并导出你的志愿表', hint: '检查冲稳保梯度是否合理，排好顺序后导出 xlsx。', cta: '', to: '', show: false }
    default:
      return { title: '', hint: '', cta: '', to: '', show: false }
  }
})

function go(to: string) {
  if (to) router.push(to)
}
</script>

<template>
  <section class="guide">
    <!-- 三步可点击卡片 -->
    <div class="guide__steps">
      <template v-for="(s, i) in steps" :key="s.key">
        <button
          class="gstep"
          :class="{
            'gstep--current': s.key === current,
            'gstep--done': s.done && !s.warn,
            'gstep--warn': s.warn,
          }"
          @click="go(s.to)"
        >
          <span class="gstep__badge">
            <span v-if="s.done && !s.warn">✓</span>
            <span v-else-if="s.warn">!</span>
            <span v-else>{{ s.index }}</span>
          </span>
          <span class="gstep__body">
            <span class="gstep__title">{{ s.title }}</span>
            <span class="gstep__desc">{{ s.desc }}</span>
            <span class="gstep__summary" v-if="s.done || s.warn">{{ s.summary }}</span>
          </span>
        </button>
        <span v-if="i < steps.length - 1" class="guide__arrow" aria-hidden="true">→</span>
      </template>
    </div>

    <!-- 当前步引导语 + 主行动 -->
    <div class="guide__lead">
      <div class="guide__lead-text">
        <span class="guide__lead-title">{{ lead.title }}</span>
        <span class="guide__lead-hint">{{ lead.hint }}</span>
      </div>
      <el-button v-if="lead.show && lead.cta" type="primary" size="large" @click="go(lead.to)">
        {{ lead.cta }}
      </el-button>
    </div>
  </section>
</template>

<style scoped>
.guide {
  margin-bottom: var(--space-5);
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--color-primary-soft), var(--color-surface));
  border: 1px solid var(--color-border);
}
.guide__steps {
  display: flex;
  align-items: stretch;
  gap: var(--space-2);
  overflow-x: auto;
}
.gstep {
  flex: 1 1 0;
  min-width: 180px;
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  text-align: left;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.12s;
}
.gstep:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.gstep--current {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-primary-soft);
}
.gstep__badge {
  flex: 0 0 28px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: var(--text-base);
  background: var(--color-border);
  color: var(--color-text-secondary);
}
.gstep--current .gstep__badge { background: var(--color-primary); color: #fff; }
.gstep--done .gstep__badge { background: var(--color-match); color: #fff; }
.gstep--warn .gstep__badge { background: var(--color-danger); color: #fff; }
.gstep__body { display: flex; flex-direction: column; gap: 2px; }
.gstep__title { font-weight: 600; font-size: var(--text-base); color: var(--color-text); }
.gstep__desc { font-size: var(--text-xs); color: var(--color-text-muted); line-height: 1.5; }
.gstep__summary {
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--color-primary);
}
.gstep--warn .gstep__summary { color: var(--color-danger); }
.guide__arrow {
  align-self: center;
  color: var(--color-text-muted);
  font-size: var(--text-xl);
  flex: 0 0 auto;
}
.guide__lead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px dashed var(--color-border-strong);
}
.guide__lead-text { display: flex; flex-direction: column; gap: var(--space-1); }
.guide__lead-title { font-size: var(--text-xl); font-weight: 700; color: var(--color-text); }
.guide__lead-hint { font-size: var(--text-sm); color: var(--color-text-secondary); }

@media (max-width: 640px) {
  .guide__arrow { display: none; }
  .guide__steps { flex-direction: column; }
}
</style>
