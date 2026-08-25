<script setup lang="ts">
/**
 * 单个「院校+专业」的历年门槛位次曲线，叠加**全省大盘基准线**。
 *
 * 基准线是这张图的全部意义：它把「全省整体在动」和「这个专业自己在动」分开。
 * 基准线的画法 = 以该单元最早一年的门槛为起点，逐年乘上全省大盘的漂移倍数
 * （market_drift.drift_log 取自 major_trend_market）。两条线贴合 = 随大盘；
 * 实线在基准线下方（位次数字更小）= 比全省更紧，反之 = 比全省更松。
 *
 * 实现沿用 Workbench 覆盖曲线的手写内联 SVG（项目里 echarts 是未使用依赖）：
 * log10 纵轴、fy() 防 NaN、缺值不连线、<title> 原生 tooltip。
 * 纵轴方向与直觉相反：位次数字越小越好，所以**越靠上越难考**，图上已标注。
 */
import { computed } from 'vue'
import type { MatchYearly, MarketDrift } from '@/types'

const props = withDefaults(
  defineProps<{
    yearly: MatchYearly[]
    marketDrift?: MarketDrift[]
    /** 考生本人位次，画一条参照线 */
    examineeRank?: number | null
    height?: number
  }>(),
  { marketDrift: () => [], examineeRank: null, height: 200 },
)

const chart = computed(() => {
  const pts = (props.yearly || [])
    .filter((d) => Number.isFinite(d.lowest_rank))
    .sort((a, b) => a.year - b.year)
  if (pts.length < 2) return null

  // 大盘基准：从首年门槛出发，按各年段的漂移倍数累乘
  const driftBy = new Map(props.marketDrift.map((d) => [`${d.year_from}-${d.year_to}`, d.drift_log]))
  const base: { year: number; v: number }[] = [{ year: pts[0].year, v: pts[0].lowest_rank }]
  for (let i = 1; i < pts.length; i++) {
    const k = `${pts[i - 1].year}-${pts[i].year}`
    const d = driftBy.get(k)
    const prev = base[base.length - 1].v
    base.push({ year: pts[i].year, v: d == null ? prev : prev * Math.exp(d) })
  }
  const hasBase = props.marketDrift.length > 0

  const vals = [...pts.map((p) => p.lowest_rank), ...base.map((b) => b.v)]
  if (props.examineeRank) vals.push(props.examineeRank)
  const finite = vals.filter((v) => Number.isFinite(v))
  const minV = Math.max(1, Math.min(...finite) * 0.85)
  const maxV = Math.max(...finite) * 1.18
  const lgMin = Math.log10(minV)
  const lgSpan = Math.max(0.05, Math.log10(maxV) - lgMin)

  const W = 460
  const H = props.height
  const padL = 54, padR = 54, padT = 14, padB = 26
  const n = pts.length
  const x = (i: number) => padL + (i / Math.max(1, n - 1)) * (W - padL - padR)
  const y = (v: number) => padT + ((Math.log10(Math.max(1, v)) - lgMin) / lgSpan) * (H - padT - padB)
  // 跳过非有限值，防 NaN 属性
  const fy = (v: number | null | undefined) =>
    v == null || !Number.isFinite(v) ? null : Math.round(y(v) * 10) / 10

  const line = (arr: { v: number }[]) =>
    arr
      .map((d, i) => {
        const yy = fy(d.v)
        return yy == null ? null : `${i ? 'L' : 'M'}${Math.round(x(i) * 10) / 10} ${yy}`
      })
      .filter(Boolean)
      .join(' ')

  const fmt = (v: number) => (v >= 10000 ? `${Math.round(v / 1000) / 10}万` : String(Math.round(v)))

  return {
    W, H, padL, padR, padT, padB, hasBase,
    unitPath: line(pts.map((p) => ({ v: p.lowest_rank }))),
    basePath: hasBase ? line(base) : '',
    dots: pts.map((p, i) => ({
      x: Math.round(x(i) * 10) / 10,
      y: fy(p.lowest_rank)!,
      year: p.year,
      rank: p.lowest_rank,
      label: fmt(p.lowest_rank),
    })),
    baseDots: hasBase
      ? base.map((b, i) => ({ x: Math.round(x(i) * 10) / 10, y: fy(b.v)!, year: b.year, v: Math.round(b.v) }))
      : [],
    exY: props.examineeRank ? fy(props.examineeRank) : null,
    exLabel: props.examineeRank ? fmt(props.examineeRank) : '',
    bottom: H - padB,
  }
})
</script>

<template>
  <div v-if="chart" class="tc">
    <div class="tc-scroll">
      <svg :viewBox="`0 0 ${chart.W} ${chart.H}`" class="tc__svg" role="img"
           aria-label="历年门槛位次曲线，含全省大盘基准线">
        <!-- 考生位次参照线 -->
        <g v-if="chart.exY != null">
          <line :x1="chart.padL" :x2="chart.W - chart.padR" :y1="chart.exY" :y2="chart.exY"
                class="tc__ex" />
          <text :x="chart.W - chart.padR + 4" :y="chart.exY + 3" class="tc__ex-label">
            你 {{ chart.exLabel }}
          </text>
        </g>

        <!-- 全省大盘基准线（虚线，中性色） -->
        <path v-if="chart.hasBase" :d="chart.basePath" class="tc__base" />
        <circle v-for="b in chart.baseDots" :key="'b' + b.year" :cx="b.x" :cy="b.y" r="2.5"
                class="tc__base-dot">
          <title>{{ b.year }} 年全省大盘基准 约 {{ b.v }} 名</title>
        </circle>

        <!-- 该专业实际门槛（实线 + 实心点） -->
        <path :d="chart.unitPath" class="tc__unit" />
        <g v-for="d in chart.dots" :key="d.year">
          <circle :cx="d.x" :cy="d.y" r="4" class="tc__dot">
            <title>{{ d.year }} 年门槛位次 {{ d.rank }}</title>
          </circle>
          <text :x="d.x" :y="d.y - 9" class="tc__val">{{ d.label }}</text>
          <text :x="d.x" :y="chart.bottom + 16" class="tc__year">{{ d.year }}</text>
        </g>

        <text :x="4" :y="chart.padT + 4" class="tc__axis">越往上越难考</text>
      </svg>
    </div>
    <div class="tc-legend">
      <span class="tc-legend__i"><i class="tc-legend__solid" />该专业实际门槛</span>
      <span v-if="chart.hasBase" class="tc-legend__i"><i class="tc-legend__dash" />全省大盘同步基准</span>
      <span v-if="chart.exY != null" class="tc-legend__i"><i class="tc-legend__ex" />你的位次</span>
    </div>
    <p v-if="chart.hasBase" class="tc-note">
      实线跑在虚线下方＝比全省更难考；跑在上方＝比全省更好考；两线贴合＝随大盘走，不是这个专业自己在动。
    </p>
  </div>
</template>

<style scoped>
.tc-scroll { overflow-x: auto; }
.tc__svg { width: 100%; min-width: 320px; height: auto; display: block; }
.tc__unit { fill: none; stroke: var(--color-primary); stroke-width: 2; }
.tc__dot { fill: var(--color-primary); }
/* 基准线用中性灰虚线：不占用五色风险调色板，灰度下也与实线可区分 */
.tc__base { fill: none; stroke: var(--color-text-muted); stroke-width: 1.5; stroke-dasharray: 5 4; }
.tc__base-dot { fill: #fff; stroke: var(--color-text-muted); stroke-width: 1.2; }
.tc__ex { stroke: var(--color-text-secondary); stroke-width: 1; stroke-dasharray: 2 3; }
.tc__ex-label { font-size: 10px; fill: var(--color-text-secondary); }
.tc__val { font-size: 10px; fill: var(--color-text); text-anchor: middle; font-family: var(--font-mono); }
.tc__year { font-size: 10px; fill: var(--color-text-muted); text-anchor: middle; }
.tc__axis { font-size: 9px; fill: var(--color-text-muted); }
.tc-legend {
  display: flex; flex-wrap: wrap; gap: var(--space-3);
  margin-top: 2px; font-size: var(--text-xs); color: var(--color-text-muted);
}
.tc-legend__i { display: inline-flex; align-items: center; gap: 4px; }
.tc-legend__solid { width: 14px; height: 0; border-top: 2px solid var(--color-primary); }
.tc-legend__dash { width: 14px; height: 0; border-top: 2px dashed var(--color-text-muted); }
.tc-legend__ex { width: 14px; height: 0; border-top: 1px dotted var(--color-text-secondary); }
.tc-note { margin: 6px 0 0; font-size: var(--text-xs); color: var(--color-text-muted); line-height: 1.6; }
</style>
