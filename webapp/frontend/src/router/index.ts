import { createRouter, createWebHistory } from 'vue-router'
import Locate from '@/views/Locate.vue'
import SchoolSearch from '@/views/SchoolSearch.vue'
import MajorSearch from '@/views/MajorSearch.vue'
import SchoolDetail from '@/views/SchoolDetail.vue'
import SchoolMajorDetail from '@/views/SchoolMajorDetail.vue'
import DataCenter from '@/views/DataCenter.vue'
import Eligibility from '@/views/Eligibility.vue'
import Match from '@/views/Match.vue'
import Workbench from '@/views/Workbench.vue'
import Auth from '@/views/Auth.vue'

const routes = [
  { path: '/', name: 'locate', component: Locate },
  { path: '/auth', name: 'auth', component: Auth, meta: { public: true } },
  { path: '/search/school', name: 'school-search', component: SchoolSearch },
  { path: '/search/major', name: 'major-search', component: MajorSearch },
  { path: '/school/:code', name: 'school-detail', component: SchoolDetail },
  { path: '/school/:code/major', name: 'school-major', component: SchoolMajorDetail },
  { path: '/match', name: 'match', component: Match },
  { path: '/workbench', name: 'workbench', component: Workbench },
  { path: '/datacenter', name: 'datacenter', component: DataCenter },
  { path: '/eligibility', name: 'eligibility', component: Eligibility },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局守卫：匿名优先（P3）。查询/定位/匹配/工作台全程无需登录，
// 数据存本机浏览器；登录仅作为「跨设备同步 + 云端保存」的增值入口。
router.beforeEach(async (to) => {
  const { useAuth } = await import('@/composables/useAuth')
  const auth = useAuth()
  await auth.restore() // 等待启动态恢复（单飞，仅首次真正执行）

  if (to.meta.public) {
    // 已登录时访问登录页 → 回首页
    if (auth.isLoggedIn.value) return { path: '/' }
    return true
  }
  return true
})

export default router
