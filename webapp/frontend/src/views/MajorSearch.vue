<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import MajorDrawer from '@/components/MajorDrawer.vue'
import type {
  CatalogDiscipline,
  CatalogCategory,
  MajorCatalogItem,
  MajorSearchItem,
} from '@/types'

const router = useRouter()

// ---------- Tab 状态 ----------
const activeTab = ref<'catalog' | 'score'>('catalog')

// ---------- Tab1：专业字典 ----------
const disciplines = ref<CatalogDiscipline[]>([])
const activeDiscipline = ref<string | null>(null)
const categories = ref<CatalogCategory[]>([])
const activeCategory = ref<string | null>(null)
const catalogQ = ref('')
const catalogResults = ref<MajorCatalogItem[]>([])
const catalogLoading = ref(false)
const catalogSearched = ref(false)

// 热门专业快捷入口（资料盘点里有的 78 个）
const hotMajors = ref<string[]>([])

// ---------- 专业详情抽屉（复用 MajorDrawer 组件）----------
const detailName = ref<string | null>(null)

// ---------- Tab2：分数查询（原功能） ----------
const meta = ref<any>(null)
const scoreQ = ref('')
const scoreYear = ref<number | null>(null)
const scoreCategory = ref<string>('')
const scoreResults = ref<MajorSearchItem[]>([])
const scoreLoading = ref(false)
const scoreError = ref<string | null>(null)
const scoreSearched = ref(false)

onMounted(async () => {
  // 三个初始请求并行发出（互不依赖），避免串行等待
  const [metaRes, discRes, hotRows] = await Promise.all([
    api.meta().catch(() => null),
    api.catalogDisciplines().catch(() => []),
    api.catalogSearch({ limit: 500 }).catch(() => [] as MajorCatalogItem[]),
  ])
  meta.value = metaRes
  disciplines.value = discRes
  // 热门专业名称列表（用于快捷入口卡片）
  hotMajors.value = hotRows
    .filter((r) => r.has_admission)
    .sort((a, b) => b.school_count - a.school_count)
    .map((r) => r.name)
    .slice(0, 24)
})

// 当前门类下的专业类（用于筛选下拉）
const filteredCategories = computed(() =>
  activeDiscipline.value
    ? categories.value.filter((c) => c.discipline === activeDiscipline.value)
    : categories.value,
)

async function selectDiscipline(d: string | null) {
  activeDiscipline.value = d
  activeCategory.value = null
  if (d) {
    categories.value = await api.catalogCategories(d).catch(() => [])
  } else {
    categories.value = []
  }
  await runCatalogSearch()
}

async function runCatalogSearch() {
  catalogLoading.value = true
  catalogSearched.value = true
  try {
    catalogResults.value = await api.catalogSearch({
      q: catalogQ.value.trim() || undefined,
      discipline: activeDiscipline.value || undefined,
      category: activeCategory.value || undefined,
      limit: 200,
    })
  } catch (e) {
    catalogResults.value = []
  } finally {
    catalogLoading.value = false
  }
}

function viewAdmission(major: string) {
  router.push({ path: '/datacenter', query: { major } })
}

// 打开专业详情抽屉（图文卡片）
function openDetail(name: string) {
  detailName.value = name
}

// ---------- Tab2 逻辑（保留原功能） ----------
async function onScoreSearch() {
  if (!scoreQ.value.trim()) return
  scoreLoading.value = true
  scoreError.value = null
  scoreSearched.value = true
  try {
    scoreResults.value = await api.searchMajors({
      q: scoreQ.value.trim(),
      year: scoreYear.value ?? undefined,
      category: scoreCategory.value || undefined,
    })
  } catch (e) {
    scoreError.value = (e as Error).message
  } finally {
    scoreLoading.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="lib-eyebrow"><span class="lib-eyebrow__dot"></span>资料库 · 查询工具</div>
    <h1 class="page__title">专业查询</h1>
    <p class="page__sub">
      两种方式帮你了解专业：<b>专业字典</b>按教育部标准专业浏览，并关联在辽招生院校与分数；
      <b>分数查询</b>直接按招生专业名查历年录取分。
    </p>

    <!-- 热门专业快捷入口（点击直接看图文详情） -->
    <div v-if="hotMajors.length" class="hot-entry">
      <div class="hot-entry__title">热门专业 · 点击看详情</div>
      <div class="hot-entry__chips">
        <button
          v-for="m in hotMajors"
          :key="m"
          class="chip"
          @click="openDetail(m)"
        >{{ m }}</button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="tabs">
      <!-- ============ Tab1: 专业字典 ============ -->
      <el-tab-pane label="专业字典" name="catalog">
        <div class="catalog">
          <!-- 左侧门类导航 -->
          <aside class="disc-nav">
            <div
              class="disc-nav__item"
              :class="{ 'is-active': activeDiscipline === null }"
              @click="selectDiscipline(null)"
            >
              全部专业 <span class="disc-nav__cnt">{{ disciplines.reduce((a, b) => a + b.count, 0) }}</span>
            </div>
            <div
              v-for="d in disciplines"
              :key="d.discipline"
              class="disc-nav__item"
              :class="{ 'is-active': activeDiscipline === d.discipline }"
              @click="selectDiscipline(d.discipline)"
            >
              {{ d.discipline }} <span class="disc-nav__cnt">{{ d.count }}</span>
            </div>
          </aside>

          <!-- 右侧内容 -->
          <section class="catalog__main">
            <div class="filters">
              <el-input
                v-model="catalogQ"
                placeholder="搜专业名称，如：计算机 / 临床"
                clearable
                class="f-q"
                @keyup.enter="runCatalogSearch"
              />
              <el-select v-model="activeCategory" placeholder="专业类" clearable class="f-sel" @change="runCatalogSearch">
                <el-option v-for="c in filteredCategories" :key="c.category" :label="c.category" :value="c.category" />
              </el-select>
              <el-button type="primary" :loading="catalogLoading" @click="runCatalogSearch">搜索</el-button>
            </div>

            <div v-if="catalogSearched && !catalogLoading && !catalogResults.length" class="empty">
              未找到匹配的专业，请尝试更短的关键词或切换门类。
            </div>

            <el-table v-if="catalogResults.length" :data="catalogResults" size="small" border class="card">
              <el-table-column prop="code" label="代码" width="100" />
              <el-table-column label="专业" min-width="200">
                <template #default="{ row }">
                  <div class="major-cell">
                    <a class="major-cell__name link" @click="openDetail(row.name)">{{ row.name }}</a>
                    <span class="major-cell__cat">{{ row.category }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="在辽招生" width="120" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.has_admission" type="success" size="small">{{ row.school_count }} 所</el-tag>
                  <el-tag v-else type="info" size="small">暂无</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="最低分区间" width="150" align="right">
                <template #default="{ row }">
                  <span class="tnum" v-if="row.lowest_score_range[0] != null">{{ row.lowest_score_range[0] }} ~ {{ row.lowest_score_range[1] }}</span>
                  <span v-else class="muted">—</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120" align="center">
                <template #default="{ row }">
                  <el-button v-if="row.has_admission" link type="primary" @click="viewAdmission(row.name)">录取记录</el-button>
                  <span v-else class="muted">—</span>
                </template>
              </el-table-column>
            </el-table>
          </section>
        </div>
      </el-tab-pane>

      <!-- ============ Tab2: 分数查询 ============ -->
      <el-tab-pane label="分数查询" name="score">
        <div class="filters">
          <el-input v-model="scoreQ" placeholder="输入招生专业名，如：计算机" clearable class="f-q" @keyup.enter="onScoreSearch" />
          <el-select v-model="scoreYear" placeholder="年份" clearable class="f-sel">
            <el-option v-for="y in (meta?.years || [])" :key="y" :label="y" :value="y" />
          </el-select>
          <el-select v-model="scoreCategory" placeholder="类别" clearable class="f-sel">
            <el-option v-for="c in (meta?.categories || [])" :key="c" :label="c" :value="c" />
          </el-select>
          <el-button type="primary" :loading="scoreLoading" @click="onScoreSearch">搜索</el-button>
        </div>

        <el-alert v-if="scoreError" type="error" :title="scoreError" show-icon :closable="false" class="card" />

        <div v-if="scoreSearched && !scoreLoading && !scoreResults.length" class="empty">
          未找到匹配的招生专业，请尝试更短的关键词。
        </div>

        <el-table v-if="scoreResults.length" :data="scoreResults" size="small" border class="card">
          <el-table-column prop="major_name" label="招生专业名" min-width="220" />
          <el-table-column prop="school_count" label="招生院校数" width="120" align="right">
            <template #default="{ row }"><span class="tnum">{{ row.school_count }}</span></template>
          </el-table-column>
          <el-table-column label="最低分区间" width="150" align="right">
            <template #default="{ row }">
              <span class="tnum" v-if="row.lowest_score_range[0] != null">{{ row.lowest_score_range[0] }} ~ {{ row.lowest_score_range[1] }}</span>
            </template>
          </el-table-column>
          <el-table-column label="最低位次区间" width="170" align="right">
            <template #default="{ row }">
              <span class="tnum" v-if="row.lowest_rank_range[0] != null">{{ row.lowest_rank_range[0] }} ~ {{ row.lowest_rank_range[1] }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button link type="primary" @click="viewAdmission(row.major_name)">录取记录</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- ============ 专业详情抽屉（图文卡片，复用组件） ============ -->
    <MajorDrawer v-model:name="detailName" />
  </div>
</template>

<style scoped>
.lib-eyebrow { display: inline-flex; align-items: center; gap: var(--space-2); font-size: var(--text-xs); color: var(--color-text-muted); margin-bottom: var(--space-2); }
.lib-eyebrow__dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-text-muted); }
.page__title { font-size: var(--text-2xl); }
.page__sub { color: var(--color-text-secondary); margin: var(--space-2) 0 var(--space-4); }
.tabs { margin-top: var(--space-2); }
.filters { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-4); }
.f-q { width: 240px; }
.f-sel { width: 140px; }
.card { margin-bottom: var(--space-4); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
.empty { padding: var(--space-8); text-align: center; color: var(--color-text-muted); }
.tnum { font-variant-numeric: tabular-nums; }
.muted { color: var(--color-text-muted); }

/* 专业字典布局 */
.catalog { display: flex; gap: var(--space-4); align-items: flex-start; }
.disc-nav {
  flex: 0 0 160px;
  max-height: 70vh;
  overflow-y: auto;
  border: 1px solid var(--color-border, #eee);
  border-radius: var(--radius-lg);
  padding: var(--space-2);
  position: sticky;
  top: var(--space-4);
}
.disc-nav__item {
  display: flex; justify-content: space-between; align-items: center;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.disc-nav__item:hover { background: var(--color-bg-hover, #f5f5f5); }
.disc-nav__item.is-active { background: var(--color-primary-soft, #e8f0fe); color: var(--color-primary, #1a73e8); font-weight: 600; }
.disc-nav__cnt { font-size: var(--text-xs); color: var(--color-text-muted); font-variant-numeric: tabular-nums; }
.catalog__main { flex: 1 1 auto; min-width: 0; }

.major-cell { display: flex; flex-direction: column; gap: 2px; }
.major-cell__name { font-weight: 500; }
.major-cell__cat { font-size: var(--text-xs); color: var(--color-text-muted); }

/* 热门专业快捷入口 */
.hot-entry { margin-bottom: var(--space-4); }
.hot-entry__title { font-size: var(--text-sm); color: var(--color-text-secondary); margin-bottom: var(--space-2); }
.hot-entry__chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.chip {
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 999px;
  background: #fff;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all .15s;
}
.chip:hover { border-color: var(--color-primary, #1a73e8); color: var(--color-primary, #1a73e8); background: var(--color-primary-soft, #e8f0fe); }

/* 专业名链接 */
.link { color: var(--color-primary, #1a73e8); cursor: pointer; }
.link:hover { text-decoration: underline; }

/* 详情抽屉 */
.detail-loading { text-align: center; padding: var(--space-8); color: var(--color-text-muted); }
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
