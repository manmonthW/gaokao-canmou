<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'

const route = useRoute()
const router = useRouter()
const code = ref<string>(route.params.code as string)
const majorName = ref<string>((route.query.major_name as string) || '')
const category = ref<string>((route.query.category as string) || '')
const records = ref<any[]>([])
const schoolName = ref<string>('')
const loading = ref(true)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    const [school, res] = await Promise.all([
      api.school(code.value),
      api.schoolMajor(code.value, {
        major_name: majorName.value,
        category: category.value || undefined,
      }),
    ])
    schoolName.value = school?.name || code.value
    records.value = res.records || []
  } catch (e: any) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(
  () => [route.params.code, route.query.major_name, route.query.category],
  ([c, m, cat]) => {
    code.value = c as string
    majorName.value = (m as string) || ''
    category.value = (cat as string) || ''
    load()
  },
)
</script>

<template>
  <div class="page">
    <el-button text @click="router.back()" class="back">返回</el-button>

    <div v-if="loading" class="empty">加载中…</div>
    <el-alert v-else-if="error" type="error" :title="error" show-icon :closable="false" />

    <template v-else>
      <h1 class="page__title">{{ schoolName }} · {{ majorName }}</h1>
      <p class="page__sub">历年最低分、最低位次、批次与征集情况。</p>

      <el-alert
        v-if="!records.length"
        type="info"
        :closable="false"
        class="card"
        title="该院校此专业在当前筛选条件下暂无记录。可能原因：专业名称含方向后缀、或属征集/提前批，请到数据中心按专业名检索全部记录。"
      />

      <el-table v-else :data="records" size="small" border class="card">
        <el-table-column prop="year" label="年份" width="90" />
        <el-table-column prop="category" label="类别" width="100" />
        <el-table-column prop="subject" label="学科类" width="120" />
        <el-table-column prop="batch" label="批次" width="130" />
        <el-table-column label="征集" width="80" align="center">
          <template #default="{ row }"><el-tag v-if="row.is_collection" size="small" type="warning" effect="plain">征集</el-tag><span v-else>—</span></template>
        </el-table-column>
        <el-table-column prop="score_kind" label="类型" width="120" />
        <el-table-column prop="lowest_score" label="最低分" width="110" align="right">
          <template #default="{ row }"><span class="tnum" v-if="row.lowest_score != null">{{ row.lowest_score }}</span><span v-else>—</span></template>
        </el-table-column>
        <el-table-column prop="lowest_rank" label="最低位次" width="120" align="right">
          <template #default="{ row }"><span class="tnum" v-if="row.lowest_rank != null">{{ row.lowest_rank.toLocaleString() }}</span><span v-else>—</span></template>
        </el-table-column>
      </el-table>
    </template>
  </div>
</template>

<style scoped>
.page__title { font-size: var(--text-2xl); }
.page__sub { color: var(--color-text-secondary); margin: var(--space-2) 0 var(--space-4); }
.back { margin-bottom: var(--space-3); }
.card { margin-bottom: var(--space-4); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
.empty { padding: var(--space-8); text-align: center; color: var(--color-text-muted); }
</style>
