import { api } from './api'
import type { EmbeddingConfig, Health, LlmProvider } from './types/system'

export const getHealth = () => api.get<Health>('/api/health').then((r) => r.data)
export const getProviders = () => api.get<{ providers?: LlmProvider[] } | LlmProvider[]>('/api/llm/providers')
  .then((r) => (Array.isArray(r.data) ? r.data : (r.data.providers ?? [])))
export const getEmbeddingConfig = () => api.get<EmbeddingConfig>('/api/vector/embedding-config').then((r) => r.data)
