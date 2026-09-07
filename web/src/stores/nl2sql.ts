import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { errorMessage } from '@/lib/api'
import { annotationSetFor } from '@/lib/annotations'
import {
  ACTION_BUTTONS, LOADING_TEXT, ask, applyAnnotations, executeSql, exampleQuestionsFor, explainPlan, getProfiles, getSchemaInfo,
  removeAnnotations, getEnvInfo, hostFromEndpoint, aclHostMatches, ENV_TEST_PROMPT, type Action, type FollowAction, type Profile, type SchemaTable,
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
  action?: Action | 'rawsql' | 'explainplan'
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
  sqlResult?: Rows | null
  /** 직접 실행창에 친 `SELECT AI …` — 결과는 자연어 답변과 같은 블록(생성된 SQL·표·서술)으로 그린다 */
  aiDirect?: boolean
}

const now = () => new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })

/**
 * NL2SQL 탭 — 앱의 첫 화면. 서브탭 3: 환경(프로필·크리덴셜·ACL 사슬) · 질문(대화) · 스키마·Annotation.
 * 프로필은 페이지 공통이라 세 서브탭이 같은 것을 본다 (2026-09-07 재설계).
 * 질문 쪽은 레거시 app.js 의 sendQuestion/executeAction/processResult 를 그대로 옮기되, 결과는 Rows 로 정규화한다.
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

  // ── 「환경」 서브탭 ────────────────────────────────────────────────────────
  // 프로필 → credential_name → 크리덴셜 / 프로필 → provider_endpoint 호스트 → ACL 사슬.
  // 세 조회는 독립이라 병렬로 부르고, 프로필이 바뀌면 다시 읽는다. 결과 형태는 /api/env-info 의 result 그대로.
  const env = ref<{ profile: any | null; credential: any | null; acl: any | null }>({ profile: null, credential: null, acl: null })
  const envLoading = ref(false)
  const envLoadedFor = ref('')
  const envTest = ref<{ busy: boolean; response: string | null; elapsedMs: number | null; error: string | null }>({ busy: false, response: null, elapsedMs: null, error: null })

  const profileAttrs = computed<Record<string, string>>(() => {
    const out: Record<string, string> = {}
    for (const r of env.value.profile?.data ?? []) out[String(r.ATTRIBUTE_NAME)] = r.ATTRIBUTE_VALUE == null ? '' : String(r.ATTRIBUTE_VALUE)
    return out
  })
  const objectList = computed<{ owner: string; name: string }[]>(() => {
    try { const v = JSON.parse(profileAttrs.value.object_list || '[]'); return Array.isArray(v) ? v : [] } catch { return [] }
  })
  const endpointHost = computed(() => hostFromEndpoint(profileAttrs.value.provider_endpoint))
  const credentialName = computed(() => profileAttrs.value.credential_name || '')
  const credentialRow = computed<Record<string, any> | null>(() => (env.value.credential?.data ?? []).find((r: any) => String(r.CREDENTIAL_NAME) === credentialName.value) ?? null)
  const credOk = computed(() => !!credentialRow.value && String(credentialRow.value.ENABLED).toUpperCase() === 'TRUE')
  const aclAll = computed<Rows | null>(() => (env.value.acl?.columns?.length ? fromColumnsData(env.value.acl) : null))
  const aclForHost = computed<Record<string, any>[]>(() => {
    const h = endpointHost.value
    return h ? (env.value.acl?.data ?? []).filter((r: any) => aclHostMatches(String(r.HOST ?? ''), h)) : []
  })
  // 앱이 붙은 계정(ADMIN)에 준 권한만 센다 — 다른 principal 의 ACE 는 이 앱에 도움이 안 된다.
  // USER_ 뷰 폴백에는 PRINCIPAL 열이 없으므로 그때는 거르지 않는다.
  const currentUser = computed(() => (system.health?.schema || '').toUpperCase())
  const aclPrivs = computed(() => new Set(
    aclForHost.value
      .filter((r) => r.PRINCIPAL == null || !currentUser.value || String(r.PRINCIPAL).toUpperCase() === currentUser.value)
      .map((r) => String(r.PRIVILEGE ?? '').toUpperCase()),
  ))
  const aclOk = computed(() => aclPrivs.value.has('CONNECT'))
  const annotationCount = computed(() => {
    let n = 0
    for (const t of schema.value ?? []) { if (t.annotation) n++; for (const c of t.columns) if (c.annotation) n++ }
    return n
  })

  async function loadEnv(force = false) {
    if (!profile.value) return
    if (!force && envLoadedFor.value === profile.value) return
    envLoading.value = true
    try {
      const [p, c, a] = await Promise.all([getEnvInfo('profile', profile.value), getEnvInfo('credential', profile.value), getEnvInfo('acl', profile.value)])
      env.value = { profile: p.result ?? null, credential: c.result ?? null, acl: a.result ?? null }
      envLoadedFor.value = profile.value
      const err = [p, c, a].map((r) => r.result?.error).find(Boolean)
      if (err) lastError.value = err
    } catch (e) { lastError.value = errorMessage(e) }
    finally { envLoading.value = false }
  }

  /** 세 카드가 전부 ✓ 여도 키가 만료됐으면 실패한다 — 그걸 이 자리에서 드러내는 것이 목적. chat 이라 테이블은 안 읽는다. */
  async function testCall() {
    if (envTest.value.busy || !profile.value) return
    envTest.value = { busy: true, response: null, elapsedMs: null, error: null }
    try {
      const r = await ask(ENV_TEST_PROMPT, 'chat', profile.value)
      if (r.success) envTest.value = { busy: false, response: typeof r.result === 'string' ? r.result : JSON.stringify(r.result), elapsedMs: r.elapsed_ms ?? null, error: null }
      else envTest.value = { busy: false, response: null, elapsedMs: r.elapsed_ms ?? null, error: r.error || '알 수 없는 오류가 발생했습니다.' }
    } catch (e: any) {
      envTest.value = { busy: false, response: null, elapsedMs: null, error: e?.code === 'ECONNABORTED' ? '요청 시간이 초과되었습니다 (120초).' : errorMessage(e) }
    }
  }

  function push(m: Omit<Nl2sqlMessage, 'id' | 'timestamp'>): Nl2sqlMessage {
    const msg: Nl2sqlMessage = { id: ++seq, timestamp: now(), ...m }
    messages.value.push(msg)
    return messages.value[messages.value.length - 1]
  }

  let inflight: Promise<void> | null = null
  const known = (name: string) => !!name && profiles.value.some((p) => p.profile_name === name)
  /**
   * 프로필 목록을 한 번만 읽고 기본 프로필을 고른다. `preferred` 는 `?profile=` 딥링크 —
   * 페이지와 서브탭이 같은 값으로 부르므로 첫 호출이 이긴다. 이미 로드된 뒤에 다른 값이 오면 그때 바꾼다.
   */
  function init(preferred?: unknown): Promise<void> {
    const want = typeof preferred === 'string' ? preferred : ''
    if (!profilesLoaded.value && !inflight) {
      inflight = (async () => {
        try {
          profiles.value = await getProfiles()
          profilesLoaded.value = true
          if (!profiles.value.length) { lastError.value = 'DB 에 등록된 AI 프로필이 없습니다.'; return }
          // 기본 프로필 우선순위. 2026-09-05: GROQ 프로필이 DB 자격증명 문제(ORA-20404 bearer://api.groq.com)로 실패해
          // GEMINI 를 앞에 둔다 — Groq credential 을 고치면 순서를 되돌려도 된다.
          const PREFER = [want, 'GEMINI_SH_PROFILE', 'GROQ_SH_PROFILE']
          const def = PREFER.map((n) => profiles.value.find((p) => p.profile_name === n)).find(Boolean) ?? profiles.value[0]
          await selectProfile(def.profile_name)
        } catch (e) { lastError.value = errorMessage(e) } finally { inflight = null }
      })()
      return inflight
    }
    return (inflight ?? Promise.resolve()).then(async () => { if (want && want !== profile.value && known(want)) await selectProfile(want) })
  }

  /**
   * 프로필 선택 — 페이지 공통. 환경 3종과 스키마를 다시 읽는다.
   * DBMS_CLOUD_AI.SET_PROFILE 은 부르지 않는다: 세션 단위라 풀 커넥션에선 의미가 없고(ORA-20046 교훈),
   * /api/ask 는 매 호출 프로필명을 명시한다. 옛 화면이 대화창에 밀어 넣던 속성 표는 「환경」 탭이 대신한다.
   */
  async function selectProfile(name: string) {
    if (!name || !known(name)) return
    const changed = profile.value !== '' && profile.value !== name
    if (name === profile.value && envLoadedFor.value === name) return
    profile.value = name
    envTest.value = { busy: false, response: null, elapsedMs: null, error: null }
    lastError.value = null
    if (changed) system.toast(`프로필 선택: ${name}`, 'success')
    await Promise.all([loadEnv(true), loadSchema()])
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
      const r = await executeSql(sql, profile.value)
      msg.elapsedMs = r.elapsed_ms ?? null
      msg.sqlResult = r.rows
      if (r.select_ai) {
        // `SELECT AI [액션] 질문` 은 자연어 질문과 같은 것이다 — 같은 블록으로 그리고 같은 후속 버튼을 단다.
        // 친 문장은 위의 「직접 실행한 SQL」 블록(배지: 프로필)에 남고, RESPONSE 한 칸짜리 표는 숨긴다.
        const act = (r.select_ai_action || 'runsql') as Action
        msg.aiDirect = true
        msg.action = act
        msg.prompt = r.select_ai_prompt || ''
        msg.profileName = r.profile_name || profile.value
        msg.cached = {}
        msg.chartType = 'bar'
        if (r.success) {
          const payload: unknown = act === 'runsql' ? r.rows.rows : r.rows.rows[0]?.[r.rows.columns[0]] ?? ''
          msg.cached[act] = payload
          processResult(msg, act, payload)
        } else msg.errorText = r.error || 'SQL 실행에 실패했습니다.'
      } else if (!r.success && !r.rows?.error) {
        // 오류는 표 자리(ResultTable 의 error 행)에 한 번만 — 상단 배너까지 겹치면 같은 문장이 두 번 보인다
        msg.errorText = r.error || 'SQL 실행에 실패했습니다.'
      }
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

  function clear() { messages.value = [] }

  return {
    profiles, profile, profilesLoaded, action, messages, input, sqlInput, sending, sqlRunning, schema, schemaLoading, expanded, annoBusy, lastError,
    examples, profileOptions, hasAnnotationSet, asked,
    env, envLoading, envTest, profileAttrs, objectList, endpointHost, credentialName, credentialRow, credOk, aclAll, aclForHost, aclPrivs, aclOk, annotationCount,
    init, selectProfile, loadEnv, testCall, loadSchema, toggleTable, send, runSql, runAction, buttonsFor, annotate, clear,
  }
})
