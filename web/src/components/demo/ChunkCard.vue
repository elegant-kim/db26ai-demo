<script setup lang="ts">
/** 참조 문서 청크 카드 — 출처·페이지·점수 배지 + 유사도 막대 + 본문(4줄 접기). 검색 4모드 공통. */
import { computed, ref } from 'vue'
import Badge from '@/components/ui/Badge.vue'
import type { Chunk } from '@/lib/vector'

const props = withDefaults(defineProps<{ chunk: Chunk; mode?: 'vector' | 'keyword' | 'hybrid'; rank?: number }>(), { mode: 'vector' })
const open = ref(false)
const sim = computed(() => (props.chunk.similarity == null ? null : Number(props.chunk.similarity)))
const tone = (s: number) => (s >= 0.85 ? 'positive' : s >= 0.7 ? 'info' : 'default')
const long = computed(() => (props.chunk.chunk_text || '').length > 260)
</script>

<template>
  <div class="rounded-md px-3 py-2.5" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
    <div class="flex flex-wrap items-center gap-1.5">
      <span v-if="rank" class="text-[11px] font-semibold w-5 h-5 rounded-full inline-flex items-center justify-center" style="background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid var(--border-default);">{{ rank }}</span>
      <Badge tone="code">{{ chunk.source_file }} p.{{ chunk.page_num }}</Badge>
      <template v-if="mode === 'hybrid'">
        <Badge tone="primary">hybrid {{ chunk.hybrid_score }}</Badge>
        <Badge v-if="sim !== null" :tone="tone(sim)">vector {{ sim }}</Badge>
        <Badge :tone="(chunk.keyword_score ?? 0) > 0 ? 'warm' : 'default'">keyword {{ chunk.keyword_score ?? 0 }}</Badge>
      </template>
      <Badge v-else-if="sim !== null" :tone="tone(sim)">cosine {{ sim }}</Badge>
    </div>
    <div v-if="mode === 'hybrid'" class="mt-1.5 flex flex-col gap-1">
      <div class="flex items-center gap-2 text-[11px]" style="color: var(--text-muted);"><span class="w-3 font-semibold">V</span><div class="flex-1 h-1.5 rounded-full overflow-hidden" style="background: var(--bg-elevated);"><div class="h-full rounded-full" :style="{ width: `${Math.round((sim ?? 0) * 100)}%`, background: 'var(--accent-info)' }" /></div><span class="w-9 text-right tabular-nums">{{ Math.round((sim ?? 0) * 100) }}%</span></div>
      <div class="flex items-center gap-2 text-[11px]" style="color: var(--text-muted);"><span class="w-3 font-semibold">K</span><div class="flex-1 h-1.5 rounded-full overflow-hidden" style="background: var(--bg-elevated);"><div class="h-full rounded-full" :style="{ width: `${Math.min(100, chunk.keyword_score ?? 0)}%`, background: 'var(--accent-warm)' }" /></div><span class="w-9 text-right tabular-nums">{{ Math.round(chunk.keyword_score ?? 0) }}</span></div>
    </div>
    <div v-else-if="sim !== null" class="mt-1.5 flex items-center gap-2 text-[11px]" style="color: var(--text-muted);">
      <div class="flex-1 h-1.5 rounded-full overflow-hidden" style="background: var(--bg-elevated);"><div class="h-full rounded-full" :style="{ width: `${Math.round(sim * 100)}%`, background: `var(--accent-${tone(sim) === 'default' ? 'primary' : tone(sim)})` }" /></div>
      <span class="w-9 text-right tabular-nums">{{ Math.round(sim * 100) }}%</span>
    </div>
    <p class="text-sm m-0 mt-2 whitespace-pre-wrap" :class="open ? '' : 'line-clamp-4'" style="color: var(--text-primary); line-height: 1.6;">{{ chunk.chunk_text }}</p>
    <button v-if="long" class="text-[11px] mt-1" style="color: var(--accent-primary);" @click="open = !open">{{ open ? '접기' : '더 보기' }}</button>
  </div>
</template>
