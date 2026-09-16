<script setup lang="ts">
import { computed } from 'vue'
import { useTheme, type ThemePreference } from '@/composables/useTheme'
import type { AuthUser } from '@/types'

const props = defineProps<{
  loggedIn: boolean
  user: AuthUser | null
}>()

const emit = defineEmits<{
  login: []
  logout: []
  releases: []
}>()

const theme = useTheme()
const avatar = computed(() => (props.user?.username || '?').slice(0, 1).toUpperCase())

function setTheme(value: string | number | boolean | undefined) {
  theme.setTheme(value as ThemePreference)
}
</script>

<template>
  <el-popover placement="bottom-end" :width="300" trigger="click" popper-class="utility-menu-popper">
    <template #reference>
      <button type="button" class="utility-trigger" aria-label="打开用户与显示设置">
        <span v-if="loggedIn" class="utility-trigger__avatar">{{ avatar }}</span>
        <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21h-4v-.09A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3v-4h.09A1.7 1.7 0 0 0 4.6 8.6a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3h4v.09A1.7 1.7 0 0 0 15.4 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.38.27.73.62 1 .99.18.3.31.65.4 1.01H21v4h-.09A1.7 1.7 0 0 0 19.4 15Z"/>
        </svg>
        <span class="utility-trigger__label">设置</span>
      </button>
    </template>

    <section class="utility-panel" aria-label="用户与显示设置">
      <div class="utility-panel__account">
        <template v-if="loggedIn">
          <span class="account-avatar">{{ avatar }}</span>
          <span class="account-copy">
            <strong>{{ user?.username }}</strong>
            <small>{{ user?.email }}</small>
          </span>
          <el-button text type="danger" size="small" @click="emit('logout')">退出</el-button>
        </template>
        <template v-else>
          <span class="account-avatar account-avatar--guest">访</span>
          <span class="account-copy">
            <strong>访客模式</strong>
            <small>登录后可同步档案与方案</small>
          </span>
          <el-button type="primary" size="small" @click="emit('login')">登录</el-button>
        </template>
      </div>

      <div class="utility-section">
        <span class="utility-section__label">页面显示</span>
        <el-segmented
          :model-value="theme.preference.value"
          :options="[
            { label: '跟随系统', value: 'system' },
            { label: '浅色', value: 'light' },
            { label: '深色', value: 'dark' },
          ]"
          size="small"
          @change="setTheme"
        />
      </div>

      <button type="button" class="utility-link" @click="emit('releases')">
        <span>
          <strong>版本更新</strong>
          <small>查看最新功能与改进</small>
        </span>
        <span aria-hidden="true">›</span>
      </button>
      <a class="utility-link" href="mailto:14324569@qq.com?subject=辽宁志愿参谋内容反馈">
        <span>
          <strong>反馈与建议</strong>
          <small>报告数据或功能问题</small>
        </span>
        <span aria-hidden="true">›</span>
      </a>
    </section>
  </el-popover>
</template>

<style scoped>
.utility-trigger { min-height: 34px; display: inline-flex; align-items: center; gap: 7px; padding: 4px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-text-secondary); font: inherit; font-size: var(--text-sm); cursor: pointer; }
.utility-trigger:hover { color: var(--color-primary); border-color: var(--color-primary); background: var(--color-primary-soft); }
.utility-trigger:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.utility-trigger__avatar, .account-avatar { width: 24px; height: 24px; display: grid; place-items: center; border-radius: 50%; background: var(--color-primary); color: #fff; font-size: var(--text-xs); font-weight: 700; }
.utility-panel { display: grid; gap: var(--space-3); color: var(--color-text); }
.utility-panel__account { display: flex; align-items: center; gap: var(--space-3); padding-bottom: var(--space-3); border-bottom: 1px solid var(--color-border); }
.account-avatar { width: 34px; height: 34px; flex: 0 0 34px; }
.account-avatar--guest { background: var(--color-border-strong); color: var(--color-text-secondary); }
.account-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; line-height: 1.4; }
.account-copy strong, .account-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.account-copy small, .utility-link small { color: var(--color-text-muted); font-size: var(--text-xs); font-weight: 400; }
.utility-section { display: grid; gap: var(--space-2); }
.utility-section__label { color: var(--color-text-secondary); font-size: var(--text-xs); font-weight: 600; }
.utility-section :deep(.el-segmented) { width: 100%; }
.utility-link { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-2); border: 0; border-radius: var(--radius-md); background: transparent; color: var(--color-text); text-align: left; text-decoration: none; font: inherit; cursor: pointer; }
.utility-link:hover { background: var(--color-bg-subtle); }
.utility-link > span:first-child { display: flex; flex-direction: column; }
.utility-link > span:last-child { color: var(--color-text-muted); font-size: 22px; }
@media (max-width: 640px), (pointer: coarse) { .utility-trigger { min-height: 44px; } }
</style>
