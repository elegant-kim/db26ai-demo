export interface Health {
  status: 'ok' | 'error' | string
  database_connected: boolean
  schema: string | null
  db_version: string | null
  profile_count: number
  doc_count: number
  chunk_count: number
  embedded_count: number
  onnx_models: { model_name: string; mining_function?: string; algorithm?: string; creation_date?: string }[]
  vector_index_status: { name: string; status: string }[] | null
  embedding_source: 'database' | 'external' | string
  embedding_model: string
  llm_provider: string
}

export interface LlmProvider {
  id?: string
  provider?: string
  name?: string
  label?: string
  model?: string
  available?: boolean
  [k: string]: unknown
}

export interface EmbeddingConfig {
  success?: boolean
  source: 'database' | 'external' | string
  model: string
  external_api_url?: string
  external_api_key_set?: boolean
}
