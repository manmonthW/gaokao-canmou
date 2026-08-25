<script lang="ts">
/**
 * 专业冷热趋势徽标。
 *
 * 视觉语法（三条约束，见 DESIGN.md 与 PRODUCT.md）：
 * 1. **不新增第四套配色**。tokens.css 的五色风险调色板（冲/稳/保/高波动/数据不足）
 *    与「The Two Palettes Rule」严格绑定，用琥珀色表示「升温」会与「冲」撞语义。
 *    本徽标一律中性色，靠**字形 + 文字**承担分类信息。
 * 2. **不能只靠颜色**（色觉友好）。字形（↓↑↕·）与文案同时出现，灰度下也可区分。
 * 3. **数据为空不渲染、不占位**。实测只有约 22% 的招生单元带持续趋势标签，
 *    38% 平稳、14% 样本不足——空状态才是常态。
 *
 * 文案与解释全部来自 /meta.trend_dictionary，前端不硬编码，口吻是中性事实陈述。
 */
import { ref } from 'vue'
import type { TrendTagDef } from '@/types'
import { api } from '@/api/client'

let _dictPromise: Promise<TrendTagDef[]> | null = null

/** 全页共享一次 /meta 请求（同 StrengthBadges 的模块级缓存做法）。 */
export function loadTrendDictionary(): Promise<TrendTagDef[]> {
  if (!_dictPromise) {
    _dictPromise = api
      .meta()
      .then((m) => m.trend_dictionary || [])
      .catch(() => [])
  }
  return _dictPromise
}
</script>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import type { MajorTrend } from '@/types'

/** 徽标只需要 label；n_schools/concord 有则进 tooltip。
 *  放宽到 Partial 是为了让专业列表这类只拿到标签的场景不必伪造整个趋势对象。 */
type TrendLike = Partial<MajorTrend> & { label: string }

const props = withDefaults(
  defineProps<{
    trend?: TrendLike | null
    /** 外部已取过词表时传入，省一次请求 */
    dictionary?: TrendTagDef[]
    /** 紧凑模式：匹配结果表等密集场景 */
    compact?: boolean
    /** 仅渲染「持续趋势」三档（表格用）；false 时低置信档也渲染（展开区用） */
    badgeOnly?: boolean
  }>(),
  { trend: null, dictionary: undefined, compact: false, badgeOnly: true },
)

const fetched = ref<TrendTagDef[]>([])
onMounted(async () => {
  if (!props.dictionary?.length) fetched.value = await loadTrendDictionary()
})

const def = computed<TrendTagDef | null>(() => {
  const t = props.trend
  if (!t) return null
  const dict = props.dictionary?.length ? props.dictionary : fetched.value
  return dict.find((d) => d.label === t.label) || null
})

// 词表未收录 → 不硬造文案，直接不渲染（同 StrengthBadges 的保守约定）
const show = computed(() => !!def.value && (!props.badgeOnly || def.value.badge))
</script>

<template>
  <el-tooltip v-if="show" placement="top" :show-after="150">
    <template #content>
      <div class="tb-tip">
        <div class="tb-tip__head">{{ def!.display }}</div>
        <div class="tb-tip__body">{{ def!.tip }}</div>
        <div v-if="trend!.n_schools" class="tb-tip__meta">
          依据：{{ trend!.n_schools }} 所院校的同专业逐年对照
          <template v-if="trend!.concord">
            ·{{ Math.round(trend!.concord * 100) }}% 同向
          </template>
        </div>
      </div>
    </template>
    <span
      class="tb"
      :class="[
        `tb--${def!.confidence}`,
        { 'tb--compact': compact },
      ]"
      tabindex="0"
    >
      <span class="tb__glyph" aria-hidden="true">{{ def!.glyph }}</span>
      <span class="tb__text">{{ def!.display }}</span>
    </span>
  </el-tooltip>
</template>

<style scoped>
.tb {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 8px;
  border: 1px solid var(--color-border-strong);
  border-radius: 999px;
  font-size: var(--text-xs);
  font-weight: 600;
  line-height: 1.6;
  color: var(--color-text-secondary);
  background: var(--color-bg-subtle);
  cursor: help;
  white-space: nowrap;
}
.tb--compact {
  padding: 0 6px;
}
/* 低置信（大小年/单年跳变）用虚线边框做冗余编码，
   与 SchoolDetail 的 .disc__tag--unofficial 同一套视觉语法 */
.tb--low {
  border-style: dashed;
  color: var(--color-text-muted);
}
.tb__glyph {
  font-family: var(--font-mono);
  font-size: 11px;
}
.tb:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
.tb-tip {
  max-width: 260px;
}
.tb-tip__head {
  font-weight: 700;
  margin-bottom: 4px;
}
.tb-tip__body {
  line-height: 1.6;
}
.tb-tip__meta {
  margin-top: 6px;
  opacity: 0.75;
  font-size: var(--text-xs);
}
</style>
