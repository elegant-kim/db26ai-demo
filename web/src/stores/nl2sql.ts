import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { errorMessage } from '@/lib/api'
import { annotationSetFor } from '@/lib/annotations'
import {
  ACTION_BUTTONS, LOADING_TEXT, ask, applyAnnotations, executeSql, exampleQuestionsFor, explainPlan, getProfiles, getSchemaInfo,
  removeAnnotations, setProfile, type Action, type FollowAction, type Profile, type SchemaTable,
} from '@/lib/nl2sql'
import { fromColumnsData, type Rows } from '@/lib/normalize'
import type { ChatMessage } from '@/lib/types/chat'
import { useSystemStore } from './system'

export type ChartType = 'bar' | 'line' | 'pie'
export interface Nl2sqlMessage extends ChatMessage {
  id: number
  timestamp: string
  // 사용자
  isSql?: boolean
  prevPrompt?: string | null
  // 어시스턴트
  action?: Action | 'rawsql' | 'profile' | 'explainplan'
  prompt?: string
  profileName?: string
  loadingText?: string
  sql?: string | null
  table?: Rows | null
  textResult?: string | null
  errorText?: string | null
  elapsedMs?: number | null
  showChart?: boolean
  chartType?: ChartType
  explainPlan?: string | null
  cached?: Record<string, unknown>
  actionLoading?: boolean
  actionLoadingText?: string
  profileResult?: { profile_name: string; attributes?: any }
  sqlResult?: Rows | null
}

const now = () => new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })

/**
 * NL2SQL 탭 — 앱의 첫 화면. 프로필·실행 모드·대화 스레드·스키마 뷰어.
 * 레거시 app.js 의 sendQuestion/executeAction/processResult 를 그대로 옮기되, 결과는 Rows 로 정규화한다.
 */
export const useNl2sqlStore = defineStore('nl2sql', () => {
  const system = useSystemStore()
  const profiles = ref<Profile[]>([])
  const profile = ref('')
  const profilesLoaded = ref(false)
  const action = ref<Action>('showsql')
  const messages = ref<Nl2sqlMessage[]>([])
  const input = ref('')
  const sqlInput = ref('')
  const sending = ref(false)
  const sqlRunning = ref(false)
  const schema = ref<SchemaTable[] | null>(null)
  const schemaLoading = ref(false)
  const expanded = ref<Record<string, boolean>>({})
  const annoBusy = ref<'' | 'apply' | 'remove'>('')
  const lastError = ref<string | null>(null)
  let seq = 0

  const examples = computed(() => exampleQuestionsFor(profile.value))
  const profileOptions = computed(() => profiles.value.map((p) => ({ value: p.profile_name, label: p.profile_name })))
  const hasAnnotationSet = computed(() => annotationSetFor(profile.value) !== null)
  const asked = computed(() => messages.value.some((m) => m.role === 'user'))

  function push(m: Omit<Nl2sqlMessage, 'id' | 'timestamp'>): Nl2sqlMessage {
    const msg: Nl2sqlMessage = { id: ++seq, timestamp: now(), ...m }
    messages.value.push(msg)
    return messages.value[messages.value.length - 1]
  }

  let inflight: Promise<void> | null = null
  function init(): Promise<void> {
    if (profilesLoaded.value) return Promise.resolve()
    if (inflight) return inflight
    inflight = (async () => {
      try {
        profiles.value = await getProfiles()
        profilesLoaded.value = true
        if (!profiles.value.length) { lastError.value = 'DB 에 등록된 AI 프로필이 없습니다.'; return }
        if (!profile.value) {
          // 기본 프로필 우선순위. 2026-09-05: GROQ 프로필이 DB 자격증명 문제(ORA-20404 bearer://api.groq.com)로 실패해
          // GEMINI 를 앞에 둔다 — Groq credential 을 고치면 순서를 되돌려도 된다.
          const PREFER = ['GEMINI_SH_PROFILE', 'GROQ_SH_PROFILE']
          const def = PREFER.map((n) => profiles.value.find((p) => p.profile_name === n)).find(Boolean) ?? profiles.value[0]
          await selectProfile(def.profile_name)
        }
      } catch (e) { lastError.value = errorMessage(e) } finally { inflight = null }
    })()
    return inflight
  }

  async function selectProfile(name: string) {
    profile.value = name
    try {
      const r = await setProfile(name)
      if (!r.success) { lastError.value = r.error || '프로필 설정 실패'; return }
      push({ role: 'assistant', content: '', action: 'profile', profileResult: { profile_name: name, attributes: r.attributes ?? null } })
      system.toast(`프로필 설정 완료: ${name}`, 'success')
    } catch (e) { lastError.value = errorMessage(e) }
    void loadSchema()
  }

  async function loadSchema() {
    schemaLoading.value = true; schema.value = null; expanded.value = {}
    try { const r = await getSchemaInfo(profile.value); schema.value = r.tables ?? [] }
    catch (e) { schema.value = []; lastError.value = errorMessage(e) }
    finally { schemaLoading.value = false }
  }
  function toggleTable(name: string) { expanded.value[name] = !expanded.value[name] }

  function processResult(msg: Nl2sqlMessage, act: Action, result: unknown) {
    if (act === 'runsql') {
      let data: unknown = result
      if (typeof result === 'string') { try { data = JSON.parse(result) } catch { data = result } }
      if (Array.isArray(data) && data.length && typeof data[0] === 'object') {
        msg.table = { columns: Object.keys(data[0] as object), rows: data as Rows['rows'] }
      } else if (Array.isArray(data) && data.length === 0) {
        msg.table = { columns: [], rows: [] }
      } else {
        msg.textResult = typeof data === 'string' ? data : JSON.stringify(data, null, 2)
      }
    } else if (act === 'showsql') {
      msg.sql = typeof result === 'string' ? result : JSON.stringify(result, null, 2)
    } else {
      msg.textResult = typeof result === 'string' ? result : JSON.stringify(result, null, 2)
    }
  }

  async function send(promptText: string) {
    const prompt = promptText.trim()
    if (!prompt || sending.value) return
    const act = action.value
    const prev = [...messages.value].reverse().find((m) => m.role === 'user' && !m.isSql)?.content ?? null
    push({ role: 'user', content: prompt, prevPrompt: prev })
    input.value = ''
    const base = LOADING_TEXT[act]
    const msg = push({ role: 'assistant', content: '', action: act, prompt, profileName: profile.value, loading: true, loadingText: `${base}… (0초)`, chartType: 'bar', cached: {} })
    sending.value = true
    const t0 = Date.now()
    const timer = window.setInterval(() => { msg.loadingText = `${base}… (${Math.round((Date.now() - t0) / 1000)}초)` }, 1000)
    try {
      const r = await ask(prompt, act, profile.value)
      if (r.success) { msg.elapsedMs = r.elapsed_ms; processResult(msg, act, r.result); msg.cached![act] = r.result }
      else msg.errorText = r.error || '알 수 없는 오류가 발생했습니다.'
    } catch (e: any) {
      msg.errorText = e?.code === 'ECONNABORTED' ? '요청 시간이 초과되었습니다 (120초). 질문을 단순화하거나 다시 시도해 주세요.' : errorMessage(e)
    } finally { window.clearInterval(timer); msg.loading = false; sending.value = false }
  }

  async function runSql(sqlText: string) {
    const sql = sqlText.trim()
    if (!sql || sqlRunning.value) return
    push({ role: 'user', content: sql, isSql: true })
    sqlInput.value = ''
    const msg = push({ role: 'assistant', content: '', action: 'rawsql', loading: true, loadingText: 'SQL 실행 중…' })
    sqlRunning.value = true
    try {
      const r = await executeSql(sql)
      msg.elapsedMs = r.elapsed_ms ?? null
      msg.sqlResult = r.rows
      if (!r.success) msg.errorText = r.error || 'SQL 실행에 실패했습니다.'
    } catch (e) { msg.errorText = errorMessage(e) }
    finally { msg.loading = false; sqlRunning.value = false }
  }

  async function runAction(msg: Nl2sqlMessage, follow: FollowAction) {
    if (msg.actionLoading) return
    if (follow === 'chart') { msg.showChart = !msg.showChart; return }
    if (follow === 'explainplan') {
      const sqlText = msg.sql ?? (msg.cached?.showsql as string | undefined)
      if (!sqlText) { system.toast('SQL 을 먼저 확인해 주세요 ([SQL 보기])', 'warn'); return }
      if (msg.cached?.explainplan) { msg.explainPlan = msg.cached.explainplan as string; msg.action = 'explainplan'; return }
      msg.actionLoading = true; msg.actionLoadingText = '실행계획을 조회하고 있습니다…'
      try {
        const r = await explainPlan(sqlText)
        if (r.success && r.plan) { msg.explainPlan = r.plan; msg.cached!.explainplan = r.plan; msg.action = 'explainplan' }
        else system.toast(r.error || '실행계획 조회 실패', 'error')
      } catch (e) { system.toast(errorMessage(e), 'error') }
      finally { msg.actionLoading = false; msg.actionLoadingText = '' }
      return
    }
    const act = follow as Action
    if (msg.cached?.[act] !== undefined) { processResult(msg, act, msg.cached[act]); msg.action = act; return }
    const base = LOADING_TEXT[act]
    msg.actionLoading = true; msg.actionLoadingText = `${base}… (0초)`
    const t0 = Date.now()
    const timer = window.setInterval(() => { msg.actionLoadingText = `${base}… (${Math.round((Date.now() - t0) / 1000)}초)` }, 1000)
    try {
      const r = await ask(msg.prompt ?? '', act, msg.profileName ?? profile.value)
      if (r.success) { msg.cached![act] = r.result; processResult(msg, act, r.result); msg.action = act; if (r.elapsed_ms) msg.elapsedMs = r.elapsed_ms }
      else system.toast(r.error || '오류가 발생했습니다.', 'error')
    } catch (e) { system.toast(errorMessage(e), 'error') }
    finally { window.clearInterval(timer); msg.actionLoading = false; msg.actionLoadingText = '' }
  }
  const buttonsFor = (msg: Nl2sqlMessage) => (ACTION_BUTTONS[msg.action ?? ''] ?? []).filter((b) => b.action !== 'chart' || (msg.table && msg.table.rows.length > 0))

  async function annotate(kind: 'apply' | 'remove') {
    const info = annotationSetFor(profile.value)
    if (!info) { system.toast('현재 프로필에 해당하는 Annotation 세트가 없습니다.', 'warn'); return }
    annoBusy.value = kind
    try {
      if (kind === 'apply') {
        const set: Record<string, Record<string, string>> = {}
        for (const [tbl, cols] of Object.entries(info.tables)) set[tbl] = { ...cols, _owner: info.owner }
        const r = await applyAnnotations(set)
        if (r.success && r.applied_count > 0) system.toast(`Annotation 적용 완료 (${r.applied_count}건${r.error_count ? `, 실패 ${r.error_count}건` : ''})`, 'success')
        else system.toast('Annotation 적용 실패: ' + (r.error || r.errors?.[0] || '적용된 항목 없음'), 'error')
      } else {
        const r = await removeAnnotations(Object.keys(info.tables), info.owner)
        if (r.success) system.toast(`Annotation 제거 완료 (${r.removed_count}건)`, 'success')
        else system.toast('Annotation 제거 실패: ' + (r.error || ''), 'error')
      }
      await loadSchema()
    } catch (e) { system.toast(errorMessage(e), 'error') } finally { annoBusy.value = '' }
  }

  function clear() { messages.value = messages.value.filter((m) => m.action === 'profile').slice(-1) }
  const profileAttrsRows = (m: Nl2sqlMessage): Rows | null => (m.profileResult?.attributes?.columns ? fromColumnsData(m.profileResult.attributes) : null)

  return {
    profiles, profile, profilesLoaded, action, messages, input, sqlInput, sending, sqlRunning, schema, schemaLoading, expanded, annoBusy, lastError,
    examples, profileOptions, hasAnnotationSet, asked,
    init, selectProfile, loadSchema, toggleTable, send, runSql, runAction, buttonsFor, annotate, clear, profileAttrsRows,
  }
})
