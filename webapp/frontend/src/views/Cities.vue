<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import SchoolDrawer from '@/components/SchoolDrawer.vue'
import type { CityListItem, CityDetail } from '@/types'

const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
const route = useRoute()
const router = useRouter()
const provinces = ref<string[]>([])
const cities = ref<CityListItem[]>([])
const loadingCities = ref(false)
const loadingDetail = ref(false)
const error = ref<string | null>(null)
const province = ref('')
const query = ref('')
const activeCity = ref<string | null>(null)
const detail = ref<CityDetail | null>(null)
const mapOpen = ref(false)
const mapError = ref(false)
const detailCode = ref<string | null>(null)

const provinceSummary = computed(() => {
  const schoolCount = cities.value.reduce((sum, item) => sum + item.school_count, 0)
  return { cities: cities.value.length, schools: schoolCount }
})

const visibleCities = computed(() => {
  const text = query.value.trim().toLowerCase()
  if (!text) return cities.value
  return cities.value.filter((item) =>
    [item.city, item.tier, item.cluster].some((value) => value?.toLowerCase().includes(text)),
  )
})

async function loadProvinces() {
  provinces.value = await api.cityProvinces().catch(() => [])
}

async function chooseProvince(value: string) {
  province.value = value
  query.value = ''
  mapOpen.value = false
  mapError.value = false
  activeCity.value = null
  detail.value = null
  if (!value) {
    cities.value = []
    if (!props.embedded && route.query.province) router.replace({ query: {} })
    return
  }
  loadingCities.value = true
  error.value = null
  try {
    cities.value = await api.cities({ province: value })
    if (!props.embedded) router.replace({ query: { province: value } })
    if (cities.value.length) await selectCity(cities.value[0].city)
  } catch (e: any) {
    error.value = e?.message || '加载失败'
  } finally {
    loadingCities.value = false
  }
}

async function selectCity(city: string) {
  activeCity.value = city
  detail.value = null
  loadingDetail.value = true
  error.value = null
  try {
    detail.value = await api.cityDetail(city)
  } catch (e: any) {
    error.value = e?.message || '加载失败'
  } finally {
    loadingDetail.value = false
  }
}

function openProvinceMap() {
  mapError.value = false
  mapOpen.value = true
}

onMounted(async () => {
  await loadProvinces()
  const initial = typeof route.query.province === 'string' ? route.query.province : ''
  if (initial) await chooseProvince(initial)
})

watch(visibleCities, (items) => {
  if (activeCity.value && !items.some((item) => item.city === activeCity.value) && items.length) {
    selectCity(items[0].city)
  }
})
</script>

<template>
  <div :class="['city-browser', { 'city-browser--standalone': !props.embedded }]">
    <template v-if="!props.embedded">
      <el-button text class="back" @click="router.push('/search/school')">← 返回院校查询</el-button>
      <h1 class="page__title">按地域浏览院校</h1>
      <p class="page__sub">从省份进入城市，再查看当地院校；适合尚未确定目标学校、优先考虑地域的考生。</p>
    </template>

    <section class="province-step" aria-labelledby="province-step-title">
      <div class="step-label"><span>1</span><strong id="province-step-title">先选择省份</strong></div>
      <el-select
        :model-value="province"
        placeholder="选择省份或自治区"
        filterable
        clearable
        class="province-select"
        aria-label="选择省份"
        @change="chooseProvince"
      >
        <el-option v-for="item in provinces" :key="item" :label="item" :value="item" />
      </el-select>
      <p class="helper">选择后会列出该省城市和本站收录院校，并可查看本科高校分布图。</p>
    </section>

    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" class="message" />

    <div v-if="!province" class="province-placeholder">
      <span class="province-placeholder__icon" aria-hidden="true">⌖</span>
      <strong>从省份开始探索</strong>
      <p>例如选择“辽宁”，再比较沈阳、大连等城市及当地院校。</p>
    </div>

    <template v-else>
      <section class="province-overview">
        <div>
          <div class="step-label"><span>2</span><strong>{{ province }}地域概览</strong></div>
          <p class="province-overview__meta">
            本站收录 <b class="tnum">{{ provinceSummary.cities }}</b> 个城市，关联
            <b class="tnum">{{ provinceSummary.schools }}</b> 所院校
          </p>
        </div>
        <el-button plain @click="openProvinceMap">查看全省本科高校分布图</el-button>
      </section>

      <section class="explore-layout">
        <div class="city-panel" v-loading="loadingCities">
          <div class="panel-head">
            <div class="step-label"><span>3</span><strong>选择城市</strong></div>
            <el-input v-model="query" placeholder="筛选城市" clearable aria-label="筛选城市" class="city-search" />
          </div>
          <div v-if="visibleCities.length" class="city-list">
            <button
              v-for="item in visibleCities"
              :key="item.city"
              type="button"
              :class="['city-item', { 'city-item--active': item.city === activeCity }]"
              @click="selectCity(item.city)"
            >
              <span class="city-item__main">
                <strong>{{ item.city }}</strong>
                <small>{{ [item.tier, item.cluster].filter(Boolean).join(' · ') || '城市资料待补充' }}</small>
              </span>
              <span class="city-item__count tnum">{{ item.school_count }} 所</span>
            </button>
          </div>
          <div v-else class="empty">没有符合条件的城市</div>
        </div>

        <div class="school-panel" v-loading="loadingDetail">
          <div v-if="!detail" class="empty">选择城市后查看院校</div>
          <template v-else>
            <div class="city-summary">
              <div>
                <div class="step-label"><span>4</span><strong>{{ detail.profile.city }}院校</strong></div>
                <p>{{ [detail.profile.region, detail.profile.tier, detail.profile.cluster].filter(Boolean).join(' · ') }}</p>
              </div>
              <div class="city-facts">
                <span v-if="detail.profile.coastal">沿海城市</span>
                <span v-if="detail.profile.gdp" class="tnum">GDP {{ detail.profile.gdp }} 亿元</span>
              </div>
            </div>

            <div v-if="detail.schools.length" class="school-list">
              <button
                v-for="school in detail.schools"
                :key="school.code"
                type="button"
                class="school-row"
                @click="detailCode = school.code"
              >
                <span class="school-row__main">
                  <strong>{{ school.name }}</strong>
                  <small>{{ [school.level, school.nature, school.type].filter(Boolean).join(' · ') || '院校资料待补充' }}</small>
                </span>
                <span class="school-row__tags">
                  <el-tag v-if="school.is_985" size="small" type="danger" effect="plain">985</el-tag>
                  <el-tag v-if="school.is_211" size="small" type="warning" effect="plain">211</el-tag>
                  <el-tag v-if="school.is_dfc" size="small" type="success" effect="plain">双一流</el-tag>
                  <span aria-hidden="true">›</span>
                </span>
              </button>
            </div>
            <div v-else class="empty">本站暂未关联该城市院校</div>
          </template>
        </div>
      </section>
    </template>

    <el-dialog v-model="mapOpen" :title="`${province}本科高校分布图`" width="min(94vw, 1100px)" destroy-on-close>
      <el-alert v-if="mapError" type="warning" title="图片加载失败，请稍后重试" show-icon :closable="false" />
      <img
        v-else
        class="province-map"
        :src="api.provinceMapImageUrl(province)"
        :alt="`${province}本科高校分布图`"
        @error="mapError = true"
      />
      <p class="source-note">资料来源：全国31省市本科高校分布图。图片仅作地域浏览参考，院校信息以下方本站数据为准。</p>
    </el-dialog>

    <SchoolDrawer v-model:code="detailCode" />
  </div>
</template>

<style scoped>
.city-browser--standalone { max-width: 1080px; margin: 0 auto; }
.back { margin-bottom: var(--space-3); }
.page__title { font-size: var(--text-2xl); }
.page__sub { color: var(--color-text-secondary); margin: var(--space-2) 0 var(--space-5); }
.province-step { padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-surface); }
.step-label { display: flex; align-items: center; gap: var(--space-2); }
.step-label > span { width: 24px; height: 24px; flex: 0 0 24px; display: grid; place-items: center; border-radius: 50%; background: var(--color-primary-soft); color: var(--color-primary); font-size: var(--text-xs); font-weight: 700; }
.step-label strong { font-size: var(--text-base); }
.province-select { width: min(100%, 360px); margin-top: var(--space-3); }
.helper { color: var(--color-text-muted); font-size: var(--text-xs); margin: var(--space-2) 0 0; }
.message { margin-top: var(--space-3); }
.province-placeholder { margin-top: var(--space-4); min-height: 240px; display: grid; place-items: center; align-content: center; gap: var(--space-2); border: 1px dashed var(--color-border); border-radius: var(--radius-lg); color: var(--color-text-muted); text-align: center; }
.province-placeholder__icon { font-size: 34px; color: var(--color-primary); }
.province-placeholder p { margin: 0; font-size: var(--text-sm); }
.province-overview { margin-top: var(--space-4); display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-surface); }
.province-overview__meta { margin: var(--space-2) 0 0 32px; color: var(--color-text-muted); font-size: var(--text-sm); }
.explore-layout { display: grid; grid-template-columns: minmax(260px, 0.85fr) minmax(420px, 1.6fr); gap: var(--space-4); margin-top: var(--space-4); align-items: start; }
.city-panel, .school-panel { min-height: 360px; border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-surface); overflow: hidden; }
.panel-head { padding: var(--space-4); border-bottom: 1px solid var(--color-border); }
.city-search { margin-top: var(--space-3); }
.city-list, .school-list { max-height: 590px; overflow-y: auto; }
.city-item, .school-row { width: 100%; border: 0; border-bottom: 1px solid var(--color-border); background: transparent; color: var(--color-text); cursor: pointer; text-align: left; }
.city-item { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) var(--space-4); }
.city-item:hover, .city-item--active { background: var(--color-primary-soft); }
.city-item--active { box-shadow: inset 3px 0 0 var(--color-primary); }
.city-item:focus-visible, .school-row:focus-visible { outline: 2px solid var(--color-primary); outline-offset: -2px; }
.city-item__main, .school-row__main { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.city-item__main small, .school-row__main small { color: var(--color-text-muted); }
.city-item__count { color: var(--color-text-muted); font-size: var(--text-xs); white-space: nowrap; }
.city-summary { padding: var(--space-4); border-bottom: 1px solid var(--color-border); display: flex; justify-content: space-between; gap: var(--space-3); }
.city-summary p { margin: var(--space-2) 0 0 32px; color: var(--color-text-muted); font-size: var(--text-sm); }
.city-facts { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--space-2); color: var(--color-text-muted); font-size: var(--text-xs); }
.city-facts span { padding: 4px 8px; border-radius: 999px; background: var(--color-primary-soft); }
.school-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) var(--space-4); }
.school-row:hover { background: var(--color-primary-soft); }
.school-row__tags { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 4px; }
.empty { min-height: 220px; display: grid; place-items: center; color: var(--color-text-muted); font-size: var(--text-sm); }
.province-map { display: block; width: 100%; height: auto; max-height: 72vh; object-fit: contain; }
.source-note { margin: var(--space-2) 0 0; color: var(--color-text-muted); font-size: var(--text-xs); text-align: center; }
@media (max-width: 760px) {
  .province-overview, .city-summary { align-items: flex-start; flex-direction: column; }
  .province-overview__meta, .city-summary p { margin-left: 0; }
  .explore-layout { grid-template-columns: 1fr; }
  .city-list { max-height: 320px; }
  .city-facts { justify-content: flex-start; }
}
</style>
