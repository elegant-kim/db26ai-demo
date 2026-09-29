<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { MessageSquareText, Terminal, Play, Eraser, MessageSquarePlus, Copy, BookmarkPlus, Pencil, Trash2 } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import Toggle from '@/components/ui/Toggle.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import ChatThread from '@/components/demo/ChatThread.vue'
import ChatComposer from '@/components/demo/ChatComposer.vue'
import Segmented from '@/components/demo/Segmented.vue'
import Nl2sqlAnswer from './Nl2sqlAnswer.vue'
import { ACTIONS, shortConv, type Action } from '@/lib/nl2sql'
import { useSystemStore } from '@/stores/system'
import { useNl2sqlStore, type Nl2sqlMessage } from '@/stores/nl2sql'

const s = useNl2sqlStore()
const system = useSystemStore()
const route = useRoute()
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

// 확인 포인트 ① (2026-09-05): 실행 모드 7종은 세그먼트 한 줄로 확정 — B 셀렉트 안은 git 125bfdd 에 남아 있다
const actionOptions = ACTIONS.map((a) => ({ value: a.value, label: a.label, hint: a.hint }))
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
</script>

<template>
  <div class="w-full flex flex-col gap-4">
    <div v-if="s.lastError" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ s.lastError }}</div>

    <Card compact>
      <ChatThread :messages="s.messages" max-height="calc(100vh - 420px)" min-height="200px" :empty-text="s.profile ? `${s.profile} 에게 자연어로 물어보세요 — 실행 모드를 바꾸면 같은 질문을 다르게 풉니다` : '프로필을 불러오는 중…'">
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
        <ChatComposer v-model="s.input" :icon="MessageSquareText" :busy="s.sending" :disabled="!s.profile" multiline placeholder="자연어로 질문하세요… (Enter 전송 · Shift+Enter 줄바꿈)" send-label="질문" @send="s.send(s.input)">
          <div class="flex flex-wrap items-center gap-2">
            <Segmented :model-value="s.action" :options="actionOptions" size="sm" @update:model-value="(v: string) => (s.action = v as Action)" />
            <div class="flex-1 min-w-[240px]"><SearchableSelect :model-value="example" :options="exampleOptions" placeholder="예시 질문 고르기… (DB 프리셋)" @update:model-value="pickExample" /></div>
          </div>
          <!-- 저장 질문 프리셋 (1-D): 입력줄의 질문을 제목과 함께 저장 · 고른 프리셋을 수정/삭제. 프로필 범위는 SH → '%SH%' -->
          <div class="flex flex-wrap items-center gap-2">
            <input v-model="presetTitle" placeholder="저장할 제목 (비우면 질문 앞 40자)" class="rounded-md px-2.5 py-1.5 text-xs flex-1 min-w-[200px] max-w-[360px]" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" />
            <Button size="sm" variant="secondary" :busy="s.presetBusy" :disabled="!s.input.trim()" title="입력줄의 질문을 프리셋으로 추가" @click="addPreset"><BookmarkPlus :size="13" :stroke-width="1.75" /> 추가</Button>
            <Button size="sm" variant="secondary" :busy="s.presetBusy" :disabled="!pickedPreset" title="고른 프리셋을 입력줄·제목·액션으로 덮어쓴다" @click="editPreset"><Pencil :size="13" :stroke-width="1.75" /> 수정</Button>
            <Button size="sm" variant="ghost" :disabled="!pickedPreset || s.presetBusy" title="고른 프리셋 삭제" @click="confirmDelete = true"><Trash2 :size="13" :stroke-width="1.75" /> 삭제</Button>
            <span class="text-[11px]" style="color: var(--text-muted);">{{ pickedPreset ? `선택: #${pickedPreset.ID} ${pickedPreset.TITLE}` : `프리셋 ${s.presets.length}건 · 범위 ${s.presets.length ? '프로필 이름 패턴' : '내장 예시(폴백)'}` }}</span>
          </div>
          <!-- 멀티턴 (PoC 1-A): 대화 ID 는 DB 의 conversation 객체, 브라우저가 들고 매 질문에 실어 보낸다 -->
          <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5">
            <Toggle v-model="s.multiTurn" label="Multi Turn" hint="ON 이면 앞 질문·답을 이어받는 대화(conversation)로 묻는다 — GENERATE(params => conversation_id)" />
            <label class="inline-flex items-center gap-1.5 text-xs select-none" :style="{ color: s.multiTurn ? 'var(--text-secondary)' : 'var(--text-muted)', opacity: s.multiTurn ? 1 : 0.5 }" title="OFF 면 이번 질문만 대화 없이 독립 실행한다 (대화는 그대로 보관)">
              <input v-model="s.chain" type="checkbox" :disabled="!s.multiTurn" class="accent-[var(--accent-primary)]" /> 이어서 질문하기
            </label>
            <Toggle v-model="s.resetOnSuccess" :disabled="!s.multiTurn" label="정상답변시 대화초기화" hint="ON 이면 성공한 답변 뒤에 conversation 을 버리고 다음 질문은 새 대화로 시작한다" />
            <Button size="sm" variant="secondary" :disabled="!s.multiTurn" title="conversation_id 를 버리고 새로 시작 (DB 의 대화 객체는 이력 뷰에 남는다)" @click="s.newConversation()"><MessageSquarePlus :size="13" :stroke-width="1.75" /> 새 대화</Button>
            <button v-if="s.conversationId" type="button" class="inline-flex items-center gap-1 text-[11px] font-mono" style="color: var(--text-muted);" :title="`conversation_id ${s.conversationId} — 클릭하면 복사`" @click="copyConv">
              <Copy :size="11" :stroke-width="1.75" /> {{ shortConv(s.conversationId) }} · {{ s.convTurns }}턴
            </button>
            <span v-else class="text-[11px]" style="color: var(--text-muted);">{{ s.multiTurn ? '대화 없음 — 첫 질문에서 발급' : '단발 실행' }}</span>
          </div>
        </ChatComposer>
        <!-- SQL 직접 실행 — 위 자연어 줄과 같은 부품(같은 높이·글자·버튼 크기). `>_` · mono · secondary 버튼이 "여긴 SQL" 이라고 말한다 -->
        <div class="flex items-center gap-2">
          <ChatComposer v-model="s.sqlInput" class="flex-1 min-w-0" :icon="Terminal" :send-icon="Play" mono send-variant="secondary" :busy="s.sqlRunning" :disabled="!s.profile"
            placeholder="SELECT 문을 직접 실행 · SELECT AI <액션> <질문> 도 됩니다 (WITH 절은 거부됨)" send-label="실행" @send="s.runSql(s.sqlInput)" />
          <Button variant="ghost" title="대화 비우기" :disabled="!s.asked" @click="s.clear()"><Eraser :size="14" :stroke-width="1.75" /></Button>
        </div>
        <div class="flex items-center gap-2 text-[11px]" style="color: var(--text-muted);">
          <Badge tone="code">{{ s.action }}</Badge><span>{{ ACTIONS.find((a) => a.value === s.action)?.hint }}</span>
          <span class="ml-auto">프로필 {{ s.profile || '—' }}</span>
        </div>
      </div>
    </Card>
    <ConfirmModal :open="confirmDelete" title="프리셋 삭제" confirm-label="삭제" danger :busy="s.presetBusy" @confirm="dropPreset" @cancel="confirmDelete = false">
      <b>{{ pickedPreset?.TITLE }}</b> 을(를) AI_PROMPT_PRESET 에서 지웁니다. 되돌릴 수 없습니다.
    </ConfirmModal>
  </div>
</template>
