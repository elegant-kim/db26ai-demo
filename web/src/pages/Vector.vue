<script setup lang="ts">
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import { Settings2, UploadCloud, Search, Wrench, type LucideIcon } from 'lucide-vue-next'
import PageHeader from '@/components/demo/PageHeader.vue'
import SubTabs from '@/components/demo/SubTabs.vue'
import RecentQueriesPanel from '@/components/demo/RecentQueriesPanel.vue'
import { useSubTab } from '@/composables/useSubTab'
import VectorEnv from './vector/VectorEnv.vue'
import VectorLoad from './vector/VectorLoad.vue'
import VectorSearch from './vector/VectorSearch.vue'
import VectorInternals from './vector/VectorInternals.vue'

/**
 * 서브탭 순서 = 시연 순서 (2026-09-09 재편 P1, 사용자 확정): 환경(무엇이 준비돼 있나) → 적재(PDF 가 SQL 로 벡터가 되는 과정) →
 * 검색·RAG(주인공) → 내부(증명·관리). NL2SQL 과 같은 문법. 옛 딥링크(docs/store/embedding)는 새 id 로 보낸다.
 */
type TabId = 'env' | 'load' | 'search' | 'internals'
const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: 'env', label: '환경', icon: Settings2 },
  { id: 'load', label: '적재', icon: UploadCloud },
  { id: 'search', label: '검색 · RAG', icon: Search },
  { id: 'internals', label: '내부', icon: Wrench },
]
const LEGACY: Record<string, TabId> = { docs: 'load', store: 'internals', embedding: 'internals' }
const { sub, set } = useSubTab<TabId>(['env', 'load', 'search', 'internals'], 'env')
const route = useRoute()
watch(() => route.query.sub, (q) => { const m = LEGACY[String(q ?? '')]; if (m) set(m) }, { immediate: true })
</script>

<template>
  <div class="flex flex-col gap-5">
    <PageHeader menu="vector" desc="먼저 「환경」에서 VECTOR 테이블 · ONNX 모델 · 인덱스가 DB 안에 있는 것을 확인하고, 「적재」에서 PDF 가 청킹 → 임베딩 → 인덱싱되는 SQL 을 단계마다 보고, 「검색」에서 같은 질문을 다섯 방식으로 풉니다.">
      <template #actions><RecentQueriesPanel endpoint="/api/vector/recent-queries" hint="V$SQL 에서 VECTOR_DISTANCE · VECTOR_EMBEDDING · CONTAINS 관련 최근 10건" /></template>
    </PageHeader>
    <SubTabs :tabs="TABS" :model-value="sub" @update:model-value="(v: string) => set(v as TabId)" />
    <KeepAlive>
      <VectorEnv v-if="sub === 'env'" />
      <VectorLoad v-else-if="sub === 'load'" />
      <VectorSearch v-else-if="sub === 'search'" />
      <VectorInternals v-else />
    </KeepAlive>
  </div>
</template>
