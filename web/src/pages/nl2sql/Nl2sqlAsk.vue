<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { MessageSquareText, Terminal, Eraser } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import ChatThread from '@/components/demo/ChatThread.vue'
import ChatComposer from '@/components/demo/ChatComposer.vue'
import Segmented from '@/components/demo/Segmented.vue'
import VersusBox from '@/components/demo/VersusBox.vue'
import Nl2sqlAnswer from './Nl2sqlAnswer.vue'
import { ACTIONS, type Action } from '@/lib/nl2sql'
import { useNl2sqlStore, type Nl2sqlMessage } from '@/stores/nl2sql'

const s = useNl2sqlStore()
const route = useRoute()
// `?profile=…&action=runsql&q=…&run=1` — 딥링크·캡처·시연용 (설계서 05 §3.3 의 run 규약 확장)
onMounted(() => {
  const a = route.query.action
  if (typeof a === 'string' && ACTIONS.some((x) => x.value === a)) s.action = a as Action
  void s.init().then(async () => {
    const p = route.query.profile
    if (typeof p === 'string' && p && p !== s.profile && s.profiles.some((x) => x.profile_name === p)) await s.selectProfile(p)
    const q = route.query.q
    if (typeof q === 'string' && q && route.query.run !== undefined) void s.send(q)
  })
})

// 사용자 확인 포인트 ① — 실행 모드 7종의 배치: A 세그먼트(기본) vs B 셀렉트 (`?modeui=select`) 두 안을 같은 화면에서 비교한다
const modeUi = computed(() => (route.query.modeui === 'select' ? 'select' : 'segment'))
const actionOptions = ACTIONS.map((a) => ({ value: a.value, label: a.label, hint: a.hint, sub: a.hint }))
const exampleOptions = computed(() => s.examples.map((q) => ({ value: q, label: q })))
const example = ref('')
function pickExample(v: string) { example.value = ''; s.input = v }
const asMsg = (m: unknown) => m as Nl2sqlMessage
</script>

<template>
  <div class="w-full max-w-[960px] mx-auto flex flex-col gap-4">
    <!-- 첫 질문 전에만: Select AI 의 차별성 -->
    <Card v-if="!s.asked" title="Oracle Select AI — 자연어로 데이터를 질의하다" :icon="MessageSquareText" compact>
      <VersusBox left-title="기존 방식" left-desc="개발자가 SQL 을 직접 작성. 스키마 이해 필수. 앱마다 쿼리 개발."
        right-title="Oracle Select AI" right-desc="자연어 → DB 가 SQL 을 자동 생성. AI 프로필이 스키마를 참조. 프로필 하나로 다양한 질문에 대응.">
        SQL 을 몰라도 데이터를 물을 수 있습니다. <strong style="color: var(--text-primary);">DB 안에서</strong> <code class="font-mono">DBMS_CLOUD_AI.GENERATE</code> 한 줄로 동작하고,
        테이블·컬럼의 <strong style="color: var(--text-primary);">Display Annotation</strong> 이 AI 의 정확도를 끌어올립니다 (「스키마·Annotation」 탭).
      </VersusBox>
    </Card>

    <div v-if="s.lastError" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ s.lastError }}</div>

    <Card compact>
      <ChatThread :messages="s.messages" max-height="calc(100vh - 420px)" min-height="200px" empty-text="프로필을 불러오는 중…">
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
        <ChatComposer v-model="s.input" :busy="s.sending" :disabled="!s.profile" placeholder="자연어로 질문하세요…" send-label="질문" @send="s.send(s.input)">
          <div class="flex flex-wrap items-center gap-2">
            <div class="w-[220px]"><SearchableSelect :model-value="s.profile" :options="s.profileOptions" placeholder="AI 프로필" :searchable="false" @update:model-value="(v: string) => s.selectProfile(v)" /></div>
            <Segmented v-if="modeUi === 'segment'" :model-value="s.action" :options="actionOptions" size="sm" @update:model-value="(v: string) => (s.action = v as Action)" />
            <div v-else class="w-[200px]"><SearchableSelect :model-value="s.action" :options="actionOptions" placeholder="실행 모드" :searchable="false" @update:model-value="(v: string) => (s.action = v as Action)" /></div>
            <div class="flex-1 min-w-[240px]"><SearchableSelect :model-value="example" :options="exampleOptions" placeholder="예시 질문 고르기…" @update:model-value="pickExample" /></div>
          </div>
        </ChatComposer>
        <div class="flex items-center gap-2">
          <Terminal :size="14" :stroke-width="1.75" style="color: var(--text-muted);" />
          <input v-model="s.sqlInput" :disabled="s.sqlRunning" placeholder="SELECT 문을 직접 실행 (WITH 절은 거부됨)" class="flex-1 min-w-0 rounded-md px-3 py-1.5 text-xs font-mono"
            style="background: var(--bg-elevated); border: 1px solid var(--border-default); color: var(--text-primary);" @keydown.enter.prevent="s.runSql(s.sqlInput)" />
          <Button variant="secondary" size="sm" :busy="s.sqlRunning" :disabled="!s.sqlInput.trim()" @click="s.runSql(s.sqlInput)">실행</Button>
          <Button variant="ghost" size="sm" title="대화 비우기" :disabled="!s.asked" @click="s.clear()"><Eraser :size="14" :stroke-width="1.75" /></Button>
        </div>
        <div class="flex items-center gap-2 text-[11px]" style="color: var(--text-muted);">
          <Badge tone="code">{{ s.action }}</Badge><span>{{ ACTIONS.find((a) => a.value === s.action)?.hint }}</span>
          <span class="ml-auto">프로필 {{ s.profile || '—' }}</span>
        </div>
      </div>
    </Card>
  </div>
</template>
