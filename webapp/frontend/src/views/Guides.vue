<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'
import type { GuidesResponse, GuideItem } from '@/types'

const data = ref<GuidesResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

// 阅读器：全屏对话框内嵌 PDF（iframe），另提供新窗口打开与下载
const viewerVisible = ref(false)
const viewerItem = ref<GuideItem | null>(null)

function fmtSize(n: number | null): string {
  if (n == null) return '—'
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await api.guides()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function openViewer(it: GuideItem) {
  if (!it.available) return
  viewerItem.value = it
  viewerVisible.value = true
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="lib-eyebrow"><span class="lib-eyebrow__dot"></span>资料库 · 官方文件</div>
    <h1 class="page__title">报考说明</h1>
    <p class="page__sub">
      辽宁省 2026 年官方招考文件在线阅读。建议按「总政策 → 填报操作 → 专项通道」的顺序阅读：
      先读懂规则，再学操作，报考军校/公安的同学别忘了对应的专项文件有时限要求。
    </p>

    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" class="card" />

    <template v-if="data">
      <section v-for="(g, gi) in data.groups" :key="g.key" class="grp">
        <div class="grp__head">
          <span class="grp__num tnum">{{ gi + 1 }}</span>
          <div>
            <h2 class="grp__title">{{ g.title }}</h2>
            <p class="grp__desc">{{ g.desc }}</p>
          </div>
        </div>
        <div class="grp__grid">
          <el-card
            v-for="it in g.items"
            :key="it.id"
            class="doc"
            shadow="hover"
            :class="{ 'doc--disabled': !it.available }"
            @click="openViewer(it)"
          >
            <div class="doc__top">
              <span class="doc__pdf">PDF</span>
              <el-tag size="small" :type="it.tag === '必读' ? 'danger' : it.tag.includes('最新') ? 'warning' : 'info'" effect="plain">{{ it.tag }}</el-tag>
            </div>
            <div class="doc__title">{{ it.title }}</div>
            <p class="doc__summary">{{ it.summary }}</p>
            <div class="doc__points">
              <span v-for="p in it.points" :key="p" class="doc__point">{{ p }}</span>
            </div>
            <div class="doc__foot">
              <span class="doc__size tnum">{{ fmtSize(it.size_bytes) }}</span>
              <span v-if="it.available" class="doc__open">点击阅读 →</span>
              <span v-else class="doc__missing">文件待上传</span>
            </div>
          </el-card>
        </div>
      </section>

      <p class="note">{{ data.note }}</p>
    </template>

    <!-- PDF 阅读器 -->
    <el-dialog
      v-model="viewerVisible"
      :title="viewerItem?.title"
      fullscreen
      append-to-body
      class="viewer"
    >
      <iframe
        v-if="viewerItem && viewerVisible"
        :src="api.guidePdfUrl(viewerItem.id)"
        class="viewer__frame"
        :title="viewerItem.title"
      />
      <template #footer>
        <el-button @click="viewerVisible = false">关闭</el-button>
        <el-button
          plain
          tag="a"
          :href="viewerItem ? api.guidePdfUrl(viewerItem.id) : '#'"
          target="_blank"
        >新窗口打开</el-button>
        <el-button
          type="primary"
          tag="a"
          :href="viewerItem ? api.guidePdfUrl(viewerItem.id) : '#'"
          :download="viewerItem?.filename"
        >下载 PDF</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.lib-eyebrow { display: inline-flex; align-items: center; gap: var(--space-2); font-size: var(--text-xs); color: var(--color-text-muted); margin-bottom: var(--space-2); }
.lib-eyebrow__dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-text-muted); }
.page__title { font-size: var(--text-2xl); }
.page__sub { color: var(--color-text-secondary); margin: var(--space-2) 0 var(--space-5); max-width: 860px; line-height: 1.8; }
.card { margin-bottom: var(--space-4); }

.grp { margin-bottom: var(--space-7); }
.grp__head { display: flex; gap: var(--space-3); align-items: flex-start; margin-bottom: var(--space-3); }
.grp__num {
  flex: none; width: 28px; height: 28px; border-radius: 50%;
  background: var(--color-primary, #3370ff); color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: var(--text-sm); font-weight: 600; margin-top: 2px;
}
.grp__title { font-size: var(--text-lg); margin: 0; }
.grp__desc { color: var(--color-text-muted); font-size: var(--text-sm); margin: 2px 0 0; }

.grp__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--space-4); }
.doc { cursor: pointer; border-radius: var(--radius-lg); transition: transform 0.12s; height: 100%; }
.doc:hover { transform: translateY(-2px); }
.doc--disabled { cursor: not-allowed; opacity: 0.6; }
.doc__top { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-2); }
.doc__pdf {
  font-size: 10px; font-weight: 700; letter-spacing: 0.05em;
  color: #d93026; background: rgba(217, 48, 38, 0.08);
  border-radius: 4px; padding: 2px 6px;
}
.doc__title { font-weight: 600; font-size: var(--text-base); line-height: 1.5; margin-bottom: var(--space-2); }
.doc__summary { color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.7; margin: 0 0 var(--space-3); }
.doc__points { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: var(--space-3); }
.doc__point { font-size: var(--text-xs); color: var(--color-text-muted); border: 1px solid var(--color-border, #e3e8ef); border-radius: 999px; padding: 2px 8px; }
.doc__foot { display: flex; align-items: center; justify-content: space-between; border-top: 1px dashed var(--color-border, #e3e8ef); padding-top: var(--space-2); }
.doc__size { color: var(--color-text-muted); font-size: var(--text-xs); }
.doc__open { color: var(--color-primary, #3370ff); font-size: var(--text-xs); }
.doc__missing { color: var(--color-text-muted); font-size: var(--text-xs); }

.note { color: var(--color-text-muted); font-size: var(--text-xs); margin-top: var(--space-4); }

.viewer :deep(.el-dialog__body) { padding: 0; height: calc(100vh - 110px); overflow: hidden; }
.viewer__frame { width: 100%; height: 100%; border: none; }
</style>
