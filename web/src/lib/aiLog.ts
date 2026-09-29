import { api } from './api'

/** Select AI 호출 이력(AI_QUERY_LOG) — 정본 app/ai_log.py. 「이력」 서브탭(PoC 1-C, 2026-09-29). */
export interface LogRow {
  ID: number; STARTED_AT: string; SOURCE: string; PROFILE_NAME: string | null; ACTION: string | null; QUESTION: string | null
  STATUS: 'SUCCEEDED' | 'FAILED'; ELAPSED_MS: number | null; CONVERSATION_ID: string | null; ROW_COUNT: number | null; MODEL: string | null
  FEEDBACK_TYPE: 'positive' | 'negative' | null; FEEDBACK_ID: number | null
}
export interface LogFeedback { ID: number; FEEDBACK_TYPE: string; FEEDBACK_CONTENT: string | null; CORRECTED_SQL: string | null; SOURCE: string; CREATED_AT: string; UPDATED_AT: string | null }
export interface LogDetail extends Omit<LogRow, 'FEEDBACK_TYPE' | 'FEEDBACK_ID'> {
  GENERATED_SQL: string | null; RESPONSE_TEXT: string | null; ERROR_MSG: string | null; SQL_ID: string | null; CREATED_BY: string | null
  feedback: LogFeedback[]
}
export interface LogFilter { q: string; date_from: string; date_to: string; profile: string; action: string; status: string; feedback: string }
export interface LogPage { success: boolean; rows: LogRow[]; total: number; page: number; size: number; sql: string; error?: string }
export interface LogSummary {
  success: boolean; total: number; succeeded: number; failed: number; success_rate: number | null; avg_ms: number | null; max_ms: number | null
  feedback_logs: number; positive: number; negative: number; feedback_rate: number | null; first_at: string | null; last_at: string | null
  by_profile: { PROFILE_NAME: string | null; MODEL: string | null; N: number; SUCCEEDED: number; AVG_MS: number | null; MAX_MS: number | null }[]
  by_action: { ACTION: string | null; N: number; AVG_MS: number | null }[]
}

export const EMPTY_FILTER: LogFilter = { q: '', date_from: '', date_to: '', profile: '', action: '', status: '', feedback: '' }
export const FEEDBACK_OPTIONS = [
  { value: '', label: '피드백 전체' }, { value: 'any', label: '피드백 있음' }, { value: 'none', label: '피드백 없음' },
  { value: 'positive', label: '👍 좋음' }, { value: 'negative', label: '👎 나쁨' },
]
export const STATUS_OPTIONS = [{ value: '', label: '상태 전체' }, { value: 'SUCCEEDED', label: '성공' }, { value: 'FAILED', label: '실패' }]

export const getHistory = (f: LogFilter, page: number, size = 20) =>
  api.get<LogPage>('/api/nl2sql/history', { params: { ...f, page, size } }).then((r) => r.data)
export const getHistorySummary = (profile = '') => api.get<LogSummary>('/api/nl2sql/history/summary', { params: { profile } }).then((r) => r.data)
export const getHistoryDetail = (id: number) => api.get<LogDetail & { success: boolean; error?: string }>(`/api/nl2sql/history/${id}`).then((r) => r.data)
