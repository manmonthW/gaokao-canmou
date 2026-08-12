<script lang="ts">
/**
 * 词表模块级缓存：
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

/**
 * 实力徽章组件：
 * - 院校级 strength_tags 徽章 + 可选专业级 major_strength 摘要标签；
 * - 标签文案与来源口径说明一律从 meta.strength_dictionary 词表解析；
 * - 智能匹配页（context='match'）精简策略：
 *   · 只保留第五轮学科评估（kind=eval5），过滤四轮/双一流/一流专业/软科/多源；
 *   · 同一学科评估只保留最高等级（A+ > A > A-）；
 *   · 文案简化为纯评级（如 "A+"、"A"），标题旁加 ⓘ 浮框说明含义；
 *   · 不显示角标（非官方/第三方），保持简洁；
 * - 其他页面（默认 context=''）：保持原有全部标签展示。
 */
const props = withDefaults(
  defineProps<{
    strengthTags?: string[]
    majorStrength?: MajorStrengthItem[]
    /** 使用场景：'match'=智能匹配页（精简模式）；其他=全量展示 */
    context?: string
    /** 紧凑模式：缩小间距 */
    compact?: boolean
    /** 外部已取到的词表 */
    dictionary?: StrengthTagDef[]
  }>(),
  {
    strengthTags: () => [],
    majorStrength: () => [],
    context: '',
    compact: false,
    dictionary: undefined,
  },
)

/** 是否为智能匹配页精简模式 */
const isMatch = computed(() => props.context === 'match')

const fetched = ref<StrengthTagDef[] | null>(null)
onMounted(async () => {
  if (!props.dictionary?.length) fetched.value = await loadStrengthDictionary()
})

const dict = computed<StrengthTagDef[]>(() =>
  props.dictionary?.length ? props.dictionary : fetched.value || [],
)
const dictMap = computed(() => new Map(dict.value.map((d) => [d.tag, d])))

// ---------- 学科评估等级排序（高→低） ----------
const EVAL_ORDER: Record<string, number> = { 'A+': 0, 'A': 1, 'A-': 2, 'B+': 3, 'B': 4, 'B-': 5, 'C': 6 }

// ---------- 院校级标签：原始列表 ----------
const rawTagItems = computed(() =>
  (props.strengthTags || [])
    .map((t) => dictMap.value.get(t))
    .filter((d): d is StrengthTagDef => !!d)
    .sort((a, b) => a.display_order - b.display_order),
)

/**
 * 智能匹配页过滤 + 去重：
 * - 只保留 kind=eval5（第五轮学科评估）
 * - 同 kind 只留等级最高的一个（A+ > A > A-）
 */
const tagItems = computed(() => {
  const items = rawTagItems.value
  if (!isMatch.value) return items

  // 只保留 eval5
  const eval5 = items.filter((d) => d.kind === 'eval5')
  if (eval5.length === 0) return []

  // 去重：按等级取最高
  const best = new Map<string, StrengthTagDef>()
  for (const d of eval5) {
    // 从 label 提取等级（如 "五轮学科评估 A+" → "A+"）
    const grade = extractGrade(d.label)
    const existing = best.get(d.kind)
    if (!existing || (grade && EVAL_ORDER[grade] < (EVAL_ORDER[extractGrade(existing.label)] ?? 99))) {
      best.set(d.kind, d)
    }
  }
  return Array.from(best.values())
})

// ---------- 专业级摘要标签 ----------
const SOURCE_TAG: Record<string, string> = {
  swyc_national: '国一流专业',
  swyc_provincial: '省一流专业',
  ruanke: '软科评级',
}
const majorItems = computed(() => {
  const seen = new Set<string>()
  const out: { def: StrengthTagDef; suffix: string }[] = []
  for (const m of props.majorStrength || []) {
    const tag = SOURCE_TAG[m.source]
    if (!tag || seen.has(tag)) continue
    const def = dictMap.value.get(tag)
    if (!def) continue
    // 智能匹配页：非 eval5 的专业标签不展示
    if (isMatch.value && def.kind !== 'eval5') continue
    seen.add(tag)
    const suffix = m.source === 'ruanke' && m.tier ? ` ${m.tier}` : ''
    out.push({ def, suffix })
  }
  return out.sort((a, b) => a.def.display_order - b.def.display_order)
})

const hasAny = computed(() => tagItems.value.length > 0 || majorItems.value.length > 0)

// ---------- 工具函数 ----------

/** 从 label 中提取评级文字（如 "五轮学科评估 A+" → "A+"） */
function extractGrade(label: string): string | undefined {
  const m = label.match(/\b([A+B+C][+-]?)\b/)
  return m?.[1]
}

/** 智能匹配页：纯评级文案（如 "A+"）；其他页面：原始 label */
function displayLabel(d: StrengthTagDef): string {
  if (!isMatch.value) return d.label
  const g = extractGrade(d.label)
  return g || d.label
}

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

function tipText(d: StrengthTagDef): string {
  return d.source_note ? `${d.label}：${d.source_note}` : d.label
}

/** 智能匹配页标题旁的帮助提示文案 */
const matchContextHelp =
  '仅显示教育部第五轮学科评估结果（A+/A/A-等）。' +
  '该结果来自各校公开发布的汇总，官方未集中公布完整名单，供参考。' +
  '更多排名数据可在「专业查询」中查看。'

/**
 * 评级等级 → 样式 tier：
 *   top = A+（金色）
 *   high = A（橙色）
 *   mid  = A-/B+（琥珀色）
 *   low  = B/B-/C（灰色，一般不出现）
 */
function gradeTier(label: string): string {
  if (label === 'A+') return 'top'
  if (label === 'A') return 'high'
  if (label === 'A-' || label === 'B+') return 'mid'
  return 'low'
}
</script>

<template>
  <span v-if="hasAny" class="sb" :class="{ 'sb--compact': compact, 'sb--match': isMatch }">
    <!-- 智能匹配页：标题旁加帮助图标 -->
    <template v-if="isMatch">
      <el-tooltip :content="matchContextHelp" placement="top" effect="dark" :show-after="400">
        <i class="sb-help">ⓘ</i>
      </el-tooltip>
    </template>

    <!-- 院校级标签 -->
    <el-tooltip
      v-for="d in tagItems"
      :key="d.tag"
      :content="tipText(d)"
      placement="top"
      :show-after="150"
    >
      <!-- 智能匹配页：自定义小徽章（纯文字，无三角箭头） -->
      <span v-if="isMatch" class="sb__badge" :class="'sb__badge--' + gradeTier(displayLabel(d))">
        {{ displayLabel(d) }}
      </span>
      <!-- 其他页面：el-tag -->
      <span v-else class="sb__wrap">
        <el-tag size="small" effect="plain" class="sb-tag" :class="kindClass(d)">
          {{ displayLabel(d) }}
        </el-tag>
        <span v-if="!isMatch && d.kind === 'eval5' && !d.third_party" class="sb__corner sb__corner--eval5">非官方</span>
        <span v-if="!isMatch && d.third_party" class="sb__corner sb__corner--third">第三方</span>
      </span>
    </el-tooltip>

    <!-- 专业级摘要标签 -->
    <el-tooltip
      v-for="m in majorItems"
      :key="'m-' + m.def.tag"
      :content="tipText(m.def)"
      placement="top"
      :show-after="150"
    >
      <span v-if="isMatch" class="sb__badge" :class="'sb__badge--' + gradeTier(displayLabel(m.def))">
        {{ displayLabel(m.def) }}{{ m.suffix }}
      </span>
      <span v-else class="sb__wrap">
        <el-tag size="small" effect="plain" class="sb-tag" :class="kindClass(m.def)">
          {{ displayLabel(m.def) }}{{ m.suffix }}
        </el-tag>
        <span v-if="!isMatch && m.def.kind === 'eval5' && !m.def.third_party" class="sb__corner sb__corner--eval5">非官方</span>
        <span v-if="!isMatch && m.def.third_party" class="sb__corner sb__corner--third">第三方</span>
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
/* 智能匹配页：更紧凑的间距 */
.sb--match { gap: 4px; }

/* 帮助图标 */
.sb-help {
  font-style: normal;
  font-size: 12px;
  color: var(--el-color-info);
  cursor: help;
  margin-right: 2px;
}

/* 角标需溢出到标签右上角，外层留出半角标空间避免被表格裁切感 */
.sb__wrap { position: relative; display: inline-flex; padding-top: 3px; }
.sb-tag { cursor: help; }

/* official 常规色：按 kind 区分主色 */
.sb-tag--eval4 {
  color: var(--el-color-primary);
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
}
/* eval5 非官方汇总：虚线边框 + 浅一档底色 */
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
/* 第三方来源：灰色系 */
.sb-tag--third {
  color: var(--el-color-info);
  border-color: var(--el-border-color);
  background: var(--el-fill-color-light);
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

/* ============================================================
 * 智能匹配页：自定义学科评估小徽章
 * - 纯文字标签，无三角箭头
 * - 按等级分色：A+ 金 / A 橙 / A- 琥珀
 * ============================================================ */
.sb__badge {
  display: inline-flex;
  align-items: center;
  font-size: 10px;
  line-height: 1.35;
  font-weight: 600;
  padding: 0 6px;
  border-radius: 2px;
  white-space: nowrap;
  cursor: help;
  vertical-align: middle;
  transition: opacity 0.15s;
}
.sb__badge:hover { opacity: 0.8; }

/* ---- A+：金色（最突出） ---- */
.sb__badge--top {
  color: #92400e;
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  border: 1px solid #f59e0b;
}

/* ---- A：橙色 ---- */
.sb__badge--high {
  color: #7c2d12;
  background: linear-gradient(135deg, #ffedd5, #fed7aa);
  border: 1px solid #f97316;
}

/* ---- A-/B+：琥珀色 ---- */
.sb__badge--mid {
  color: #78350f;
  background: linear-gradient(135deg, #fef9c3, #fef08a);
  border: 1px solid #eab308;
}

/* ---- B/B-/C：灰色（一般不出现） ---- */
.sb__badge--low {
  color: #374151;
  background: linear-gradient(135deg, #f3f4f6, #e5e7eb);
  border: 1px solid #9ca3af;
}
</style>
