<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { CURRENT_VERSION, PRODUCT_RELEASES, RELEASE_STORAGE_KEY } from '@/data/releases'

const open = ref(false)
const unread = ref(false)
const latest = computed(() => PRODUCT_RELEASES[0])

function show() {
  open.value = true
  unread.value = false
  localStorage.setItem(RELEASE_STORAGE_KEY, CURRENT_VERSION)
}

onMounted(() => {
  unread.value = localStorage.getItem(RELEASE_STORAGE_KEY) !== CURRENT_VERSION
})
</script>

<template>
  <div class="release-notes">
    <button type="button" class="release-trigger" aria-label="查看版本更新" @click="show">
      <span aria-hidden="true">✦</span>
      <span>版本更新</span>
      <span class="release-trigger__version">v{{ CURRENT_VERSION }}</span>
      <span v-if="unread" class="release-trigger__new">新</span>
    </button>

    <el-drawer v-model="open" title="版本更新" direction="rtl" size="min(92vw, 460px)" class="release-drawer" append-to-body>
      <div class="release-intro">
        <span class="release-intro__badge">当前版本 v{{ CURRENT_VERSION }}</span>
        <strong>{{ latest.title }}</strong>
        <p>这里记录每次更新中用户可以直接使用的新功能。</p>
      </div>

      <ol class="timeline">
        <li v-for="(release, index) in PRODUCT_RELEASES" :key="release.version" class="release-item">
          <span class="release-item__dot" aria-hidden="true"></span>
          <div class="release-item__head">
            <div>
              <strong>{{ release.title }}</strong>
              <span v-if="index === 0" class="latest">最新</span>
            </div>
            <span class="release-item__meta">v{{ release.version }} · {{ release.date }}</span>
          </div>
          <p class="release-item__summary">{{ release.summary }}</p>
          <ul>
            <li v-for="feature in release.features" :key="feature">{{ feature }}</li>
          </ul>
        </li>
      </ol>

      <div class="feedback">
        <strong>内容反馈与功能建议</strong>
        <p>如果发现数据、文案或功能问题，请发送邮件并尽量附上页面地址和截图。</p>
        <a href="mailto:14324569@qq.com?subject=辽宁志愿参谋内容反馈">14324569@qq.com</a>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.release-notes { display: flex; align-items: center; }
.release-trigger { position: relative; min-height: 34px; display: inline-flex; align-items: center; gap: 5px; padding: 4px 9px; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-text-secondary); font-size: var(--text-xs); cursor: pointer; white-space: nowrap; }
.release-trigger:hover { border-color: var(--color-primary); color: var(--color-primary); background: var(--color-primary-soft); }
.release-trigger:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.release-trigger__version { color: var(--color-text-muted); font-variant-numeric: tabular-nums; }
.release-trigger__new { position: absolute; top: -8px; right: -7px; min-width: 20px; height: 18px; padding: 0 4px; display: grid; place-items: center; border-radius: 9px; background: var(--color-danger); color: #fff; font-size: 10px; font-weight: 700; }
.release-drawer :deep(.el-drawer__body) { overflow-y: auto; padding-bottom: var(--space-6); }
.release-intro { padding: var(--space-4); border-radius: var(--radius-lg); background: var(--color-primary-soft); display: flex; flex-direction: column; gap: var(--space-2); }
.release-intro__badge { align-self: flex-start; padding: 3px 8px; border-radius: 999px; background: var(--color-primary); color: #fff; font-size: var(--text-xs); }
.release-intro p { margin: 0; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.7; }
.timeline { list-style: none; margin: var(--space-5) 0; padding: 0 0 0 14px; border-left: 1px solid var(--color-border); }
.release-item { position: relative; padding: 0 0 var(--space-6) var(--space-5); }
.release-item:last-child { padding-bottom: 0; }
.release-item__dot { position: absolute; left: -20px; top: 4px; width: 11px; height: 11px; border-radius: 50%; background: var(--color-primary); border: 3px solid var(--color-surface); box-shadow: 0 0 0 1px var(--color-primary); }
.release-item__head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-2); }
.release-item__head strong { font-size: var(--text-base); }
.release-item__meta { color: var(--color-text-muted); font-size: var(--text-xs); white-space: nowrap; font-variant-numeric: tabular-nums; }
.latest { margin-left: 6px; padding: 2px 6px; border-radius: 999px; background: var(--color-primary-soft); color: var(--color-primary); font-size: 10px; font-weight: 700; }
.release-item__summary { margin: var(--space-2) 0; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.65; }
.release-item ul { margin: 0; padding-left: 18px; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.8; }
.feedback { padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg-subtle, #f7f9fc); }
.feedback p { margin: var(--space-2) 0; color: var(--color-text-muted); font-size: var(--text-sm); line-height: 1.65; }
.feedback a { color: var(--color-primary); font-weight: 600; }
@media (max-width: 640px), (pointer: coarse) { .release-trigger { min-height: 44px; } }
</style>
