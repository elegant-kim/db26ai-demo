import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { errorMessage } from '@/lib/api'
import {
  compareDuality, createDualityViews, dropDualityViews, fetchDualityDoc, getDualityViews, listDualityDocs,
  runEtagSimulation, updateDualityDoc,
  type ActionResult, type CompareResult, type DocResult, type DocSummary, type DualityView, type UpdateResult,
} from '@/lib/duality'
import type { Step } from '@/lib/types/steps'

type Busy = '' | 'views' | 'create' | 'drop' | 'compare' | 'docs' | 'doc' | 'update' | 'etag'
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** Duality 탭 상태 — 뷰 목록은 한 번만, 결과는 서브탭을 오가도 남는다. */
export const useDualityStore = defineStore('duality', () => {
  const views = ref<DualityView[]>([])
  const viewsLoaded = ref(false)
  const manageResult = ref<ActionResult | null>(null)

  const compareView = ref('CUSTOMERS_DV')
  const compareLimit = ref(5)
  const compareResult = ref<CompareResult | null>(null)

  const crudView = ref('CUSTOMERS_DV')
  const docId = ref('')
  const docList = ref<DocSummary[]>([])
  const docListSql = ref<string | undefined>()
  const doc = ref<DocResult | null>(null)
  const docText = ref('')
  const updateResult = ref<UpdateResult | null>(null)

  const etagSteps = ref<Step[] | null>(null)
  const etagRevealed = ref(0)
  const etagError = ref<string | null>(null)

  const busy = ref<Busy>('')
  const lastError = ref<string | null>(null)
  const hasViews = computed(() => views.value.length > 0)
  const viewOptions = computed(() => views.value.map((v) => ({ value: v.name, label: v.name, sub: v.status })))

  let inflight: Promise<void> | null = null
  function loadViews(force = false): Promise<void> {
    if (viewsLoaded.value && !force) return Promise.resolve()
    if (inflight) return inflight
    inflight = getDualityViews()
      .then((r) => {
        views.value = r.views ?? []
        viewsLoaded.value = true
        if (views.value.length && !views.value.some((v) => v.name === compareView.value)) compareView.value = views.value[0].name
        if (views.value.length && !views.value.some((v) => v.name === crudView.value)) crudView.value = views.value[0].name
      })
      .catch((e) => { lastError.value = errorMessage(e) })
      .finally(() => { inflight = null })
    return inflight
  }

  async function act(kind: 'create' | 'drop' | 'views') {
    busy.value = kind
    try {
      if (kind === 'views') {
        const r = await getDualityViews()
        manageResult.value = { ...r, message: `Duality View ${(r.views ?? []).length}개` }
        views.value = r.views ?? []
        viewsLoaded.value = true
      } else {
        manageResult.value = await (kind === 'create' ? createDualityViews() : dropDualityViews())
        compareResult.value = null; docList.value = []; doc.value = null; etagSteps.value = null
        await loadViews(true)
      }
    } catch (e) { manageResult.value = { success: false, error: errorMessage(e) } } finally { busy.value = '' }
  }

  async function compare() {
    busy.value = 'compare'
    try { compareResult.value = await compareDuality(compareView.value, compareLimit.value); lastError.value = null }
    catch (e) { lastError.value = errorMessage(e) } finally { busy.value = '' }
  }

  async function listDocs() {
    busy.value = 'docs'
    try { const r = await listDualityDocs(crudView.value); docList.value = r.docs ?? []; docListSql.value = r.sql_executed; lastError.value = r.error ?? null }
    catch (e) { lastError.value = errorMessage(e) } finally { busy.value = '' }
  }
  async function fetchDoc(id = docId.value) {
    docId.value = id
    busy.value = 'doc'; updateResult.value = null
    try {
      const r = await fetchDualityDoc(crudView.value, id)
      doc.value = r
      docText.value = r.document_text ?? (r.document ? JSON.stringify(r.document, null, 2) : '')
      lastError.value = r.error ?? null
    } catch (e) { lastError.value = errorMessage(e) } finally { busy.value = '' }
  }
  async function saveDoc() {
    let parsed: Record<string, any>
    try { parsed = JSON.parse(docText.value) } catch (e) { updateResult.value = { success: false, error: 'JSON 파싱 오류: ' + (e as Error).message }; return }
    busy.value = 'update'
    try {
      const r = await updateDualityDoc(crudView.value, parsed)
      updateResult.value = r
      if (r.success && doc.value) {
        doc.value = { ...doc.value, etag: r.new_etag ?? doc.value.etag }
        if (r.new_etag && parsed._metadata) { parsed._metadata.etag = r.new_etag; docText.value = JSON.stringify(parsed, null, 2) }
      }
    } catch (e) { updateResult.value = { success: false, error: errorMessage(e) } } finally { busy.value = '' }
  }

  let token = 0
  async function runEtag() {
    const my = ++token
    busy.value = 'etag'; etagError.value = null; etagSteps.value = null; etagRevealed.value = 0
    try {
      const r = await runEtagSimulation()
      if (my !== token) return
      etagSteps.value = r.steps ?? []
      if (r.error) etagError.value = r.error
      for (let i = 0; i < etagSteps.value.length; i++) {
        await sleep(i === 0 ? 300 : 1200)
        if (my !== token) return
        etagRevealed.value = i + 1
      }
    } catch (e) { if (my === token) etagError.value = errorMessage(e) }
    finally { if (my === token) busy.value = '' }
  }
  function revealEtag() { if (etagSteps.value) etagRevealed.value = etagSteps.value.length }

  return {
    views, viewsLoaded, hasViews, viewOptions, manageResult,
    compareView, compareLimit, compareResult,
    crudView, docId, docList, docListSql, doc, docText, updateResult,
    etagSteps, etagRevealed, etagError,
    busy, lastError, loadViews, act, compare, listDocs, fetchDoc, saveDoc, runEtag, revealEtag,
  }
})
