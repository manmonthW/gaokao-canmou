<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import type { MajorDetail } from '@/types'

/**
 * 专业详情抽屉：从任意页面（专业查询 / 智能匹配 / 院校详情）右侧滑出，
 * 展示标准专业 + 热门专业图文（OCR 资料），看完关闭即回到原页面。
 * 与「点击大学在右侧出现」的体验一致。
 */
const props = defineProps<{ name: string | null }>()
const emit = defineEmits<{ (e: 'update:name', v: string | null): void }>()

const router = useRouter()
const open = ref(false)
const data = ref<MajorDetail | null>(null)
const loading = ref(false)

watch(
  () => props.name,
  async (name) => {
    if (!name) {
      open.value = false
      return
    }
    open.value = true
    loading.value = true
    data.value = null
    try {
      data.value = await api.catalogDetail(name)
    } catch (e: any) {
      data.value = null
    } finally {
      loading.value = false
    }
  },
)

function onClose() {
  open.value = false
  emit('update:name', null)
}

function viewAdmission(name: string) {
  onClose()
  router.push({ path: '/datacenter', query: { major: name } })
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
        <span class="dh__title">{{ data?.name || '专业详情' }}</span>
      </div>
    </template>

    <div v-if="loading" class="loading">
      <el-icon class="is-loading"><Loading /></el-icon> 加载中…
    </div>

    <template v-else-if="data">
      <!-- 基础信息 -->
      <div class="d-section">
        <div class="d-tags">
          <el-tag size="small" type="info">{{ data.discipline }}</el-tag>
          <el-tag size="small" type="info">{{ data.category }}</el-tag>
          <el-tag size="small">代码 {{ data.code }}</el-tag>
        </div>
      </div>

      <!-- 图文详情（OCR 资料） -->
      <template v-if="data.hot_profile">
        <div v-if="data.hot_profile.has_image" class="d-image">
          <img :src="api.hotImageUrl(data.name)" :alt="data.name" loading="lazy" />
        </div>

        <div class="d-section" v-if="data.hot_profile.degree || data.hot_profile.length">
          <div class="d-grid">
            <div v-if="data.hot_profile.degree"><span class="d-k">授予学位</span><span class="d-v">{{ data.hot_profile.degree }}</span></div>
            <div v-if="data.hot_profile.length"><span class="d-k">学制</span><span class="d-v">{{ data.hot_profile.length }} 年</span></div>
            <div v-if="data.hot_profile.gender_ratio"><span class="d-k">男女比例</span><span class="d-v">{{ data.hot_profile.gender_ratio }}</span></div>
          </div>
        </div>

        <div class="d-section" v-if="data.hot_profile.introduction">
          <h4 class="d-h">专业介绍</h4>
          <p class="d-p">{{ data.hot_profile.introduction }}</p>
        </div>

        <div class="d-section" v-if="data.hot_profile.subject_req">
          <h4 class="d-h">选科要求</h4>
          <p class="d-p">{{ data.hot_profile.subject_req }}</p>
        </div>

        <div class="d-section" v-if="data.hot_profile.career">
          <h4 class="d-h">就业前景</h4>
          <p class="d-p">{{ data.hot_profile.career }}</p>
        </div>

        <div class="d-section" v-if="data.hot_profile.training_goal">
          <h4 class="d-h">培养目标</h4>
          <p class="d-p">{{ data.hot_profile.training_goal }}</p>
        </div>

        <div class="d-section" v-if="data.hot_profile.main_courses">
          <h4 class="d-h">主要课程</h4>
          <p class="d-p">{{ data.hot_profile.main_courses }}</p>
        </div>

        <div class="d-section" v-if="data.hot_profile.employment_dir">
          <h4 class="d-h">就业方向</h4>
          <p class="d-p">{{ data.hot_profile.employment_dir }}</p>
        </div>

        <div class="d-section" v-if="data.hot_profile.postgrad_dir">
          <h4 class="d-h">考研方向</h4>
          <p class="d-p">{{ data.hot_profile.postgrad_dir }}</p>
        </div>

        <div class="d-section" v-if="data.hot_profile.hot_schools?.length">
          <h4 class="d-h">开设院校</h4>
          <div class="d-schools">
            <el-tag v-for="s in data.hot_profile.hot_schools" :key="s" size="small" class="d-school">{{ s }}</el-tag>
          </div>
        </div>
      </template>

      <el-empty v-else description="暂无该专业的图文资料" :image-size="80" />

      <!-- 在辽招生关联 -->
      <div class="d-section">
        <el-button type="primary" plain class="d-adm-btn" @click="viewAdmission(data.name)">
          查看在辽招生院校与分数 →
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.dh { display: flex; align-items: center; justify-content: space-between; width: 100%; }
.dh__title { font-weight: 600; }
.loading { text-align: center; padding: var(--space-8); color: var(--color-text-muted); }
.d-section { margin-bottom: var(--space-4); }
.d-tags { display: flex; gap: var(--space-2); flex-wrap: wrap; margin-bottom: var(--space-2); }
.d-image { margin-bottom: var(--space-4); border-radius: var(--radius-lg); overflow: hidden; box-shadow: var(--shadow-sm); }
.d-image img { width: 100%; display: block; }
.d-h { font-size: var(--text-sm); font-weight: 600; margin: 0 0 var(--space-2); color: var(--color-text, #333); }
.d-p { font-size: var(--text-sm); line-height: 1.7; color: var(--color-text-secondary); margin: 0; }
.d-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-2); }
.d-grid > div { display: flex; flex-direction: column; gap: 2px; }
.d-k { font-size: var(--text-xs); color: var(--color-text-muted); }
.d-v { font-size: var(--text-sm); font-weight: 500; }
.d-schools { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.d-school { margin: 0; }
.d-adm-btn { width: 100%; }
</style>
