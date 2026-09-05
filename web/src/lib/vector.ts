import { api } from './api'
import { fromColumnsData, type Rows } from './normalize'

export type SearchMode = 'vector' | 'keyword' | 'hybrid' | 'compare'
/** 검색 모드 4종 — 정본은 app/routers/vector.py 의 분기. 하이브리드가 26ai 의 차별점 */
export const SEARCH_MODES: { value: SearchMode; label: string; hint: string }[] = [
  { value: 'vector', label: '의미 검색', hint: 'VECTOR_DISTANCE — 단어가 달라도 뜻이 비슷하면 찾는다' },
  { value: 'keyword', label: '키워드 검색', hint: 'Oracle Text CONTAINS / LIKE — 단어가 있어야 찾는다' },
  { value: 'hybrid', label: '하이브리드 (26ai)', hint: 'CONTAINS + VECTOR_DISTANCE 를 한 SQL 에서 결합' },
  { value: 'compare', label: '비교', hint: '키워드 vs 의미 검색을 나란히' },
]
export const LOADING_STEPS = ['질문 임베딩 중…', '벡터 유사도 검색 중…', '참조 문서 수집 중…', 'RAG 답변 생성 중…']
export const EXAMPLE_QUESTIONS = [
  '자동차 사고 시 보험금 청구 절차는 어떻게 되나요?', '음주운전 사고도 보험 보상이 되나요?', '피보험자에 보상하지 않는 경우는 어떤 경우인가?',
  '카드 분실 시 부정사용 책임은 누구에게 있나요?', '카드 연회비 반환 조건은 무엇인가요?', '결제대금 이의제기 절차와 기한을 알려주세요',
  '외래어 사용 기준은 무엇인가요?', '행정기관의 공문서 작성 원칙을 알려주세요', '쉬운 공공언어로 바꿔야 하는 어려운 용어 사례는?',
  '인덱스를 효율적으로 사용하려면 SQL 을 어떻게 작성해야 하나요?',
]

export interface Chunk { chunk_id?: number; chunk_text: string; source_file: string; page_num: number; similarity: number | null; keyword_score?: number; hybrid_score?: number }
export interface SideResult { chunks: Chunk[]; match_count: number; sql_executed: string; elapsed_ms: number }
export interface SearchResponse {
  success: boolean; mode: SearchMode; error?: string
  answer?: string; chunks?: Chunk[]; match_count?: number; sql_executed?: string; elapsed_ms?: number
  vector_weight?: number; keyword_weight?: number; hybrid_fallback?: boolean; hybrid_note?: string
  keyword_results?: SideResult; vector_results?: SideResult
}
export interface EmbeddingInfo { success: boolean; input_text?: string; model?: string; source?: string; dimensions?: number; processing_ms?: number; vector_preview?: string; error?: string }
export interface IndexInfo {
  success: boolean; total_chunks?: number; embedded_chunks?: number; total_documents?: number; embedding_model?: string; embedding_source?: string
  vector_dimensions?: number | string; distance_metric?: string; index?: { index_name: string; index_type: string; status: string } | null; error?: string
}
export interface VizPoint { chunk_id: number; source_file: string; page_num: number; x: number; y: number; matched: boolean }
export interface VizData { success: boolean; points: VizPoint[]; query_point?: { x: number; y: number; label: string }; total_chunks?: number; error?: string }
export interface DocItem { doc_id: number; filename: string; upload_date: string; status: string; chunks_count: number; embed_dim?: number | null }
export interface TableAction { success: boolean; tables?: { table: string; status: string; message?: string }[]; created?: string[]; existing?: string[]; sql_executed?: string; error?: string }
export interface EmbeddingConfig { success: boolean; source: 'database' | 'external'; model: string; external_api_url?: string; external_api_key_set?: boolean; message?: string; error?: string }
export interface OnnxModel { model_name: string; mining_function: string; algorithm: string; creation_date: string }
export interface OnnxTest { success: boolean; model_name: string; sample_text?: string; sql_executed?: string; dimensions?: number; vector_preview?: string; processing_ms?: number; error?: string }
export interface ExplainPlan { success: boolean; target_sql?: string; explain_sql?: string; plan_text?: string; error?: string }
export interface UploadDone { doc_id?: number; filename: string; chunks_count: number; embedded_count?: number; not_embedded_count?: number; pages_count?: number; total_ms: number; warning?: string }
export interface PipelineStep { step: number; label: string; status: 'pending' | 'running' | 'done'; detail?: string; duration_ms?: number }

export const search = (query: string, mode: SearchMode, top_k: number, provider: string) =>
  api.post<SearchResponse>('/api/vector/search', { query, mode, top_k, provider: provider || '' }).then((r) => r.data)
export const getEmbeddingInfo = (text: string) => api.post<EmbeddingInfo>('/api/vector/embedding-info', { text }).then((r) => r.data)
export const getIndexInfo = () => api.get<IndexInfo>('/api/vector/index-info').then((r) => r.data)
export const getVisualization = (query: string, matched_chunk_ids: number[]) => api.post<VizData>('/api/vector/visualize', { query, matched_chunk_ids }).then((r) => r.data)
export const listDocuments = () => api.get<{ success: boolean; documents: DocItem[] }>('/api/vector/documents').then((r) => r.data.documents ?? [])
export const deleteDocument = (doc_id: number) => api.delete<{ success: boolean; error?: string }>(`/api/vector/documents/${doc_id}`).then((r) => r.data)
export const dropTables = () => api.post<TableAction>('/api/vector/drop-tables').then((r) => r.data)
export const createTables = () => api.post<TableAction>('/api/vector/create-tables').then((r) => r.data)
export const tableDefinition = (table_name: string) => api.post('/api/vector/table-definition', { table_name }).then((r) => fromColumnsData(r.data) as Rows)
export const tableData = (table_name: string, limit = 50) => api.post('/api/vector/table-data', { table_name, limit }).then((r) => fromColumnsData(r.data) as Rows)
export const tableIndexes = (table_name: string) => api.post('/api/vector/table-indexes', { table_name }).then((r) => fromColumnsData(r.data) as Rows)
export const explainPlan = () => api.post<ExplainPlan>('/api/vector/explain-plan').then((r) => r.data)
export const getEmbeddingConfig = () => api.get<EmbeddingConfig>('/api/vector/embedding-config').then((r) => r.data)
export const setEmbeddingConfig = (body: { source?: string; model?: string; reset_model?: boolean }) => api.post<EmbeddingConfig>('/api/vector/embedding-config', body).then((r) => r.data)
export const getOnnxModels = () => api.get<{ success: boolean; models: OnnxModel[] }>('/api/vector/onnx-models').then((r) => r.data.models ?? [])
export const testOnnx = (model_name: string, sample_text: string) => api.post<OnnxTest>('/api/vector/onnx-models/test', { model_name, sample_text }).then((r) => r.data)
export const deleteOnnx = (model_name: string) => api.delete<{ success: boolean; message?: string; error?: string }>(`/api/vector/onnx-models/${encodeURIComponent(model_name)}`).then((r) => r.data)
export const uploadOnnxLocal = (file: File, model_name: string) => {
  const form = new FormData(); form.append('file', file); form.append('model_name', model_name)
  return api.post<{ success: boolean; message?: string; error?: string; size_mb?: number; elapsed_ms?: number }>('/api/vector/onnx-models/upload', form, { timeout: 600_000 }).then((r) => r.data)
}
export const loadOnnxCloud = (location_uri: string, onnx_file_name: string, model_name: string) =>
  api.post<{ success: boolean; message?: string; error?: string; elapsed_ms?: number }>('/api/vector/onnx-models/load-cloud', { location_uri, onnx_file_name, model_name }, { timeout: 600_000 }).then((r) => r.data)

/** ONNX 적재 PL/SQL 참고 (레거시 화면의 상수) */
export const ONNX_LOAD_PLSQL = `DECLARE
  v_model VARCHAR2(200) := 'MODEL_NAME';
  v_file  VARCHAR2(200) := 'model_file.onnx';
  v_uri   VARCHAR2(500) := 'https://...PAR_URL.../o/';
BEGIN
  -- 기존 모델 삭제 (없으면 무시)
  BEGIN DBMS_DATA_MINING.DROP_MODEL(v_model);
  EXCEPTION WHEN OTHERS THEN NULL; END;

  -- Object Storage → DATA_PUMP_DIR
  DBMS_CLOUD.GET_OBJECT(
    credential_name => NULL,
    directory_name  => 'DATA_PUMP_DIR',
    object_uri      => v_uri || v_file
  );

  -- ONNX 모델 DB 적재
  DBMS_VECTOR.LOAD_ONNX_MODEL(
    directory  => 'DATA_PUMP_DIR',
    file_name  => v_file,
    model_name => v_model
  );
END;`
