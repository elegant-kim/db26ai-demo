<script setup lang="ts">
/**
 * SQL 블록 ★ — 이 앱의 주인공 (06 문서 §5.6, 설계서 D10).
 * 라이트·다크 모두 다크 터미널 스타일(--code-* 는 테마 무관). 카드 배경과의 대비가 "여기가 SQL" 신호다.
 */
import { computed, ref } from 'vue'
import { Check, Copy } from 'lucide-vue-next'
import Badge from '@/components/ui/Badge.vue'
import { highlightJson, highlightSql, highlightSqlLines } from '@/lib/sqlHighlight'
import { fmtMs } from '@/lib/format'

interface Props {
  code: string | null | undefined
  label?: string
  lang?: 'sql' | 'json' | 'text'
  lineNumbers?: boolean
  maxHeight?: string
  elapsedMs?: number | null
  badge?: string
  badgeTone?: 'default' | 'primary' | 'positive' | 'negative' | 'warm' | 'info' | 'code'
}
const props = withDefaults(defineProps<Props>(), { label: '실행된 SQL', lang: 'sql', lineNumbers: false, maxHeight: '320px', badgeTone: 'primary' })

const html = computed(() => {
  if (props.lang === 'json') return highlightJson(props.code)
  if (props.lang === 'text') return (props.code || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return props.lineNumbers ? highlightSqlLines(props.code) : highlightSql(props.code)
})

const copied = ref(false)
async function copy() {
  try { await navigator.clipboard.writeText(props.code || ''); copied.value = true; setTimeout(() => (copied.value = false), 1500) } catch { /* 클립보드 권한 없음 */ }
}
</script>

<template>
  <div class="sql-block rounded-md overflow-hidden" style="border: 1px solid var(--border-default);">
    <div class="flex items-center justify-between gap-2 px-3" style="height: 36px; background: var(--bg-surface); border-bottom: 1px solid var(--border-default);">
      <div class="flex items-center gap-2 min-w-0">
        <span class="text-xs font-medium truncate" style="color: var(--text-secondary);">{{ label }}</span>
        <Badge v-if="badge" :tone="badgeTone">{{ badge }}</Badge>
        <Badge v-if="elapsedMs != null" tone="code">{{ fmtMs(elapsedMs) }}</Badge>
      </div>
      <button class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded" style="color: var(--text-secondary);" :title="copied ? '복사됨' : '복사'" @click="copy">
        <component :is="copied ? Check : Copy" :size="13" :stroke-width="1.75" :style="{ color: copied ? 'var(--accent-positive)' : undefined }" />
        <span class="hidden sm:inline">{{ copied ? '복사됨' : '복사' }}</span>
      </button>
    </div>
    <pre class="sql-code m-0 overflow-auto" :style="{ background: 'var(--code-bg)', padding: '14px 16px', maxHeight, whiteSpace: lineNumbers ? 'pre' : 'pre-wrap', wordBreak: 'break-word' }" v-html="html"></pre>
  </div>
</template>
