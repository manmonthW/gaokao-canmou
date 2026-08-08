<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'
import type { MajorFlagDef } from '@/types'

// 报考资格自查清单（D2c）：位次只解决「够不够得着」，
// 这一页解决「有没有资格报」——后者是一票否决项。
const majorFlags = ref<MajorFlagDef[]>([])

onMounted(async () => {
  const m = await api.meta().catch(() => null)
  majorFlags.value = m?.major_flags || []
})

// 体检受限常见类目的静态提示（详情以官方体检规定 PDF 为准）
const bodyChecks = [
  { k: '军队院校', note: '执行军队院校招收学员体格检查标准，体检结论分指挥/非指挥等，不合格不录取。' },
  { k: '公安警察类', note: '身高、体重、视力、体能测试均有门槛，提前批报考前先看当年规定。' },
  { k: '招飞（空军/海军/民航）', note: '初检→复检→背景调查流程长，视力与身体条件极其严格。' },
  { k: '医学类', note: '色盲色弱通常限报临床、口腔、药学等专业，以院校招生章程为准。' },
  { k: '师范/航海/定向类', note: '部分专业对身高、听力、口吃等有附加要求，录取后可能需签协议。' },
]
</script>

<template>
  <div class="page">
    <div class="lib-eyebrow"><span class="lib-eyebrow__dot"></span>资料库 · 资格自查</div>
    <h1 class="page__title">报考资格自查清单</h1>
    <p class="page__sub">
      位次比较只回答「够不够得着」，但「能不能报」由资格一票否决：
      选科要求、体检结论、单科成绩、特殊招生条件任一不满足，投档即被退档。
      本清单不保存勾选结果，请逐项自查后在纸质清单上确认。
    </p>

    <el-card class="card" shadow="never">
      <template #header><div class="card__head"><span>① 选科要求（3+1+2）</span></div></template>
      <ul class="list">
        <li>首选科目（物理/历史）决定你属于哪个学科类，与考生档案一致。</li>
        <li>再选两科常被专业要求约束（如「化学必选」「化学/生物 2 选 1」）。</li>
        <li>
          2027 年在辽选科要求以官方发布为准（通常于考前一年底至当年初发布）；
          官方要求入库后，「智能匹配」页填写再选科目即可自动过滤不可报单元。
        </li>
        <li>在「智能匹配」页的考生档案中填写再选科目（选填，可随时修改）。</li>
      </ul>
    </el-card>

    <el-card class="card" shadow="never">
      <template #header><div class="card__head"><span>② 体检结论</span></div></template>
      <p class="hint-line">体检结论在高考后由各县区招办下发，受限专业会明确标注。常见门槛类目：</p>
      <el-table :data="bodyChecks" size="small" border fit>
        <el-table-column prop="k" label="类目" width="160" />
        <el-table-column prop="note" label="要点" min-width="320" show-overflow-tooltip />
      </el-table>
      <p class="hint-line">
        详细规定见资料库 PDF：军校体检规定 / 警校高考体检规定 / 空军招飞体检规定 /
        定向士官生体检规定 / 三大招飞报考流程及体检。
      </p>
    </el-card>

    <el-card class="card" shadow="never">
      <template #header><div class="card__head"><span>③ 单科成绩与外语语种</span></div></template>
      <ul class="list">
        <li>部分外语类、国际课程类专业设英语单科最低分（如 ≥110/120），以院校招生章程为准。</li>
        <li>中外合作办学专业常要求英语语种考生，部分授课为全英文。</li>
        <li>部分院校的数学类、计算机类专业对数学单科有要求。</li>
      </ul>
    </el-card>

    <el-card class="card" shadow="never">
      <template #header><div class="card__head"><span>④ 特殊报考标记（匹配结果中会以徽标提示）</span></div></template>
      <div v-if="majorFlags.length" class="flag-list">
        <div v-for="d in majorFlags" :key="d.flag" class="flag-item">
          <el-tag :type="d.severity === 'warn' ? 'warning' : 'info'" effect="plain">{{ d.label }}</el-tag>
          <span class="flag-item__note">{{ d.note }}</span>
        </div>
      </div>
      <p v-else class="hint-line">标记词表加载失败，请刷新重试。</p>
      <p class="hint-line">
        在「智能匹配」页可勾选「排除」相应标记；工作台方案分析会对含标记志愿给出核实提醒；
        导出方案 xlsx 中「报考标记」列会完整列出。
      </p>
    </el-card>

    <el-card class="card" shadow="never">
      <template #header><div class="card__head"><span>⑤ 其他硬条件</span></div></template>
      <ul class="list">
        <li>少数民族预科 / 民族班：仅限符合相应民族条件的考生。</li>
        <li>定向就业：录取前通常需与定向单位签协议，违约成本高，务必看清去向。</li>
        <li>专项计划（国家/地方/高校）：需满足户籍、学籍与实施区域条件。</li>
        <li>边防军人子女预科班：仅限符合条件的军人子女。</li>
        <li>征集志愿与常规志愿位次不可比：本站匹配已自动排除征集志愿数据。</li>
      </ul>
    </el-card>

    <p class="foot">
      以上为通用提醒，最终资格判定以辽宁省招考办与各院校当年招生章程、体检结论为准。
    </p>
  </div>
</template>

<style scoped>
.lib-eyebrow { display: inline-flex; align-items: center; gap: var(--space-2); font-size: var(--text-xs); color: var(--color-text-muted); margin-bottom: var(--space-2); }
.lib-eyebrow__dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-text-muted); }
.page__title { font-size: var(--text-2xl); }
.page__sub { color: var(--color-text-secondary); margin: var(--space-2) 0 var(--space-4); max-width: 820px; line-height: 1.7; }
.card { margin-bottom: var(--space-4); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
.card__head { font-weight: 600; }
.list { margin: 0; padding-left: 1.4em; line-height: 2; color: var(--color-text-secondary); }
.hint-line { color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.8; margin: var(--space-2) 0; }
.flag-list { display: flex; flex-direction: column; gap: var(--space-3); }
.flag-item { display: flex; align-items: baseline; gap: var(--space-3); flex-wrap: wrap; }
.flag-item__note { color: var(--color-text-secondary); font-size: var(--text-sm); }
.foot { color: var(--color-text-muted); font-size: var(--text-xs); line-height: 1.7; }
</style>
