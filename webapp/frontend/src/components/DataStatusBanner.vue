<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'

const status = ref<any>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    status.value = await api.dataStatus()
  } catch {
    status.value = null
  } finally {
    loading.value = false
  }
})

function fmt(s?: string | null): string {
  return s ? s.replace('T', ' ').slice(0, 19) : '—'
}
</script>

<template>
  <div v-if="!loading && status" class="ds-banner">
    <el-alert
      v-if="status.pending_batches && status.pending_batches.length"
      type="warning"
      :closable="false"
      show-icon
      class="ds-banner__alert"
    >
      <template #title>当前年度部分批次尚未发布或入库</template>
      <div class="ds-banner__tags">
        <el-tag
          v-for="(b, i) in status.pending_batches"
          :key="i"
          type="warning"
          effect="light"
          size="small"
          class="ds-banner__tag"
        >
          {{ b.year }} · {{ b.category }} · {{ b.subject }} · {{ b.batch }}（{{ b.status }}）
        </el-tag>
      </div>
    </el-alert>

    <div v-if="status.release" class="ds-banner__ver">
      <el-tag type="success" effect="plain" size="small">{{ status.release.status }}</el-tag>
      <span>版本 <b class="tnum">{{ status.release.version }}</b></span>
      <span class="ds-banner__muted">数据截止 {{ fmt(status.release.data_as_of) }}</span>
      <span class="ds-banner__muted">覆盖 {{ status.release.covered_years.join('、') }}</span>
    </div>
  </div>
</template>

<style scoped>
.ds-banner__alert {
  margin-bottom: var(--space-3);
}
.ds-banner__tags {
  margin-top: var(--space-2);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.ds-banner__ver {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  padding: var(--space-2) 0;
}
.ds-banner__muted {
  color: var(--color-text-muted);
}
</style>
