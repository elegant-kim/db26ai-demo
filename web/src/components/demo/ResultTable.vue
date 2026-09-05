<script setup lang="ts">
/** 결과 표 ★ — Rows(lib/normalize) 하나만 받는다 (06 문서 §5.5). */
import { computed } from 'vue'
import type { Rows } from '@/lib/normalize'
import { fmtMs, fmtNum, isNumeric } from '@/lib/format'
import EmptyState from './EmptyState.vue'
import { Table2 } from 'lucide-vue-next'

interface Props { rows: Rows; maxHeight?: string; emptyText?: string; hideFooter?: boolean; dense?: boolean }
const props = withDefaults(defineProps<Props>(), { maxHeight: '420px', emptyText: '결과가 없습니다.', hideFooter: false, dense: false })

const numericCols = computed(() => {
  const s = new Set<string>()
  for (const c of props.rows.columns) {
    const vals = props.rows.rows.map((r) => r[c]).filter((v) => v != null)
    if (vals.length && vals.every(isNumeric)) s.add(c)
  }
  return s
})
function cell(v: unknown): string {
  if (v == null) return '—'
  if (isNumeric(v)) return fmtNum(v, 4)
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
const pad = computed(() => (props.dense ? '5px 8px' : '8px 10px'))
</script>

<template>
  <div>
    <div v-if="rows.error" class="flex items-start gap-2 px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">
      <span style="color: var(--accent-negative); font-weight: 600;">오류</span>
      <span class="font-mono text-xs break-all" style="color: var(--text-secondary);">{{ rows.error }}</span>
    </div>
    <EmptyState v-else-if="!rows.rows.length" :icon="Table2" :title="emptyText" compact />
    <div v-else class="overflow-auto rounded-md" :style="{ maxHeight, border: '1px solid var(--border-default)' }">
      <table class="w-full border-collapse text-sm" style="min-width: max-content;">
        <thead>
          <tr>
            <th v-for="c in rows.columns" :key="c" class="text-left font-semibold sticky top-0 z-10 whitespace-nowrap"
              :style="{ padding: pad, background: 'var(--bg-surface)', color: 'var(--text-primary)', borderBottom: '1px solid var(--border-default)', textAlign: numericCols.has(c) ? 'right' : 'left' }">{{ c }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in rows.rows" :key="i" class="row">
            <td v-for="c in rows.columns" :key="c" class="max-w-[480px] truncate"
              :title="String(r[c] ?? '')"
              :style="{ padding: pad, color: r[c] == null ? 'var(--text-muted)' : 'var(--text-primary)', borderBottom: '1px solid var(--border-default)', textAlign: numericCols.has(c) ? 'right' : 'left', fontVariantNumeric: numericCols.has(c) ? 'tabular-nums' : undefined }">{{ cell(r[c]) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="!hideFooter && rows.rows.length" class="flex items-center gap-2 text-xs mt-1.5" style="color: var(--text-muted);">
      <span>{{ fmtNum(rows.rows.length) }}행</span>
      <span v-if="rows.elapsedMs != null">· {{ fmtMs(rows.elapsedMs) }}</span>
    </div>
  </div>
</template>

<style scoped>
.row:hover td { background: var(--bg-hover); }
</style>
