<script setup lang="ts">
/** 결과 세션 탭 — AWR 분석 이력·벡터 검색 세션 공통. 라벨 + 보조(제공자) + 시각 + 닫기. */
import { X as XIcon } from 'lucide-vue-next'

interface Tab { id: string | number; label: string; sub?: string; time?: string; closable?: boolean }
defineProps<{ tabs: Tab[]; modelValue: number; closable?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [number]; close: [number] }>()
</script>

<template>
  <div class="flex gap-1.5 flex-wrap">
    <div v-for="(t, i) in tabs" :key="t.id" class="tab flex items-center gap-2 rounded-md pl-3 pr-1.5 py-1.5 cursor-pointer text-sm"
      :class="{ active: i === modelValue }" role="tab" :aria-selected="i === modelValue" @click="emit('update:modelValue', i)">
      <span class="font-medium truncate max-w-[260px]">{{ t.label }}</span>
      <span v-if="t.sub" class="text-xs" style="color: var(--text-muted);">{{ t.sub }}</span>
      <span v-if="t.time" class="text-xs tabular-nums" style="color: var(--text-muted);">{{ t.time }}</span>
      <button v-if="t.closable ?? closable" class="close rounded p-0.5" title="닫기" @click.stop="emit('close', i)"><XIcon :size="13" :stroke-width="2" /></button>
    </div>
  </div>
</template>

<style scoped>
.tab { background: var(--bg-elevated); border: 1px solid var(--border-default); color: var(--text-secondary); }
.tab:hover { background: var(--bg-surface); }
.tab.active { background: var(--accent-primary-soft); border-color: var(--accent-primary); color: var(--accent-primary); }
.close { color: var(--text-muted); }
.close:hover { color: var(--accent-negative); background: var(--bg-surface); }
</style>
