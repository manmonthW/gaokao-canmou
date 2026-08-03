<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getJson } from '@/api/client'
import type { DataStatusResponse, MetaResponse } from '@/types'

const status = ref<DataStatusResponse | null>(null)
const meta = ref<MetaResponse | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    const [s, m] = await Promise.all([
      getJson<DataStatusResponse>('/data-status'),
      getJson<MetaResponse>('/meta'),
    ])
    status.value = s
    meta.value = m
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
})

function fmtDateTime(s?: string | null): string {
  return s ? s.replace('T', ' ').slice(0, 19) : '—'
}

// 当前年度「普通类·专科批(常规)」官方尚未发布、且库内无对应数据，
// 属于悬空待发布项，不在首页横幅展示（仍保留于发布状态表，便于后续跟踪）。
const HIDDEN_PENDING = (b: { category?: string; batch?: string }) =>
  !(b.category === '普通类' && b.batch === '专科批')

const visiblePending = computed(() =>
  (status.value?.pending_batches ?? []).filter(HIDDEN_PENDING)
)
</script>

<template>
  <div class="page">
    <section class="hero">
      <h1>了解数据，再做决定</h1>
      <p class="hero__sub">
        本工具基于辽宁省往年录取数据，帮助你定位位次、发现适合的院校与专业。
        所有结论仅作参考，最终以辽宁省招考部门及院校官方信息为准。
      </p>
    </section>

    <el-alert
      v-if="error"
      type="error"
      :title="'数据加载失败：' + error"
      show-icon
      :closable="false"
    />

    <div v-if="loading" class="loading">加载数据状态…</div>

    <template v-else-if="status">
      <!-- 待发布批次横幅：必须显式展示，不藏说明页 -->
      <el-alert
        v-if="visiblePending.length"
        type="warning"
        :closable="false"
        show-icon
        class="banner"
      >
        <template #title>
          当前年度部分批次尚未发布或入库
        </template>
        <div class="banner__list">
          <el-tag
            v-for="(b, i) in visiblePending"
            :key="i"
            type="warning"
            effect="light"
            class="banner__tag"
          >
            {{ b.year }} · {{ b.category }} · {{ b.subject }} · {{ b.batch }}（{{ b.status }}）
          </el-tag>
        </div>
      </el-alert>

      <!-- 数据版本卡 -->
      <el-card v-if="status.release" class="card" shadow="never">
        <template #header>
          <div class="card__head">
            <span>当前数据版本</span>
            <el-tag type="success" effect="plain">{{ status.release.status }}</el-tag>
          </div>
        </template>
        <div class="kv">
          <div class="kv__item">
            <span class="kv__k">版本号</span>
            <span class="kv__v tnum">{{ status.release.version }}</span>
          </div>
          <div class="kv__item">
            <span class="kv__k">数据截止</span>
            <span class="kv__v tnum">{{ fmtDateTime(status.release.data_as_of) }}</span>
          </div>
          <div class="kv__item">
            <span class="kv__k">覆盖年份</span>
            <span class="kv__v tnum">{{ status.release.covered_years.join('、') }}</span>
          </div>
          <div class="kv__item kv__item--full">
            <span class="kv__k">数据说明</span>
            <span class="kv__v">{{ status.release.quality_summary }}</span>
          </div>
        </div>
      </el-card>

      <!-- 数据覆盖统计 -->
      <el-card class="card" shadow="never">
        <template #header><div class="card__head"><span>数据覆盖（按年份 / 科类）</span></div></template>
        <el-table :data="status.coverage" size="small" border>
          <el-table-column prop="year" label="年份" width="100" />
          <el-table-column prop="category" label="科类" width="120" />
          <el-table-column prop="count" label="录取记录数" align="right">
            <template #default="{ row }"><span class="tnum">{{ row.count.toLocaleString() }}</span></template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 可用筛选枚举（后续页面复用） -->
      <el-card v-if="meta" class="card" shadow="never">
        <template #header><div class="card__head"><span>可选维度（已就绪，供后续检索/匹配使用）</span></div></template>
        <div class="chips">
          <div class="chips__group"><b>年份</b> <el-tag v-for="y in meta.years" :key="y" size="small">{{ y }}</el-tag></div>
          <div class="chips__group"><b>科类</b> <el-tag v-for="c in meta.categories" :key="c" size="small">{{ c }}</el-tag></div>
          <div class="chips__group"><b>学科类</b> <el-tag v-for="s in meta.subjects" :key="s" size="small">{{ s }}</el-tag></div>
          <div class="chips__group"><b>批次</b> <el-tag v-for="b in meta.batches" :key="b" size="small">{{ b }}</el-tag></div>
        </div>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.hero {
  margin-bottom: var(--space-6);
}
.hero h1 {
  font-size: var(--text-2xl);
}
.hero__sub {
  color: var(--color-text-secondary);
  max-width: 720px;
  margin-top: var(--space-2);
}
.loading {
  padding: var(--space-8);
  text-align: center;
  color: var(--color-text-muted);
}
.banner {
  margin-bottom: var(--space-4);
}
.banner__list {
  margin-top: var(--space-2);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.card {
  margin-bottom: var(--space-4);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}
.kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3) var(--space-5);
}
.kv__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.kv__item--full {
  grid-column: 1 / -1;
}
.kv__k {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}
.kv__v {
  font-size: var(--text-base);
}
.chips {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.chips__group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.chips__group b {
  color: var(--color-text-secondary);
  margin-right: var(--space-1);
  font-weight: 500;
}
</style>
