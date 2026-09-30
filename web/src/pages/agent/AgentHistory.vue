<script setup lang="ts">
/** Agent History 탭 — USER_AI_AGENT_TEAM_HISTORY ⋈ 앱 로그 ⋈ 피드백. 행 클릭 → 단계·툴 호출·답·피드백 편집(FeedbackBox, source HISTORY). */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { History, Search, RotateCcw, X as XIcon, ThumbsUp, ThumbsDown, Copy, ChevronRight, ChevronDown } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import Pagination from '@/components/ui/Pagination.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import KvGrid from '@/components/demo/KvGrid.vue'
import FeedbackBox from '@/components/demo/FeedbackBox.vue'
import { renderMarkdown } from '@/lib/markdown'
import { fmtDateTime, fmtMs } from '@/lib/format'
import { shortConv, type FeedbackInfo } from '@/lib/nl2sql'
import { useAgentStore } from '@/stores/agent'
import { useSystemStore } from '@/stores/system'

const a = useAgentStore()
const system = useSystemStore()
const showSql = ref(false)
onMounted(() => { if (!a.loadedOnce) void a.loadHistory(1); window.addEventListener('keydown', onKey) })
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
function onKey(e: KeyboardEvent) { if (e.key === 'Escape' && a.detail) a.close() }
const teamOptions = computed(() => [{ value: '', label: '팀 전체' }, ...a.teams.map((t) => ({ value: t, label: t }))])
const stateOptions = [{ value: '', label: '상태 전체' }, { value: 'SUCCEEDED', label: 'SUCCEEDED' }, { value: 'FAILED', label: 'FAILED' }, { value: 'WAITING_FOR_HUMAN', label: 'WAITING_FOR_HUMAN' }]
async function copy(v: string) { try { await navigator.clipboard.writeText(v); system.toast('복사했습니다', 'success') } catch { system.toast(v, 'info') } }
const existingFb = computed<FeedbackInfo | null>(() => { const f = a.detail?.feedback?.[0]; return f ? { id: f.ID, type: f.FEEDBACK_TYPE as FeedbackInfo['type'], content: f.FEEDBACK_CONTENT ?? '', correctedSql: f.CORRECTED_SQL ?? '' } : null })
async function afterFb() { if (a.detail) { const id = a.detail.TEAM_EXEC_ID; await Promise.all([a.open(id), a.loadHistory(a.page)]) } }
const kv = computed(() => { const d = a.detail; if (!d) return {}; return { 시작: fmtDateTime(d.START_DATE), 종료: fmtDateTime(d.END_DATE), Team: d.TEAM_NAME, 상태: d.STATE, 프로필: d.log?.PROFILE_NAME ?? '—', 소요: fmtMs(d.log?.ELAPSED_MS ?? null), conversation_id: d.CONVERSATION_ID ?? '—', team_exec_id: d.TEAM_EXEC_ID } })
const fmtJson = (v: unknown) => (typeof v === 'string' ? v : JSON.stringify(v, null, 2))
</script>

<template>
  <div class="flex flex-col gap-4">
    <div v-if="a.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ a.error }}</div>
    <Card title="Agent History" subtitle="USER_AI_AGENT_TEAM_HISTORY — RUN_TEAM 실행마다 한 행. 질문·피드백은 앱 로그(AI_QUERY_LOG.exec_id)로 붙인다" :icon="History">
      <template #actions><Badge tone="info">{{ a.total.toLocaleString() }}건</Badge></template>
      <form class="flex flex-wrap items-center gap-2 mb-3" @submit.prevent="a.loadHistory(1)">
        <label class="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 flex-1 min-w-[220px]" style="background: var(--bg-elevated); border: 1px solid var(--border-strong);"><Search :size="14" :stroke-width="1.75" style="color: var(--text-muted);" /><input v-model="a.filter.q" placeholder="질문 검색" class="bg-transparent outline-none text-sm w-full" style="color: var(--text-primary);" /></label>
        <input v-model="a.filter.date_from" type="datetime-local" class="rounded-md px-2 py-1.5 text-sm" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" /><span class="text-xs" style="color: var(--text-muted);">~</span>
        <input v-model="a.filter.date_to" type="datetime-local" class="rounded-md px-2 py-1.5 text-sm" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" />
        <div class="w-[200px]"><SearchableSelect v-model="a.filter.team" :options="teamOptions" :searchable="false" placeholder="팀 전체" /></div>
        <div class="w-[180px]"><SearchableSelect v-model="a.filter.state" :options="stateOptions" :searchable="false" placeholder="상태 전체" /></div>
        <Button type="submit" :busy="a.histLoading"><Search :size="14" :stroke-width="2" /> 조회</Button>
        <Button variant="ghost" size="sm" @click="a.filter = { q: '', date_from: '', date_to: '', team: '', state: '' }; a.loadHistory(1)"><RotateCcw :size="14" :stroke-width="1.75" /></Button>
      </form>
      <LoadingBlock v-if="a.histLoading && !a.rows.length" compact label="이력을 읽는 중…" />
      <EmptyState v-else-if="!a.rows.length" :icon="History" compact title="실행 이력이 없습니다" desc="「실행」 탭에서 팀을 돌리면 여기 쌓입니다." />
      <div v-else class="rounded-md overflow-auto" style="border: 1px solid var(--border-default);">
        <table class="w-full text-sm" style="border-collapse: collapse;">
          <thead><tr style="background: var(--bg-surface); color: var(--text-muted);"><th v-for="c in ['시작시각', 'Team', '질문', '상태', '소요', '피드백', 'conversation_id']" :key="c" class="text-left text-[11px] font-semibold px-3 py-2 whitespace-nowrap">{{ c }}</th></tr></thead>
          <tbody>
            <tr v-for="r in a.rows" :key="r.TEAM_EXEC_ID" class="row cursor-pointer" @click="a.open(r.TEAM_EXEC_ID)">
              <td class="px-3 py-2 whitespace-nowrap font-mono text-xs" style="color: var(--text-secondary);">{{ fmtDateTime(r.START_DATE) }}</td>
              <td class="px-3 py-2 font-mono text-xs" style="color: var(--text-primary);">{{ r.TEAM_NAME }}</td>
              <td class="px-3 py-2 max-w-[380px] truncate" style="color: var(--text-primary);">{{ r.QUESTION ?? '—' }}</td>
              <td class="px-3 py-2"><Badge :tone="r.STATE === 'SUCCEEDED' ? 'positive' : r.STATE === 'FAILED' ? 'negative' : 'warm'">{{ r.STATE }}</Badge></td>
              <td class="px-3 py-2 font-mono text-xs text-right whitespace-nowrap" style="color: var(--text-secondary);">{{ fmtMs(r.ELAPSED_MS) }}</td>
              <td class="px-3 py-2 text-center"><ThumbsUp v-if="r.FEEDBACK_TYPE === 'positive'" :size="14" :stroke-width="1.75" style="color: var(--accent-positive);" /><ThumbsDown v-else-if="r.FEEDBACK_TYPE === 'negative'" :size="14" :stroke-width="1.75" style="color: var(--accent-negative);" /><span v-else style="color: var(--text-muted);">—</span></td>
              <td class="px-3 py-2 whitespace-nowrap"><button v-if="r.CONVERSATION_ID" type="button" class="inline-flex items-center gap-1 font-mono text-[11px]" style="color: var(--text-muted);" :title="r.CONVERSATION_ID" @click.stop="copy(r.CONVERSATION_ID!)"><Copy :size="10" :stroke-width="1.75" />{{ shortConv(r.CONVERSATION_ID) }}</button><span v-else style="color: var(--text-muted);">—</span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <Pagination :total="a.total" :page="a.page" :page-size="a.size" class="mt-2" @update:page="(p: number) => a.loadHistory(p)" />
      <button v-if="a.sql" type="button" class="mt-2 inline-flex items-center gap-1 text-xs" style="color: var(--text-secondary);" @click="showSql = !showSql"><component :is="showSql ? ChevronDown : ChevronRight" :size="13" :stroke-width="2" /> 조회 SQL</button>
      <SqlBlock v-if="showSql && a.sql" :code="a.sql" label="USER_AI_AGENT_TEAM_HISTORY 조회 SQL" max-height="260px" class="mt-2" />
    </Card>

    <Teleport to="body">
      <div v-if="a.detail || a.detailLoading" class="fixed inset-0 z-[60] flex items-center justify-center p-4" style="background: rgba(0,0,0,0.5);" @click.self="a.close()">
        <div class="w-full max-w-[900px] max-h-[90vh] flex flex-col rounded-md" style="background: var(--bg-elevated); box-shadow: var(--shadow-elevated);" role="dialog" aria-label="실행 상세">
          <header class="flex items-center justify-between px-5 py-3 shrink-0" style="border-bottom: 1px solid var(--border-default);">
            <div class="flex items-center gap-2"><History :size="18" :stroke-width="1.75" style="color: var(--accent-primary);" /><span class="font-semibold" style="color: var(--text-primary);">실행 {{ a.detail ? a.detail.TEAM_EXEC_ID.slice(0, 8) + '…' : '' }}</span><Badge v-if="a.detail" :tone="a.detail.STATE === 'SUCCEEDED' ? 'positive' : 'negative'">{{ a.detail.STATE }}</Badge></div>
            <button class="p-1.5 rounded-md" style="color: var(--text-secondary);" @click="a.close()"><XIcon :size="18" :stroke-width="1.75" /></button>
          </header>
          <div class="flex-1 overflow-auto p-5 flex flex-col gap-4">
            <LoadingBlock v-if="a.detailLoading" compact label="상세를 읽는 중…" />
            <template v-else-if="a.detail">
              <div v-if="a.detail.log?.QUESTION" class="rounded-xl px-3.5 py-2.5 text-sm whitespace-pre-wrap" style="background: var(--accent-primary); color: var(--text-on-accent);">{{ a.detail.log.QUESTION }}</div>
              <KvGrid :data="kv" />
              <div v-if="a.detail.log?.RESPONSE_TEXT" class="md-body text-sm rounded-md px-3.5 py-3" style="background: var(--bg-surface); color: var(--text-primary);" v-html="renderMarkdown(a.detail.log.RESPONSE_TEXT)" />
              <div v-if="a.detail.log?.ERROR_MSG" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);"><span class="font-mono text-xs break-all whitespace-pre-wrap">{{ a.detail.log.ERROR_MSG }}</span></div>
              <SqlBlock v-if="a.detail.log?.GENERATED_SQL" :code="a.detail.log.GENERATED_SQL" label="툴이 만든 SQL" max-height="220px" />
              <div class="rounded-md overflow-hidden text-xs" style="border: 1px solid var(--border-default);">
                <div class="px-3 py-1.5 font-medium" style="background: var(--bg-surface); color: var(--text-secondary);">단계 {{ a.detail.tasks.length }} · 툴 호출 {{ a.detail.tools.length }}</div>
                <div v-for="t in a.detail.tasks" :key="t.TASK_ORDER" class="flex items-center gap-3 px-3 py-1.5" style="border-top: 1px solid var(--border-default);"><span class="font-mono" style="color: var(--text-muted);">#{{ t.TASK_ORDER }}</span><span class="font-mono" style="color: var(--text-primary);">{{ t.TASK_NAME }}</span><span style="color: var(--text-muted);">{{ t.AGENT_NAME }}</span><Badge :tone="t.STATE === 'SUCCEEDED' ? 'positive' : 'negative'">{{ t.STATE }}</Badge><span class="ml-auto font-mono">{{ fmtMs(t.ELAPSED_MS) }}</span></div>
                <div v-for="t in a.detail.tools" :key="t.INVOCATION_ID" class="px-3 py-2 flex flex-col gap-1" style="border-top: 1px solid var(--border-default); background: var(--bg-surface);"><div class="flex items-center gap-2"><Badge tone="code">{{ t.TOOL_NAME }}</Badge><span style="color: var(--text-muted);">{{ fmtMs(t.ELAPSED_MS) }}</span></div><pre class="m-0 whitespace-pre-wrap break-words font-mono text-[11px]" style="color: var(--text-primary);">{{ fmtJson(t.INPUT_JSON ?? t.INPUT) }}</pre><pre class="m-0 whitespace-pre-wrap break-words font-mono text-[11px] max-h-32 overflow-auto" style="color: var(--text-secondary);">{{ fmtJson(t.OUTPUT_JSON ?? t.OUTPUT) }}</pre></div>
              </div>
              <div class="flex flex-col gap-1.5">
                <span class="font-medium text-sm" style="color: var(--text-primary);">피드백</span>
                <FeedbackBox v-if="a.detail.log && a.detail.STATE === 'SUCCEEDED'" :key="a.detail.TEAM_EXEC_ID" :log-id="a.detail.log.ID" :existing="existingFb" source="HISTORY" @saved="afterFb" @deleted="afterFb" />
                <p v-else class="text-xs m-0" style="color: var(--text-muted);">앱 로그가 없거나 실패한 실행에는 피드백을 붙이지 않습니다.</p>
              </div>
            </template>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.row + .row td { border-top: 1px solid var(--border-default); }
.row:hover td { background: var(--bg-surface); }
</style>
