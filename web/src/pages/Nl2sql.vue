<script setup lang="ts">
import { MessageSquareText, Table2, type LucideIcon } from 'lucide-vue-next'
import PageHeader from '@/components/demo/PageHeader.vue'
import SubTabs from '@/components/demo/SubTabs.vue'
import { useSubTab } from '@/composables/useSubTab'
import Nl2sqlAsk from './nl2sql/Nl2sqlAsk.vue'
import Nl2sqlSchema from './nl2sql/Nl2sqlSchema.vue'

type TabId = 'ask' | 'schema'
const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: 'ask', label: '질문', icon: MessageSquareText },
  { id: 'schema', label: '스키마 · Annotation', icon: Table2 },
]
const { sub, set } = useSubTab<TabId>(['ask', 'schema'], 'ask')
</script>

<template>
  <div class="flex flex-col gap-5">
    <PageHeader menu="nl2sql" desc="자연어로 묻고, Oracle 이 DB 안에서 SQL 을 만들어 실행합니다. 프로필을 고르고 실행 모드를 바꿔 가며 같은 질문을 7가지로 풀어 보세요." />
    <SubTabs :tabs="TABS" :model-value="sub" @update:model-value="(v: string) => set(v as TabId)" />
    <KeepAlive>
      <Nl2sqlAsk v-if="sub === 'ask'" />
      <Nl2sqlSchema v-else />
    </KeepAlive>
  </div>
</template>
