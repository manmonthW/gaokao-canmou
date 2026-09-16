import { computed, ref } from 'vue'

export type ThemePreference = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'ln-zhiyuan-theme'
const saved = localStorage.getItem(STORAGE_KEY)
const preference = ref<ThemePreference>(saved === 'light' || saved === 'dark' ? saved : 'system')
const systemDark = ref(window.matchMedia('(prefers-color-scheme: dark)').matches)

const media = window.matchMedia('(prefers-color-scheme: dark)')
media.addEventListener('change', (event) => {
  systemDark.value = event.matches
  applyTheme()
})

function applyTheme() {
  const dark = preference.value === 'dark' || (preference.value === 'system' && systemDark.value)
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
}

function setTheme(value: ThemePreference) {
  preference.value = value
  localStorage.setItem(STORAGE_KEY, value)
  applyTheme()
}

applyTheme()

export function useTheme() {
  return {
    preference,
    isDark: computed(() => preference.value === 'dark' || (preference.value === 'system' && systemDark.value)),
    setTheme,
  }
}
