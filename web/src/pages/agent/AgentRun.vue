<script setup lang="ts">
/** 실행 탭 — 팀 선택 + RUN_TEAM 대화. 답 아래 Thinking(툴 호출) · 단계별 시간 · 메타 · 피드백. */
import { computed, onMounted, ref } from 'vue'
import { Bot, MessageSquarePlus, Eraser, Copy, ChevronDown, ChevronRight, Brain, Timer } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import Toggle from '@/components/ui/Toggle.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import ChatThread from '@/components/demo/ChatThread.vue'
import ChatComposer from '@/components/demo/ChatComposer.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import FeedbackBox from '@/components/demo/FeedbackBox.vue'
import { renderMarkdown } from '@/lib/markdown'
import { fmtMs } from '@/lib/format'
import { shortConv } from '@/lib/nl2sql'
import { useAgentStore, type AgentMessage } from '@/stores/agent'
import { useSystemStore } from '@/stores/system'

const a = useAgentStore()
const system = useSystemStore()
onMounted(() => { void a.loadDefs().then(() => { if (!a.team && a.teamNames.length) a.team = a.teamNames[0] }) })
const teamOptions = computed(() => a.teamNames.map((t) => ({ value: t, label: t })))
const asMsg = (m: unknown) => m as AgentMessage
const open = ref<Record<string, boolean>>({})
const key = (m: AgentMessage, k: string) => `${m.id}:${k}`
async function copy(v: string) { try { await navigator.clipboard.writeText(v); system.toast('복사했습니다', 'success') } catch { system.toast(v, 'info') } }
const stepTotal = (m: AgentMessage) => (m.run?.tasks ?? []).reduce((s, t) => s + (t.ELAPSED_MS ?? 0), 0)
const fmtJson = (v: unknown) => (typeof v === 'string' ? v : JSON.stringify(v, null, 2))
</script>

<template>
  <div class="flex flex-col gap-4">
    <Card compact>
      <ChatThread :messages="a.messages" max-height="calc(100vh - 430px)" min-height="220px" :empty-text="a.team ? `${a.team} 에게 자연어로 물어보세요 — 에이전트가 SQL 도구를 써서 답합니다 (1턴 15~25초)` : '「정의」 탭에서 샘플 팀을 먼저 만드세요'">
        <template #user="{ msg }"><div class="max-w-[80%] rounded-xl px-3.5 py-2 text-sm whitespace-pre-wrap" style="background: var(--accent-primary); color: var(--text-on-accent);">{{ msg.content }}<div class="text-[10px] opacity-70 mt-1 text-right">{{ asMsg(msg).timestamp }}</div></div></template>
        <template #assistant="{ msg }">
          <div class="flex items-start gap-2.5 w-full min-w-0">
            <div class="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5" style="background: var(--bg-surface); border: 1px solid var(--border-default); color: var(--accent-primary);"><Bot :size="15" :stroke-width="1.75" /></div>
            <div class="flex-1 min-w-0 flex flex-col gap-2">
              <LoadingBlock v-if="msg.loading" compact label="RUN_TEAM 실행 중 — 에이전트가 도구를 고르고 SQL 을 돌립니다…" />
              <template v-else>
                <div v-if="msg.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);"><span class="font-mono text-xs break-all whitespace-pre-wrap">{{ msg.content }}</span></div>
                <div v-else class="md-body text-sm rounded-md px-3.5 py-3" style="background: var(--bg-surface); color: var(--text-primary);" v-html="renderMarkdown(msg.content)" />
                <template v-if="asMsg(msg).run">
                  <!-- Thinking: 툴 호출 입력→출력 -->
                  <div v-if="asMsg(msg).run!.tools?.length">
                    <button type="button" class="inline-flex items-center gap-1 text-xs" style="color: var(--text-secondary);" @click="open[key(asMsg(msg), 'think')] = !open[key(asMsg(msg), 'think')]"><component :is="open[key(asMsg(msg), 'think')] ? ChevronDown : ChevronRight" :size="13" :stroke-width="2" /><Brain :size="13" :stroke-width="1.75" /> Thinking — 툴 호출 {{ asMsg(msg).run!.tools.length }}회</button>
                    <div v-if="open[key(asMsg(msg), 'think')]" class="mt-2 flex flex-col gap-2">
                      <div v-for="t in asMsg(msg).run!.tools" :key="t.INVOCATION_ID" class="rounded-md p-2.5 text-xs flex flex-col gap-1.5" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
                        <div class="flex items-center gap-2"><Badge tone="code">{{ t.TOOL_NAME }}</Badge><span style="color: var(--text-muted);">{{ t.AGENT_NAME }} · {{ fmtMs(t.ELAPSED_MS) }}</span></div>
                        <div><span style="color: var(--text-muted);">입력</span><pre class="m-0 mt-0.5 whitespace-pre-wrap break-words font-mono text-[11px]" style="color: var(--text-primary);">{{ fmtJson(t.INPUT_JSON ?? t.INPUT) }}</pre></div>
                        <div><span style="color: var(--text-muted);">출력</span><pre class="m-0 mt-0.5 whitespace-pre-wrap break-words font-mono text-[11px] max-h-40 overflow-auto" style="color: var(--text-primary);">{{ fmtJson(t.OUTPUT_JSON ?? t.OUTPUT) }}</pre></div>
                      </div>
                    </div>
                  </div>
                  <!-- 단계별 시간 -->
                  <div v-if="asMsg(msg).run!.tasks?.length">
                    <button type="button" class="inline-flex items-center gap-1 text-xs" style="color: var(--text-secondary);" @click="open[key(asMsg(msg), 'time')] = !open[key(asMsg(msg), 'time')]"><component :is="open[key(asMsg(msg), 'time')] ? ChevronDown : ChevronRight" :size="13" :stroke-width="2" /><Timer :size="13" :stroke-width="1.75" /> 단계별 시간 ({{ asMsg(msg).run!.tasks.length }}단계 · 총 {{ fmtMs(asMsg(msg).run!.elapsed_ms) }}) · 이 대화 누적 {{ fmtMs(a.convTotalMs) }}</button>
                    <div v-if="open[key(asMsg(msg), 'time')]" class="mt-2 rounded-md overflow-hidden text-xs" style="border: 1px solid var(--border-default);">
                      <div v-for="t in asMsg(msg).run!.tasks" :key="t.TASK_ORDER" class="flex items-center gap-3 px-3 py-1.5" style="background: var(--bg-surface); border-bottom: 1px solid var(--border-default);"><span class="font-mono" style="color: var(--text-muted);">#{{ t.TASK_ORDER }}</span><span class="font-mono" style="color: var(--text-primary);">{{ t.TASK_NAME }}</span><span style="color: var(--text-muted);">{{ t.AGENT_NAME }}</span><Badge :tone="t.STATE === 'SUCCEEDED' ? 'positive' : 'negative'">{{ t.STATE }}</Badge><span class="ml-auto font-mono">{{ fmtMs(t.ELAPSED_MS) }}</span></div>
                      <div v-for="t in asMsg(msg).run!.tools" :key="'t' + t.INVOCATION_ID" class="flex items-center gap-3 px-3 py-1.5 pl-8" style="background: var(--bg-elevated); border-bottom: 1px solid var(--border-default);"><span style="color: var(--text-muted);">└ 툴</span><span class="font-mono" style="color: var(--text-primary);">{{ t.TOOL_NAME }}</span><span class="ml-auto font-mono">{{ fmtMs(t.ELAPSED_MS) }}</span></div>
                      <div class="flex items-center gap-3 px-3 py-1.5 text-[11px]" style="color: var(--text-muted);">RUN_TEAM 왕복 {{ fmtMs(asMsg(msg).run!.elapsed_ms) }} · 태스크 합 {{ fmtMs(stepTotal(asMsg(msg))) }} — 차이는 스케줄러 체인·잡 기동</div>
                    </div>
                  </div>
                  <SqlBlock v-if="asMsg(msg).run!.sql" :code="asMsg(msg).run!.sql!" label="툴이 만든 SQL (SHOWSQL)" max-height="200px" />
                  <!-- 메타 -->
                  <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px]" style="color: var(--text-muted);">
                    <button v-if="asMsg(msg).run!.conversation_id" type="button" class="inline-flex items-center gap-1 font-mono" :title="asMsg(msg).run!.conversation_id" @click="copy(asMsg(msg).run!.conversation_id!)"><Copy :size="10" :stroke-width="1.75" />{{ shortConv(asMsg(msg).run!.conversation_id) }}</button>
                    <span>· elapsed {{ (asMsg(msg).run!.elapsed_ms ?? 0).toLocaleString() }} ms</span><span>· team {{ asMsg(msg).team }}</span><span>· multi turn {{ a.multiTurn ? 'ON' : 'OFF' }}</span>
                    <span v-if="asMsg(msg).run!.team_exec_id" class="font-mono" :title="asMsg(msg).run!.team_exec_id!">· exec {{ asMsg(msg).run!.team_exec_id!.slice(0, 8) }}…</span><span v-if="asMsg(msg).run!.log_id">· log #{{ asMsg(msg).run!.log_id }}</span>
                    <span class="ml-auto">AI · {{ asMsg(msg).timestamp }}</span>
                  </div>
                  <FeedbackBox v-if="asMsg(msg).run!.log_id && asMsg(msg).run!.success" :log-id="asMsg(msg).run!.log_id!" :existing="asMsg(msg).feedback ?? null" source="INLINE" @saved="(f) => (asMsg(msg).feedback = f)" @deleted="asMsg(msg).feedback = null" />
                </template>
              </template>
            </div>
          </div>
        </template>
      </ChatThread>
      <div class="mt-4 pt-4 flex flex-col gap-3" style="border-top: 1px solid var(--border-default);">
        <ChatComposer v-model="a.input" :icon="Bot" :busy="a.sending" :disabled="!a.team" multiline placeholder="에이전트에게 물어보세요… (Enter 전송 · Shift+Enter 줄바꿈)" send-label="실행" @send="a.send(a.input)">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-xs" style="color: var(--text-muted);">실행 설정 · Team</span>
            <div class="w-[260px]"><SearchableSelect v-model="a.team" :options="teamOptions" :searchable="false" placeholder="팀 고르기" /></div>
            <Toggle v-model="a.multiTurn" label="Multi Turn" hint="ON 이면 conversation_id 를 이어 보낸다 — RUN_TEAM 은 conversation_id 없이는 돌지 않아 OFF 면 매번 새 대화" />
            <Button size="sm" variant="secondary" @click="a.newConversation()"><MessageSquarePlus :size="13" :stroke-width="1.75" /> 새 대화</Button>
            <span v-if="a.conversationId" class="text-[11px] font-mono" style="color: var(--text-muted);">{{ shortConv(a.conversationId) }} · {{ a.turns }}턴 · 누적 {{ fmtMs(a.convTotalMs) }}</span>
            <Button variant="ghost" size="sm" class="ml-auto" title="대화 비우기" :disabled="!a.messages.length" @click="a.clear()"><Eraser :size="14" :stroke-width="1.75" /></Button>
          </div>
        </ChatComposer>
      </div>
    </Card>
  </div>
</template>
