<script setup lang="ts">
import { computed, ref } from 'vue'
import { CURRENT_VERSION, RELEASE_STORAGE_KEY } from '@/data/releases'
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

const open = ref(false)
const theme = useTheme()
const avatar = computed(() => (props.user?.username || '?').slice(0, 1).toUpperCase())
const hasUpdate = ref(localStorage.getItem(RELEASE_STORAGE_KEY) !== CURRENT_VERSION)

function closeAndEmit(event: 'login' | 'logout' | 'releases') {
  open.value = false
  if (event === 'releases') hasUpdate.value = false
  emit(event)
}

function setTheme(value: ThemePreference) {
  theme.setTheme(value)
}
</script>

<template>
  <div class="account-tools">
    <button v-if="!loggedIn" type="button" class="login-link" @click="emit('login')">登录</button>

    <el-popover
      v-model:visible="open"
      placement="bottom-end"
      :width="288"
      trigger="click"
      popper-class="utility-menu-popper"
    >
      <template #reference>
        <button
          type="button"
          class="account-trigger"
          :class="{ 'account-trigger--user': loggedIn }"
          :aria-label="loggedIn ? '打开账户菜单' : '打开设置菜单'"
          :aria-expanded="open"
        >
          <span v-if="loggedIn" class="account-trigger__avatar">{{ avatar }}</span>
          <svg v-else viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21h-4v-.09A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3v-4h.09A1.7 1.7 0 0 0 4.6 8.6a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3h4v.09A1.7 1.7 0 0 0 15.4 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.38.27.73.62 1 .99.18.3.31.65.4 1.01H21v4h-.09A1.7 1.7 0 0 0 19.4 15Z"/>
          </svg>
          <svg v-if="loggedIn" class="account-trigger__chevron" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg>
          <span v-if="hasUpdate" class="account-trigger__notice" aria-label="有新版本"></span>
        </button>
      </template>

      <nav class="utility-menu" aria-label="账户与设置">
        <div v-if="loggedIn" class="account-summary">
          <span class="account-summary__avatar">{{ avatar }}</span>
          <span class="account-summary__copy">
            <strong>{{ user?.username }}</strong>
            <small>{{ user?.email }}</small>
          </span>
        </div>

        <section class="menu-section">
          <span class="menu-section__title">外观</span>
          <div class="theme-options" role="radiogroup" aria-label="页面显示模式">
            <button
              v-for="option in ([
                { value: 'system', label: '自动' },
                { value: 'light', label: '浅色' },
                { value: 'dark', label: '深色' },
              ] as const)"
              :key="option.value"
              type="button"
              class="theme-option"
              :class="{ 'theme-option--active': theme.preference.value === option.value }"
              role="radio"
              :aria-checked="theme.preference.value === option.value"
              @click="setTheme(option.value)"
            >
              <svg v-if="option.value === 'system'" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
              <svg v-else-if="option.value === 'light'" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41"/></svg>
              <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.5 8.5 0 1 0 20.5 14.2Z"/></svg>
              <span>{{ option.label }}</span>
            </button>
          </div>
        </section>

        <div class="menu-list">
          <button type="button" class="menu-item" @click="closeAndEmit('releases')">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12M8 11l4 4 4-4"/><path d="M5 19h14"/></svg>
            <span>版本更新</span>
            <span class="menu-item__meta tnum">v{{ CURRENT_VERSION }}</span>
            <span v-if="hasUpdate" class="menu-item__new">新</span>
          </button>
          <a class="menu-item" href="mailto:14324569@qq.com?subject=辽宁志愿参谋内容反馈" @click="open = false">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z"/><path d="M8 9h8M8 13h5"/></svg>
            <span>反馈与建议</span>
          </a>
        </div>

        <button v-if="loggedIn" type="button" class="menu-item menu-item--danger" @click="closeAndEmit('logout')">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 17l5-5-5-5M15 12H3"/><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/></svg>
          <span>退出登录</span>
        </button>
        <button v-else type="button" class="menu-item menu-item--login" @click="closeAndEmit('login')">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 7l5 5-5 5M19 12H7"/><path d="M9 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h4"/></svg>
          <span>登录并同步数据</span>
        </button>
      </nav>
    </el-popover>
  </div>
</template>

<style scoped>
.account-tools { display: inline-flex; align-items: center; gap: var(--space-2); flex: 0 0 auto; }
.login-link { min-height: 34px; padding: 0 5px; border: 0; background: transparent; color: var(--color-primary); font: inherit; font-size: var(--text-sm); font-weight: 500; cursor: pointer; }
.login-link:hover { color: var(--color-primary-hover); text-decoration: underline; text-underline-offset: 4px; }
.login-link:focus-visible, .account-trigger:focus-visible, .theme-option:focus-visible, .menu-item:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.account-trigger { position: relative; width: 34px; height: 34px; display: inline-flex; align-items: center; justify-content: center; padding: 0; border: 0; border-radius: 50%; background: transparent; color: var(--color-text-secondary); cursor: pointer; transition: background-color .18s ease, color .18s ease; }
.account-trigger:hover, .account-trigger[aria-expanded='true'] { background: var(--color-bg-subtle); color: var(--color-text); }
.account-trigger--user { width: auto; gap: 3px; padding: 2px 6px 2px 2px; border-radius: 999px; }
.account-trigger__avatar, .account-summary__avatar { display: grid; place-items: center; border-radius: 50%; background: var(--color-primary); color: #fff; font-weight: 700; }
.account-trigger__avatar { width: 30px; height: 30px; font-size: var(--text-sm); }
.account-trigger__chevron { color: var(--color-text-muted); transition: transform .18s ease; }
.account-trigger[aria-expanded='true'] .account-trigger__chevron { transform: rotate(180deg); }
.account-trigger__notice { position: absolute; top: 2px; right: 2px; width: 7px; height: 7px; border: 2px solid var(--color-surface); border-radius: 50%; background: var(--color-primary); }
.utility-menu { margin: -4px; color: var(--color-text); }
.account-summary { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) var(--space-2) var(--space-3); border-bottom: 1px solid var(--color-border); }
.account-summary__avatar { width: 38px; height: 38px; flex: 0 0 38px; font-size: var(--text-base); }
.account-summary__copy { min-width: 0; display: flex; flex-direction: column; line-height: 1.45; }
.account-summary__copy strong, .account-summary__copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.account-summary__copy strong { font-size: var(--text-sm); }
.account-summary__copy small { color: var(--color-text-muted); font-size: var(--text-xs); }
.menu-section { padding: var(--space-3) var(--space-2); }
.menu-section__title { display: block; margin-bottom: var(--space-2); color: var(--color-text-muted); font-size: var(--text-xs); font-weight: 500; }
.theme-options { display: grid; grid-template-columns: repeat(3, 1fr); padding: 3px; border-radius: var(--radius-md); background: var(--color-bg-subtle); }
.theme-option { min-height: 34px; display: inline-flex; align-items: center; justify-content: center; gap: 5px; padding: 0 6px; border: 0; border-radius: 6px; background: transparent; color: var(--color-text-muted); font: inherit; font-size: var(--text-xs); cursor: pointer; }
.theme-option:hover { color: var(--color-text); }
.theme-option--active { background: var(--color-surface); color: var(--color-primary); font-weight: 600; box-shadow: var(--shadow-sm); }
.menu-list { padding: var(--space-1) 0; border-top: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); }
.menu-item { width: 100%; min-height: 40px; display: grid; grid-template-columns: 22px 1fr auto auto; align-items: center; gap: var(--space-2); padding: 7px var(--space-2); border: 0; border-radius: var(--radius-sm); background: transparent; color: var(--color-text-secondary); text-align: left; text-decoration: none; font: inherit; font-size: var(--text-sm); cursor: pointer; transition: background-color .15s ease, color .15s ease; }
.menu-item:hover { background: var(--color-bg-subtle); color: var(--color-text); }
.menu-item svg { color: var(--color-text-muted); }
.menu-item__meta { color: var(--color-text-muted); font-size: var(--text-xs); }
.menu-item__new { min-width: 18px; padding: 1px 4px; border-radius: 4px; background: var(--color-primary-soft); color: var(--color-primary); font-size: 10px; font-weight: 700; text-align: center; }
.menu-item--danger, .menu-item--login { margin-top: var(--space-1); }
.menu-item--danger:hover, .menu-item--danger:hover svg { color: var(--color-danger); }
.menu-item--login, .menu-item--login svg { color: var(--color-primary); }
@media (max-width: 640px), (pointer: coarse) {
  .login-link, .account-trigger { min-height: 44px; }
  .account-trigger { width: 44px; }
  .account-trigger--user { width: auto; }
  .theme-option, .menu-item { min-height: 44px; }
}
</style>
