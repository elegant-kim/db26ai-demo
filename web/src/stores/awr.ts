import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { errorMessage } from '@/lib/api'
import { analyzeAwr, awrFollowup, loadAwrJson, AWR_MAX_BYTES, type AnalyzeResult, type AwrAnalysis, type ParseInfo } from '@/lib/awr'
import type { ChatMessage } from '@/lib/types/chat'
import { useSystemStore } from './system'

export interface AwrSession {
  id: number
  sessionId: string          // 백엔드 캐시 키 — 후속 질문·원문 보기에 쓴다 (서버 재기동이면 사라진다)
  filename: string
  provider: string
  timestamp: string
  analysis: AwrAnalysis
  parseInfo: ParseInfo
  elapsedMs: number
  messages: ChatMessage[]
  imported?: boolean         // ?load= 로 연 결과 — 후속 질문 불가(서버 캐시 없음)
}

/**
 * AWR 탭 상태. 분석 응답은 한 번에 오지만(30~120초) 사용자는 "멈춤"과 "작업 중"을 구분해야 하므로
 * 레거시의 3단계 연출(2초 후 2단계, 90초 후 3단계, 5초마다 +5%)을 타이머로 재현한다(개발노하우 §4).
 */
export const useAwrStore = defineStore('awr', () => {
  const system = useSystemStore()
  const sessions = ref<AwrSession[]>([])
  const active = ref(0)
  const provider = ref('')                      // '' = 서버 기본(.env LLM_PROVIDER)
  const loading = ref(false)
  const step = ref(0)                           // 1 파싱 · 2 AI 분석 · 3 정리
  const elapsedSec = ref(0)
  const percent = ref(0)
  const error = ref<string | null>(null)
  const asking = ref(false)
  let seq = 0
  let timers: number[] = []

  const current = computed(() => sessions.value[active.value] ?? null)
  const providerLabel = computed(() => {
    const id = provider.value || system.health?.llm_provider || ''
    const p = system.providers.find((x) => x.id === id || x.provider === id)
    return p?.name || id || '기본'
  })

  function clearTimers() { timers.forEach((t) => window.clearTimeout(t)); timers = [] }

  function push(r: AnalyzeResult, providerName: string, imported = false) {
    sessions.value.push({
      id: ++seq, sessionId: r.session_id, filename: r.filename, provider: providerName,
      timestamp: new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }),
      analysis: r.analysis, parseInfo: r.parse_info, elapsedMs: r.elapsed_ms, messages: [], imported,
    })
    active.value = sessions.value.length - 1
  }

  async function analyze(file: File) {
    if (!/\.(html?|htm)$/i.test(file.name)) { error.value = 'HTML 파일만 업로드할 수 있습니다.'; return }
    if (file.size > AWR_MAX_BYTES) { error.value = '파일 크기가 20MB 를 초과합니다.'; return }
    clearTimers()
    loading.value = true; error.value = null; step.value = 1; elapsedSec.value = 0; percent.value = 0
    const t0 = Date.now()
    timers.push(window.setInterval(() => { elapsedSec.value = Math.round((Date.now() - t0) / 1000) }, 1000))
    timers.push(window.setInterval(() => { if (percent.value < 95) percent.value += 5 }, 5000))
    timers.push(window.setTimeout(() => { if (loading.value) step.value = 2 }, 2000))
    timers.push(window.setTimeout(() => { if (loading.value) step.value = 3 }, 90000))
    try {
      const r = await analyzeAwr(file, provider.value || undefined)
      if (!r.success) throw new Error(r.error || '분석에 실패했습니다.')
      if (!r.analysis || (!r.analysis.categoryScores && !r.analysis.section1_system_overview)) throw new Error('LLM 응답에서 유효한 분석 결과를 추출하지 못했습니다. 다시 시도해 주세요.')
      push(r, providerLabel.value)
      system.toast(`AWR 분석 완료 (${(r.elapsed_ms / 1000).toFixed(1)}초)`, 'success')
    } catch (e: any) {
      error.value = e?.code === 'ECONNABORTED' ? '분석 시간이 초과되었습니다 (3분).' : errorMessage(e)
    } finally {
      clearTimers(); loading.value = false; step.value = 0; percent.value = 0
    }
  }

  async function loadFromUrl(url: string) {
    error.value = null
    try {
      const r = await loadAwrJson(url)
      if (!r?.analysis) throw new Error('분석 결과 JSON 이 아닙니다.')
      push(r, '가져온 결과', true)
    } catch (e) { error.value = errorMessage(e) }
  }

  async function ask(question: string) {
    const s = current.value
    const q = question.trim()
    if (!s || !q || asking.value) return
    s.messages.push({ role: 'user', content: q })
    const reply: ChatMessage = { role: 'assistant', content: '', loading: true }
    s.messages.push(reply)
    asking.value = true
    const t0 = Date.now()
    try {
      const r = await awrFollowup(s.sessionId, q, provider.value)
      reply.content = r.success ? (r.answer || '') : `오류: ${r.error || '응답 생성에 실패했습니다.'}`
      reply.error = !r.success
      reply.elapsedMs = r.elapsed_ms ?? Date.now() - t0
    } catch (e) { reply.content = `오류: ${errorMessage(e)}`; reply.error = true }
    finally { reply.loading = false; asking.value = false }
  }

  function select(i: number) { if (i >= 0 && i < sessions.value.length) active.value = i }
  function remove(i: number) {
    sessions.value.splice(i, 1)
    if (active.value >= sessions.value.length) active.value = Math.max(0, sessions.value.length - 1)
  }

  return { sessions, active, current, provider, providerLabel, loading, step, elapsedSec, percent, error, asking, analyze, loadFromUrl, ask, select, remove }
})
