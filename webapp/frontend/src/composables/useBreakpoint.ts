import { onBeforeUnmount, onMounted, ref } from 'vue'

/**
 * 视口宽度断点（与 tokens.css / 各页面 @media 使用的 640px 保持一致）。
 * 用于需要「移动端直接不渲染某些列/控件」而非仅靠 CSS 隐藏的场景——
 * el-table 用 <colgroup> 固定列宽，CSS display:none 隐藏单元格不会真正
 * 收窄表格，必须在组件层面不渲染对应 <el-table-column> 才有效。
 */
export function useIsMobile(breakpoint = 640) {
  const isMobile = ref(false)
  let mql: MediaQueryList | null = null
  function update() {
    isMobile.value = mql?.matches ?? false
  }
  onMounted(() => {
    mql = window.matchMedia(`(max-width: ${breakpoint}px)`)
    update()
    mql.addEventListener('change', update)
  })
  onBeforeUnmount(() => {
    mql?.removeEventListener('change', update)
  })
  return isMobile
}
