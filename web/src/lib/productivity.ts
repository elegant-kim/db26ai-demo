import { api } from './api'

import type { Step } from './types/steps'
export type { Step }
export interface StepsResult { success: boolean; steps: Step[]; error?: string }

export const runLockFree = () => api.post<StepsResult>('/api/productivity/lockfree').then((r) => r.data)
export const runPriorityTx = () => api.post<StepsResult>('/api/productivity/priority-tx').then((r) => r.data)
