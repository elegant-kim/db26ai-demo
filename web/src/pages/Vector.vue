<script setup lang="ts">
import { Search, FileText, Database, Cpu, type LucideIcon } from 'lucide-vue-next'
import PageHeader from '@/components/demo/PageHeader.vue'
import SubTabs from '@/components/demo/SubTabs.vue'
import RecentQueriesPanel from '@/components/demo/RecentQueriesPanel.vue'
import { useSubTab } from '@/composables/useSubTab'
import VectorSearch from './vector/VectorSearch.vue'
import VectorDocs from './vector/VectorDocs.vue'
import VectorStore from './vector/VectorStore.vue'
import VectorEmbedding from './vector/VectorEmbedding.vue'

type TabId = 'search' | 'docs' | 'store' | 'embedding'
const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: 'search', label: '검색 · RAG', icon: Search },
  { id: 'docs', label: '문서 · 업로드', icon: FileText },
  { id: 'store', label: 'Vector Store', icon: Database },
  { id: 'embedding', label: '임베딩 · ONNX', icon: Cpu },
]
const { sub, set } = useSubTab<TabId>(['search', 'docs', 'store', 'embedding'], 'search')
</script>

<template>
  <div class="flex flex-col gap-5">
    <PageHeader menu="vector" desc="PDF 를 올리면 DB 안에서 청킹 → ONNX 임베딩 → VECTOR 저장이 돌고, 같은 질문을 의미 · 키워드 · 하이브리드로 검색해 RAG 답변까지 봅니다.">
      <template #actions><RecentQueriesPanel endpoint="/api/vector/recent-queries" hint="V$SQL 에서 VECTOR_DISTANCE · VECTOR_EMBEDDING · CONTAINS 관련 최근 10건" /></template>
    </PageHeader>
    <SubTabs :tabs="TABS" :model-value="sub" @update:model-value="(v: string) => set(v as TabId)" />
    <KeepAlive>
      <VectorSearch v-if="sub === 'search'" />
      <VectorDocs v-else-if="sub === 'docs'" />
      <VectorStore v-else-if="sub === 'store'" />
      <VectorEmbedding v-else />
    </KeepAlive>
  </div>
</template>
