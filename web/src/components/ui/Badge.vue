<script setup lang="ts">
interface Props { tone?: 'default' | 'primary' | 'positive' | 'negative' | 'warm' | 'info' | 'code' }
const props = withDefaults(defineProps<Props>(), { tone: 'default' })

// info·code 는 db26ai 추가 (06 문서 §5.4) — 소요시간은 code, 안내는 info
const map: Record<string, { bg: string; fg: string; mono?: boolean }> = {
  default: { bg: 'var(--bg-surface)', fg: 'var(--text-secondary)' },
  primary: { bg: 'var(--accent-primary-soft)', fg: 'var(--accent-primary)' },
  positive: { bg: 'var(--accent-positive-soft)', fg: 'var(--accent-positive)' },
  negative: { bg: 'var(--accent-negative-soft)', fg: 'var(--accent-negative)' },
  warm: { bg: 'var(--accent-warm-soft)', fg: 'var(--accent-warm)' },
  info: { bg: 'var(--accent-info-soft)', fg: 'var(--accent-info)' },
  code: { bg: 'var(--bg-surface)', fg: 'var(--text-secondary)', mono: true },
}
</script>

<template>
  <span
    class="inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap"
    :style="{ background: map[props.tone].bg, color: map[props.tone].fg, fontFamily: map[props.tone].mono ? 'var(--font-mono)' : undefined }"
  >
    <slot />
  </span>
</template>
