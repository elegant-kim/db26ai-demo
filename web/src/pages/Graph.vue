<script setup lang="ts">
import { Boxes, GitCompareArrows, Route, Network } from 'lucide-vue-next'
import PageHeader from '@/components/demo/PageHeader.vue'
import SubTabs from '@/components/demo/SubTabs.vue'
import RecentQueriesPanel from '@/components/demo/RecentQueriesPanel.vue'
import { useSubTab } from '@/composables/useSubTab'
import GraphManage from './graph/GraphManage.vue'
import GraphCompare from './graph/GraphCompare.vue'
import GraphPattern from './graph/GraphPattern.vue'
import GraphViz from './graph/GraphViz.vue'

const TABS = [
  { id: 'manage', label: '그래프 관리', icon: Boxes },
  { id: 'compare', label: 'SQL vs SQL/PGQ', icon: GitCompareArrows },
  { id: 'pattern', label: '관계 탐색', icon: Route },
  { id: 'viz', label: '시각화', icon: Network },
] as const
type TabId = (typeof TABS)[number]['id']
const { sub, set } = useSubTab<TabId>(TABS.map((t) => t.id), 'manage')
</script>

<template>
  <div class="flex flex-col gap-5">
    <PageHeader menu="graph" desc="기존 테이블(CUSTOMERS · PRODUCTS · SALES) 위에 그래프를 정의하고, 같은 질문을 JOIN 과 SQL/PGQ 로 나란히 풀어 봅니다.">
      <template #actions><RecentQueriesPanel endpoint="/api/graph/recent-queries" hint="V$SQL 에서 GRAPH_TABLE · SALES_GRAPH 관련 최근 10건" /></template>
    </PageHeader>
    <SubTabs :tabs="TABS as any" :model-value="sub" @update:model-value="(v: string) => set(v as TabId)" />
    <KeepAlive>
      <GraphManage v-if="sub === 'manage'" />
      <GraphCompare v-else-if="sub === 'compare'" />
      <GraphPattern v-else-if="sub === 'pattern'" />
      <GraphViz v-else />
    </KeepAlive>
  </div>
</template>
