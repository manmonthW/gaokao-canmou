<script setup lang="ts">
import { ref, computed, watch } from 'vue'
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

import TrendBadge from '@/components/TrendBadge.vue'
import TrendDetail from '@/components/TrendDetail.vue'

// 冷热趋势：本科批在前（主战场），「样本不足」不渲染（数据为空不占位）
const trendGroups = computed(() =>
  (data.value?.trend || []).filter((t) => t.label !== '样本不足'),
)

// 第五轮学科评估：按 A+ → A → A- 顺序展示
const EVAL5_ORDER = ['A+', 'A', 'A-']
const eval5Grades = computed(() => {
  if (!data.value?.eval5?.grades) return []
  return EVAL5_ORDER.filter((g) => (data.value!.eval5.grades[g]?.length ?? 0) > 0)
})

// 评级等级 → 样式 tier（与 StrengthBadges 一致：A+ 金 / A 橙 / A- 琥珀）
function gradeTier(label: string): string {
  if (label === 'A+') return 'top'
  if (label === 'A') return 'high'
  return 'mid'
}

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

    <div v-if="loading" class="loading">加载中…</div>

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

        <div class="d-section" v-if="data.hot_profile.degree || data.hot_profile.length || data.hot_profile.arts_science_ratio || data.hot_profile.gender_ratio">
          <div class="d-grid">
            <div v-if="data.hot_profile.degree"><span class="d-k">授予学位</span><span class="d-v">{{ data.hot_profile.degree }}</span></div>
            <div v-if="data.hot_profile.length"><span class="d-k">学制</span><span class="d-v">{{ data.hot_profile.length }} 年</span></div>
            <div v-if="data.hot_profile.arts_science_ratio"><span class="d-k">文理比例</span><span class="d-v">{{ data.hot_profile.arts_science_ratio }}</span></div>
            <div v-if="data.hot_profile.gender_ratio"><span class="d-k">男女比例</span><span class="d-v">{{ data.hot_profile.gender_ratio }}</span></div>
          </div>
        </div>

        <!-- 近三年冷热趋势（migration 0017）。按学科类×批次分组展示，
             不跨学科类合并——同一专业在物理/历史类可能结论相反。 -->
        <div class="d-section" v-if="trendGroups.length">
          <h4 class="d-h">
            近三年录取门槛走势
            <el-tooltip placement="top" effect="dark"
              content="以在辽招生的同「院校+专业」逐年对照，扣除全省整体漂移后得出；三年仅两个年段，趋势判断置信度有限，不用于预测明年门槛。不覆盖艺术类、体育类与提前批。"
            >
              <i class="d-help" tabindex="0">ⓘ</i>
            </el-tooltip>
          </h4>
          <div v-for="g in trendGroups" :key="g.subject + g.batch" class="trend-grp">
            <div class="trend-grp__head">
              <span class="trend-grp__scope">{{ g.subject }} · {{ g.batch }}</span>
              <TrendBadge :trend="g" :badge-only="false" />
            </div>
            <TrendDetail :trend="g" />
          </div>
        </div>

        <div class="d-section" v-if="data.hot_profile.introduction">
          <h4 class="d-h">专业介绍</h4>
          <p class="d-p">{{ data.hot_profile.introduction }}</p>
        </div>

        <!-- 第五轮学科评估 -->
        <div class="d-section" v-if="data.eval5 && data.eval5.discipline">
          <h4 class="d-h">
            第五轮学科评估
            <el-tooltip :content="`对应学科：${data.eval5.discipline}。教育部第五轮学科评估结果（A+/A/A-），来自各校公开发布汇总，官方未集中公布完整名单，仅供参考。`" placement="top" effect="dark">
              <i class="d-help" tabindex="0">ⓘ</i>
            </el-tooltip>
          </h4>
          <div class="eval5-block">
            <div
              v-for="g in eval5Grades"
              :key="g"
              class="eval5-row"
            >
              <span class="eval5-grade" :class="'eval5-grade--' + gradeTier(g)">{{ g }}</span>
              <div class="eval5-schools">
                <span v-for="s in data.eval5.grades[g]" :key="s" class="eval5-school">{{ s }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="d-section" v-if="data.hot_profile.subject_req">
          <h4 class="d-h">选科要求</h4>
          <p class="d-p">{{ data.hot_profile.subject_req }}</p>
        </div>

        <!-- 就业前景（career，PNG OCR）与就业方向语义重复，且 31 行均有
             employment_dir 覆盖，页面不再单列，避免重复区块 -->
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

        <div class="d-section" v-if="data.hot_profile.training_req">
          <h4 class="d-h">培养要求</h4>
          <p class="d-p">{{ data.hot_profile.training_req }}</p>
        </div>

        <div class="d-section" v-if="data.hot_profile.knowledge_ability">
          <h4 class="d-h">知识能力</h4>
          <p class="d-p">{{ data.hot_profile.knowledge_ability }}</p>
        </div>

        <div class="d-section" v-if="data.hot_profile.social_celebrities">
          <h4 class="d-h">社会名人</h4>
          <p class="d-p">{{ data.hot_profile.social_celebrities }}</p>
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
.trend-grp { margin-bottom: var(--space-4); }
.trend-grp:last-child { margin-bottom: 0; }
.trend-grp__head { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1); flex-wrap: wrap; }
.trend-grp__scope { font-size: var(--text-xs); color: var(--color-text-muted); }
.d-h { font-size: var(--text-sm); font-weight: 600; margin: 0 0 var(--space-2); color: var(--color-text, #333); }
.d-p { font-size: var(--text-sm); line-height: 1.7; color: var(--color-text-secondary); margin: 0; }
.d-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-2); }
.d-grid > div { display: flex; flex-direction: column; gap: 2px; }
.d-k { font-size: var(--text-xs); color: var(--color-text-muted); }
.d-v { font-size: var(--text-sm); font-weight: 500; }
.d-schools { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.d-school { margin: 0; }
.d-adm-btn { width: 100%; }

/* 第五轮学科评估区块 */
.d-help {
  font-style: normal;
  font-size: 12px;
  color: var(--el-color-info);
  cursor: help;
  margin-left: 4px;
  vertical-align: middle;
}
.d-help:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.eval5-block { display: flex; flex-direction: column; gap: 6px; }
.eval5-row { display: flex; align-items: flex-start; gap: 8px; }
.eval5-grade {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  font-size: 10px;
  font-weight: 600;
  line-height: 1.35;
  padding: 0 6px;
  border-radius: 2px;
  white-space: nowrap;
  margin-top: 1px;
}
.eval5-grade--top {
  color: #92400e;
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  border: 1px solid #f59e0b;
}
.eval5-grade--high {
  color: #7c2d12;
  background: linear-gradient(135deg, #ffedd5, #fed7aa);
  border: 1px solid #f97316;
}
.eval5-grade--mid {
  color: #78350f;
  background: linear-gradient(135deg, #fef9c3, #fef08a);
  border: 1px solid #eab308;
}
.eval5-schools {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: var(--text-sm);
  line-height: 1.5;
}
.eval5-school { color: var(--color-text); }
</style>
