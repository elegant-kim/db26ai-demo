<script setup lang="ts">
/** 8개 보고서 섹션 한 장 — data → KvGrid · table/tables → ResultTable · interpretation → 서술 (레거시 하이브리드 렌더 계승) */
import { computed, ref } from 'vue'
import { ChevronDown, ChevronUp } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import KvGrid from '@/components/demo/KvGrid.vue'
import ResultTable from '@/components/demo/ResultTable.vue'
import type { AwrSection, AwrTable } from '@/lib/awr'
import type { Rows } from '@/lib/normalize'

const props = defineProps<{ index: number; section: AwrSection; fallbackTitle: string }>()
const open = ref(true)
const toRows = (t: AwrTable): Rows => ({
  columns: t.headers,
  rows: t.rows.map((r) => Object.fromEntries(t.headers.map((h, i) => [h, r[i] ?? null]))),
})
const tables = computed<AwrTable[]>(() => props.section.tables ?? (props.section.table ? [props.section.table] : []))
</script>

<template>
  <Card :title="`${index}. ${section.title || fallbackTitle}`">
    <template #actions>
      <Button variant="ghost" size="sm" @click="open = !open"><component :is="open ? ChevronUp : ChevronDown" :size="14" :stroke-width="2" /> {{ open ? '접기' : '펼치기' }}</Button>
    </template>
    <div v-show="open" class="flex flex-col gap-3">
      <KvGrid v-if="section.data" :data="section.data" />
      <div v-for="(t, i) in tables" :key="i" class="flex flex-col gap-1">
        <div v-if="t.subtitle" class="text-sm font-semibold" style="color: var(--text-secondary);">{{ t.subtitle }}</div>
        <ResultTable :rows="toRows(t)" dense hide-footer max-height="420px" />
      </div>
      <p v-if="section.interpretation" class="interp m-0 text-sm rounded-md px-3.5 py-3 whitespace-pre-wrap" style="background: var(--bg-surface); color: var(--text-primary); line-height: 1.7;">{{ section.interpretation }}</p>
    </div>
  </Card>
</template>
