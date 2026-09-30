import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { errorMessage } from '@/lib/api'
import { deleteFeedback } from '@/lib/nl2sql'
import { listFeedback, parseFewshot, purgeFeedback, registerFewshot, validateFewshot, type FeedbackRow, type FewshotRow, type RegisterSummary, type RowResult } from '@/lib/fewshot'
import { useSystemStore } from './system'

/** 「피드백 · Few-shot」 서브탭 상태 — 파일 미리보기·검증·SSE 등록 진행·등록된 피드백 목록. */
export const useFewshotStore = defineStore('fewshot', () => {
  const system = useSystemStore()
  const filename = ref('')
  const headers = ref<string[]>([])
  const rows = ref<FewshotRow[]>([])
  const parsing = ref(false)
  const validating = ref(false)
  const validated = ref(false)
  const registering = ref(false)
  const results = ref<Record<number, RowResult>>({})
  const summary = ref<RegisterSummary | null>(null)
  const startedAt = ref(0)
  const elapsedSec = ref(0)
  const error = ref<string | null>(null)
  let timer: number | null = null
  let abort: AbortController | null = null

  const validRows = computed(() => rows.value.filter((r) => r.valid === true))
  const failedRows = computed(() => rows.value.filter((r) => results.value[r.row]?.ok === false))
  const doneCount = computed(() => Object.keys(results.value).length)

  async function load(file: File) {
    parsing.value = true; error.value = null; results.value = {}; summary.value = null; validated.value = false
    try {
      const r = await parseFewshot(file)
      if (!r.success) throw new Error(r.error || '파싱 실패')
      filename.value = r.filename; headers.value = r.headers; rows.value = r.rows
      if (!r.rows.length) system.toast('행이 없습니다 — 헤더는 question,sql,note (또는 질문,SQL,설명)', 'warn')
    } catch (e) { error.value = errorMessage(e) } finally { parsing.value = false }
  }
  async function validate() {
    if (!rows.value.length) return
    validating.value = true; error.value = null
    try {
      const r = await validateFewshot(rows.value)
      if (!r.success) throw new Error(r.error || '검증 실패')
      rows.value = r.rows; validated.value = true
      system.toast(`검증 완료 — 통과 ${r.valid} · 실패 ${r.invalid}`, r.invalid ? 'warn' : 'success')
    } catch (e) { error.value = errorMessage(e) } finally { validating.value = false }
  }
  async function register(profile: string, target?: FewshotRow[]) {
    const list = target ?? validRows.value
    if (!list.length || registering.value) return
    registering.value = true; error.value = null; summary.value = null
    for (const r of list) delete results.value[r.row]
    startedAt.value = Date.now(); elapsedSec.value = 0
    timer = window.setInterval(() => { elapsedSec.value = Math.round((Date.now() - startedAt.value) / 1000) }, 1000)
    abort = new AbortController()
    try {
      await registerFewshot(profile, list, (type, data) => {
        if (type === 'row') results.value[data.row] = data as RowResult
        else if (type === 'done') summary.value = data as RegisterSummary
        else if (type === 'error') error.value = data?.message || '등록 중 오류'
      }, abort.signal)
      if (summary.value) system.toast(`등록 ${summary.value.ok}건 · 실패 ${summary.value.failed}건`, summary.value.failed ? 'warn' : 'success')
      await loadFeedback(profile)
    } catch (e) { error.value = errorMessage(e) }
    finally { registering.value = false; if (timer) { window.clearInterval(timer); timer = null }; abort = null }
  }
  function cancel() { abort?.abort() }
  /** 파일 없이 한 건 직접 입력 — 미리보기 표에 행으로 붙는다(검증·등록은 같은 흐름) */
  function addManual(question: string, sql: string, note = '') {
    const q = question.trim(), sq = sql.trim().replace(/;\s*$/, '')
    if (!q || !sq) { system.toast('질문과 정답 SQL 을 둘 다 적어 주세요', 'warn'); return false }
    const row = (rows.value.reduce((m, r) => Math.max(m, r.row), 0) || 0) + 1
    rows.value.push({ row, question: q, sql: sq, note: note.trim(), error: null, valid: null })
    if (!filename.value) filename.value = '(직접 입력)'
    validated.value = false; summary.value = null
    return true
  }
  function clear() { filename.value = ''; headers.value = []; rows.value = []; results.value = {}; summary.value = null; validated.value = false; error.value = null }

  // ── 등록된 피드백 목록 ──
  const feedback = ref<FeedbackRow[]>([])
  const feedbackLoading = ref(false)
  const feedbackFor = ref('')
  async function loadFeedback(profile: string) {
    if (!profile) return
    feedbackLoading.value = true
    try { const r = await listFeedback(profile); feedback.value = r.feedback ?? []; feedbackFor.value = profile }
    catch (e) { error.value = errorMessage(e) } finally { feedbackLoading.value = false }
  }
  async function remove(id: number, profile: string) {
    try { const r = await deleteFeedback(id); if (!r.success) throw new Error(r.error); system.toast('삭제했습니다', 'success'); await loadFeedback(profile) }
    catch (e) { system.toast(errorMessage(e), 'error') }
  }
  async function purge(profile: string) {
    try { const r = await purgeFeedback(profile); if (!r.success) throw new Error(r.error)
      system.toast(`${profile} 피드백 전체 삭제 — 인덱스 ${r.removed_oracle}건 · 앱 ${r.removed_app}건`, 'success'); await loadFeedback(profile); return true }
    catch (e) { system.toast(errorMessage(e), 'error'); return false }
  }

  return { filename, headers, rows, parsing, validating, validated, registering, results, summary, elapsedSec, error, validRows, failedRows, doneCount,
    load, validate, register, cancel, clear, addManual, feedback, feedbackLoading, feedbackFor, loadFeedback, remove, purge }
})
