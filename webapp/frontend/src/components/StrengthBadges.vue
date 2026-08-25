<script lang="ts">
/**
 * 词表模块级缓存（W1 修复）：
 * <script setup> 内的变量是「实例级」（每个组件实例一份），多实例会各自
 * 请求 /meta。提升到普通 <script> 块——其作用域是模块级，整个页面所有
 * StrengthBadges 实例共享同一个 promise，只发一次 /meta 请求。
 */
import { api } from '@/api/client'
import type { StrengthTagDef } from '@/types'

let _dictPromise: Promise<StrengthTagDef[]> | null = null

export function loadStrengthDictionary(): Promise<StrengthTagDef[]> {
  if (!_dictPromise) {
    _dictPromise = api
      .meta()
      .then((m) => m.strength_dictionary || [])
      .catch(() => [] as StrengthTagDef[])
  }
  return _dictPromise
}
</script>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { StrengthTagDef, MajorStrengthItem } from '@/types'
// loadStrengthDictionary 来自上方普通 <script> 块（模块级），同 SFC 内可直接引用

/**
 * 实力徽章（任务 #9，词表 migration 0014）：
 * - 院校级 strength_tags 徽章 + 可选专业级 major_strength 摘要标签；
 * - 标签文案与来源口径说明一律从 meta.strength_dictionary 词表解析
 *   （同 Match.vue major_flags 惯例，前端不硬编码文案）；
 * - 样式按 kind 区分：official 常规色；eval5（非官方汇总）虚线边框 + 「非官方」角标；
 *   third_party=true 灰色系 + 「第三方」角标（免责口径与词表 source_note 一致）；
 * - 按 display_order 排序；数据为空 / 词表未收录时不渲染任何内容（不占位）。
 */
const props = withDefaults(
  defineProps<{
    strengthTags?: string[]
    majorStrength?: MajorStrengthItem[]
    /** 紧凑模式：匹配结果表等密集场景，缩小间距 */
    compact?: boolean
    /** 外部已取到的词表（如页面已请求 meta）；缺省时组件自行请求并模块级缓存 */
    dictionary?: StrengthTagDef[]
  }>(),
  {
    strengthTags: () => [],
    majorStrength: () => [],
    compact: false,
    dictionary: undefined,
  },
)

const fetched = ref<StrengthTagDef[] | null>(null)
onMounted(async () => {
  if (!props.dictionary?.length) fetched.value = await loadStrengthDictionary()
})
// 外部传入的词表优先；两者皆空 → 无徽章可渲染
const dict = computed<StrengthTagDef[]>(() =>
  props.dictionary?.length ? props.dictionary : fetched.value || [],
)
const dictMap = computed(() => new Map(dict.value.map((d) => [d.tag, d])))

// 院校级标签：方案 A 只保留 eval5（第五轮学科评估），其余暂存数据库不展示
const tagItems = computed(() =>
  (props.strengthTags || [])
    .map((t) => dictMap.value.get(t))
    .filter((d): d is StrengthTagDef => !!d && d.kind === 'eval5')
    .sort((a, b) => a.display_order - b.display_order),
)

// major_strength.source → 词表 tag（摘要标签文案同样取自词表）
// 方案 A：只显示第五轮学科评估，grade 决定具体 tag
const EVAL5_GRADE_TAG: Record<string, string> = {
  'A+': '五轮A+',
  'A': '五轮A',
  'A-': '五轮A-',
}
function eval5Tier(grade: string): string {
  if (grade === 'A+') return 'top'
  if (grade === 'A') return 'high'
  return 'mid'
}
const majorItems = computed(() => {
  const seen = new Set<string>()
  const out: { def: StrengthTagDef; grade: string; tier: string }[] = []
  for (const m of props.majorStrength || []) {
    // 方案 A：只渲染 eval5_a 来源
    if (m.source !== 'eval5_a') continue
    const grade = m.tier
    if (!grade) continue
    const tag = EVAL5_GRADE_TAG[grade]
    if (!tag || seen.has(tag)) continue
    const def = dictMap.value.get(tag)
    if (!def) continue
    seen.add(tag)
    out.push({ def, grade, tier: eval5Tier(grade) })
  }
  return out
})

const hasAny = computed(() => majorItems.value.length > 0)

// 颜色映射按 kind 定义（词表文案仍来自后端）
function kindClass(d: StrengthTagDef): string {
  if (d.third_party) return 'sb-tag--third'
  switch (d.kind) {
    case 'eval4':
      return 'sb-tag--eval4'
    case 'eval5':
      return 'sb-tag--eval5'
    case 'dfc2022':
      return 'sb-tag--dfc'
    case 'swyc':
      return 'sb-tag--swyc'
    default:
      return 'sb-tag--meta'
  }
}
// tooltip：label + source_note（平实解释）
function tipText(d: StrengthTagDef): string {
  return d.source_note ? `${d.label}：${d.source_note}` : d.label
}
</script>

<template>
  <span v-if="hasAny" class="sb" :class="{ 'sb--compact': compact }">
    <el-tooltip
      v-for="m in majorItems"
      :key="'m-' + m.def.tag"
      :content="tipText(m.def)"
      placement="top"
      :show-after="150"
    >
      <span class="sb__wrap">
        <span class="sb-eval5" :class="'sb-eval5--' + m.tier" tabindex="0">{{ m.grade }}</span>
      </span>
    </el-tooltip>
  </span>
</template>

<style scoped>
.sb {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  vertical-align: middle;
}
.sb--compact { gap: 4px; }
/* 角标需溢出到标签右上角，外层留出半角标空间避免被表格裁切感 */
.sb__wrap { position: relative; display: inline-flex; padding-top: 3px; }
.sb-tag { cursor: help; }
/* official 常规色：按 kind 区分主色 */
.sb-tag--eval4 {
  color: var(--el-color-primary);
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
}
/* eval5 非官方汇总：虚线边框 + 浅一档底色，与官方评估视觉区隔 */
.sb-tag--eval5 {
  color: var(--el-color-primary);
  border-style: dashed;
  border-color: var(--el-color-primary-light-3);
  background: var(--el-color-primary-light-9);
}
.sb-tag--dfc {
  color: var(--el-color-success);
  border-color: var(--el-color-success-light-5);
  background: var(--el-color-success-light-9);
}
.sb-tag--swyc {
  color: var(--el-color-warning);
  border-color: var(--el-color-warning-light-5);
  background: var(--el-color-warning-light-9);
}
.sb-tag--meta {
  color: var(--el-color-primary);
  border-color: var(--el-color-primary-light-7);
  background: var(--el-color-primary-light-9);
}
/* 第三方来源：灰色系，弱化视觉权重，免责提示在角标与 tooltip */
.sb-tag--third {
  color: var(--el-color-info);
  border-color: var(--el-border-color);
  background: var(--el-fill-color-light);
}
/* 第五轮学科评估紧凑角标（方案 A）：仅显示 A+/A/A-，类 MajorDrawer 配色 */
.sb-eval5 {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  min-width: 20px;
  height: 18px;
  padding: 0 5px;
  border-radius: 2px;
  line-height: 1;
  cursor: help;
  letter-spacing: 0.5px;
}
.sb-eval5:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.sb-eval5--top {
  color: #92400e;
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  border: 1px solid #f59e0b;
}
.sb-eval5--high {
  color: #7c2d12;
  background: linear-gradient(135deg, #ffedd5, #fed7aa);
  border: 1px solid #f97316;
}
.sb-eval5--mid {
  color: #78350f;
  background: linear-gradient(135deg, #fef9c3, #fef08a);
  border: 1px solid #eab308;
}
.sb__corner {
  position: absolute;
  top: 0;
  right: -7px;
  font-size: 9px;
  line-height: 1;
  padding: 2px 3px;
  border-radius: 6px;
  white-space: nowrap;
  pointer-events: none;
}
.sb__corner--eval5 {
  background: var(--el-color-primary-light-8);
  color: var(--el-color-primary);
  border: 1px solid var(--el-color-primary-light-5);
}
.sb__corner--third {
  background: var(--el-fill-color);
  color: var(--el-color-info);
  border: 1px solid var(--el-border-color);
}
</style>
