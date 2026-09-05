<script setup lang="ts">
import { Lock, Zap, type LucideIcon } from 'lucide-vue-next'
import PageHeader from '@/components/demo/PageHeader.vue'
import SubTabs from '@/components/demo/SubTabs.vue'
import RecentQueriesPanel from '@/components/demo/RecentQueriesPanel.vue'
import { useSubTab } from '@/composables/useSubTab'
import LockFree from './productivity/LockFree.vue'
import PriorityTx from './productivity/PriorityTx.vue'

type TabId = 'lockfree' | 'priority'
const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: 'lockfree', label: 'Lock-Free Reservations', icon: Lock },
  { id: 'priority', label: 'Priority Transactions', icon: Zap },
]
const { sub, set } = useSubTab<TabId>(['lockfree', 'priority'], 'lockfree')
</script>

<template>
  <div class="flex flex-col gap-5">
    <PageHeader menu="productivity" desc="26ai 가 동시성 문제를 DB 안에서 어떻게 줄이는지, 세션 여러 개를 실제로 돌려 단계별로 보여줍니다.">
      <template #actions><RecentQueriesPanel endpoint="/api/productivity/recent-queries" hint="V$SQL 에서 DEMO_LOCKFREE · DEMO_PRIORITY · TXN_PRIORITY · RESERVABLE 관련 최근 10건" /></template>
    </PageHeader>
    <SubTabs :tabs="TABS" :model-value="sub" @update:model-value="(v: string) => set(v as TabId)" />
    <KeepAlive>
      <LockFree v-if="sub === 'lockfree'" />
      <PriorityTx v-else />
    </KeepAlive>
  </div>
</template>
