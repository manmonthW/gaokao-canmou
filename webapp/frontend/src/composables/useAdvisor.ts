import { computed, ref } from 'vue'
import { api } from '@/api/client'
import type { AdvisorEvent, AdvisorHistoryTurn, AdvisorJob } from '@/types'

const STORAGE_KEY = 'ln-zhiyuan-advisor'
const TERMINAL = new Set(['ready', 'failed', 'timeout', 'cancelled'])
const CLIENT_TIMEOUT_MS = 90_000

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
let pollStartedAt = 0
let pollGeneration = 0
let lastSeq = 0
let transientFailures = 0

function saveHistory() {
  history.value = history.value.slice(-20)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(history.value))
}

function stopPolling() {
  pollGeneration += 1
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = null
}

async function poll(jobId: string, generation: number) {
  if (generation !== pollGeneration) return
  if (pollStartedAt && Date.now() - pollStartedAt > CLIENT_TIMEOUT_MS) {
    error.value = '本轮分析已超时，可以重新提问'
    try {
      await api.cancelAdvisorJob(jobId)
    } catch {
      // The backend may already have moved the job to a terminal state.
    }
    if (generation === pollGeneration && job.value?.job_id === jobId) {
      job.value.status = 'timeout'
      stopPolling()
    }
    return
  }
  try {
    const latest = await api.advisorJob(jobId, lastSeq)
    if (generation !== pollGeneration || job.value?.job_id !== jobId) return
    if (latest.events.length) events.value.push(...latest.events)
    lastSeq = latest.events.at(-1)?.seq || lastSeq
    transientFailures = 0
    job.value = { ...latest, events: [...events.value] }
    if (TERMINAL.has(latest.status)) {
      stopPolling()
      const assistant = latest.result?.answer?.summary || latest.result?.clarify
      if (assistant) {
        history.value.push({
          role: 'assistant', content: assistant, job_id: jobId,
          answer: latest.result?.answer || undefined,
          clarify: latest.result?.clarify || undefined,
        })
        saveHistory()
      }
      if (latest.status !== 'ready') error.value = latest.error_message || '本轮分析未完成'
      return
    }
    pollTimer = setTimeout(() => poll(jobId, generation), 1000)
  } catch (reason) {
    if (generation !== pollGeneration) return
    transientFailures += 1
    if (transientFailures <= 3) {
      pollTimer = setTimeout(() => poll(jobId, generation), Math.min(4000, 1000 * 2 ** transientFailures))
    } else {
      error.value = reason instanceof Error ? reason.message : '参谋服务暂时不可用'
      if (job.value) job.value.status = 'failed'
      stopPolling()
    }
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
      .map(({ role, content }) => ({ role, content }))
    const created = await api.createAdvisorJob({
      message: question,
      mode,
      profile,
      page_context: pageContext,
      history: recent,
    })
    history.value.push({ role: 'user', content: question, job_id: created.job_id })
    saveHistory()
    job.value = { job_id: created.job_id, status: created.status as AdvisorJob['status'], events: [] }
    pollStartedAt = Date.now()
    lastSeq = 0
    transientFailures = 0
    const generation = pollGeneration
    await poll(created.job_id, generation)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '参谋服务暂时不可用'
  }
}

async function cancel() {
  if (!job.value || TERMINAL.has(job.value.status)) return
  const jobId = job.value.job_id
  await api.cancelAdvisorJob(jobId)
  if (job.value?.job_id === jobId) job.value.status = 'cancelled'
  stopPolling()
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
