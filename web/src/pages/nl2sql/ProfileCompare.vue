<script setup lang="ts">
/** 프로필(모델) 비교 결과 블록 (PoC 3-C) — 프로필마다 한 열: 모델 · 생성 SQL · 결과 앞 5행 · 소요. 스레드의 어시스턴트 메시지로 그린다. */
import { computed } from 'vue'
import Badge from '@/components/ui/Badge.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import ResultTable from '@/components/demo/ResultTable.vue'
import { fmtMs } from '@/lib/format'
import type { CompareState } from '@/stores/nl2sql'

const props = defineProps<{ cp: CompareState }>()
const cols = computed(() => props.cp.profiles.map((m) => ({ meta: m, r: props.cp.steps[m.profile] })))
const sameTables = computed(() => { const s = new Set(props.cp.profiles.map((m) => JSON.stringify(m.object_list ?? null))); return s.size <= 1 })
const grid = computed(() => (props.cp.profiles.length >= 3 ? 'lg:grid-cols-3' : 'lg:grid-cols-2'))
</script>

<template>
  <div class="flex flex-col gap-3 w-full">
    <div class="text-xs" style="color: var(--text-secondary);">같은 질문 <b style="color: var(--text-primary);">「{{ cp.question }}」</b> 을 프로필 {{ cp.profiles.length }}개로 순서대로 풉니다 — 모델이 다르면 SQL 도 시간도 다릅니다.</div>
    <div v-if="cp.profiles.length && !sameTables" class="text-xs px-3 py-2 rounded-md" style="background: var(--accent-warm-soft); color: var(--text-primary);">프로필들이 보는 테이블(object_list)이 다릅니다 — SQL 이 다른 건 모델 차이가 아니라 데이터 차이일 수 있습니다. 같은 테이블을 보는 프로필끼리 비교해야 뜻이 있습니다.</div>
    <div class="grid grid-cols-1 gap-3 items-start" :class="grid">
      <div v-for="c in cols" :key="c.meta.profile" class="rounded-md p-3 flex flex-col gap-2 min-w-0" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0"><div class="font-semibold text-sm truncate" style="color: var(--text-primary);">{{ c.meta.profile }}</div><div class="text-[11px] font-mono truncate" style="color: var(--text-muted);">{{ c.meta.provider ?? '—' }} · {{ c.meta.model ?? '—' }}</div></div>
          <div class="flex items-center gap-1 shrink-0"><Badge v-if="c.r?.status === 'done' && c.r.generate_ms != null" tone="code" title="SQL 생성(GENERATE)만">{{ fmtMs(c.r.generate_ms) }}</Badge><Badge v-if="cp.done?.fastest === c.meta.profile" tone="positive">가장 빠름</Badge></div>
        </div>
        <LoadingBlock v-if="!c.r || c.r.status === 'running'" compact :label="c.r ? 'SQL 생성 중…' : '대기'" />
        <template v-else>
          <div v-if="c.r.error" class="text-xs px-2 py-1.5 rounded" style="background: var(--accent-negative-soft); color: var(--text-primary);"><span class="font-mono break-all">{{ c.r.error }}</span></div>
          <SqlBlock v-if="c.r.sql" :code="c.r.sql" label="생성된 SQL" max-height="220px" />
          <div v-if="c.r.run_error" class="text-[11px] px-2 py-1.5 rounded font-mono break-all" style="background: var(--accent-warm-soft); color: var(--text-primary);">실행 오류: {{ c.r.run_error }}</div>
          <template v-else-if="c.r.rows">
            <div class="text-[11px]" style="color: var(--text-muted);">결과 {{ c.r.row_count ?? c.r.rows.rows.length }}행 — 앞 {{ c.r.rows.rows.length }}행 · 생성+실행 {{ fmtMs(c.r.elapsed_ms) }}</div>
            <ResultTable :rows="c.r.rows" dense hide-footer max-height="180px" empty-text="결과 행이 없습니다." />
          </template>
        </template>
      </div>
    </div>
    <div v-if="cp.done" class="text-xs px-3 py-2 rounded-md" :style="{ background: cp.done.all_same_sql ? 'var(--accent-positive-soft)' : 'var(--accent-info-soft)', color: 'var(--text-primary)' }">
      {{ cp.done.all_same_sql ? '모든 프로필이 같은 SQL 을 만들었습니다.' : 'SQL 이 서로 다릅니다 — 결과 행수와 값을 비교해 보세요.' }} 총 {{ fmtMs(cp.done.elapsed_ms) }}<span v-if="cp.done.fastest"> · 가장 빠른 프로필 {{ cp.done.fastest }}</span>
    </div>
    <div v-if="cp.error" class="text-xs px-3 py-2 rounded-md" style="background: var(--accent-negative-soft); color: var(--text-primary);">{{ cp.error }}</div>
  </div>
</template>
