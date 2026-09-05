<script setup lang="ts">
import type { LucideIcon } from 'lucide-vue-next'

interface Props { label: string; value: string | number; hint?: string; tone?: 'default' | 'positive' | 'negative' | 'warm'; icon?: LucideIcon }
const props = withDefaults(defineProps<Props>(), { tone: 'default' })
const toneColor: Record<string, string> = {
  default: 'var(--text-primary)', positive: 'var(--accent-positive)', negative: 'var(--accent-negative)', warm: 'var(--accent-warm)',
}
</script>

<template>
  <div class="border" style="background: var(--bg-elevated); border-color: var(--border-default); border-radius: var(--radius-card); box-shadow: var(--shadow-card); padding: var(--space-5);">
    <div class="flex items-center gap-2 mb-2">
      <component v-if="props.icon" :is="props.icon" :size="16" :stroke-width="1.75" style="color: var(--text-secondary);" />
      <span class="text-sm" style="color: var(--text-secondary);">{{ props.label }}</span>
    </div>
    <div class="text-2xl font-semibold tabular-nums" :style="{ color: toneColor[props.tone] }">{{ props.value }}</div>
    <div v-if="props.hint" class="text-xs mt-1" style="color: var(--text-muted);">{{ props.hint }}</div>
  </div>
</template>
