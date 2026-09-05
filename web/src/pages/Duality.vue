<script setup lang="ts">
import { Layers, GitCompareArrows, FileJson, ShieldCheck, type LucideIcon } from 'lucide-vue-next'
import PageHeader from '@/components/demo/PageHeader.vue'
import SubTabs from '@/components/demo/SubTabs.vue'
import RecentQueriesPanel from '@/components/demo/RecentQueriesPanel.vue'
import { useSubTab } from '@/composables/useSubTab'
import DualityViews from './duality/DualityViews.vue'
import DualityCompare from './duality/DualityCompare.vue'
import DualityCrud from './duality/DualityCrud.vue'
import DualityEtag from './duality/DualityEtag.vue'

type TabId = 'views' | 'compare' | 'crud' | 'etag'
const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: 'views', label: '뷰 관리', icon: Layers },
  { id: 'compare', label: '관계형 vs JSON', icon: GitCompareArrows },
  { id: 'crud', label: '문서 CRUD', icon: FileJson },
  { id: 'etag', label: 'ETag 동시성', icon: ShieldCheck },
]
const { sub, set } = useSubTab<TabId>(['views', 'compare', 'crud', 'etag'], 'views')
</script>

<template>
  <div class="flex flex-col gap-5">
    <PageHeader menu="duality" desc="관계형 테이블 위에 JSON 문서 뷰를 정의하고, 같은 데이터를 SQL 과 JSON 으로 나란히 읽고 고칩니다.">
      <template #actions><RecentQueriesPanel endpoint="/api/duality/recent-queries" hint="V$SQL 에서 CUSTOMERS_DV · PRODUCTS_DV · DUALITY 관련 최근 10건" /></template>
    </PageHeader>
    <SubTabs :tabs="TABS" :model-value="sub" @update:model-value="(v: string) => set(v as TabId)" />
    <KeepAlive>
      <DualityViews v-if="sub === 'views'" />
      <DualityCompare v-else-if="sub === 'compare'" />
      <DualityCrud v-else-if="sub === 'crud'" />
      <DualityEtag v-else />
    </KeepAlive>
  </div>
</template>
