<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'

const route = useRoute()
const router = useRouter()
const code = ref<string>(route.params.code as string)
const data = ref<any>(null)
const loading = ref(true)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await api.school(code.value)
  } catch (e: any) {
    error.value = e?.message || '加载失败'
    data.value = null
  } finally {
    loading.value = false
  }
}

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
              <span v-if="!data.profile.is_985 && !data.profile.is_211 && !data.profile.is_dfc">—</span>
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
.hint { color: var(--color-text-muted); font-size: var(--text-xs); margin: var(--space-2) 0 0; }
.intro { margin: var(--space-4) 0 0; padding: var(--space-3) var(--space-4); background: var(--color-bg-subtle, #f7f9fc); border-radius: var(--radius-md); font-size: var(--text-sm); line-height: 1.8; color: var(--color-text-secondary); }
.empty { padding: var(--space-8); text-align: center; color: var(--color-text-muted); }
</style>
