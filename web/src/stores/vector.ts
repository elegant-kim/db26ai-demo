import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { errorMessage } from '@/lib/api'
import { postSse } from '@/composables/useSse'
import {
  LOADING_STEPS, createTables, deleteDocument, deleteOnnx, dropTables, explainPlan, getEmbeddingConfig, getEmbeddingInfo, getIndexInfo,
  getOnnxModels, getVisualization, listDocuments, loadOnnxCloud, search, setEmbeddingConfig, tableData, tableDefinition, tableIndexes,
  testOnnx, uploadOnnxLocal,
  type Chunk, type DocItem, type EmbeddingInfo, type ExplainPlan, type IndexInfo, type OnnxModel, type OnnxTest, type PipelineStep,
  type SearchMode, type SideResult, type TableAction, type UploadDone, type VizData,
} from '@/lib/vector'
import type { Rows } from '@/lib/normalize'
import type { ChatMessage } from '@/lib/types/chat'
import { useSystemStore } from './system'

export interface VectorMessage extends ChatMessage {
  id: number
  timestamp: string
  mode?: SearchMode
  query?: string
  loadingText?: string
  answer?: string | null
  chunks?: Chunk[] | null
  sql?: string | null
  errorText?: string | null
  elapsedMs?: number | null
  vectorWeight?: number | null
  keywordWeight?: number | null
  hybridNote?: string | null
  keywordResults?: SideResult | null
  vectorResults?: SideResult | null
  embeddingInfo?: EmbeddingInfo | null
  indexInfo?: IndexInfo | null
  keywordCompare?: SideResult | null
  viz?: VizData | null
  extraBusy?: '' | 'embedding' | 'index' | 'keyword' | 'viz'
}
export interface VectorSession { id: number; label: string; source: string; model: string; timestamp: string; messages: VectorMessage[] }
export type Extra = 'embedding' | 'index' | 'keyword' | 'viz'

const now = () => new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
const PIPELINE: PipelineStep[] = [
  { step: 1, label: '문서 등록', status: 'pending' }, { step: 2, label: '텍스트 추출', status: 'pending' }, { step: 3, label: '청크 분할', status: 'pending' },
  { step: 4, label: '임베딩 & 저장', status: 'pending' }, { step: 5, label: '인덱싱 완료', status: 'pending' },
]

/**
 * Vector 탭 — 이 앱에서 상태가 가장 얽힌 곳(설계서 R2). 화면은 스토어만 보고, 스토어는 네 덩어리다:
 * 임베딩 설정(소스·모델·ONNX·인덱스) → 문서/업로드(SSE 파이프라인) → 검색(세션·메시지) → Vector Store 점검.
 * 임베딩 소스를 바꾸면 검색 스레드를 세션으로 저장하고 비운다(레거시 계승) — 차원이 달라진 결과를 섞지 않기 위해.
 */
export const useVectorStore = defineStore('vector', () => {
  const system = useSystemStore()
  let seq = 0

  // ── 임베딩 설정 ──
  const source = ref<'database' | 'external'>('database')
  const model = ref('')
  const apiUrl = ref('')
  const apiKeySet = ref(false)
  const onnxModels = ref<OnnxModel[]>([])
  const indexInfo = ref<IndexInfo | null>(null)
  const configLoaded = ref(false)
  const configError = ref<string | null>(null)
  let configInflight: Promise<void> | null = null

  function loadConfig(force = false): Promise<void> {
    if (configLoaded.value && !force) return Promise.resolve()
    if (configInflight) return configInflight
    configInflight = (async () => {
      try {
        const [c, m, ii] = await Promise.all([getEmbeddingConfig(), getOnnxModels().catch(() => [] as OnnxModel[]), getIndexInfo().catch(() => null)])
        source.value = c.source; model.value = c.model; apiUrl.value = c.external_api_url ?? ''; apiKeySet.value = !!c.external_api_key_set
        onnxModels.value = m; indexInfo.value = ii; configLoaded.value = true; configError.value = null
      } catch (e) { configError.value = errorMessage(e) } finally { configInflight = null }
    })()
    return configInflight
  }
  /** 인덱스가 다른 모델(차원)로 만들어져 있으면 업로드 시 ORA-51932 — 화면에 경고(개발노하우 3.2, 열린 과제 1) */
  const dimensionWarning = computed(() => {
    const ii = indexInfo.value
    if (!ii || !(Number(ii.embedded_chunks) > 0) || !ii.embedding_model || !model.value) return null
    if (ii.embedding_model === model.value && (source.value === 'database') === (ii.embedding_source === 'database')) return null
    return `저장된 임베딩 ${ii.embedded_chunks}건은 ${ii.embedding_model}(${ii.vector_dimensions}차원)로 만들어졌는데 현재 설정은 ${source.value === 'database' ? 'ONNX' : 'API'} · ${model.value} 입니다. ` +
      '차원이 다르면 업로드가 ORA-51932 로 실패하고 검색도 어긋납니다 — Vector Store 를 초기화하고 문서를 다시 올리세요.'
  })

  async function applySource(next: 'database' | 'external') {
    const r = await setEmbeddingConfig({ source: next, reset_model: true })
    if (!r.success) throw new Error(r.error || '설정 변경 실패')
    saveSession(); messages.value = []; activeSession.value = -1
    source.value = r.source; model.value = r.model
    system.toast(r.message || '임베딩 소스 변경', 'success')
    await Promise.all([loadConfig(true), loadDocs()])
  }
  async function applyModel(name: string) {
    const r = await setEmbeddingConfig({ model: name })
    if (!r.success) { system.toast(r.error || '모델 변경 실패', 'error'); return }
    model.value = r.model; system.toast(r.message || `모델 → ${name}`, 'success')
    await loadConfig(true)
  }

  // ── 문서 · 업로드 ──
  const docs = ref<DocItem[]>([])
  const docsLoaded = ref(false)
  async function loadDocs() { try { docs.value = await listDocuments(); docsLoaded.value = true } catch (e) { configError.value = errorMessage(e) } }
  async function removeDoc(id: number) {
    try { const r = await deleteDocument(id); if (r.success) { system.toast('문서를 삭제했습니다.', 'success'); await Promise.all([loadDocs(), loadConfig(true)]) } else system.toast(r.error || '삭제 실패', 'error') }
    catch (e) { system.toast(errorMessage(e), 'error') }
  }

  const uploading = ref(false)
  const pipeline = ref<PipelineStep[]>([])
  const progress = ref<{ current: number; total: number; percent: number } | null>(null)
  const uploadResult = ref<UploadDone | null>(null)
  const uploadError = ref<string | null>(null)
  const uploadElapsedSec = ref(0)
  const currentStep = computed(() => {
    const running = pipeline.value.find((p) => p.status === 'running')
    if (running) return running.step
    return pipeline.value.filter((p) => p.status === 'done').length + 1
  })
  const ringPercent = computed(() => {
    if (!pipeline.value.length) return 0
    const done = pipeline.value.filter((p) => p.status === 'done').length
    const running = pipeline.value.find((p) => p.status === 'running')
    const extra = running ? (running.step === 4 && progress.value ? (progress.value.percent || 0) / 100 : 0.5) : 0
    return Math.round(((done + extra) / pipeline.value.length) * 100)
  })
  async function upload(file: File) {
    if (!/\.pdf$/i.test(file.name)) { uploadError.value = 'PDF 파일만 업로드할 수 있습니다.'; return }
    if (file.size > 10 * 1024 * 1024) { uploadError.value = '파일 크기가 10MB 를 초과합니다.'; return }
    uploading.value = true; uploadError.value = null; uploadResult.value = null; progress.value = null; uploadElapsedSec.value = 0
    pipeline.value = PIPELINE.map((p) => ({ ...p }))
    const t0 = Date.now()
    const timer = window.setInterval(() => { uploadElapsedSec.value = Math.round((Date.now() - t0) / 1000) }, 1000)
    const form = new FormData(); form.append('file', file)
    try {
      await postSse('/api/vector/upload', form, (type, data) => {
        if (type === 'step') {
          const s = pipeline.value.find((p) => p.step === data.step)
          if (s) { s.status = data.status; if (data.detail) s.detail = data.detail; if (data.duration_ms) s.duration_ms = data.duration_ms }
        } else if (type === 'progress') progress.value = data
        else if (type === 'done') { pipeline.value.forEach((p) => { p.status = 'done' }); uploadResult.value = data; system.toast(`${data.filename}: ${data.chunks_count}개 청크 처리 완료 (${(data.total_ms / 1000).toFixed(1)}초)`, data.warning ? 'warn' : 'success') }
        else if (type === 'error') uploadError.value = data.message || '처리 실패'
      })
    } catch (e) { uploadError.value = errorMessage(e) }
    finally { window.clearInterval(timer); uploading.value = false; await Promise.all([loadDocs(), loadConfig(true)]) }
  }

  // ── Vector Store 점검 ──
  const tableAction = ref<TableAction | null>(null)
  const tableBusy = ref<'' | 'create' | 'drop'>('')
  async function manageTables(kind: 'create' | 'drop') {
    tableBusy.value = kind; tableAction.value = null
    try {
      const r = await (kind === 'create' ? createTables() : dropTables())
      tableAction.value = r
      if (r.success) system.toast(kind === 'drop' ? '테이블을 삭제했습니다.' : (r.created?.length ? `테이블 생성: ${r.created.join(', ')}` : '기존 테이블에 연결했습니다.'), 'success')
      else system.toast(r.error || '실패', 'error')
      await Promise.all([loadDocs(), loadConfig(true)])
    } catch (e) { tableAction.value = { success: false, error: errorMessage(e) } } finally { tableBusy.value = '' }
  }
  /** 임베딩 소스 전환 뒤의 초기화 = drop + create (레거시 흐름) */
  async function resetStore() { await manageTables('drop'); await manageTables('create'); saveSession(); messages.value = []; activeSession.value = -1 }

  const inspectTarget = ref<'DOC_CHUNKS' | 'DOCUMENTS'>('DOC_CHUNKS')
  const inspect = ref<Record<'def' | 'data' | 'idx', Rows | null>>({ def: null, data: null, idx: null })
  const inspectBusy = ref<'' | 'def' | 'data' | 'idx'>('')
  async function runInspect(kind: 'def' | 'data' | 'idx') {
    inspectBusy.value = kind
    try { inspect.value[kind] = await (kind === 'def' ? tableDefinition(inspectTarget.value) : kind === 'data' ? tableData(inspectTarget.value, 50) : tableIndexes(inspectTarget.value)) }
    catch (e) { inspect.value[kind] = { columns: [], rows: [], error: errorMessage(e) } } finally { inspectBusy.value = '' }
  }
  const plan = ref<ExplainPlan | null>(null)
  const planBusy = ref(false)
  async function loadPlan() { planBusy.value = true; try { plan.value = await explainPlan() } catch (e) { plan.value = { success: false, error: errorMessage(e) } } finally { planBusy.value = false } }

  // ── 검색 (RAG) ──
  const mode = ref<SearchMode>('vector')
  const topK = ref(5)
  const provider = ref('')
  const input = ref('')
  const searching = ref(false)
  const messages = ref<VectorMessage[]>([])
  const sessions = ref<VectorSession[]>([])
  const activeSession = ref(-1)
  const visibleMessages = computed(() => (activeSession.value === -1 ? messages.value : sessions.value[activeSession.value]?.messages ?? []))
  const sourceLabel = computed(() => (source.value === 'database' ? 'ONNX' : 'API'))

  function push(m: Omit<VectorMessage, 'id' | 'timestamp'>): VectorMessage {
    messages.value.push({ id: ++seq, timestamp: now(), ...m })
    return messages.value[messages.value.length - 1]
  }
  async function send(text: string) {
    const q = text.trim()
    if (!q || searching.value) return
    if (activeSession.value !== -1) activeSession.value = -1
    const m = mode.value
    push({ role: 'user', content: q })
    input.value = ''
    const msg = push({ role: 'assistant', content: '', mode: m, query: q, loading: true, loadingText: LOADING_STEPS[0], extraBusy: '' })
    searching.value = true
    let i = 0
    const timer = window.setInterval(() => { i = (i + 1) % LOADING_STEPS.length; msg.loadingText = LOADING_STEPS[i] }, 1500)
    try {
      const r = await search(q, m, topK.value, provider.value)
      if (!r.success) { msg.errorText = r.error || '검색에 실패했습니다.' }
      else if (m === 'compare') { msg.keywordResults = r.keyword_results ?? null; msg.vectorResults = r.vector_results ?? null; msg.elapsedMs = r.elapsed_ms ?? null }
      else {
        msg.answer = r.answer ?? null; msg.chunks = r.chunks ?? []; msg.sql = r.sql_executed ?? null; msg.elapsedMs = r.elapsed_ms ?? null
        if (m === 'hybrid') { msg.vectorWeight = r.vector_weight ?? null; msg.keywordWeight = r.keyword_weight ?? null; msg.hybridNote = r.hybrid_fallback ? (r.hybrid_note || '') : null }
      }
    } catch (e) { msg.errorText = errorMessage(e) }
    finally { window.clearInterval(timer); msg.loading = false; searching.value = false }
  }
  async function toggleExtra(msg: VectorMessage, kind: Extra) {
    if (msg.extraBusy) return
    const key = ({ embedding: 'embeddingInfo', index: 'indexInfo', keyword: 'keywordCompare', viz: 'viz' } as const)[kind]
    if (msg[key]) { (msg as any)[key] = null; return }
    msg.extraBusy = kind
    try {
      if (kind === 'embedding') msg.embeddingInfo = await getEmbeddingInfo(msg.query ?? '')
      else if (kind === 'index') msg.indexInfo = await getIndexInfo()
      else if (kind === 'keyword') { const r = await search(msg.query ?? '', 'keyword', topK.value, ''); msg.keywordCompare = r.success ? { chunks: r.chunks ?? [], match_count: r.match_count ?? 0, sql_executed: r.sql_executed ?? '', elapsed_ms: r.elapsed_ms ?? 0 } : null; if (!r.success) system.toast(r.error || '키워드 검색 실패', 'error') }
      else { const ids = (msg.chunks ?? []).map((c) => c.chunk_id).filter((x): x is number => typeof x === 'number'); const r = await getVisualization(msg.query ?? '', ids); if (r.success) msg.viz = r; else system.toast(r.error || '시각화 실패', 'error') }
    } catch (e) { system.toast(errorMessage(e), 'error') } finally { msg.extraBusy = '' }
  }
  function saveSession() {
    if (!messages.value.length) return
    sessions.value.push({ id: ++seq, label: `${sourceLabel.value}/${model.value}`, source: source.value, model: model.value, timestamp: now(), messages: [...messages.value] })
  }
  function switchSession(i: number) { activeSession.value = i >= 0 && i < sessions.value.length ? i : -1 }
  function removeSession(i: number) { sessions.value.splice(i, 1); if (activeSession.value >= sessions.value.length) activeSession.value = -1 }
  function clearCurrent() { messages.value = [] }

  // ── ONNX 모델 ──
  const onnxTest = ref<OnnxTest | null>(null)
  const onnxBusy = ref<'' | 'test' | 'delete' | 'upload' | 'cloud' | 'refresh'>('')
  const onnxLocalResult = ref<{ success: boolean; message?: string; error?: string; size_mb?: number; elapsed_ms?: number } | null>(null)
  const onnxCloudResult = ref<{ success: boolean; message?: string; error?: string; elapsed_ms?: number } | null>(null)
  async function refreshOnnx() { onnxBusy.value = 'refresh'; try { onnxModels.value = await getOnnxModels(); system.toast(`ONNX 모델 ${onnxModels.value.length}개`, 'success') } catch (e) { system.toast(errorMessage(e), 'error') } finally { onnxBusy.value = '' } }
  async function testModel(name: string) { onnxBusy.value = 'test'; onnxTest.value = null; try { onnxTest.value = await testOnnx(name, '한국어 임베딩 모델 테스트 문장입니다.') } catch (e) { onnxTest.value = { success: false, model_name: name, error: errorMessage(e) } } finally { onnxBusy.value = '' } }
  async function deleteModel(name: string) { onnxBusy.value = 'delete'; try { const r = await deleteOnnx(name); if (r.success) { system.toast(r.message || '삭제했습니다.', 'success'); await loadConfig(true) } else system.toast(r.error || '삭제 실패', 'error') } catch (e) { system.toast(errorMessage(e), 'error') } finally { onnxBusy.value = '' } }
  async function uploadLocal(file: File, name: string) {
    onnxBusy.value = 'upload'; onnxLocalResult.value = null
    const modelName = name.trim() || file.name.replace(/\.onnx$/i, '').replace(/[^a-zA-Z0-9_]/g, '_').toUpperCase()
    try { const r = await uploadOnnxLocal(file, modelName); onnxLocalResult.value = r; if (r.success) { system.toast(r.message || '적재 완료', 'success'); await loadConfig(true) } }
    catch (e: any) { onnxLocalResult.value = { success: false, error: e?.code === 'ECONNABORTED' ? '적재 시간이 초과되었습니다 (10분).' : errorMessage(e) } } finally { onnxBusy.value = '' }
  }
  async function loadCloud(uri: string, file: string, name: string) {
    onnxBusy.value = 'cloud'; onnxCloudResult.value = null
    try { const r = await loadOnnxCloud(uri.trim(), file.trim(), name.trim()); onnxCloudResult.value = r; if (r.success) { system.toast(r.message || '적재 완료', 'success'); await loadConfig(true) } }
    catch (e: any) { onnxCloudResult.value = { success: false, error: e?.code === 'ECONNABORTED' ? '적재 시간이 초과되었습니다 (10분).' : errorMessage(e) } } finally { onnxBusy.value = '' }
  }

  return {
    source, model, apiUrl, apiKeySet, onnxModels, indexInfo, configLoaded, configError, loadConfig, dimensionWarning, applySource, applyModel,
    docs, docsLoaded, loadDocs, removeDoc, uploading, pipeline, progress, uploadResult, uploadError, uploadElapsedSec, currentStep, ringPercent, upload,
    tableAction, tableBusy, manageTables, resetStore, inspectTarget, inspect, inspectBusy, runInspect, plan, planBusy, loadPlan,
    mode, topK, provider, input, searching, messages, sessions, activeSession, visibleMessages, sourceLabel, send, toggleExtra, saveSession, switchSession, removeSession, clearCurrent,
    onnxTest, onnxBusy, onnxLocalResult, onnxCloudResult, refreshOnnx, testModel, deleteModel, uploadLocal, loadCloud,
  }
})
