<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'

/**
 * 院校详情抽屉：从主线（如智能匹配结果）内查看院校画像，
 * 看完关闭即回到原页面与滚动位置，不丢失决策现场。
 */
const props = defineProps<{ code: string | null }>()
const emit = defineEmits<{ (e: 'update:code', v: string | null): void }>()

const router = useRouter()
const open = ref(false)
const data = ref<any>(null)
const loading = ref(false)
const error = ref<string | null>(null)

watch(
  () => props.code,
  async (code) => {
    if (!code) {
      open.value = false
      return
    }
    open.value = true
    loading.value = true
    error.value = null
    data.value = null
    try {
      data.value = await api.school(code)
    } catch (e: any) {
      error.value = e?.message || '加载失败'
    } finally {
      loading.value = false
    }
  },
)

function onClose() {
  open.value = false
  emit('update:code', null)
}

function openFullPage() {
  if (props.code) router.push(`/school/${props.code}`)
}
</script>

<template>
  <el-drawer
    v-model="open"
    :size="480"
    direction="rtl"
    :with-header="true"
    @closed="onClose"
  >
    <template #header>
      <div class="dh">
        <span class="dh__title">院校详情</span>
        <el-button link type="primary" size="small" @click="openFullPage">在整页打开 ↗</el-button>
      </div>
    </template>

    <div v-if="loading" class="empty">加载中…</div>
    <el-alert v-else-if="error" type="error" :title="error" show-icon :closable="false" />

    <div v-else-if="data" class="body">
      <h2 class="name">{{ data.name }} <span class="code">代码 {{ data.code }}</span></h2>

      <div v-if="data.profile" class="sect">
        <div class="sect__t">院校画像</div>
        <div class="tags">
          <el-tag v-if="data.profile.is_985" size="small" type="danger" effect="plain">985</el-tag>
          <el-tag v-if="data.profile.is_211" size="small" type="warning" effect="plain">211</el-tag>
          <el-tag v-if="data.profile.is_dfc" size="small" type="success" effect="plain">双一流</el-tag>
          <el-tooltip v-if="data.profile.postgrad_rate != null" content="保研率：本科毕业生获推免读研资格的比例（最新年口径，仅供参考）" placement="top">
            <el-tag size="small" type="primary" effect="plain">保研 {{ data.profile.postgrad_rate }}%</el-tag>
          </el-tooltip>
        </div>
        <div class="kv">
          <div><span class="k">省份/城市</span><span class="v">{{ data.profile.province || '—' }} · {{ data.profile.city || '—' }}</span></div>
          <div><span class="k">层次</span><span class="v">{{ data.profile.level || '—' }}</span></div>
          <div><span class="k">性质</span><span class="v">{{ data.profile.nature || '—' }}</span></div>
          <div><span class="k">类型</span><span class="v">{{ data.profile.type || '—' }}</span></div>
          <div v-if="data.profile.affiliation"><span class="k">隶属</span><span class="v">{{ data.profile.affiliation }}</span></div>
          <div v-if="data.profile.established"><span class="k">建校年</span><span class="v tnum">{{ data.profile.established }}</span></div>
        </div>
        <p v-if="data.profile.strength" class="line"><span class="k">优势学科：</span>{{ data.profile.strength }}</p>
        <p v-if="data.profile.intro" class="intro">{{ data.profile.intro }}</p>
      </div>

      <div v-if="data.city" class="sect">
        <div class="sect__t">城市 · {{ data.city.city }}</div>
        <div class="kv">
          <div><span class="k">地理大区</span><span class="v">{{ data.city.region || '—' }}</span></div>
          <div><span class="k">城市分级</span><span class="v">{{ data.city.tier || '—' }}</span></div>
          <div v-if="data.city.gdp"><span class="k">GDP（亿元）</span><span class="v tnum">{{ data.city.gdp }}（{{ data.city.gdp_year }}）</span></div>
          <div><span class="k">沿海</span><span class="v">{{ data.city.coastal ? '是' : '否' }}</span></div>
        </div>
      </div>

      <div v-if="data.yearly_summary && data.yearly_summary.length" class="sect">
        <div class="sect__t">历年招生摘要</div>
        <el-table :data="data.yearly_summary" size="small" border>
          <el-table-column prop="year" label="年" width="64" />
          <el-table-column prop="subject" label="学科类" min-width="90" />
          <el-table-column label="最低位次区间" align="right">
            <template #default="{ row }">
              <span class="tnum" v-if="row.lowest_rank_range[0] != null">{{ row.lowest_rank_range[0] }} ~ {{ row.lowest_rank_range[1] }}</span>
              <span v-else>—</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.dh { display: flex; align-items: center; justify-content: space-between; width: 100%; }
.dh__title { font-weight: 600; }
.empty { padding: var(--space-8); text-align: center; color: var(--color-text-muted); }
.name { font-size: var(--text-xl); margin-bottom: var(--space-4); }
.code { font-size: var(--text-sm); color: var(--color-text-muted); font-weight: 400; }
.sect { margin-bottom: var(--space-5); }
.sect__t { font-weight: 600; margin-bottom: var(--space-2); padding-bottom: var(--space-1); border-bottom: 1px solid var(--color-border); }
.tags { display: flex; gap: var(--space-2); margin-bottom: var(--space-2); }
.kv { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-2) var(--space-4); }
.kv > div { display: flex; flex-direction: column; gap: 2px; }
.k { font-size: var(--text-xs); color: var(--color-text-muted); }
.v { font-size: var(--text-sm); }
.line { font-size: var(--text-sm); color: var(--color-text-secondary); margin: var(--space-3) 0 0; }
.intro { margin: var(--space-3) 0 0; padding: var(--space-3); background: var(--color-bg); border-radius: var(--radius-md); font-size: var(--text-sm); line-height: 1.8; color: var(--color-text-secondary); }
</style>
