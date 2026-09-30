import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { errorMessage } from '@/lib/api'
import { createDemoTeam, dropDemoTeam, getAgentHistory, getDefinitions, getExecDetail, runTeam, type Definitions, type ExecDetail, type HistoryRow, type RunResult } from '@/lib/agent'
import type { FeedbackInfo } from '@/lib/nl2sql'
import type { ChatMessage } from '@/lib/types/chat'
import { useSystemStore } from './system'

export interface AgentMessage extends ChatMessage {
  id: number; timestamp: string
  run?: RunResult | null
  team?: string
  feedback?: FeedbackInfo | null
}
const now = () => new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })

/** ⑦ Select AI Agent — 정의(뷰) · 실행(RUN_TEAM 대화, conversation_id 로 멀티턴) · 히스토리. */
export const useAgentStore = defineStore('agent', () => {
  const system = useSystemStore()
  // ── 정의 ──
  const defs = ref<Definitions | null>(null)
  const defsLoading = ref(false)
  const error = ref<string | null>(null)
  async function loadDefs() {
    defsLoading.value = true
    try { defs.value = await getDefinitions(); error.value = null } catch (e) { error.value = errorMessage(e) } finally { defsLoading.value = false }
  }
  const teamNames = computed(() => (defs.value?.teams ?? []).map((t) => t.name))
  const demoBusy = ref(false)
  const demoSteps = ref<{ label: string; plsql: string }[]>([])
  async function makeDemo(base: string) {
    demoBusy.value = true
    try { const r = await createDemoTeam(base); if (!r.success) throw new Error(r.error); demoSteps.value = r.steps ?? []
      system.toast(`샘플 팀 ${r.team} 준비 — 프로필 ${r.profile}${r.profile_created ? ' (새로 만듦)' : ''}`, 'success'); await loadDefs(); if (!team.value) team.value = r.team ?? '' }
    catch (e) { system.toast(errorMessage(e), 'error') } finally { demoBusy.value = false }
  }
  async function dropDemo() {
    demoBusy.value = true
    try { const r = await dropDemoTeam(); if (!r.success) throw new Error(r.error); system.toast('샘플 팀을 지웠습니다', 'success'); demoSteps.value = []; await loadDefs() }
    catch (e) { system.toast(errorMessage(e), 'error') } finally { demoBusy.value = false }
  }

  // ── 실행 ──
  const team = ref('')
  const messages = ref<AgentMessage[]>([])
  const input = ref('')
  const sending = ref(false)
  const multiTurn = ref(true)
  const conversationId = ref('')
  const turns = ref(0)
  let seq = 0
  function push(m: Omit<AgentMessage, 'id' | 'timestamp'>): AgentMessage { const msg = { id: ++seq, timestamp: now(), ...m }; messages.value.push(msg); return messages.value[messages.value.length - 1] }
  function newConversation() { conversationId.value = ''; turns.value = 0; system.toast('새 대화 — 다음 질문은 새 conversation 으로', 'success') }
  async function send(text: string) {
    const q = text.trim()
    if (!q || sending.value || !team.value) return
    push({ role: 'user', content: q })
    input.value = ''
    const msg = push({ role: 'assistant', content: '', loading: true, team: team.value })
    sending.value = true
    const cid = multiTurn.value ? conversationId.value : ''
    try {
      const r = await runTeam(team.value, q, cid)
      msg.run = r
      if (r.success) { msg.content = r.answer ?? ''; if (r.conversation_id && multiTurn.value) { conversationId.value = r.conversation_id; turns.value++ } }
      else { msg.error = true; msg.content = r.error ?? 'RUN_TEAM 실패' }
      msg.elapsedMs = r.elapsed_ms
    } catch (e: any) {
      const d = e?.response?.data
      msg.error = true; msg.content = d?.error ?? errorMessage(e); msg.run = d ?? null
    } finally { msg.loading = false; sending.value = false }
  }
  /** 이 대화의 누적 시간(성공한 턴) */
  const convTotalMs = computed(() => messages.value.filter((m) => m.run?.success).reduce((a, m) => a + (m.run?.elapsed_ms ?? 0), 0))
  function clear() { messages.value = [] }

  // ── 히스토리 ──
  const filter = ref({ q: '', date_from: '', date_to: '', team: '', state: '' })
  const rows = ref<HistoryRow[]>([]); const total = ref(0); const page = ref(1); const size = ref(20); const sql = ref(''); const teams = ref<string[]>([])
  const histLoading = ref(false); const loadedOnce = ref(false)
  const detail = ref<ExecDetail | null>(null); const detailLoading = ref(false)
  async function loadHistory(p = page.value) {
    histLoading.value = true
    try { const r = await getAgentHistory(filter.value, p, size.value); if (!r.success) throw new Error(r.error); rows.value = r.rows; total.value = r.total; page.value = r.page; sql.value = r.sql; teams.value = r.teams; loadedOnce.value = true; error.value = null }
    catch (e) { error.value = errorMessage(e) } finally { histLoading.value = false }
  }
  async function open(id: string) {
    detailLoading.value = true; detail.value = null
    try { const r = await getExecDetail(id); if (!r.success) throw new Error(r.error); detail.value = r } catch (e) { error.value = errorMessage(e) } finally { detailLoading.value = false }
  }
  function close() { detail.value = null }

  return { defs, defsLoading, error, loadDefs, teamNames, demoBusy, demoSteps, makeDemo, dropDemo,
    team, messages, input, sending, multiTurn, conversationId, turns, send, newConversation, convTotalMs, clear,
    filter, rows, total, page, size, sql, teams, histLoading, loadedOnce, detail, detailLoading, loadHistory, open, close }
})
