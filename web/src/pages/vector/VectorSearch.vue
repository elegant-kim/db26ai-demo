<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Search, Eraser, Save } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import ChatThread from '@/components/demo/ChatThread.vue'
import ChatComposer from '@/components/demo/ChatComposer.vue'
import Segmented from '@/components/demo/Segmented.vue'
import SessionTabs from '@/components/demo/SessionTabs.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import VectorAnswer from './VectorAnswer.vue'
import { EXAMPLE_QUESTIONS, SEARCH_MODES, type SearchMode } from '@/lib/vector'
import { useSystemStore } from '@/stores/system'
import { useVectorStore, type VectorMessage } from '@/stores/vector'

const v = useVectorStore()
const system = useSystemStore()
const route = useRoute()
// `?mode=hybrid&q=…&run=1` — 딥링크·캡처·시연용
onMounted(() => {
  const m = route.query.mode
  if (typeof m === 'string' && SEARCH_MODES.some((x) => x.value === m)) v.mode = m as SearchMode
  void Promise.all([v.loadConfig(), v.docsLoaded ? Promise.resolve() : v.loadDocs()]).then(() => {
    const q = route.query.q
    if (typeof q === 'string' && q && route.query.run !== undefined && !v.messages.length) void v.send(q)
  })
})
const modeOptions = SEARCH_MODES.map((m) => ({ value: m.value, label: m.label, hint: m.hint }))
const providerOptions = computed(() => [{ value: '', label: '서버 기본', sub: system.llmModel }, ...system.providers.map((p) => ({ value: p.id as string, label: p.name as string, sub: p.model as string }))])
const exampleOptions = EXAMPLE_QUESTIONS.map((q) => ({ value: q, label: q }))
const example = ref('')
function pickExample(q: string) { example.value = ''; v.input = q }
const tabs = computed(() => [
  { id: 'current', label: '현재', sub: v.sourceLabel, time: v.model, closable: false },
  ...v.sessions.map((s) => ({ id: s.id, label: s.label, sub: s.source === 'database' ? 'ONNX' : 'API', time: s.timestamp, closable: true })),
])
const asMsg = (m: unknown) => m as VectorMessage
const readonly = computed(() => v.activeSession !== -1)
</script>

<template>
  <div class="w-full flex flex-col gap-4">
    <div v-if="v.docsLoaded && !v.docs.length" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-warm-soft); border-left: 3px solid var(--accent-warm); color: var(--text-primary);">아직 올린 문서가 없습니다 — 「문서 · 업로드」에서 PDF 를 올리면 청킹 → 임베딩 → 저장이 자동으로 돕니다.</div>
    <div v-if="v.configError" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ v.configError }}</div>

    <Card compact>
      <div class="flex items-center gap-2 flex-wrap mb-3">
        <SessionTabs :tabs="tabs" :model-value="v.activeSession + 1" @update:model-value="(i: number) => v.switchSession(i - 1)" @close="(i: number) => v.removeSession(i - 1)" />
        <span class="flex-1" />
        <Button v-if="!readonly && v.messages.length" variant="ghost" size="sm" title="지금 스레드를 세션 탭으로 보관" @click="v.saveSession(); v.clearCurrent()"><Save :size="14" :stroke-width="1.75" /> 세션으로 보관</Button>
        <Button v-if="!readonly && v.messages.length" variant="ghost" size="sm" title="대화 비우기" @click="v.clearCurrent()"><Eraser :size="14" :stroke-width="1.75" /></Button>
      </div>

      <ChatThread :messages="v.visibleMessages" max-height="calc(100vh - 440px)" min-height="160px">
        <template #assistant="{ msg }"><VectorAnswer :msg="asMsg(msg)" :readonly="readonly" /></template>
      </ChatThread>
      <EmptyState v-if="!v.visibleMessages.length" :icon="Search" title="문서에 대해 자연어로 물어보세요" desc="의미 검색은 단어가 달라도 뜻으로 찾고, 하이브리드(26ai)는 키워드 점수까지 한 SQL 에서 합칩니다. 비교 모드로 둘을 나란히 보세요." compact />

      <div v-if="!readonly" class="mt-4 pt-4 flex flex-col gap-3" style="border-top: 1px solid var(--border-default);">
        <ChatComposer v-model="v.input" :busy="v.searching" placeholder="문서에 대해 자연어로 질문하세요…" send-label="검색" @send="v.send(v.input)">
          <div class="flex flex-wrap items-center gap-2">
            <Segmented :model-value="v.mode" :options="modeOptions" size="sm" @update:model-value="(m: string) => (v.mode = m as SearchMode)" />
            <label class="flex items-center gap-1.5 text-xs" style="color: var(--text-secondary);">Top-K
              <input v-model.number="v.topK" type="number" min="1" max="20" class="w-14 rounded-md px-2 py-1 text-xs" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" />
            </label>
            <div class="w-[190px]"><SearchableSelect v-model="v.provider" :options="providerOptions" placeholder="LLM" :searchable="false" /></div>
            <div class="flex-1 min-w-[220px]"><SearchableSelect :model-value="example" :options="exampleOptions" placeholder="예시 질문 고르기…" @update:model-value="pickExample" /></div>
          </div>
        </ChatComposer>
        <div class="text-[11px]" style="color: var(--text-muted);">{{ SEARCH_MODES.find((m) => m.value === v.mode)?.hint }} · 임베딩 {{ v.sourceLabel }} · {{ v.model || '—' }}</div>
      </div>
      <p v-else class="text-xs mt-3 mb-0" style="color: var(--text-muted);">보관된 세션입니다 — 「현재」 탭에서 새로 검색하세요.</p>
    </Card>
  </div>
</template>
