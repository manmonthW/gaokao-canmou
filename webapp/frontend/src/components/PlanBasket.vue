<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { usePlanner } from '@/composables/usePlanner'

/**
 * 常驻「方案篮」：跨主线页面显示已攒志愿数与冲/稳/保结构，
 * 让「攒志愿 → 去工作台整理」的路径始终可见（类似购物车）。
 * 仅在有收藏或方案时出现。
 */
const props = defineProps<{ hide?: boolean }>()
const router = useRouter()
const planner = usePlanner()

// 汇总所有方案里的志愿；若尚未建方案，则以收藏作为“待整理”提示
const stats = computed(() => {
  const counts: Record<string, number> = { 冲: 0, 稳: 0, 保: 0, 高波动: 0, 数据不足: 0 }
  let entries = 0
  for (const p of planner.plans.value) {
    for (const e of p.entries) {
      counts[e.risk] = (counts[e.risk] || 0) + 1
      entries++
    }
  }
  return { counts, entries, plans: planner.plans.value.length, favs: planner.favorites.value.length }
})

const visible = computed(
  () => !props.hide && (stats.value.entries > 0 || stats.value.favs > 0),
)

function goWorkbench() {
  router.push('/workbench')
}
</script>

<template>
  <transition name="basket">
    <div v-if="visible" class="basket">
      <div class="basket__main">
        <span class="basket__count tnum">{{ stats.entries }}</span>
        <span class="basket__label">个志愿在方案中</span>
        <span class="basket__chips" v-if="stats.entries">
          <span class="basket__chip basket__chip--reach">冲 {{ stats.counts['冲'] }}</span>
          <span class="basket__chip basket__chip--match">稳 {{ stats.counts['稳'] }}</span>
          <span class="basket__chip basket__chip--safe">保 {{ stats.counts['保'] }}</span>
        </span>
        <span class="basket__fav" v-if="stats.favs">· 收藏 {{ stats.favs }}</span>
      </div>
      <el-button type="primary" @click="goWorkbench">去工作台整理 →</el-button>
    </div>
  </transition>
</template>

<style scoped>
.basket {
  position: sticky;
  bottom: var(--space-4);
  z-index: 8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-5);
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: 999px;
  box-shadow: var(--shadow-lg);
}
.basket__main {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.basket__count {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--color-primary);
}
.basket__label { color: var(--color-text); }
.basket__chips { display: flex; gap: var(--space-1); margin-left: var(--space-2); }
.basket__chip {
  font-size: var(--text-xs);
  padding: 1px 8px;
  border-radius: 999px;
  font-variant-numeric: tabular-nums;
}
.basket__chip--reach { background: var(--color-reach-soft); color: var(--color-reach); }
.basket__chip--match { background: var(--color-match-soft); color: var(--color-match); }
.basket__chip--safe { background: var(--color-safe-soft); color: var(--color-safe); }
.basket__fav { color: var(--color-text-muted); }

.basket-enter-active,
.basket-leave-active { transition: opacity 0.2s, transform 0.2s; }
.basket-enter-from,
.basket-leave-to { opacity: 0; transform: translateY(8px); }
</style>
