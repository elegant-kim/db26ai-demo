import { defineStore } from 'pinia'
import { ref } from 'vue'
import { errorMessage } from '@/lib/api'
import { EMPTY_FILTER, getHistory, getHistoryDetail, getHistorySummary, type LogDetail, type LogFilter, type LogRow, type LogSummary } from '@/lib/aiLog'

/** 「이력」 서브탭 상태 — 필터·표·요약·상세 모달. 조회는 「조회」 버튼(자동 재조회 없음 — 필터를 여러 개 고칠 때 요청이 튀지 않게). */
export const useAiLogStore = defineStore('aiLog', () => {
  const filter = ref<LogFilter>({ ...EMPTY_FILTER })
  const rows = ref<LogRow[]>([])
  const total = ref(0)
  const page = ref(1)
  const size = ref(20)
  const sql = ref('')
  const loading = ref(false)
  const error = ref<string | null>(null)
  const summary = ref<LogSummary | null>(null)
  const summaryLoading = ref(false)
  const detail = ref<LogDetail | null>(null)
  const detailLoading = ref(false)
  const loadedOnce = ref(false)

  async function load(p = page.value) {
    loading.value = true; error.value = null
    try {
      const r = await getHistory(filter.value, p, size.value)
      if (!r.success) throw new Error(r.error || '이력 조회 실패')
      rows.value = r.rows; total.value = r.total; page.value = r.page; sql.value = r.sql; loadedOnce.value = true
    } catch (e) { error.value = errorMessage(e) } finally { loading.value = false }
  }
  async function loadSummary(profile = '') {
    summaryLoading.value = true
    try { summary.value = await getHistorySummary(profile) }
    catch (e) { error.value = errorMessage(e) } finally { summaryLoading.value = false }
  }
  /** 「조회」 — 1쪽부터, 요약도 같이 */
  async function search() { await Promise.all([load(1), loadSummary()]) }
  function reset() { filter.value = { ...EMPTY_FILTER } }
  async function open(id: number) {
    detailLoading.value = true; detail.value = null
    try {
      const r = await getHistoryDetail(id)
      if (!r.success) throw new Error(r.error || '상세 조회 실패')
      detail.value = r
    } catch (e) { error.value = errorMessage(e) } finally { detailLoading.value = false }
  }
  function close() { detail.value = null }

  return { filter, rows, total, page, size, sql, loading, error, summary, summaryLoading, detail, detailLoading, loadedOnce, load, loadSummary, search, reset, open, close }
})
