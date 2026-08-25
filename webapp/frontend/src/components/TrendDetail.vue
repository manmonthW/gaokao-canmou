<script setup lang="ts">
/**
 * 趋势详情块：匹配页展开行与专业抽屉共用。
 *
 * 呈现次序是刻意的，从最好懂到最专业：
 *  ① 一句人话结论（等效分 + 全省大盘对照）
 *  ② 在辽招生单元数变动 —— 这条比标签本身更重要，见下
 *  ③ 判定依据（院校数 / 两段幅度 / 同向率）
 *  ④ 院校层次分化
 *  ⑤ 社会背景（人工撰写，强制带来源与日期，明标非本站数据）
 *  ⑥ 免责：趋势 ≠ 建议
 *
 * 为什么等效分是一线数字：报告里的「超额漂移」正号表示**变松**，对普通用户
 * 读起来是反的；等效分「门槛降了 19 分」则和直觉一致。
 * 为什么必须同时给大盘：只说「降了 19 分」会让用户把全省整体下移误当成
 * 这个专业自己的变化。
 * 为什么必须给招生单元数：人工智能门槛「平稳」但单元 +67%（强需求吃下扩招），
 * 土木工程门槛「平稳」但单元 −28%（靠缩招撑住），只看标签会把两者读成一回事。
 */
import { computed } from 'vue'
import type { MajorTrend } from '@/types'

const props = defineProps<{ trend: MajorTrend | null; compact?: boolean }>()

const t = computed(() => props.trend)

/** 等效分文案。负 = 门槛下降了多少分。 */
const eqText = computed(() => {
  const d = t.value?.eq_score_delta
  const m = t.value?.eq_score_delta_market
  if (d === null || d === undefined) return null
  const word = (v: number) => (v < 0 ? `下降约 ${Math.abs(v)} 分` : v > 0 ? `上升约 ${v} 分` : '基本持平')
  const self = `近三年门槛${word(d)}`
  if (m === null || m === undefined) return `${self}。`
  const mkt = m === 0 ? '全省整体基本持平' : `全省整体${word(m)}`
  const diff = Math.round((d - m) * 10) / 10
  const rel =
    Math.abs(diff) < 1
      ? '与全省大盘同步，不是这个专业自己的变化'
      : diff < 0
        ? `比全省多降 ${Math.abs(diff)} 分`
        : `比全省多涨 ${diff} 分`
  return `${self}；同期${mkt}——${rel}。`
})

const units = computed(() => t.value?.units || null)
const supplyText = computed(() => {
  const u = units.value
  if (!u) return null
  const a = u[2024], b = u[2026]
  if (!a || !b) return null
  const pct = Math.round((b / a - 1) * 100)
  const word = pct > 0 ? `扩招 ${pct}%` : pct < 0 ? `缩招 ${Math.abs(pct)}%` : '基本持平'
  return `在辽招生单元 ${a} → ${u[2025]} → ${b}（${word}）`
})

const tiers = computed(() => {
  const ts = t.value?.tier_split
  if (!ts) return []
  const order = ['985', '211', '双一流', '普通公办', '民办']
  return Object.entries(ts)
    .sort((x, y) => order.indexOf(x[0]) - order.indexOf(y[0]))
    .map(([tier, v]) => ({ tier, n: v.n, pct: Math.round(v.e * 1000) / 10 }))
})
</script>

<template>
  <div v-if="t" class="td" :class="{ 'td--compact': compact }">
    <p v-if="eqText" class="td__lead">{{ eqText }}</p>

    <p v-if="supplyText" class="td__row">
      <span class="td__k">招生规模</span>
      <span class="td__v tnum">{{ supplyText }}</span>
    </p>

    <p v-if="t.n_schools" class="td__row">
      <span class="td__k">判定依据</span>
      <span class="td__v">
        {{ t.n_schools }} 所院校的同专业逐年对照<template v-if="t.concord">，其中
          {{ Math.round(t.concord * 100) }}% 同向移动</template><template v-if="t.label_reason">；{{ t.label_reason }}</template>
      </span>
    </p>

    <p v-if="tiers.length" class="td__row">
      <span class="td__k">院校分化</span>
      <span class="td__v tnum">
        <template v-for="(x, i) in tiers" :key="x.tier">
          <template v-if="i">　</template>{{ x.tier }} {{ x.n }} 所 {{ x.pct > 0 ? '+' : '' }}{{ x.pct }}%
        </template>
      </span>
    </p>

    <div v-if="t.context" class="td__ctx">
      <div class="td__ctx-head">背景参考 · 外部资讯，非本站数据</div>
      <p class="td__ctx-note">{{ t.context.note }}</p>
      <p class="td__ctx-src">
        来源：<a :href="t.context.source_url" target="_blank" rel="noopener noreferrer">{{ t.context.source_name }}</a>
        <template v-if="t.context.published_on">（{{ t.context.published_on }}）</template>
      </p>
    </div>

    <p class="td__note">
      趋势只说明「历史最难年还值不值得当参考」，不是报考建议；三年数据仅两个年段，
      不用于预测明年门槛。分化率为正表示相对全省变松。
    </p>
  </div>
</template>

<style scoped>
.td {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: 1.7;
}
.td__lead {
  margin: 0 0 var(--space-2);
  color: var(--color-text);
  font-weight: 600;
}
.td__row {
  margin: 0 0 var(--space-1);
  display: flex;
  gap: var(--space-2);
}
.td__k {
  flex: 0 0 4.5em;
  color: var(--color-text-muted);
}
.td__v {
  flex: 1;
  min-width: 0;
}
.td__ctx {
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-left: 3px solid var(--color-border-strong);
  background: var(--color-bg-subtle);
  border-radius: var(--radius-sm);
}
.td__ctx-head {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  margin-bottom: 2px;
}
.td__ctx-note {
  margin: 0;
}
.td__ctx-src {
  margin: 4px 0 0;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}
.td__note {
  margin: var(--space-2) 0 0;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}
.td--compact {
  font-size: var(--text-xs);
}
@media (max-width: 640px) {
  .td__row {
    flex-direction: column;
    gap: 0;
  }
  .td__k {
    flex: none;
  }
}
</style>
