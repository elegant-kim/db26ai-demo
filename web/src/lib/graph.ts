import { api } from './api'
import { fromColumnsData, fromGraphSide, type Rows } from './normalize'

export interface QueryDef { label: string; index: number }
export interface GraphQueries { compare: QueryDef[]; pattern: QueryDef[] }
export interface ActionResult { success: boolean; message?: string; error?: string; sql_executed?: string }

export interface CompareResult {
  label: string
  sql: Rows       // 기존 SQL (JOIN)
  pgq: Rows       // SQL/PGQ
}

export const getGraphQueries = () => api.get<GraphQueries & { success: boolean }>('/api/graph/queries').then((r) => r.data)
export const createGraph = () => api.post<ActionResult>('/api/graph/create').then((r) => r.data)
export const dropGraph = () => api.post<ActionResult>('/api/graph/drop').then((r) => r.data)

export async function compareGraph(index: number): Promise<CompareResult> {
  const { data } = await api.post('/api/graph/compare', { query_index: index })
  return { label: data.label, sql: fromGraphSide(data, 'sql'), pgq: fromGraphSide(data, 'pgq') }
}

export async function runPattern(index: number): Promise<Rows> {
  const { data } = await api.post('/api/graph/pattern', { query_index: index })
  return fromColumnsData(data)
}

export const graphRecentQueries = () => api.get('/api/graph/recent-queries').then((r) => fromColumnsData(r.data))
