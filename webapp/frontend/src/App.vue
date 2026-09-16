<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'
import { RouterView, RouterLink, useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useJourney } from '@/composables/useJourney'
import { useAuth } from '@/composables/useAuth'
import ReleaseNotes from '@/components/ReleaseNotes.vue'
import UtilityMenu from '@/components/UtilityMenu.vue'
import { useIsMobile } from '@/composables/useBreakpoint'

const AdvisorDrawer = defineAsyncComponent(() => import('@/components/advisor/AdvisorDrawer.vue'))

const route = useRoute()
const router = useRouter()
const journey = useJourney()
const auth = useAuth()
const isMobile = useIsMobile()
const advisorOpen = ref(false)
const releaseNotes = ref<InstanceType<typeof ReleaseNotes> | null>(null)

function openAdvisor() {
  if (!auth.isLoggedIn.value) {
    goAuth()
    return
  }
  if (isMobile.value) router.push('/advisor')
  else advisorOpen.value = true
}

function goAuth() {
  router.push({ path: '/auth', query: { redirect: route.fullPath } })
}
function onLogout() {
  auth.logout()
  ElMessage.success('已退出登录，可继续匿名使用（本机数据已清空）')
  router.push('/')
}

function showReleaseNotes() {
  releaseNotes.value?.show()
}

// 决策主线三步（有序、带状态）
const steps = computed(() => [
  {
    key: 'locate',
    to: '/',
    index: 1,
    label: '我的定位',
    summary: journey.locateSummary.value,
    done: journey.locateDone.value,
    warn: false,
    active: route.name === 'locate',
  },
  {
    key: 'match',
    to: '/match',
    index: 2,
    label: '智能匹配',
    summary: journey.matchSummary.value,
    done: journey.matchStarted.value,
    warn: false,
    active: route.name === 'match',
  },
  {
    key: 'workbench',
    to: '/workbench',
    index: 3,
    label: '决策工作台',
    summary: journey.workbenchSummary.value,
    done: journey.planStats.value.entries > 0,
    warn: journey.workbenchWarn.value,
    active: route.name === 'workbench',
  },
])

// 资料库（工具，无序、随时查）：图标分段按钮，各入口独立配色便于区分
const library = [
  {
    to: '/guides',
    label: '报考说明',
    icon: 'guide',
    style: '--icon: var(--color-doc-accent); --icon-soft: var(--color-doc-accent-soft)',
  },
  {
    to: '/search/school',
    label: '院校查询',
    icon: 'school',
    style: '--icon: var(--color-primary); --icon-soft: var(--color-primary-soft)',
  },
  {
    to: '/search/major',
    label: '专业查询',
    icon: 'book',
    style: '--icon: var(--color-volatile); --icon-soft: var(--color-volatile-soft)',
  },
  {
    to: '/datacenter',
    label: '数据中心',
    icon: 'chart',
    style: '--icon: var(--color-match); --icon-soft: var(--color-match-soft)',
  },
  {
    to: '/eligibility',
    label: '资格自查',
    icon: 'check',
    style: '--icon: var(--el-color-warning); --icon-soft: var(--el-color-warning-light-8)',
  },
]
// 登录页等公开页不显示应用外壳（顶栏 + 步骤条）；匿名优先（P3）：匿名也显示外壳
const chromeless = computed(() => route.meta.public === true)
</script>

<template>
  <div class="app-shell">
    <header v-if="!chromeless" class="app-header">
      <div class="app-header__inner">
        <RouterLink to="/" class="brand">
          <span class="brand__mark">辽</span>
          <span class="brand__name">辽宁志愿参谋</span>
        </RouterLink>
        <span class="brand__tag">辽宁高考录取数据 · 志愿决策辅助</span>

        <!-- 资料库：工具入口，图标 + 文字分段按钮，置于右上 -->
        <nav class="lib-nav" aria-label="资料库">
          <RouterLink
            v-for="l in library"
            :key="l.to"
            :to="l.to"
            class="lib-btn"
            :style="l.style"
          >
            <span class="lib-btn__icon" aria-hidden="true">
              <!-- 报考说明：官方文件 -->
              <svg v-if="l.icon === 'guide'" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M9 13h6M9 17h6"/></svg>
              <!-- 院校：学位帽 -->
              <svg v-else-if="l.icon === 'school'" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10 12 5 2 10l10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
              <!-- 专业：翻开的书 -->
              <svg v-else-if="l.icon === 'book'" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z"/></svg>
              <!-- 数据：柱状图 -->
              <svg v-else-if="l.icon === 'chart'" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-3"/></svg>
              <!-- 资格：带勾清单 -->
              <svg v-else viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="m8 12 3 3 5-6"/></svg>
            </span>
            {{ l.label }}
          </RouterLink>
        </nav>

        <!-- 高频 AI 入口和统一工具设置 -->
        <el-button v-if="auth.isLoggedIn.value" class="advisor-entry" size="small" type="primary" @click="openAdvisor">问参谋</el-button>
        <UtilityMenu
          :logged-in="auth.isLoggedIn.value"
          :user="auth.user.value"
          @login="goAuth"
          @logout="onLogout"
          @releases="showReleaseNotes"
        />
      </div>

      <!-- 决策主线：步骤条，视觉主导，带序号 / 连接线 / 实时状态 -->
      <div class="stepper">
        <div class="stepper__inner">
          <template v-for="(s, i) in steps" :key="s.key">
            <RouterLink
              :to="s.to"
              class="step"
              :class="{ 'step--active': s.active, 'step--done': s.done, 'step--warn': s.warn }"
            >
              <span class="step__badge">
                <span v-if="s.done && !s.warn" class="step__check">✓</span>
                <span v-else-if="s.warn" class="step__check">!</span>
                <span v-else>{{ s.index }}</span>
              </span>
              <span class="step__text">
                <span class="step__label">{{ s.label }}</span>
                <span class="step__summary">{{ s.summary }}</span>
              </span>
            </RouterLink>
            <span v-if="i < steps.length - 1" class="step__arrow" aria-hidden="true">→</span>
          </template>
        </div>
      </div>
    </header>

    <main class="app-main">
      <RouterView />
    </main>
    <AdvisorDrawer v-if="advisorOpen" v-model="advisorOpen" />
    <ReleaseNotes ref="releaseNotes" class="release-notes-host" />
    <footer class="app-footer">
      <span>数据仅供参考，最终报考资格与录取规则以辽宁省招考部门及院校官方信息为准。</span>
      <span class="app-footer__sep" aria-hidden="true">·</span>
      <a href="mailto:14324569@qq.com?subject=辽宁志愿参谋内容反馈">内容反馈：14324569@qq.com</a>
    </footer>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.app-header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: color-mix(in srgb, var(--color-surface) 90%, transparent);
  backdrop-filter: saturate(180%) blur(8px);
  border-bottom: 1px solid var(--color-border);
}
.app-header__inner {
  max-width: 1080px;
  margin: 0 auto;
  padding: var(--space-3) var(--space-4);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text);
}
.brand__mark {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 700;
}
.brand__name {
  font-size: var(--text-lg);
  font-weight: 600;
}
.brand__tag {
  color: var(--color-text-muted);
  font-size: var(--text-sm);
}

/* ---- 资料库（图标分段按钮） ---- */
.lib-nav {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.lib-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 34px;
  padding: 4px 12px 4px 6px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  text-decoration: none;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s, box-shadow 0.15s, color 0.15s;
}
.lib-btn__icon {
  width: 24px;
  height: 24px;
  flex: 0 0 24px;
  border-radius: var(--radius-sm);
  display: grid;
  place-items: center;
  background: var(--icon-soft);
  color: var(--icon);
  transition: filter 0.15s;
}
.lib-btn:hover {
  background: var(--icon-soft);
  border-color: var(--icon);
  color: var(--color-text);
}
.lib-btn:focus-visible {
  outline: 2px solid var(--icon);
  outline-offset: 2px;
}
.lib-btn.router-link-active {
  background: var(--icon-soft);
  border-color: var(--icon);
  color: var(--icon);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

/* ---- 右上工具 ---- */
.advisor-entry { flex: 0 0 auto; }
.release-notes-host { display: none; }

/* ---- 决策主线步骤条 ---- */
.stepper {
  border-top: 1px solid var(--color-border);
  background: linear-gradient(180deg, color-mix(in srgb, var(--color-primary-soft) 50%, transparent), transparent);
}
.stepper__inner {
  max-width: 1080px;
  margin: 0 auto;
  padding: var(--space-3) var(--space-4);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  overflow-x: auto;
}
.step {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid transparent;
  text-decoration: none;
  color: var(--color-text-secondary);
  transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
  white-space: nowrap;
}
.step:hover {
  background: var(--color-surface);
  border-color: var(--color-border);
}
.step--active {
  background: var(--color-surface);
  border-color: var(--color-primary);
  box-shadow: var(--shadow-sm);
}
.step__badge {
  width: 26px;
  height: 26px;
  flex: 0 0 26px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: var(--text-sm);
  font-weight: 700;
  background: var(--color-border);
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}
.step--active .step__badge {
  background: var(--color-primary);
  color: #fff;
}
.step--done .step__badge {
  background: var(--color-match);
  color: #fff;
}
.step--warn .step__badge {
  background: var(--color-danger);
  color: #fff;
}
.step__check {
  font-size: var(--text-base);
  line-height: 1;
}
.step__text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}
.step__label {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-text);
}
.step__summary {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}
.step--warn .step__summary {
  color: var(--color-danger);
  font-weight: 600;
}
.step__arrow {
  color: var(--color-text-muted);
  font-size: var(--text-lg);
  flex: 0 0 auto;
}

.app-main {
  flex: 1;
  max-width: 1080px;
  width: 100%;
  margin: 0 auto;
  padding: var(--space-6) var(--space-4);
}
.app-footer {
  border-top: 1px solid var(--color-border);
  padding: var(--space-4);
  text-align: center;
  color: var(--color-text-muted);
  font-size: var(--text-xs);
  display: flex;
  justify-content: center;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.app-footer a { color: var(--color-primary); text-decoration: none; }
.app-footer a:hover { text-decoration: underline; }

@media (max-width: 640px) {
  .brand__tag {
    display: none;
  }
  .lib-nav {
    margin-left: 0;
  }
}
/* 触控输入设备（不只是窄屏），按 adapt.md 建议用 pointer:coarse 检测加大热区 */
@media (max-width: 640px), (pointer: coarse) {
  .lib-btn { min-height: 44px; }
}
</style>
