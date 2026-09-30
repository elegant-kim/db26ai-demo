<script setup lang="ts">
import { Boxes, MessageSquareText, History, type LucideIcon } from 'lucide-vue-next'
import PageHeader from '@/components/demo/PageHeader.vue'
import SubTabs from '@/components/demo/SubTabs.vue'
import { useSubTab } from '@/composables/useSubTab'
import AgentDefine from './agent/AgentDefine.vue'
import AgentRun from './agent/AgentRun.vue'
import AgentHistory from './agent/AgentHistory.vue'

/** ⑦ Select AI Agent (Phase 4, 2026-09-30) — 정의(객체 4종) → 실행(RUN_TEAM 대화) → Agent History. */
type TabId = 'define' | 'run' | 'history'
const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: 'define', label: '정의', icon: Boxes },
  { id: 'run', label: '실행', icon: MessageSquareText },
  { id: 'history', label: 'Agent History', icon: History },
]
const { sub, set } = useSubTab<TabId>(['define', 'run', 'history'], 'define')
</script>

<template>
  <div class="flex flex-col gap-5">
    <PageHeader menu="agent" desc="DBMS_CLOUD_AI_AGENT — 툴(SQL) · 에이전트 · 태스크 · 팀이 DB 안의 객체로 있고, RUN_TEAM 한 줄이 에이전트가 도구를 골라 쓰며 답을 만든다. 「정의」에서 샘플 팀을 만들고 「실행」에서 대화, 「Agent History」에서 되짚는다." />
    <SubTabs :tabs="TABS" :model-value="sub" @update:model-value="(v: string) => set(v as TabId)" />
    <KeepAlive>
      <AgentDefine v-if="sub === 'define'" />
      <AgentRun v-else-if="sub === 'run'" />
      <AgentHistory v-else />
    </KeepAlive>
  </div>
</template>
