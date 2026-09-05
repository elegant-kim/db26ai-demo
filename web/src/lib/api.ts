import axios, { type AxiosInstance } from 'axios'

// investhub lib/api.ts 이식. 인증이 없으므로 401 리다이렉트는 제거했다.
export const api: AxiosInstance = axios.create({
  baseURL: '/',
  timeout: 120_000,   // 프론트 120초 = DB call 타임아웃과 일치 (CLAUDE.md)
})

// ── 일시적 서버오류 자동 재시도 ──
// 맥 절전→깨어남 직후 ADB 커넥션 풀이 잠깐 stale 한 창을 흡수한다.
// 안전한 요청만: GET(부수효과 없음). 변경성 POST/DELETE 는 중복 실행 위험이라 제외.
const RETRY_LIMIT = 5
const RETRY_BASE_MS = 1500

function isTransient(err: any): boolean {
  const s = err?.response?.status
  return !err?.response || s === 500 || s === 502 || s === 503 || s === 504
}
function isRetriable(err: any): boolean {
  const cfg = err?.config
  if (!cfg || !isTransient(err)) return false
  return (cfg.method || 'get').toLowerCase() === 'get'
}

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const cfg = err?.config
    if (cfg && isRetriable(err)) {
      cfg.__retry = (cfg.__retry || 0) + 1
      if (cfg.__retry <= RETRY_LIMIT) {
        try { window.dispatchEvent(new CustomEvent('api:retry', { detail: { count: cfg.__retry, url: cfg.url } })) } catch { /* noop */ }
        await new Promise((res) => setTimeout(res, Math.min(RETRY_BASE_MS * cfg.__retry, 6000)))
        return api(cfg)
      }
    }
    return Promise.reject(err)
  },
)

/** axios 오류 → 사람이 읽을 한 줄. 백엔드는 {success:false, error:"..."} 관례. */
export function errorMessage(err: any, fallback = '요청에 실패했습니다.'): string {
  return err?.response?.data?.error || err?.response?.data?.detail || err?.message || fallback
}
