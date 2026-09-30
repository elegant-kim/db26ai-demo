import { api } from './api'

/** ⑦ Select AI Agent — 정본 app/agent.py (Phase 4, 2026-09-30). */
export interface AgentObj { name: string; status: string; description: string | null; created: string | null; attributes: Record<string, unknown> }
export interface Definitions { success: boolean; teams: AgentObj[]; agents: AgentObj[]; tasks: AgentObj[]; tools: AgentObj[]; demo: { team: string; agent: string; task: string; tool: string; native_profile: string }; error?: string }
export interface TaskStep { TASK_ORDER: number; AGENT_NAME: string; TASK_NAME: string; STATE: string; START_DATE: string; END_DATE: string | null; INPUT: string | null; RESULT: string | null; ELAPSED_MS: number | null }
export interface ToolCall { INVOCATION_ID: number; TASK_ORDER: number; TOOL_NAME: string; AGENT_NAME: string; START_DATE: string; END_DATE: string | null; INPUT: string | null; OUTPUT: string | null; TOOL_OUTPUT: string | null; INPUT_JSON: unknown; OUTPUT_JSON: unknown; ELAPSED_MS: number | null }
export interface RunResult { success: boolean; answer?: string; team_exec_id?: string | null; elapsed_ms: number; tasks: TaskStep[]; tools: ToolCall[]; sql?: string | null; log_id?: number | null; profile?: string | null; conversation_id?: string; error?: string }
export interface HistoryRow { TEAM_EXEC_ID: string; TEAM_NAME: string; STATE: string; START_DATE: string; END_DATE: string | null; CONVERSATION_ID: string | null; ELAPSED_MS: number | null; QUESTION: string | null; LOG_ID: number | null; PROFILE_NAME: string | null; FEEDBACK_TYPE: 'positive' | 'negative' | null; FEEDBACK_ID: number | null }
export interface HistoryPage { success: boolean; rows: HistoryRow[]; total: number; page: number; size: number; sql: string; teams: string[]; error?: string }
export interface ExecDetail { success: boolean; TEAM_EXEC_ID: string; TEAM_NAME: string; STATE: string; START_DATE: string; END_DATE: string | null; CONVERSATION_ID: string | null; PARAMS: string | null; tasks: TaskStep[]; tools: ToolCall[]; log: { ID: number; PROFILE_NAME: string | null; QUESTION: string | null; GENERATED_SQL: string | null; RESPONSE_TEXT: string | null; STATUS: string; ERROR_MSG: string | null; ELAPSED_MS: number | null } | null; feedback: { ID: number; FEEDBACK_TYPE: string; FEEDBACK_CONTENT: string | null; CORRECTED_SQL: string | null; SOURCE: string; CREATED_AT: string }[]; error?: string }

export const getDefinitions = () => api.get<Definitions>('/api/agent/definitions').then((r) => r.data)
export const createDemoTeam = (base_profile: string) => api.post<{ success: boolean; team?: string; profile?: string; profile_created?: boolean; steps?: { label: string; plsql: string }[]; error?: string }>('/api/agent/demo-team', { base_profile }).then((r) => r.data)
export const dropDemoTeam = () => api.delete<{ success: boolean; error?: string }>('/api/agent/demo-team').then((r) => r.data)
export const runTeam = (team_name: string, prompt: string, conversation_id: string) => api.post<RunResult>('/api/agent/run', { team_name, prompt, conversation_id }, { timeout: 300_000 }).then((r) => r.data)
export const getAgentHistory = (f: { q: string; date_from: string; date_to: string; team: string; state: string }, page: number, size = 20) => api.get<HistoryPage>('/api/agent/history', { params: { ...f, page, size } }).then((r) => r.data)
export const getExecDetail = (id: string) => api.get<ExecDetail>(`/api/agent/history/${encodeURIComponent(id)}`).then((r) => r.data)
