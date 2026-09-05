<script setup lang="ts">
import { computed } from 'vue'

interface Props { total: number; page: number; pageSize: number; maxButtons?: number }
const props = withDefaults(defineProps<Props>(), { maxButtons: 7 })
const emit = defineEmits<{ (e: 'update:page', page: number): void }>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / Math.max(1, props.pageSize))))
const cur = computed(() => Math.min(Math.max(1, props.page), totalPages.value))
const visiblePages = computed(() => {
  const total = totalPages.value
  const max = Math.min(props.maxButtons, total)
  const half = Math.floor(max / 2)
  let start = Math.max(1, cur.value - half)
  let end = start + max - 1
  if (end > total) { end = total; start = Math.max(1, end - max + 1) }
  return Array.from({ length: end - start + 1 }, (_, i) => start + i)
})
const rangeText = computed(() => {
  if (props.total === 0) return '0건'
  const from = (cur.value - 1) * props.pageSize + 1
  const to = Math.min(cur.value * props.pageSize, props.total)
  return `${from}–${to} / ${props.total}건`
})
function go(p: number) {
  const next = Math.min(Math.max(1, p), totalPages.value)
  if (next !== cur.value) emit('update:page', next)
}
const navStyle = (disabled: boolean) => ({
  background: 'var(--bg-surface)', color: disabled ? 'var(--text-muted)' : 'var(--text-primary)',
  borderColor: 'var(--border-default)', cursor: disabled ? 'not-allowed' : 'pointer',
})
</script>

<template>
  <div v-if="total > 0" class="flex items-center justify-between gap-2 flex-wrap text-sm py-1">
    <span style="color: var(--text-muted);">{{ rangeText }}</span>
    <div v-if="totalPages > 1" class="flex items-center gap-1">
      <button class="px-2 py-1 rounded border text-xs" :disabled="cur === 1" :style="navStyle(cur === 1)" @click="go(1)">«</button>
      <button class="px-2 py-1 rounded border text-xs" :disabled="cur === 1" :style="navStyle(cur === 1)" @click="go(cur - 1)">‹</button>
      <button v-for="p in visiblePages" :key="p" class="px-2.5 py-1 rounded text-xs font-medium min-w-[28px]"
        :style="{ background: p === cur ? 'var(--accent-primary)' : 'var(--bg-surface)', color: p === cur ? 'var(--text-on-accent)' : 'var(--text-secondary)', border: '1px solid ' + (p === cur ? 'var(--accent-primary)' : 'var(--border-default)') }"
        @click="go(p)">{{ p }}</button>
      <button class="px-2 py-1 rounded border text-xs" :disabled="cur === totalPages" :style="navStyle(cur === totalPages)" @click="go(cur + 1)">›</button>
      <button class="px-2 py-1 rounded border text-xs" :disabled="cur === totalPages" :style="navStyle(cur === totalPages)" @click="go(totalPages)">»</button>
    </div>
  </div>
</template>
