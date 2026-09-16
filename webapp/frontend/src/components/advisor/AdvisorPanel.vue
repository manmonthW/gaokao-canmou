<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { useProfile } from '@/composables/useProfile'
import { useAdvisor } from '@/composables/useAdvisor'
import AnswerView from './AnswerView.vue'

const props = withDefaults(defineProps<{ mode?: string; initialQuestion?: string; pageContext?: Record<string, unknown> }>(), {
  mode: '问答', initialQuestion: '', pageContext: () => ({}),
})
const { profile } = useProfile()
const advisor = useAdvisor()
const message = ref(props.initialQuestion)
const feedbackSent = ref(false)

async function submit() {
  const value = message.value
  message.value = ''
  feedbackSent.value = false
  await advisor.submit(value, props.mode, { ...profile.value }, props.pageContext)
}
async function sendFeedback(helpful: boolean) {
  await advisor.feedback(helpful)
  feedbackSent.value = true
}
onBeforeUnmount(advisor.stopPolling)
</script>

<template>
  <div class="advisor-panel">
    <header class="advisor-head">
      <div><span class="advisor-mark">参</span><div><strong>志愿参谋</strong><small>{{ profile.subject }} · {{ profile.rank ? `位次 ${profile.rank.toLocaleString()}` : '待补充位次' }}</small></div></div>
      <el-button v-if="advisor.busy.value" link @click="advisor.cancel">取消分析</el-button>
    </header>

    <main class="advisor-body">
      <div v-if="!advisor.job.value && !advisor.error.value" class="advisor-intro">
        <h2>先查数据，再给判断</h2>
        <p>可以问选校范围，也可以从匹配结果中追问某个院校专业为什么被分到这一档。</p>
        <div class="suggestions">
          <button type="button" @click="message = '按我的位次，推荐一些稳档的计算机类专业'">稳档计算机类</button>
          <button type="button" @click="message = '我想留在东北，哪些学校比较匹配？'">东北地区选校</button>
        </div>
      </div>

      <div v-if="advisor.events.value.length" class="timeline" aria-live="polite">
        <div v-for="event in advisor.events.value" :key="event.seq"><span></span>{{ event.message }}</div>
      </div>
      <el-alert v-if="advisor.error.value" :title="advisor.error.value" type="error" :closable="false" show-icon />
      <el-alert v-if="advisor.job.value?.error_message" :title="advisor.job.value.error_message" type="warning" :closable="false" show-icon />
      <p v-if="advisor.job.value?.result?.clarify" class="clarify">{{ advisor.job.value.result.clarify }}</p>
      <AnswerView v-if="advisor.job.value?.result?.answer" :answer="advisor.job.value.result.answer" :evidence="advisor.job.value.result.evidence || []" />
      <div v-if="advisor.job.value?.status === 'ready' && !feedbackSent" class="feedback">
        <span>这次分析有帮助吗？</span>
        <el-button size="small" @click="sendFeedback(true)">有帮助</el-button>
        <el-button size="small" @click="sendFeedback(false)">需改进</el-button>
      </div>
      <span v-else-if="feedbackSent" class="feedback-done">感谢反馈</span>
    </main>

    <form class="advisor-compose" @submit.prevent="submit">
      <el-input v-model="message" type="textarea" :rows="2" maxlength="500" show-word-limit placeholder="问选校范围、分档依据或专业情况" aria-label="向志愿参谋提问" />
      <el-button type="primary" native-type="submit" :loading="advisor.busy.value" :disabled="!message.trim() || advisor.busy.value">发送</el-button>
    </form>
  </div>
</template>

<style scoped>
.advisor-panel { height: 100%; min-height: 560px; display: grid; grid-template-rows: auto 1fr auto; background: var(--color-surface); }
.advisor-head { display: flex; justify-content: space-between; align-items: center; padding: var(--space-4) var(--space-5); border-bottom: 1px solid var(--color-border); }
.advisor-head > div { display: flex; align-items: center; gap: var(--space-3); }
.advisor-head strong, .advisor-head small { display: block; }
.advisor-head small { color: var(--color-text-muted); margin-top: 2px; }
.advisor-mark { width: 34px; height: 34px; display: grid; place-items: center; border-radius: var(--radius-sm); color: white; background: var(--color-primary); font-weight: 700; }
.advisor-body { overflow-y: auto; padding: var(--space-5); display: flex; flex-direction: column; gap: var(--space-5); }
.advisor-intro { margin: auto 0; padding: var(--space-8) var(--space-4); text-align: center; }
.advisor-intro h2 { margin: 0 0 var(--space-3); }
.advisor-intro p { color: var(--color-text-secondary); line-height: 1.7; }
.suggestions { display: flex; justify-content: center; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-5); }
.suggestions button { border: 1px solid var(--color-border); background: white; border-radius: 999px; padding: 8px 12px; color: var(--color-primary); cursor: pointer; }
.timeline { display: grid; gap: var(--space-2); color: var(--color-text-secondary); font-size: var(--text-sm); }
.timeline div { display: flex; align-items: center; gap: var(--space-2); }
.timeline span { width: 7px; height: 7px; border-radius: 50%; background: var(--color-match); }
.clarify { padding: var(--space-4); background: var(--color-primary-soft); border-radius: var(--radius-md); line-height: 1.7; }
.feedback { display: flex; gap: var(--space-2); align-items: center; padding-top: var(--space-4); border-top: 1px solid var(--color-border); color: var(--color-text-muted); font-size: var(--text-sm); }
.feedback-done { color: var(--color-match-text); font-size: var(--text-sm); }
.advisor-compose { display: grid; grid-template-columns: 1fr auto; gap: var(--space-3); align-items: end; padding: var(--space-4); border-top: 1px solid var(--color-border); background: var(--color-bg-subtle); }
@media (max-width: 640px) { .advisor-panel { min-height: 100dvh; } .advisor-head, .advisor-body { padding-left: var(--space-4); padding-right: var(--space-4); } }
</style>
