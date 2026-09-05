import { api } from './api'

export interface CategoryScore { score: number; label: string; detail?: string }
export interface AwrTable { subtitle?: string; headers: string[]; rows: (string | number | null)[][] }
export interface AwrSection {
  title?: string
  data?: Record<string, string | number | null>
  table?: AwrTable
  tables?: AwrTable[]
  interpretation?: string
}
export interface ActionItem { priority: string; action: string; evidence?: string; expectedImpact?: string; category?: string }
export interface AwrAnalysis {
  categoryScores?: Record<string, CategoryScore>
  actionItems?: ActionItem[]
  [section: string]: any
}
export interface ParseInfo {
  section_count: number; is_rac: boolean; is_exadata: boolean; parse_ms?: number
  extracted_sections?: string[]; raw_text_length?: number; max_input_chars?: number
}
export interface AnalyzeResult {
  success: boolean; session_id: string; analysis: AwrAnalysis; parse_info: ParseInfo
  elapsed_ms: number; filename: string; error?: string
}

/** 8개 보고서 섹션 — 순서 정본은 app/awr_analyzer_v2.py 의 프롬프트 JSON 스키마 */
export const SECTION_KEYS = [
  'section1_system_overview', 'section2_bottleneck', 'section3_top_sql', 'section4_io',
  'section5_hot_segments', 'section6_memory', 'section7_host_cpu', 'section8_recommendations',
] as const

export const AWR_MAX_BYTES = 20 * 1024 * 1024
export const ANALYZE_TIMEOUT_MS = 180_000

/** 분석은 SSE 가 아니다 — LLM 이 끝나면 JSON 이 한 번에 온다 (30~120초). 진행 표시는 화면의 타이머 연출. */
export async function analyzeAwr(file: File, provider?: string): Promise<AnalyzeResult> {
  const form = new FormData()
  form.append('file', file)
  if (provider) form.append('provider', provider)
  const { data } = await api.post<AnalyzeResult>('/api/awr/analyze', form, { timeout: ANALYZE_TIMEOUT_MS })
  return data
}

export const awrFollowup = (session_id: string, question: string, provider?: string) =>
  api.post<{ success: boolean; answer?: string; error?: string; elapsed_ms?: number }>(
    '/api/awr/followup', { session_id, question, provider: provider || '' }, { timeout: ANALYZE_TIMEOUT_MS },
  ).then((r) => r.data)

export const awrSourceUrl = (session_id: string, section?: string) =>
  `/api/awr/source/${encodeURIComponent(session_id)}${section ? `?section=${encodeURIComponent(section)}` : ''}`

/** 저장해 둔 분석 응답(JSON) 을 그대로 세션으로 연다 — 시연·캡처용 (`/awr?load=<url>`) */
export const loadAwrJson = (url: string) => api.get<AnalyzeResult>(url).then((r) => r.data)
