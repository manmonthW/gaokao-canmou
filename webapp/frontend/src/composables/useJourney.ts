import { computed } from 'vue'
import { useProfile } from './useProfile'
import { usePlanner } from './usePlanner'

/**
 * 决策主线（定位 → 匹配 → 工作台）的全局状态。
 * 从共享的考生档案（useProfile）与决策数据（usePlanner）派生，
 * 用于顶部步骤条实时展示「我在哪 / 完成了没 / 下一步去哪」。
 */
export function useJourney() {
  const { profile } = useProfile()
  const planner = usePlanner()

  // ① 我的定位：填了全省位次（唯一锚点）即视为已定位
  const locateDone = computed(() => profile.value.rank != null && profile.value.rank > 0)
  const locateSummary = computed(() => {
    if (!locateDone.value) return '未填位次'
    const parts: string[] = [`位次${profile.value.rank!.toLocaleString()}`]
    if (profile.value.score != null) parts.push(`${profile.value.score}分`)
    return parts.join(' · ')
  })

  // ② 智能匹配：以收藏数量作为“已在筛选候选”的信号
  const favCount = computed(() => planner.favorites.value.length)
  const matchStarted = computed(() => favCount.value > 0)
  const matchSummary = computed(() => {
    if (!locateDone.value) return '待定位'
    if (!matchStarted.value) return '待匹配'
    return `已收藏 ${favCount.value}`
  })

  // ③ 决策工作台：跨所有方案汇总志愿数 + 健康度（任一方案有问题即提示）
  const planStats = computed(() => {
    const plans = planner.plans.value
    let entries = 0
    let issues = 0
    const firstProblems: string[] = []
    for (const p of plans) {
      const a = planner.analyzePlan(p)
      entries += a.total
      issues += a.issues
      if (a.issues && firstProblems.length === 0 && !a.ok) {
        firstProblems.push(a.warnings[0])
      }
    }
    return { planCount: plans.length, entries, issues, firstProblem: firstProblems[0] || '' }
  })
  const workbenchSummary = computed(() => {
    const s = planStats.value
    if (s.planCount === 0) return '未建方案'
    if (s.entries === 0) return `${s.planCount} 个空方案`
    return `方案含 ${s.entries} 个志愿`
  })
  const workbenchWarn = computed(() => planStats.value.issues > 0)

  return {
    profile,
    locateDone,
    locateSummary,
    matchStarted,
    matchSummary,
    favCount,
    workbenchSummary,
    workbenchWarn,
    planStats,
  }
}
