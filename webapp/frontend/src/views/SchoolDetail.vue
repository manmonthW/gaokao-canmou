<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import StrengthBadges from '@/components/StrengthBadges.vue'
import type { StrengthTagDef, StrengthDiscipline, StrengthMajor } from '@/types'

const route = useRoute()
const router = useRouter()
const code = ref<string>(route.params.code as string)
const data = ref<any>(null)
const loading = ref(true)
const error = ref<string | null>(null)
// 实力标签词表（任务 #9）：与 Match.vue 一致从 /meta 获取，标签文案不硬编码
const meta = ref<{ strength_dictionary?: StrengthTagDef[] } | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    const [d, m] = await Promise.all([api.school(code.value), api.meta().catch(() => null)])
    data.value = d
    meta.value = m
  } catch (e: any) {
    error.value = e?.message || '加载失败'
    data.value = null
  } finally {
    loading.value = false
  }
}

// ---- 学科与专业实力明细（任务 #9）：文案/口径说明一律取自 strength_dictionary ----
const dictMap = computed(
  () => new Map((meta.value?.strength_dictionary || []).map((d) => [d.tag, d])),
)
// 学科记录 → 词表 tag：四轮/五轮按评级拼 tag，双一流固定 tag
function discTag(d: StrengthDiscipline): string | null {
  if (d.source === 'eval4_official' && d.grade) return `四轮${d.grade}`
  if (d.source === 'eval5_a' && d.grade) return `五轮${d.grade}`
  if (d.source === 'dfc2022') return '双一流学科'
  return null
}
// 按学科分组：同一学科的多来源评级并列展示（如「四轮学科评估 A｜五轮学科评估 A+」）
const discGroups = computed(() => {
  const rows: StrengthDiscipline[] = data.value?.strength?.disciplines || []
  const map = new Map<string, { row: StrengthDiscipline; def: StrengthTagDef }[]>()
  for (const r of rows) {
    const def = discTag(r) ? dictMap.value.get(discTag(r)!) : undefined
    if (!def) continue // 词表未收录不硬造文案，直接不渲染该条
    const arr = map.get(r.discipline_name) || []
    arr.push({ row: r, def })
    map.set(r.discipline_name, arr)
  }
  return [...map.entries()].map(([name, items]) => ({ name, items }))
})
// 专业实力来源 → 词表 tag（与 StrengthBadges 保持一致）
const MAJOR_SOURCE_TAG: Record<string, string> = {
  swyc_national: '国一流专业',
  swyc_provincial: '省一流专业',
  ruanke: '软科评级',
}
function majorDef(source: string): StrengthTagDef | undefined {
  const tag = MAJOR_SOURCE_TAG[source]
  return tag ? dictMap.value.get(tag) : undefined
}
const strengthMajors = computed<StrengthMajor[]>(() => data.value?.strength?.majors || [])
const hasStrengthDetail = computed(
  () => discGroups.value.length > 0 || strengthMajors.value.length > 0,
)

function openMajor(major: string) {
  router.push({ path: `/school/${code.value}/major`, query: { major_name: major } })
}

onMounted(load)
watch(() => route.params.code, (c) => { code.value = c as string; load() })
</script>

<template>
  <div class="page">
    <el-button text @click="router.back()" class="back">← 返回</el-button>

    <div v-if="loading" class="empty">加载中…</div>
    <el-alert v-else-if="error" type="error" :title="error" show-icon :closable="false" />

    <template v-else-if="data">
      <h1 class="page__title">{{ data.name }} <span class="code">代码 {{ data.code }}</span></h1>

      <el-card v-if="data.profile" class="card" shadow="never">
        <template #header><div class="card__head"><span>院校画像</span></div></template>
        <div class="kv">
          <div class="kv__item"><span class="kv__k">省份</span><span class="kv__v">{{ data.profile.province || '—' }}</span></div>
          <div class="kv__item"><span class="kv__k">城市</span><span class="kv__v">{{ data.profile.city || '—' }}</span></div>
          <div class="kv__item"><span class="kv__k">层次</span><span class="kv__v">{{ data.profile.level || '—' }}</span></div>
          <div class="kv__item"><span class="kv__k">性质</span><span class="kv__v">{{ data.profile.nature || '—' }}</span></div>
          <div class="kv__item"><span class="kv__k">类型</span><span class="kv__v">{{ data.profile.type || '—' }}</span></div>
          <div class="kv__item"><span class="kv__k">隶属</span><span class="kv__v">{{ data.profile.affiliation || '—' }}</span></div>
          <div class="kv__item">
            <span class="kv__k">标签</span>
            <span class="kv__v">
              <el-tag v-if="data.profile.is_985" size="small" type="danger" effect="plain">985</el-tag>
              <el-tag v-if="data.profile.is_211" size="small" type="warning" effect="plain">211</el-tag>
              <el-tag v-if="data.profile.is_dfc" size="small" type="success" effect="plain">双一流</el-tag>
              <el-tooltip v-if="data.profile.postgrad_rate != null" content="保研率：本科毕业生获推免读研资格的比例（最新年口径，仅供参考）" placement="top">
                <el-tag size="small" type="primary" effect="plain">保研 {{ data.profile.postgrad_rate }}%</el-tag>
              </el-tooltip>
              <!-- 实力标签（任务 #9）：词表文案 + 来源口径 tooltip；空数组不渲染 -->
              <StrengthBadges :strength-tags="data.strength?.strength_tags || []" :dictionary="meta?.strength_dictionary" />
              <span v-if="!data.profile.is_985 && !data.profile.is_211 && !data.profile.is_dfc && data.profile.postgrad_rate == null && !(data.strength?.strength_tags?.length)">—</span>
            </span>
          </div>
          <div class="kv__item" v-if="data.profile.established"><span class="kv__k">建校年</span><span class="kv__v tnum">{{ data.profile.established }}</span></div>
          <div class="kv__item kv__item--full" v-if="data.profile.strength"><span class="kv__k">优势学科</span><span class="kv__v">{{ data.profile.strength }}</span></div>
          <div class="kv__item kv__item--full" v-if="data.profile.rank_ref"><span class="kv__k">参考排名</span><span class="kv__v">{{ data.profile.rank_ref }}</span></div>
          <div class="kv__item kv__item--full" v-if="data.profile.website">
            <span class="kv__k">官方网站</span>
            <span class="kv__v">
              <el-link type="primary" :href="data.profile.website" target="_blank" rel="noopener noreferrer">{{ data.profile.website }}</el-link>
            </span>
          </div>
        </div>
        <p class="intro" v-if="data.profile.intro">{{ data.profile.intro }}</p>
      </el-card>

      <!-- 学科与专业实力明细（任务 #9）：数据为空时整卡不渲染 -->
      <el-card v-if="hasStrengthDetail" class="card" shadow="never">
        <template #header><div class="card__head"><span>学科与专业实力明细</span></div></template>
        <!-- 学科评估/一流学科：同一学科多来源并列（如「四轮学科评估 A｜五轮学科评估 A+」），悬停看来源说明 -->
        <div v-if="discGroups.length" class="disc">
          <div v-for="g in discGroups" :key="g.name" class="disc__row">
            <span class="disc__name">{{ g.name }}</span>
            <span class="disc__evals">
              <template v-for="(it, i) in g.items" :key="it.row.source + '-' + (it.row.data_year ?? '')">
                <span v-if="i > 0" class="disc__sep">｜</span>
                <el-tooltip :content="it.def.source_note || it.def.label" placement="top">
                  <el-tag
                    size="small"
                    effect="plain"
                    class="disc__tag"
                    :class="{ 'disc__tag--unofficial': !it.row.official }"
                  >{{ it.def.label }}</el-tag>
                </el-tooltip>
              </template>
            </span>
          </div>
        </div>
        <!-- 一流专业建设点 / 第三方专业评级 -->
        <el-table v-if="strengthMajors.length" :data="strengthMajors" size="small" border>
          <el-table-column prop="major_name" label="专业" min-width="140" show-overflow-tooltip />
          <el-table-column label="实力认定" min-width="150">
            <template #default="{ row }">
              <el-tooltip v-if="majorDef(row.source)" :content="majorDef(row.source)!.source_note || majorDef(row.source)!.label" placement="top">
                <el-tag size="small" effect="plain" style="cursor: help;"
                  :type="majorDef(row.source)!.third_party ? 'info' : 'warning'">{{ majorDef(row.source)!.label }}</el-tag>
              </el-tooltip>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column label="评级/名次" width="110" align="right">
            <template #default="{ row }">
              <span class="tnum">{{ row.tier || (row.rank != null ? `第 ${row.rank} 名` : '—') }}</span>
            </template>
          </el-table-column>
          <el-table-column label="年份" width="80" align="right">
            <template #default="{ row }"><span class="tnum">{{ row.data_year ?? '—' }}</span></template>
          </el-table-column>
          <el-table-column prop="note" label="备注" min-width="120" show-overflow-tooltip />
        </el-table>
        <p class="hint">悬停各标签可查看来源与口径说明；非官方（虚线）与第三方来源已单独标注，仅供报考参考。</p>
      </el-card>

      <el-card v-if="data.city" class="card" shadow="never">
        <template #header><div class="card__head"><span>城市画像 · {{ data.city.city }}</span></div></template>
        <div class="kv">
          <div class="kv__item"><span class="kv__k">地理大区</span><span class="kv__v">{{ data.city.region || '—' }}</span></div>
          <div class="kv__item"><span class="kv__k">城市分级</span><span class="kv__v">{{ data.city.tier || '—' }}</span></div>
          <div class="kv__item"><span class="kv__k">城市群</span><span class="kv__v">{{ data.city.cluster || '—' }}</span></div>
          <div class="kv__item"><span class="kv__k">沿海</span><span class="kv__v">{{ data.city.coastal ? '是' : '否' }}</span></div>
          <div class="kv__item" v-if="data.city.gdp"><span class="kv__k">GDP（亿元）</span><span class="kv__v tnum">{{ data.city.gdp }}（{{ data.city.gdp_year }}）</span></div>
        </div>
      </el-card>

      <el-card class="card" shadow="never">
        <template #header><div class="card__head"><span>历年招生摘要</span></div></template>
        <el-table :data="data.yearly_summary" size="small" border>
          <el-table-column prop="year" label="年份" width="90" />
          <el-table-column prop="category" label="类别" width="100" />
          <el-table-column prop="subject" label="学科类" width="120" />
          <el-table-column prop="records" label="记录数" width="90" align="right">
            <template #default="{ row }"><span class="tnum">{{ row.records }}</span></template>
          </el-table-column>
          <el-table-column prop="major_count" label="专业数" width="90" align="right">
            <template #default="{ row }"><span class="tnum">{{ row.major_count }}</span></template>
          </el-table-column>
          <el-table-column label="最低分区间" align="right">
            <template #default="{ row }"><span class="tnum" v-if="row.lowest_score_range[0] != null">{{ row.lowest_score_range[0] }} ~ {{ row.lowest_score_range[1] }}</span></template>
          </el-table-column>
          <el-table-column label="最低位次区间" align="right">
            <template #default="{ row }"><span class="tnum" v-if="row.lowest_rank_range[0] != null">{{ row.lowest_rank_range[0] }} ~ {{ row.lowest_rank_range[1] }}</span></template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="card" shadow="never">
        <template #header><div class="card__head"><span>招生专业（点击查看历年趋势）</span></div></template>
        <div class="majors">
          <el-tag
            v-for="m in data.majors"
            :key="m.major_name + (m.major_code || '')"
            class="majors__tag"
            effect="light"
            @click="openMajor(m.major_name)"
          >
            {{ m.major_name }} <span class="majors__dim">（{{ m.years }}年 · {{ m.records }}条）</span>
            <span v-if="m.flags?.length" class="majors__flag" :title="m.flags.join('、')">⚑ {{ m.flags.join('/') }}</span>
          </el-tag>
        </div>
        <p class="hint" v-if="data.majors.length >= 300">仅显示前 300 个专业，可在数据中心按专业名检索全部记录。</p>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.page__title { font-size: var(--text-2xl); }
.code { font-size: var(--text-sm); color: var(--color-text-muted); font-weight: 400; margin-left: var(--space-2); }
.back { margin-bottom: var(--space-3); }
.card { margin-bottom: var(--space-4); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
.card__head { font-weight: 600; }
.kv { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: var(--space-3) var(--space-5); }
.kv__item { display: flex; flex-direction: column; gap: 2px; }
.kv__item--full { grid-column: 1 / -1; }
.kv__k { font-size: var(--text-xs); color: var(--color-text-muted); }
.kv__v { font-size: var(--text-base); display: flex; align-items: center; gap: var(--space-2); }
.majors { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.majors__tag { cursor: pointer; }
.majors__dim { color: var(--color-text-muted); font-size: var(--text-xs); }
.majors__flag { color: var(--el-color-warning); font-size: var(--text-xs); margin-left: 4px; }
/* 学科实力明细（任务 #9） */
.disc { display: flex; flex-direction: column; gap: var(--space-2); margin-bottom: var(--space-4); }
.disc__row { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.disc__name { font-size: var(--text-sm); font-weight: 600; min-width: 160px; }
.disc__evals { display: inline-flex; align-items: center; flex-wrap: wrap; gap: 2px; }
.disc__sep { color: var(--color-text-muted); font-size: var(--text-sm); }
.disc__tag { cursor: help; }
.disc__tag--unofficial { border-style: dashed; }
.hint { color: var(--color-text-muted); font-size: var(--text-xs); margin: var(--space-2) 0 0; }
.intro { margin: var(--space-4) 0 0; padding: var(--space-3) var(--space-4); background: var(--color-bg-subtle, #f7f9fc); border-radius: var(--radius-md); font-size: var(--text-sm); line-height: 1.8; color: var(--color-text-secondary); }
.empty { padding: var(--space-8); text-align: center; color: var(--color-text-muted); }
</style>
