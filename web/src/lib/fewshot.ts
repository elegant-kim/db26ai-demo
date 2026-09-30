import { api } from './api'
import { postSse, type SseHandler } from '@/composables/useSse'

/** Few-shot 일괄 등록 (PoC 2-A) — 정본 app/fewshot.py. 파일 → 미리보기 → 검증 → SSE 등록(행당 LLM 1회). */
export interface FewshotRow { row: number; question: string; sql: string; note: string; error: string | null; valid: boolean | null }
export interface RowResult { row: number; question: string; ok: boolean; error?: string; feedback_id?: number; elapsed_ms: number; generate_ms?: number }
export interface RegisterSummary { ok: number; failed: number; total: number; elapsed_ms: number }
export interface FeedbackRow { ID: number; LOG_ID: number | null; PROFILE_NAME: string; FEEDBACK_TYPE: 'positive' | 'negative'; QUESTION: string | null; FEEDBACK_CONTENT: string | null; HAS_CORRECTED: number; SOURCE: string; CREATED_AT: string; UPDATED_AT: string | null }

export const TEMPLATE_URL = '/api/nl2sql/fewshot/template'
export const parseFewshot = (file: File) => { const fd = new FormData(); fd.append('file', file); return api.post<{ success: boolean; filename: string; headers: string[]; rows: FewshotRow[]; total: number; error?: string }>('/api/nl2sql/fewshot/parse', fd).then((r) => r.data) }
export const validateFewshot = (rows: FewshotRow[]) => api.post<{ success: boolean; rows: FewshotRow[]; valid: number; invalid: number; error?: string }>('/api/nl2sql/fewshot/validate', { rows }).then((r) => r.data)
export const registerFewshot = (profile_name: string, rows: FewshotRow[], onEvent: SseHandler, signal?: AbortSignal) => postSse('/api/nl2sql/fewshot/register', { profile_name, rows }, onEvent, signal)
export const listFeedback = (profile: string) => api.get<{ success: boolean; feedback: FeedbackRow[]; error?: string }>('/api/nl2sql/feedback', { params: { profile } }).then((r) => r.data)
export const purgeFeedback = (profile_name: string) => api.post<{ success: boolean; removed_oracle: number; removed_app: number; index_questions: number; error?: string }>('/api/nl2sql/feedback/purge', { profile_name }).then((r) => r.data)
