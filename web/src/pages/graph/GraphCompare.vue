<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { GitCompareArrows } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import ResultTable from '@/components/demo/ResultTable.vue'
import CompareView from '@/components/demo/CompareView.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import { rowsEqual } from '@/lib/normalize'
import { useGraphStore } from '@/stores/graph'

const g = useGraphStore()
const route = useRoute()
// `?run=1` 이면 mount 직후 한 번 실행한다 — 기능 지도 딥링크·헤드리스 캡처·시연용 (설계서 05 §3.3)
onMounted(() => { void g.loadQueries().then(() => { if (route.query.run !== undefined && !g.currentCompare) void g.compare() }) })

const options = computed(() => g.compareQueries.map((q) => ({ value: String(q.index), label: q.label })))
const selected = computed({ get: () => String(g.compareIndex), set: (v: string) => { g.compareIndex = Number(v) } })
const result = computed(() => g.currentCompare)
const equal = computed(() => (result.value && !result.value.sql.error && !result.value.pgq.error) ? rowsEqual(result.value.sql, result.value.pgq) : null)
</script>

<template>
  <Card title="SQL vs SQL/PGQ 비교" subtitle="같은 질문을 기존 JOIN SQL 과 SQL/PGQ 그래프 질의로 각각 실행해 결과와 소요시간을 비교합니다" :icon="GitCompareArrows">
    <div class="flex flex-wrap items-center gap-2 mb-4">
      <div class="flex-1 min-w-[280px] max-w-[560px]"><SearchableSelect v-model="selected" :options="options" placeholder="비교 쿼리 선택" :searchable="false" /></div>
      <Button :busy="g.busy === 'compare'" :disabled="!g.queriesLoaded" @click="g.compare()">비교 실행</Button>
    </div>

    <div v-if="g.lastError" class="px-3 py-2.5 rounded-md text-sm mb-4" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ g.lastError }}</div>

    <LoadingBlock v-if="g.busy === 'compare' && !result" compact label="두 방식으로 실행 중…" hint="SQL 과 SQL/PGQ 를 차례로 실행합니다 (각 0.2초 안팎)" />
    <EmptyState v-else-if="!result" :icon="GitCompareArrows" title="쿼리를 고르고 [비교 실행]을 누르세요" desc="세 질문 모두 양쪽이 완전히 같은 결과를 냅니다 — 3번(2-hop 추천)이 하이라이트입니다." compact />

    <CompareView v-else
      :left="{ title: '기존 SQL (JOIN)', elapsedMs: result.sql.elapsedMs, error: result.sql.error, rowCount: result.sql.rows.length }"
      :right="{ title: 'SQL/PGQ (그래프 질의)', elapsedMs: result.pgq.elapsedMs, error: result.pgq.error, rowCount: result.pgq.rows.length, badge: '26ai' }"
      :equal="equal">
      <template #left>
        <SqlBlock :code="result.sql.sql" label="SQL" max-height="260px" />
        <div class="mt-2"><ResultTable :rows="result.sql" dense max-height="360px" /></div>
      </template>
      <template #right>
        <SqlBlock :code="result.pgq.sql" label="SQL/PGQ" max-height="260px" badge="GRAPH_TABLE" />
        <div class="mt-2"><ResultTable :rows="result.pgq" dense max-height="360px" /></div>
      </template>
    </CompareView>
  </Card>
</template>
