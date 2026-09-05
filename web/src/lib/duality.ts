import { api } from './api'
import { fromDualityRelational, type Rows } from './normalize'
import type { Step } from './types/steps'

export interface DualityView { name: string; status: string }
export interface ActionResult { success: boolean; message?: string; error?: string; sql_executed?: string; views?: DualityView[] }
export interface CompareResult {
  relational: Rows
  jsonSql?: string
  jsonDocs: Record<string, any>[] | null
  jsonElapsed: number | null
  jsonError?: string
}
export interface DocSummary { id: string; summary: string }
export interface DocResult { success: boolean; document?: Record<string, any>; document_text?: string; etag?: string | null; sql_executed?: string; error?: string }
export interface UpdateResult { success: boolean; message?: string; error?: string; new_etag?: string | null; sql_executed?: string }
export interface EtagResult { success: boolean; steps: Step[]; error?: string }

export const getDualityViews = () => api.get<ActionResult>('/api/duality/views').then((r) => r.data)
export const createDualityViews = () => api.post<ActionResult>('/api/duality/create-views').then((r) => r.data)
export const dropDualityViews = () => api.post<ActionResult>('/api/duality/drop-views').then((r) => r.data)

export async function compareDuality(view_name: string, limit: number): Promise<CompareResult> {
  const { data } = await api.post('/api/duality/compare', { view_name, limit })
  return {
    relational: fromDualityRelational(data),
    jsonSql: data.json_sql,
    jsonDocs: Array.isArray(data.json_data) ? data.json_data : null,
    jsonElapsed: data.json_elapsed ?? null,
    jsonError: data.json_error,
  }
}

export const listDualityDocs = (view_name: string) =>
  api.post<{ success: boolean; docs: DocSummary[]; sql_executed?: string; error?: string }>('/api/duality/docs', { view_name }).then((r) => r.data)
export const fetchDualityDoc = (view_name: string, doc_id: string) =>
  api.post<DocResult>('/api/duality/doc', { view_name, doc_id }).then((r) => r.data)
export const updateDualityDoc = (view_name: string, doc_json: Record<string, any>) =>
  api.post<UpdateResult>('/api/duality/doc/update', { view_name, doc_json }).then((r) => r.data)
export const runEtagSimulation = () => api.post<EtagResult>('/api/duality/etag-simulation').then((r) => r.data)
