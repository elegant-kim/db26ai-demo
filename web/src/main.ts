import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/tailwind.css'
import { applyThemeFromStorage } from './lib/theme'

applyThemeFromStorage()

// 배포 직후 stale-chunk 404 자동 회복 (investhub 에서 이식).
// 새 빌드로 갈리면 옛 hash chunk 는 dist 에서 사라져 404 → 옛 SPA 가 dynamic import 하다
// 실패하면 화면이 회색 또는 hang. 한 번만 reload 하면 새 index.html → 새 chunk 로 복구.
// 30초 시간창 가드로 연속 루프만 막는다(하루 여러 번 배포해도 다음 배포에서 다시 복구 가능).
const RELOAD_KEY = '__db26ai_chunk_reload__'
function isChunkLoadError(e: unknown): boolean {
  const msg = String((e as { message?: string })?.message || e)
  return (
    msg.includes('Failed to fetch dynamically imported module') ||
    msg.includes('error loading dynamically imported module') ||
    msg.includes('Importing a module script failed') ||
    /Loading chunk \S+ failed/.test(msg)
  )
}
function maybeReloadForStaleChunk(e: unknown) {
  if (!isChunkLoadError(e)) return
  const last = Number(sessionStorage.getItem(RELOAD_KEY) || 0)
  if (Date.now() - last < 30_000) return
  sessionStorage.setItem(RELOAD_KEY, String(Date.now()))
  console.warn('[db26ai] stale chunk 감지 → 자동 새로고침')
  window.location.reload()
}
window.addEventListener('error', (ev) => maybeReloadForStaleChunk(ev.error || ev.message))
window.addEventListener('unhandledrejection', (ev) => maybeReloadForStaleChunk(ev.reason))
window.addEventListener('vite:preloadError', () => maybeReloadForStaleChunk(
  new Error('Failed to fetch dynamically imported module (vite:preloadError)')))
router.onError((err) => maybeReloadForStaleChunk(err))

const app = createApp(App)
// 서브탭 defineAsyncComponent 실패는 Vue 가 삼켜 window 훅에 안 잡힌다 → 전역 에러 훅에서도 감지
app.config.errorHandler = (err, _instance, info) => {
  maybeReloadForStaleChunk(err)
  console.error('[db26ai]', info, err)
}
app.use(createPinia())
app.use(router)
app.mount('#app')
