<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { MessageSquareText, Terminal, Play, Eraser } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import ChatThread from '@/components/demo/ChatThread.vue'
import ChatComposer from '@/components/demo/ChatComposer.vue'
import Segmented from '@/components/demo/Segmented.vue'
import Nl2sqlAnswer from './Nl2sqlAnswer.vue'
import { ACTIONS, type Action } from '@/lib/nl2sql'
import { useNl2sqlStore, type Nl2sqlMessage } from '@/stores/nl2sql'

const s = useNl2sqlStore()
const route = useRoute()
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
const exampleOptions = computed(() => s.examples.map((q) => ({ value: q, label: q })))
const example = ref('')
function pickExample(v: string) { example.value = ''; s.input = v }
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
        <ChatComposer v-model="s.input" :icon="MessageSquareText" :busy="s.sending" :disabled="!s.profile" placeholder="자연어로 질문하세요…" send-label="질문" @send="s.send(s.input)">
          <div class="flex flex-wrap items-center gap-2">
            <Segmented :model-value="s.action" :options="actionOptions" size="sm" @update:model-value="(v: string) => (s.action = v as Action)" />
            <div class="flex-1 min-w-[240px]"><SearchableSelect :model-value="example" :options="exampleOptions" placeholder="예시 질문 고르기…" @update:model-value="pickExample" /></div>
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
  </div>
</template>
