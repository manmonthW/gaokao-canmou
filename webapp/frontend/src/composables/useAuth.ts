import { ref, computed } from 'vue'
import { api, setAuthToken } from '@/api/client'
import type { AuthUser } from '@/types'

/**
 * 认证状态（全局单例）+ 用户数据云同步。
 *
 * 匿名优先策略（P3，与 development-spec §9.3 / product-plan MVP 约定一致）：
 *  - 查询/定位/匹配/工作台全程无需登录，数据存 localStorage；
 *  - token 存 localStorage（Bearer 头）；应用启动时恢复并校验；
 *  - 登录是「跨设备同步 + 云端保存」的增值入口：
 *    云端为空 → 把本机数据推上去；云端非空 → 以云端为准；
 *    之后本地变化时防抖回写服务端。
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
   * 应用启动：校验 token 并加载该账号云端数据。单飞（single-flight），路由守卫可 await。
   * 匿名优先（P3）：无 token 时保留本机数据（匿名用户的档案/方案就在本机）；
   * 仅当 token 失效（数据属于已登录账号）时才清空本地。
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
            // 云端为空：本机若有数据则推上去（云端以本机为准），否则保持空
            if (Object.keys(snapshotLocal()).length > 0) {
              await pushData()
            }
          }
          window.dispatchEvent(new Event('ln-userdata-restored'))
        } catch {
          // token 失效/网络异常：退回匿名并清空属于该账号的本地数据
          clearSession()
          clearLocalUserData()
        }
      }
      // 无 token：匿名使用，本机数据原样保留
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
    // 匿名优先合并（P3）：先快照本机匿名数据；云端非空 → 以云端为准，
    // 云端为空 → 保留本机数据并推上去，不丢匿名期间的劳动成果。
    const localSnap = snapshotLocal()
    for (const k of SYNC_KEYS) localStorage.removeItem(k)
    setSession(res.token, res.user)
    try {
      const { data } = await api.getUserData()
      if (data && Object.keys(data).length > 0) {
        applyToLocal(data)
      } else if (Object.keys(localSnap).length > 0) {
        applyToLocal(localSnap)
        await pushData()
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
