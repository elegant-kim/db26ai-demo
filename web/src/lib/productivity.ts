import { api } from './api'

/** 시뮬레이션 한 단계 — 백엔드 app/productivity.py 의 steps[] 원소 그대로 */
export interface Step { description: string; sql?: string | null; success: boolean }
export interface StepsResult { success: boolean; steps: Step[]; error?: string }

export const runLockFree = () => api.post<StepsResult>('/api/productivity/lockfree').then((r) => r.data)
export const runPriorityTx = () => api.post<StepsResult>('/api/productivity/priority-tx').then((r) => r.data)
