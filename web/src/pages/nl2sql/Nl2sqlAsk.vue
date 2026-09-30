<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { MessageSquareText, Terminal, Play, Eraser, MessageSquarePlus, Copy, BookmarkPlus, Pencil, Trash2, FlaskConical, GitCompare, PanelLeftClose, PanelLeftOpen, SlidersHorizontal } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import Toggle from '@/components/ui/Toggle.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import ChatThread from '@/components/demo/ChatThread.vue'
import ChatComposer from '@/components/demo/ChatComposer.vue'
import Nl2sqlAnswer from './Nl2sqlAnswer.vue'
import { ACTIONS, shortConv, type Action } from '@/lib/nl2sql'
import { useSystemStore } from '@/stores/system'
import { useNl2sqlStore, type Nl2sqlMessage } from '@/stores/nl2sql'

const s = useNl2sqlStore()
const system = useSystemStore()
const route = useRoute()
// 2단 레이아웃(2026-10-01 사용자 요청): 왼쪽 「실행 설정」 패널은 접을 수 있고, 시연 중엔 접어 대화만 보인다. 전역 사이드바는 두지 않는다(설계서 05).
const PANEL_KEY = 'db26ai.nl2sql.panel'
const panelOpen = ref(true)
try { const v = localStorage.getItem(PANEL_KEY); if (v !== null) panelOpen.value = v === '1' } catch { /* noop */ }
function togglePanel() { panelOpen.value = !panelOpen.value; try { localStorage.setItem(PANEL_KEY, panelOpen.value ? '1' : '0') } catch { /* noop */ } }
async function copyConv() { if (!s.conversationId) return; try { await navigator.clipboard.writeText(s.conversationId); system.toast('conversation_id 복사', 'success') } catch { system.toast(s.conversationId, 'info') } }
// `?profile=…&action=runsql&q=…&run=1` — 딥링크·캡처·시연용 (설계서 05 §3.3 의 run 규약 확장). 프로필은 스토어 init 이 받는다.
onMounted(() => {
  const a = route.query.action
  if (typeof a === 'string' && ACTIONS.some((x) => x.value === a)) s.action = a as Action
  void s.init(route.query.profile).then(() => {
    const q = route.query.q
    if (typeof q === 'string' && q && route.query.run !== undefined) void s.send(q)
  })
})

// 실행 모드 7종은 2026-10-01 부터 왼쪽 패널의 세로 목록(확인 포인트 ① 의 세그먼트 한 줄은 2단 레이아웃으로 대체)
// 예시 질문 = DB 프리셋(1-D). 드롭다운은 제목 + 질문(sub). 고르면 질문·액션이 입력줄에 들어가고, 그 프리셋이 「수정/삭제」 대상이 된다
const exampleOptions = computed(() => (s.presets.length
  ? s.presets.map((p) => ({ value: String(p.ID), label: p.TITLE, sub: p.QUESTION }))
  : s.examples.map((q) => ({ value: q, label: q }))))
const example = ref('')
const picked = ref<number | null>(null)
const presetTitle = ref('')
const confirmDelete = ref(false)
function pickExample(v: string) {
  const p = s.presets.find((x) => String(x.ID) === v)
  if (p) { picked.value = p.ID; presetTitle.value = p.TITLE; s.input = p.QUESTION; if (p.ACTION) s.action = p.ACTION as Action }
  else { picked.value = null; s.input = v }
  example.value = v
}
const pickedPreset = computed(() => s.presets.find((p) => p.ID === picked.value) ?? null)
async function addPreset() {
  const q = s.input.trim(); if (!q) { system.toast('저장할 질문을 입력줄에 먼저 적어 주세요', 'warn'); return }
  if (await s.savePreset({ title: presetTitle.value.trim() || q.slice(0, 40), question: q, action: s.action })) { presetTitle.value = ''; picked.value = null; example.value = '' }
}
async function editPreset() {
  const p = pickedPreset.value; if (!p) return
  const q = s.input.trim() || p.QUESTION
  await s.savePreset({ title: presetTitle.value.trim() || p.TITLE, question: q, action: s.action, profile_name: p.PROFILE_NAME }, p.ID)
}
async function dropPreset() { const p = pickedPreset.value; if (!p) return; if (await s.removePreset(p.ID)) { picked.value = null; presetTitle.value = ''; example.value = '' } confirmDelete.value = false }
const asMsg = (m: unknown) => m as Nl2sqlMessage
// 3-C 프로필 비교 — 체크박스 팝오버. 기본 선택: 현재 프로필 + 목록의 다음 하나
const comparePick = ref(false)
function toggleTarget(p: string) { const t = s.compareTargets; const i = t.indexOf(p); if (i >= 0) t.splice(i, 1); else if (t.length < 3) t.push(p); else system.toast('최대 3개', 'warn') }
function openCompare() {
  if (!s.compareTargets.length) { const names = s.profiles.map((p) => p.profile_name); const other = names.find((n) => n !== s.profile); s.compareTargets = other ? [s.profile, other] : [s.profile] }
  comparePick.value = !comparePick.value
}
</script>

<template>
  <div class="w-full flex flex-col gap-4">
    <div v-if="s.lastError" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ s.lastError }}</div>

    <div class="flex gap-4 items-start">
      <!-- ── 왼쪽: 실행 설정 패널 (접이식) ── -->
      <aside v-if="panelOpen" class="shrink-0 w-[300px] flex flex-col gap-3">
        <Card compact>
          <template #header><div class="flex items-center gap-1.5 text-sm font-semibold" style="color: var(--text-primary);"><SlidersHorizontal :size="15" :stroke-width="1.75" /> 실행 설정</div></template>
          <template #actions><button type="button" class="p-1 rounded" style="color: var(--text-muted);" title="패널 접기 — 시연 중엔 대화만" @click="togglePanel"><PanelLeftClose :size="16" :stroke-width="1.75" /></button></template>

          <!-- 실행 모드 -->
          <section class="flex flex-col gap-1.5">
            <div class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">실행 모드 (action)</div>
            <div class="flex flex-col gap-0.5">
              <button v-for="a in ACTIONS" :key="a.value" type="button" class="flex items-center gap-2 px-2 py-1.5 rounded-md text-left text-xs" :title="a.hint"
                :style="{ background: s.action === a.value ? 'var(--accent-primary-soft)' : 'transparent', color: s.action === a.value ? 'var(--accent-primary)' : 'var(--text-secondary)' }" @click="s.action = a.value">
                <span class="font-mono w-[90px] shrink-0">{{ a.value }}</span><span class="truncate" :style="{ color: s.action === a.value ? 'var(--accent-primary)' : 'var(--text-muted)' }">{{ a.label.replace(/^[a-z]+\((.*)\)$/, '$1') }}</span>
              </button>
            </div>
          </section>

          <!-- 예시 질문 · 프리셋 -->
          <section class="flex flex-col gap-1.5 mt-3 pt-3" style="border-top: 1px solid var(--border-default);">
            <div class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">예시 질문 · 프리셋 <span class="normal-case font-normal">({{ s.presets.length }})</span></div>
            <SearchableSelect :model-value="example" :options="exampleOptions" placeholder="고르면 입력줄로…" @update:model-value="pickExample" />
            <input v-model="presetTitle" placeholder="저장할 제목 (비우면 질문 앞 40자)" class="rounded-md px-2.5 py-1.5 text-xs" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" />
            <div class="flex items-center gap-1">
              <Button size="sm" variant="secondary" :busy="s.presetBusy" :disabled="!s.input.trim()" title="입력줄의 질문을 프리셋으로 추가" @click="addPreset"><BookmarkPlus :size="13" :stroke-width="1.75" /> 추가</Button>
              <Button size="sm" variant="secondary" :busy="s.presetBusy" :disabled="!pickedPreset" title="고른 프리셋을 입력줄·제목·액션으로 덮어쓴다" @click="editPreset"><Pencil :size="13" :stroke-width="1.75" /> 수정</Button>
              <Button size="sm" variant="ghost" :disabled="!pickedPreset || s.presetBusy" title="고른 프리셋 삭제" @click="confirmDelete = true"><Trash2 :size="13" :stroke-width="1.75" /></Button>
            </div>
            <div class="text-[11px] truncate" style="color: var(--text-muted);">{{ pickedPreset ? `선택: #${pickedPreset.ID} ${pickedPreset.TITLE}` : (s.presets.length ? '범위: 프로필 이름 패턴' : '내장 예시(폴백)') }}</div>
          </section>

          <!-- 대화 -->
          <section class="flex flex-col gap-2 mt-3 pt-3" style="border-top: 1px solid var(--border-default);">
            <div class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">대화 (conversation)</div>
            <Toggle v-model="s.multiTurn" label="Multi Turn" hint="ON 이면 앞 질문·답을 이어받는 대화(conversation)로 묻는다 — GENERATE(params => conversation_id)" />
            <label class="inline-flex items-center gap-1.5 text-xs select-none" :style="{ color: s.multiTurn ? 'var(--text-secondary)' : 'var(--text-muted)', opacity: s.multiTurn ? 1 : 0.5 }" title="OFF 면 이번 질문만 대화 없이 독립 실행한다 (대화는 그대로 보관)">
              <input v-model="s.chain" type="checkbox" :disabled="!s.multiTurn" /> 이어서 질문하기
            </label>
            <Toggle v-model="s.resetOnSuccess" :disabled="!s.multiTurn" label="정상답변시 대화초기화" hint="ON 이면 성공한 답변 뒤에 conversation 을 버리고 다음 질문은 새 대화로 시작한다" />
            <div class="flex items-center gap-2">
              <Button size="sm" variant="secondary" :disabled="!s.multiTurn" title="conversation_id 를 버리고 새로 시작 (DB 의 대화 객체는 이력 뷰에 남는다)" @click="s.newConversation()"><MessageSquarePlus :size="13" :stroke-width="1.75" /> 새 대화</Button>
              <button v-if="s.conversationId" type="button" class="inline-flex items-center gap-1 text-[11px] font-mono" style="color: var(--text-muted);" :title="`conversation_id ${s.conversationId} — 클릭하면 복사`" @click="copyConv"><Copy :size="11" :stroke-width="1.75" /> {{ shortConv(s.conversationId) }} · {{ s.convTurns }}턴</button>
              <span v-else class="text-[11px]" style="color: var(--text-muted);">{{ s.multiTurn ? '첫 질문에서 발급' : '단발 실행' }}</span>
            </div>
          </section>

          <!-- 도구 -->
          <section class="flex flex-col gap-1.5 mt-3 pt-3" style="border-top: 1px solid var(--border-default);">
            <div class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">도구 — 입력줄의 질문으로</div>
            <Button size="sm" variant="secondary" class="justify-start" :busy="s.scenarioRunning" :disabled="s.sending" title="① Annotation 없이 → ② 적용 → ③ 피드백 반영 으로 세 번 풀어 나란히. 프로필 속성을 잠시 바꾸고 끝나면 복원. 1분 안팎" @click="s.input.trim() ? s.runScenario(s.input) : system.toast('오른쪽 입력줄에 질문을 먼저 적어 주세요 — 그 질문으로 ①②③ 을 돌립니다', 'warn')"><FlaskConical :size="13" :stroke-width="1.75" /> 정확도 개선 시나리오</Button>
            <div class="relative">
              <Button size="sm" variant="secondary" class="justify-start w-full" :busy="s.compareRunning" :disabled="s.sending" title="같은 질문을 고른 프로필 2~3개로 순차 실행해 SQL·결과·소요를 나란히" @click="s.profiles.length < 2 ? system.toast('비교하려면 프로필이 2개 이상 있어야 합니다', 'warn') : openCompare()"><GitCompare :size="13" :stroke-width="1.75" /> 프로필 비교{{ s.compareTargets.length ? ` (${s.compareTargets.length})` : '' }}</Button>
              <div v-if="comparePick" class="mt-1 rounded-md p-2 flex flex-col gap-1" style="background: var(--bg-elevated); border: 1px solid var(--border-strong);">
                <div class="text-[11px] px-1" style="color: var(--text-muted);">비교할 프로필 (2~3개)</div>
                <label v-for="p in s.profiles" :key="p.profile_name" class="flex items-center gap-2 text-xs px-1 py-0.5 rounded cursor-pointer" style="color: var(--text-primary);"><input type="checkbox" :checked="s.compareTargets.includes(p.profile_name)" @change="toggleTarget(p.profile_name)" /> {{ p.profile_name }}</label>
                <div v-if="!s.input.trim()" class="text-[11px] px-1" style="color: var(--accent-warm);">오른쪽 입력줄에 질문을 먼저 적어 주세요</div>
                <div class="flex justify-end gap-1 mt-1"><Button size="sm" variant="ghost" @click="comparePick = false">닫기</Button><Button size="sm" :disabled="s.compareTargets.length < 2 || !s.input.trim()" @click="comparePick = false; s.runCompare(s.input, s.compareTargets)"><Play :size="12" :stroke-width="2" /> 실행</Button></div>
              </div>
            </div>
          </section>
        </Card>
      </aside>

      <!-- ── 오른쪽: 대화 + 입력 ── -->
      <Card compact class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-2">
          <button v-if="!panelOpen" type="button" class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md" style="color: var(--text-secondary); background: var(--bg-surface);" title="실행 설정 패널 펴기" @click="togglePanel"><PanelLeftOpen :size="14" :stroke-width="1.75" /> 실행 설정</button>
          <Badge tone="code">{{ s.action }}</Badge><span class="text-[11px]" style="color: var(--text-muted);">{{ ACTIONS.find((a) => a.value === s.action)?.hint }}</span>
          <span class="ml-auto text-[11px]" style="color: var(--text-muted);">프로필 {{ s.profile || '—' }}<template v-if="s.multiTurn && s.conversationId"> · 대화 {{ shortConv(s.conversationId) }}</template></span>
        </div>
        <ChatThread :messages="s.messages" max-height="calc(100vh - 380px)" min-height="260px" :empty-text="s.profile ? `${s.profile} 에게 자연어로 물어보세요 — 실행 모드를 바꾸면 같은 질문을 다르게 풉니다` : '프로필을 불러오는 중…'">
          <template #user="{ msg }">
            <div class="max-w-[80%] rounded-xl px-3.5 py-2 text-sm" style="background: var(--accent-primary); color: var(--text-on-accent);">
              <div v-if="asMsg(msg).isSql" class="text-[10px] font-semibold tracking-wide opacity-80 mb-0.5">SQL 직접 실행</div>
              <div v-else-if="asMsg(msg).prevPrompt" class="text-[11px] opacity-75 mb-0.5 truncate">↩ 이전: {{ asMsg(msg).prevPrompt }}</div>
              <div class="whitespace-pre-wrap" :class="asMsg(msg).isSql ? 'font-mono text-xs' : ''">{{ msg.content }}</div>
              <div class="text-[10px] opacity-70 mt-1 text-right">{{ asMsg(msg).timestamp }}</div>
            </div>
          </template>
          <template #assistant="{ msg }"><Nl2sqlAnswer :msg="asMsg(msg)" /></template>
        </ChatThread>
        <div class="mt-4 pt-4 flex flex-col gap-3" style="border-top: 1px solid var(--border-default);">
          <ChatComposer v-model="s.input" :icon="MessageSquareText" :busy="s.sending" :disabled="!s.profile" multiline placeholder="자연어로 질문하세요… (Enter 전송 · Shift+Enter 줄바꿈)" send-label="질문" @send="s.send(s.input)" />
          <!-- SQL 직접 실행 — 같은 부품, `>_` · mono · secondary 가 "여긴 SQL" -->
          <div class="flex items-center gap-2">
            <ChatComposer v-model="s.sqlInput" class="flex-1 min-w-0" :icon="Terminal" :send-icon="Play" mono send-variant="secondary" :busy="s.sqlRunning" :disabled="!s.profile"
              placeholder="SELECT 문을 직접 실행 · SELECT AI <액션> <질문> 도 됩니다 (WITH 절은 거부됨)" send-label="실행" @send="s.runSql(s.sqlInput)" />
            <Button variant="ghost" title="대화 비우기" :disabled="!s.asked" @click="s.clear()"><Eraser :size="14" :stroke-width="1.75" /></Button>
          </div>
        </div>
      </Card>
    </div>

    <ConfirmModal :open="confirmDelete" title="프리셋 삭제" confirm-label="삭제" danger :busy="s.presetBusy" @confirm="dropPreset" @cancel="confirmDelete = false">
      <b>{{ pickedPreset?.TITLE }}</b> 을(를) AI_PROMPT_PRESET 에서 지웁니다. 되돌릴 수 없습니다.
    </ConfirmModal>
  </div>
</template>
