import { ref, computed } from 'vue'
import { api, setAuthToken } from '@/api/client'
import type { AuthUser } from '@/types'

/**
 * 认证状态（全局单例）+ 用户数据云同步。
 *
 * MVP 策略（与产品约定一致）：
 *  - token 存 localStorage（Bearer 头）；应用启动时恢复并校验；
 *  - 未登录仍可用（数据在 localStorage），登录后把本地方案上传服务端，
 *    之后以服务端为准，并在本地变化时防抖回写服务端。
 */

const TOKEN_KEY = 'ln-zhiyuan-token'
// 需要云同步的本地键（考生档案 / 收藏 / 对比 / 方案）
const SYNC_KEYS = [
  'ln-zhiyuan-profile',
  'ln-zhiyuan-favorites',
  'ln-zhiyuan-compare',
  'ln-zhiyuan-plans',
]

const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
const user = ref<AuthUser | null>(null)
const ready = ref(false) // 启动恢复是否完成
setAuthToken(token.value)

const isLoggedIn = computed(() => !!token.value && !!user.value)

function snapshotLocal(): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const k of SYNC_KEYS) {
    const raw = localStorage.getItem(k)
    if (raw != null) {
      try {
        out[k] = JSON.parse(raw)
      } catch {
        /* 跳过损坏项 */
      }
    }
  }
  return out
}

function applyToLocal(data: Record<string, unknown>) {
  for (const k of SYNC_KEYS) {
    if (k in data && data[k] != null) {
      localStorage.setItem(k, JSON.stringify(data[k]))
    }
  }
}

function setSession(t: string, u: AuthUser) {
  token.value = t
  user.value = u
  localStorage.setItem(TOKEN_KEY, t)
  setAuthToken(t)
}

function clearSession() {
  token.value = null
  user.value = null
  localStorage.removeItem(TOKEN_KEY)
  setAuthToken(null)
}

/** 清除本地已同步的用户数据（考生档案/收藏/对比/方案），并通知各 store 重置内存态。 */
function clearLocalUserData() {
  for (const k of SYNC_KEYS) {
    localStorage.removeItem(k)
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('ln-userdata-cleared'))
  }
}

let syncTimer: ReturnType<typeof setTimeout> | null = null

let restorePromise: Promise<void> | null = null

export function useAuth() {
  /**
   * 应用启动：校验 token 并加载该账号云端数据。
   * 登录必需模型：未登录（无 token / token 失效）时清空本地遗留数据，
   * 保证「未登录 = 无数据」。单飞（single-flight），路由守卫可 await。
   */
  function restore(): Promise<void> {
    if (ready.value) return Promise.resolve()
    if (restorePromise) return restorePromise
    restorePromise = (async () => {
      if (token.value) {
        try {
          user.value = await api.me()
          const { data } = await api.getUserData()
          if (data && Object.keys(data).length > 0) {
            applyToLocal(data)
          } else {
            // 云端为空：清掉可能残留的本地数据，避免展示旧数据
            for (const k of SYNC_KEYS) localStorage.removeItem(k)
          }
          window.dispatchEvent(new Event('ln-userdata-restored'))
        } catch {
          // token 失效/网络异常：退回未登录并清空本地
          clearSession()
          clearLocalUserData()
        }
      } else {
        // 无 token：确保本地无遗留用户数据
        clearLocalUserData()
      }
      ready.value = true
    })()
    return restorePromise
  }

  async function register(email: string, username: string, password: string) {
    const res = await api.register({ email, username, password })
    setSession(res.token, res.user)
    // 新账号：把本地已有方案上传作为初始云端数据
    await pushData()
  }

  async function login(loginId: string, password: string) {
    const res = await api.login({ login: loginId, password })
    // 清掉任何遗留本地数据，仅加载该账号云端数据
    for (const k of SYNC_KEYS) localStorage.removeItem(k)
    setSession(res.token, res.user)
    try {
      const { data } = await api.getUserData()
      if (data && Object.keys(data).length > 0) {
        applyToLocal(data)
      }
      window.dispatchEvent(new Event('ln-userdata-restored'))
    } catch {
      /* 忽略同步失败，不阻断登录 */
    }
  }

  function logout() {
    clearSession()
    // 退出后清空本地数据，避免共享设备上他人看到上一个账号的方案
    clearLocalUserData()
  }

  /** 立即把本地数据推到服务端。 */
  async function pushData() {
    if (!token.value) return
    try {
      await api.putUserData(snapshotLocal())
    } catch {
      /* 忽略偶发失败，下次变更会重试 */
    }
  }

  /** 防抖同步（本地数据变化时调用）。 */
  function scheduleSync() {
    if (!token.value) return
    if (syncTimer) clearTimeout(syncTimer)
    syncTimer = setTimeout(() => pushData(), 1200)
  }

  return { token, user, isLoggedIn, ready, restore, register, login, logout, pushData, scheduleSync }
}
