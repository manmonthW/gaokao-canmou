<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AdvisorPanel from '@/components/advisor/AdvisorPanel.vue'

const route = useRoute()
const router = useRouter()
const mode = computed(() => String(route.query.mode || '问答'))
const question = computed(() => String(route.query.q || ''))
const pageContext = computed<Record<string, unknown>>(() => {
  try {
    return JSON.parse(sessionStorage.getItem('ln-zhiyuan-advisor-context') || '{}')
  } catch {
    return {}
  }
})
</script>

<template>
  <div class="advisor-page">
    <button type="button" class="advisor-back" @click="router.back()">← 返回</button>
    <AdvisorPanel :mode="mode" :initial-question="question" :page-context="pageContext" />
  </div>
</template>

<style scoped>
.advisor-page { position: fixed; inset: 0; z-index: 100; background: var(--color-surface); }
.advisor-back { position: fixed; z-index: 101; top: 17px; right: 16px; border: 0; background: transparent; color: var(--color-primary); cursor: pointer; }
</style>
