import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { errorMessage } from '@/lib/api'
import { compareGraph, createGraph, dropGraph, getGraphQueries, runPattern, type ActionResult, type CompareResult, type QueryDef } from '@/lib/graph'
import type { Rows } from '@/lib/normalize'

/** Property Graph 탭 상태 — 질의 목록·선택·결과 캐시. 탭을 오가도 결과가 남는다(레거시 v-show 경험 보존). */
export const useGraphStore = defineStore('graph', () => {
  const compareQueries = ref<QueryDef[]>([])
  const patternQueries = ref<QueryDef[]>([])
  const queriesLoaded = ref(false)

  const compareIndex = ref(0)
  const patternIndex = ref(0)
  const compareResults = ref<Record<number, CompareResult>>({})
  const patternResults = ref<Record<number, Rows>>({})
  const manageResult = ref<ActionResult | null>(null)

  const busy = ref<'' | 'queries' | 'create' | 'drop' | 'compare' | 'pattern'>('')
  const lastError = ref<string | null>(null)

  let inflight: Promise<void> | null = null
  /** 질의 목록은 한 번만 — 서브탭 두 개가 같은 틱에 mount 되면 요청이 겹치므로 in-flight 를 공유한다 */
  function loadQueries(): Promise<void> {
    if (queriesLoaded.value) return Promise.resolve()
    if (inflight) return inflight
    busy.value = 'queries'
    inflight = getGraphQueries()
      .then((q) => { compareQueries.value = q.compare; patternQueries.value = q.pattern; queriesLoaded.value = true; lastError.value = null })
      .catch((e) => { lastError.value = errorMessage(e) })
      .finally(() => { busy.value = ''; inflight = null })
    return inflight
  }

  async function create() {
    busy.value = 'create'
    try { manageResult.value = await createGraph(); compareResults.value = {}; patternResults.value = {} }
    catch (e) { manageResult.value = { success: false, error: errorMessage(e) } } finally { busy.value = '' }
  }
  async function drop() {
    busy.value = 'drop'
    try { manageResult.value = await dropGraph(); compareResults.value = {}; patternResults.value = {} }
    catch (e) { manageResult.value = { success: false, error: errorMessage(e) } } finally { busy.value = '' }
  }
  async function compare(index = compareIndex.value) {
    busy.value = 'compare'
    try { compareResults.value = { ...compareResults.value, [index]: await compareGraph(index) }; lastError.value = null }
    catch (e) { lastError.value = errorMessage(e) } finally { busy.value = '' }
  }
  async function pattern(index = patternIndex.value) {
    busy.value = 'pattern'
    try { patternResults.value = { ...patternResults.value, [index]: await runPattern(index) }; lastError.value = null }
    catch (e) { lastError.value = errorMessage(e) } finally { busy.value = '' }
  }

  const currentCompare = computed(() => compareResults.value[compareIndex.value] ?? null)
  const currentPattern = computed(() => patternResults.value[patternIndex.value] ?? null)

  return {
    compareQueries, patternQueries, queriesLoaded, compareIndex, patternIndex,
    compareResults, patternResults, manageResult, busy, lastError,
    loadQueries, create, drop, compare, pattern, currentCompare, currentPattern,
  }
})
