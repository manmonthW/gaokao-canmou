<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import type { HotSchool, HotSchoolCategory } from '@/types'

const router = useRouter()
const q = ref('')
const results = ref<any[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const searched = ref(false)

async function onSearch() {
  if (!q.value.trim()) return
  loading.value = true
  error.value = null
  searched.value = true
  try {
    results.value = await api.searchSchools(q.value.trim())
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function open(code: string) {
  router.push(`/school/${code}`)
}

// ---- 热门大学介绍 ----
const categories = ref<HotSchoolCategory[]>([])
const activeCat = ref<string>('')
const hotSchools = ref<HotSchool[]>([])
const hotLoading = ref(false)
const dialogVisible = ref(false)
const current = ref<HotSchool | null>(null)

async function loadCategories() {
  try {
    const r = await api.hotSchoolCategories()
    categories.value = r.categories
  } catch (e) {
    console.error('加载热门大学分类失败', e)
  }
}

async function loadHot(category: string) {
  activeCat.value = category
  hotLoading.value = true
  try {
    const r = await api.hotSchools(category || undefined)
    hotSchools.value = r.schools
  } catch (e) {
    console.error('加载热门大学失败', e)
  } finally {
    hotLoading.value = false
  }
}

function openHot(s: HotSchool) {
  current.value = s
  dialogVisible.value = true
}

function goSchool(code?: string | null) {
  if (code) {
    dialogVisible.value = false
    open(code)
  }
}

onMounted(() => {
  loadCategories().then(() => {
    if (categories.value.length) loadHot(categories.value[0].category)
  })
})
</script>

<template>
  <div class="page">
    <div class="lib-eyebrow"><span class="lib-eyebrow__dot"></span>资料库 · 查询工具</div>
    <h1 class="page__title">院校查询</h1>
    <p class="page__sub">按院校名称或代码搜索，查看院校画像、城市与历年招生专业。随时查询，不影响你的定位与方案。</p>

    <el-input
      v-model="q"
      placeholder="输入院校名称或代码，如：大连理工"
      clearable
      class="search"
      @keyup.enter="onSearch"
    >
      <template #append>
        <el-button :loading="loading" @click="onSearch">搜索</el-button>
      </template>
    </el-input>

    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" class="card" />

    <div v-if="searched && !loading && !results.length" class="empty">
      未找到匹配的院校，请尝试更短的关键词。
    </div>

    <div class="grid" v-if="results.length">
      <el-card
        v-for="s in results"
        :key="s.code"
        class="school"
        shadow="hover"
        @click="open(s.code)"
      >
        <div class="school__name">{{ s.name }}</div>
        <div class="school__meta">
          <el-tag v-if="s.is_985" size="small" type="danger" effect="plain">985</el-tag>
          <el-tag v-if="s.is_211" size="small" type="warning" effect="plain">211</el-tag>
          <el-tag v-if="s.is_dfc" size="small" type="success" effect="plain">双一流</el-tag>
          <span class="school__dim">{{ s.province }} · {{ s.city || '—' }}</span>
          <span class="school__dim" v-if="s.level">{{ s.level }}</span>
          <span class="school__dim" v-if="s.nature">{{ s.nature }}</span>
          <span class="school__dim" v-if="s.type">{{ s.type }}</span>
        </div>
        <div class="school__code">代码 {{ s.code }}</div>
      </el-card>
    </div>

    <!-- 热门大学介绍 -->
    <section class="hot" v-if="categories.length">
      <div class="hot__head">
        <h2 class="hot__title">热门大学介绍</h2>
        <span class="hot__hint">按分类浏览「每日一校」卡片，点击查看完整信息</span>
      </div>

      <div class="hot__tabs">
        <button
          v-for="c in categories"
          :key="c.category"
          class="hot__tab"
          :class="{ 'hot__tab--active': activeCat === c.category }"
          @click="loadHot(c.category)"
        >
          {{ c.category }} <span class="hot__count">{{ c.count }}</span>
        </button>
      </div>

      <div v-loading="hotLoading" class="hot__grid">
        <el-card
          v-for="s in hotSchools"
          :key="s.name"
          class="hot__card"
          shadow="hover"
          @click="openHot(s)"
        >
          <div class="hot__card-name">{{ s.name }}</div>
          <div class="hot__card-tags">
            <el-tag
              v-for="cat in s.categories"
              :key="cat"
              size="small"
              effect="plain"
              class="hot__cat"
            >{{ cat }}</el-tag>
          </div>
          <div class="hot__card-meta">
            <span v-if="s.established" class="hot__dim">建校 {{ s.established }}</span>
            <span v-if="s.location" class="hot__dim">{{ s.location }}</span>
            <span v-if="s.nature" class="hot__dim">{{ s.nature }}</span>
            <span v-if="s.school_type" class="hot__dim">{{ s.school_type }}</span>
          </div>
        </el-card>
      </div>
    </section>

    <!-- 详情弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="current?.name"
      width="720px"
      top="5vh"
      class="hot-dialog"
    >
      <div v-if="current" class="hot-detail">
        <div class="hot-detail__cats">
          <el-tag
            v-for="cat in current.categories"
            :key="cat"
            size="small"
            effect="plain"
          >{{ cat }}</el-tag>
        </div>

        <el-image
          v-if="current.has_image"
          :src="api.hotSchoolImageUrl(current.name)"
          fit="contain"
          class="hot-detail__img"
          :preview-src-list="[api.hotSchoolImageUrl(current.name)]"
        />

        <div class="kv">
          <div class="kv__item" v-if="current.established"><span class="kv__k">建校年</span><span class="kv__v tnum">{{ current.established }}</span></div>
          <div class="kv__item" v-if="current.location"><span class="kv__k">所在地</span><span class="kv__v">{{ current.location }}</span></div>
          <div class="kv__item" v-if="current.nature"><span class="kv__k">办学性质</span><span class="kv__v">{{ current.nature }}</span></div>
          <div class="kv__item" v-if="current.school_type"><span class="kv__k">院校类型</span><span class="kv__v">{{ current.school_type }}</span></div>
          <div class="kv__item" v-if="current.upgrade_rate"><span class="kv__k">升学率</span><span class="kv__v">{{ current.upgrade_rate }}</span></div>
          <div class="kv__item" v-if="current.grad_recommend_rate"><span class="kv__k">保研率</span><span class="kv__v">{{ current.grad_recommend_rate }}</span></div>
          <div class="kv__item" v-if="current.master_points != null"><span class="kv__k">硕士点</span><span class="kv__v tnum">{{ current.master_points }}</span></div>
          <div class="kv__item" v-if="current.doctor_points != null"><span class="kv__k">博士点</span><span class="kv__v tnum">{{ current.doctor_points }}</span></div>
          <div class="kv__item kv__item--full" v-if="current.ranking"><span class="kv__k">学校排名</span><span class="kv__v">{{ current.ranking }}</span></div>
        </div>

        <div class="hot-block" v-if="current.intro">
          <div class="hot-block__title">院校简介</div>
          <p class="hot-block__text">{{ current.intro }}</p>
        </div>
        <div class="hot-block" v-if="current.discipline_eval">
          <div class="hot-block__title">学科评估 / 建设</div>
          <p class="hot-block__text">{{ current.discipline_eval }}</p>
        </div>
        <div class="hot-block" v-if="current.features">
          <div class="hot-block__title">特色专业 / 王牌专业</div>
          <p class="hot-block__text">{{ current.features }}</p>
        </div>
        <div class="hot-block" v-if="current.honors">
          <div class="hot-block__title">所获荣誉</div>
          <p class="hot-block__text">{{ current.honors }}</p>
        </div>
        <div class="hot-block" v-if="current.faculty">
          <div class="hot-block__title">师资配备</div>
          <p class="hot-block__text">{{ current.faculty }}</p>
        </div>

        <el-button
          v-if="current.code"
          type="primary"
          plain
          class="hot-detail__link"
          @click="goSchool(current.code)"
        >查看完整招生数据 →</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.lib-eyebrow { display: inline-flex; align-items: center; gap: var(--space-2); font-size: var(--text-xs); color: var(--color-text-muted); text-transform: none; letter-spacing: 0.02em; margin-bottom: var(--space-2); }
.lib-eyebrow__dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-text-muted); }
.page__title { font-size: var(--text-2xl); }
.page__sub { color: var(--color-text-secondary); margin: var(--space-2) 0 var(--space-4); }
.search { max-width: 560px; margin-bottom: var(--space-4); }
.card { margin-bottom: var(--space-4); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
.empty { padding: var(--space-8); text-align: center; color: var(--color-text-muted); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: var(--space-4); }
.school { cursor: pointer; border-radius: var(--radius-lg); transition: transform 0.12s; }
.school:hover { transform: translateY(-2px); }
.school__name { font-weight: 600; font-size: var(--text-base); margin-bottom: var(--space-2); }
.school__meta { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); }
.school__dim { color: var(--color-text-muted); font-size: var(--text-xs); }
.school__code { margin-top: var(--space-2); color: var(--color-text-muted); font-size: var(--text-xs); }

/* 热门大学 */
.hot { margin-top: var(--space-8); border-top: 1px solid var(--color-border, #eee); padding-top: var(--space-6); }
.hot__head { display: flex; align-items: baseline; gap: var(--space-3); flex-wrap: wrap; margin-bottom: var(--space-4); }
.hot__title { font-size: var(--text-xl); margin: 0; }
.hot__hint { color: var(--color-text-muted); font-size: var(--text-xs); }
.hot__tabs { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-4); }
.hot__tab {
  border: 1px solid var(--color-border, #e3e8ef);
  background: var(--color-bg, #fff);
  color: var(--color-text-secondary);
  border-radius: 999px;
  padding: 6px 14px;
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all 0.12s;
}
.hot__tab:hover { border-color: var(--color-primary, #3370ff); color: var(--color-primary, #3370ff); }
.hot__tab--active { background: var(--color-primary, #3370ff); border-color: var(--color-primary, #3370ff); color: #fff; }
.hot__count { font-size: var(--text-xs); opacity: 0.7; margin-left: 4px; }
.hot__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--space-4); min-height: 120px; }
.hot__card { cursor: pointer; border-radius: var(--radius-lg); transition: transform 0.12s; }
.hot__card:hover { transform: translateY(-2px); }
.hot__card-name { font-weight: 600; font-size: var(--text-base); margin-bottom: var(--space-2); }
.hot__card-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: var(--space-2); }
.hot__card-meta { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.hot__dim { color: var(--color-text-muted); font-size: var(--text-xs); }

/* 详情弹窗 */
.hot-detail__cats { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: var(--space-3); }
.hot-detail__img { width: 100%; height: auto; border-radius: var(--radius-md); margin-bottom: var(--space-4); background: #f5f7fa; }
.kv { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-3) var(--space-5); margin-bottom: var(--space-4); }
.kv__item { display: flex; flex-direction: column; gap: 2px; }
.kv__item--full { grid-column: 1 / -1; }
.kv__k { font-size: var(--text-xs); color: var(--color-text-muted); }
.kv__v { font-size: var(--text-base); }
.hot-block { margin-bottom: var(--space-4); }
.hot-block__title { font-weight: 600; font-size: var(--text-sm); margin-bottom: var(--space-2); color: var(--color-text-secondary); }
.hot-block__text { margin: 0; font-size: var(--text-sm); line-height: 1.9; color: var(--color-text-secondary); white-space: pre-wrap; }
.hot-detail__link { margin-top: var(--space-2); }
</style>
