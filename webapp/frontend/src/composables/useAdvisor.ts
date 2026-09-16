import { computed, ref } from 'vue'
import { api } from '@/api/client'
import type { AdvisorEvent, AdvisorHistoryTurn, AdvisorJob } from '@/types'

const STORAGE_KEY = 'ln-zhiyuan-advisor'
const TERMINAL = new Set(['ready', 'failed', 'timeout', 'cancelled'])

function loadHistory(): AdvisorHistoryTurn[] {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(value) ? value.slice(-20) : []
  } catch {
    return []
  }
}

const history = ref<AdvisorHistoryTurn[]>(loadHistory())
const job = ref<AdvisorJob | null>(null)
const events = ref<AdvisorEvent[]>([])
const error = ref<string | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null

function saveHistory() {
  history.value = history.value.slice(-20)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(history.value))
}

function stopPolling() {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = null
}

async function poll(jobId: string) {
  try {
    const latest = await api.advisorJob(jobId, events.value.at(-1)?.seq || 0)
    if (latest.events.length) events.value.push(...latest.events)
    job.value = { ...latest, events: [...events.value] }
    if (TERMINAL.has(latest.status)) {
      stopPolling()
      const assistant = latest.result?.answer?.summary || latest.result?.clarify
      if (assistant) {
        history.value.push({ role: 'assistant', content: assistant })
        saveHistory()
      }
      return
    }
    pollTimer = setTimeout(() => poll(jobId), 1000)
  } catch (reason) {
    stopPolling()
    error.value = reason instanceof Error ? reason.message : '参谋服务暂时不可用'
  }
}

async function submit(message: string, mode = '问答', profile: Record<string, unknown> = {}, pageContext: Record<string, unknown> = {}) {
  const question = message.trim()
  if (!question) return
  stopPolling()
  error.value = null
  events.value = []
  job.value = null
  try {
    const recent = history.value.slice(-6)
    const created = await api.createAdvisorJob({
      message: question,
      mode,
      profile,
      page_context: pageContext,
      history: recent,
    })
    history.value.push({ role: 'user', content: question })
    saveHistory()
    job.value = { job_id: created.job_id, status: created.status as AdvisorJob['status'], events: [] }
    await poll(created.job_id)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '参谋服务暂时不可用'
  }
}

async function cancel() {
  if (!job.value || TERMINAL.has(job.value.status)) return
  await api.cancelAdvisorJob(job.value.job_id)
  await poll(job.value.job_id)
}

async function feedback(helpful: boolean) {
  if (job.value?.status === 'ready') await api.advisorFeedback(job.value.job_id, helpful)
}

function clearHistory() {
  history.value = []
  localStorage.removeItem(STORAGE_KEY)
}

const busy = computed(() => job.value != null && !TERMINAL.has(job.value.status))

export function useAdvisor() {
  return { history, job, events, error, busy, submit, cancel, feedback, clearHistory, stopPolling }
}
