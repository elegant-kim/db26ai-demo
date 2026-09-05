import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { MENUS, homePath } from '@/lib/menu'

// 페이지는 lazy — 탭별 chunk.
const routes: RouteRecordRaw[] = [
  { path: '/', redirect: () => homePath() },
  { path: '/nl2sql', component: () => import('@/pages/Nl2sql.vue'), meta: { menu: 'nl2sql' } },
  { path: '/vector', component: () => import('@/pages/Vector.vue'), meta: { menu: 'vector' } },
  { path: '/duality', component: () => import('@/pages/Duality.vue'), meta: { menu: 'duality' } },
  { path: '/graph', component: () => import('@/pages/Graph.vue'), meta: { menu: 'graph' } },
  { path: '/productivity', component: () => import('@/pages/Productivity.vue'), meta: { menu: 'productivity' } },
  { path: '/awr', component: () => import('@/pages/Awr.vue'), meta: { menu: 'awr' } },
  { path: '/manual', component: () => import('@/pages/Manual.vue'), meta: { menu: 'manual' } },
  // 디자인 토대 검증 화면 (5-0). 메뉴에는 없다 — URL 로만 진입.
  { path: '/styleguide', component: () => import('@/pages/Styleguide.vue') },
  { path: '/:pathMatch(.*)*', redirect: () => homePath() },
]

const router = createRouter({ history: createWebHistory(), routes })

router.afterEach((to) => {
  const m = MENUS.find((x) => x.id === to.meta.menu)
  document.title = m ? `${m.title} · Oracle AI Database 26ai 데모` : 'Oracle AI Database 26ai 데모'
})

export default router
