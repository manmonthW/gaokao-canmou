import { ref, watch } from 'vue'
import type { ExamineeProfile } from '@/types'

const STORAGE_KEY = 'ln-zhiyuan-profile'

/**
 * 考生所在年份：固定为「今年」，是隐含常量，不作为用户可选项。
 * 2025/2026 一律作为历史参考年（见 locate 服务 rank_context）。
 * 说明：profile.year 字段仍保留，仅用于后端需要 year 的旧接口（如 match 内部
 * score→rank 反查），其值恒等于 EXAMINEE_YEAR，用户不再手动切换。
 */
export const EXAMINEE_YEAR = 2027

const defaultProfile: ExamineeProfile = {
  year: EXAMINEE_YEAR,
  category: '普通类',
  subject: '物理学科类',
  batch: '本科批',
  score: null,
  rank: null,
}

function load(): ExamineeProfile {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...defaultProfile }
    // 强制 year 为 EXAMINEE_YEAR：历史存档里可能残留 2025/2026
    return { ...defaultProfile, ...JSON.parse(raw), year: EXAMINEE_YEAR }
  } catch {
    return { ...defaultProfile }
  }
}

// 全局单例：跨页面（定位 / 匹配）共享同一份考生档案
const profile = ref<ExamineeProfile>(load())

watch(
  profile,
  (v) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(v))
    } catch {
      /* 忽略写入失败（如隐私模式） */
    }
    // 登录状态下，本地变更防抖同步到服务端
    notifyChange()
  },
  { deep: true },
)

// 云端数据恢复后（登录/启动），重新从 localStorage 读取，刷新内存态
if (typeof window !== 'undefined') {
  window.addEventListener('ln-userdata-restored', () => {
    profile.value = load()
  })
  // 退出登录：重置为默认档案
  window.addEventListener('ln-userdata-cleared', () => {
    profile.value = { ...defaultProfile }
  })
}

// 惰性获取 scheduleSync，避免与 useAuth 的循环依赖
let _scheduleSync: (() => void) | null = null
function notifyChange() {
  if (_scheduleSync) return _scheduleSync()
  import('./useAuth').then(({ useAuth }) => {
    _scheduleSync = useAuth().scheduleSync
    _scheduleSync()
  })
}

export function useProfile() {
  return { profile }
}
