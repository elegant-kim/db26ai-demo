<script setup lang="ts">
/** 정의 탭 — 팀·에이전트·태스크·툴 목록 + 속성 JSON, 「샘플 팀 만들기」(PL/SQL 4개 표시), 삭제. */
import { computed, onMounted, ref } from 'vue'
import { Boxes, Bot, ListChecks, Wrench, Plus, Trash2, ChevronDown, ChevronRight } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import { useAgentStore } from '@/stores/agent'
import { useNl2sqlStore } from '@/stores/nl2sql'

const a = useAgentStore()
const s = useNl2sqlStore()
const confirmDrop = ref(false)
const showSteps = ref(true)
const baseProfile = ref('GEMINI_SH_PROFILE')
onMounted(() => { void a.loadDefs(); void s.init().then(() => { if (s.profile && !s.profiles.some((p) => p.profile_name === baseProfile.value)) baseProfile.value = s.profile }) })
const profileOptions = computed(() => s.profiles.map((p) => ({ value: p.profile_name, label: p.profile_name })))
const groups = computed(() => [
  { key: 'teams', title: '팀 (Team)', icon: Boxes, items: a.defs?.teams ?? [], hint: 'agents[{name, task}] · process(sequential)' },
  { key: 'agents', title: '에이전트 (Agent)', icon: Bot, items: a.defs?.agents ?? [], hint: 'profile_name · role' },
  { key: 'tasks', title: '태스크 (Task)', icon: ListChecks, items: a.defs?.tasks ?? [], hint: 'instruction · tools[]' },
  { key: 'tools', title: '툴 (Tool)', icon: Wrench, items: a.defs?.tools ?? [], hint: 'tool_type(SQL) · tool_params{profile_name, action}' },
])
const pretty = (v: unknown) => JSON.stringify(v, null, 2)
const hasDemo = computed(() => !!a.defs?.teams.some((t) => t.name === a.defs?.demo.team))
</script>

<template>
  <div class="flex flex-col gap-4">
    <div v-if="a.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ a.error }}</div>
    <Card title="샘플 팀 만들기" subtitle="PL/SQL 4개 — ① SQL 툴 → ② 에이전트 → ③ 태스크 → ④ 팀(sequential). Agent 는 provider=google 네이티브 프로필이 필요해, 고른 프로필이 OpenAI 호환이면 같은 크리덴셜·테이블로 GEMINI_SH_NATIVE 를 자동으로 만든다" :icon="Plus">
      <template #actions>
        <div class="w-[220px]"><SearchableSelect v-model="baseProfile" :options="profileOptions" :searchable="false" placeholder="기준 프로필" /></div>
        <Button size="sm" :busy="a.demoBusy" :disabled="!baseProfile" @click="a.makeDemo(baseProfile)"><Plus :size="14" :stroke-width="2" /> {{ hasDemo ? '다시 만들기' : '샘플 팀 만들기' }}</Button>
        <Button v-if="hasDemo" size="sm" variant="danger" :disabled="a.demoBusy" @click="confirmDrop = true"><Trash2 :size="13" :stroke-width="1.75" /> 삭제</Button>
      </template>
      <p class="text-xs m-0" style="color: var(--text-secondary);">실측(2026-09-30): OpenAI 호환(Gemini) 엔드포인트로는 Agent 의 마지막 LLM 호출이 <span class="font-mono">HTTP 400 "Requests ending with a model turn are not supported"</span> 로 실패한다. 네이티브 프로필로는 멀티턴("그중 …")까지 된다. 태스크의 <span class="font-mono">input: "{query}"</span> 자리표시자는 ORA-20051 — 사용자 질문은 자동으로 첫 태스크에 들어간다.</p>
      <template v-if="a.demoSteps.length">
        <button type="button" class="mt-3 inline-flex items-center gap-1 text-xs" style="color: var(--text-secondary);" @click="showSteps = !showSteps"><component :is="showSteps ? ChevronDown : ChevronRight" :size="13" :stroke-width="2" /> 실행한 PL/SQL {{ a.demoSteps.length }}개</button>
        <div v-if="showSteps" class="mt-2 flex flex-col gap-2"><SqlBlock v-for="st in a.demoSteps" :key="st.label" :code="st.plsql" :label="st.label" max-height="200px" /></div>
      </template>
    </Card>

    <LoadingBlock v-if="a.defsLoading && !a.defs" compact label="정의를 읽는 중…" />
    <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
      <Card v-for="g in groups" :key="g.key" :title="g.title" :subtitle="g.hint" :icon="g.icon">
        <template #actions><Badge>{{ g.items.length }}</Badge></template>
        <EmptyState v-if="!g.items.length" compact :icon="g.icon" title="없음" desc="위 「샘플 팀 만들기」로 만들거나 DBMS_CLOUD_AI_AGENT.CREATE_* 로 직접 만든다." />
        <div v-else class="flex flex-col gap-2">
          <details v-for="it in g.items" :key="it.name" class="rounded-md px-3 py-2" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
            <summary class="cursor-pointer flex items-center gap-2 text-sm select-none"><span class="font-mono font-semibold" style="color: var(--text-primary);">{{ it.name }}</span><Badge :tone="it.status === 'ENABLED' ? 'positive' : 'default'">{{ it.status }}</Badge><span class="text-xs truncate" style="color: var(--text-muted);">{{ it.description }}</span></summary>
            <SqlBlock :code="pretty(it.attributes)" lang="json" label="attributes (USER_AI_AGENT_*_ATTRIBUTES)" max-height="260px" class="mt-2" />
          </details>
        </div>
      </Card>
    </div>
    <ConfirmModal :open="confirmDrop" title="샘플 팀 삭제" confirm-label="삭제" danger :busy="a.demoBusy" @confirm="a.dropDemo(); confirmDrop = false" @cancel="confirmDrop = false">팀 · 태스크 · 에이전트 · 툴을 DROP 합니다(프로필은 남깁니다). 실행 이력은 뷰에 남습니다.</ConfirmModal>
  </div>
</template>
