<script setup lang="ts">
/** 두 텍스트의 줄 diff — 추가(+) 초록, 삭제(−) 빨강, 같은 줄은 바뀐 곳 주변만 (PoC 2-C showprompt 전/후). */
import { computed } from 'vue'
import { collapseSame, lineDiff } from '@/lib/diff'

const props = withDefaults(defineProps<{ before: string; after: string; label?: string; maxHeight?: string; context?: number }>(), { label: 'diff', maxHeight: '360px', context: 2 })
const lines = computed(() => collapseSame(lineDiff(props.before || '', props.after || ''), props.context))
const stats = computed(() => { const d = lineDiff(props.before || '', props.after || ''); return { add: d.filter((l) => l.kind === 'add').length, del: d.filter((l) => l.kind === 'del').length } })
</script>

<template>
  <div class="rounded-md overflow-hidden" style="border: 1px solid var(--border-default);">
    <div class="flex items-center justify-between px-3 py-1.5 text-xs" style="background: var(--bg-surface); color: var(--text-secondary);">
      <span class="font-medium">{{ label }}</span><span class="font-mono"><span style="color: var(--accent-positive);">+{{ stats.add }}</span> <span style="color: var(--accent-negative);">−{{ stats.del }}</span></span>
    </div>
    <pre class="m-0 p-3 text-[11px] leading-relaxed overflow-auto font-mono" :style="{ maxHeight, background: 'var(--bg-elevated)', color: 'var(--text-primary)' }"><template v-for="(l, i) in lines" :key="i"><div v-if="l.kind === 'gap'" class="px-1 opacity-60" style="color: var(--text-muted);">… {{ l.count }}줄 같음 …</div><div v-else class="px-1 whitespace-pre-wrap break-words" :style="{ background: l.kind === 'add' ? 'var(--accent-positive-soft)' : l.kind === 'del' ? 'var(--accent-negative-soft)' : 'transparent' }">{{ l.kind === 'add' ? '+ ' : l.kind === 'del' ? '− ' : '  ' }}{{ l.text }}</div></template></pre>
  </div>
</template>
