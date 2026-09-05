<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Route } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import ResultTable from '@/components/demo/ResultTable.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import { useGraphStore } from '@/stores/graph'

const g = useGraphStore()
const route = useRoute()
// `?run=1` 이면 mount 직후 한 번 실행한다 — 기능 지도 딥링크·헤드리스 캡처·시연용 (설계서 05 §3.3)
onMounted(() => { void g.loadQueries().then(() => { if (route.query.run !== undefined && !g.currentPattern) void g.pattern() }) })
const options = computed(() => g.patternQueries.map((q) => ({ value: String(q.index), label: q.label })))
const selected = computed({ get: () => String(g.patternIndex), set: (v: string) => { g.patternIndex = Number(v) } })
const result = computed(() => g.currentPattern)
</script>

<template>
  <Card title="관계 탐색 (패턴 매칭)" subtitle="SQL/PGQ 의 MATCH 패턴으로 정점과 간선의 관계를 따라갑니다 — JOIN 으로 쓰기 힘든 질의" :icon="Route">
    <div class="flex flex-wrap items-center gap-2 mb-4">
      <div class="flex-1 min-w-[280px] max-w-[560px]"><SearchableSelect v-model="selected" :options="options" placeholder="패턴 쿼리 선택" :searchable="false" /></div>
      <Button :busy="g.busy === 'pattern'" :disabled="!g.queriesLoaded" @click="g.pattern()">실행</Button>
    </div>
    <LoadingBlock v-if="g.busy === 'pattern' && !result" compact label="그래프를 탐색 중…" />
    <EmptyState v-else-if="!result" :icon="Route" title="패턴 쿼리를 고르고 [실행]을 누르세요" compact />
    <div v-else class="flex flex-col gap-3">
      <SqlBlock :code="result.sql" label="SQL/PGQ" badge="MATCH" :elapsed-ms="result.elapsedMs" line-numbers />
      <ResultTable :rows="result" />
    </div>
  </Card>
</template>
