<script setup lang="ts">
/** 빈 상태 — 아이콘 + 한 줄 + 다음 행동 (06 문서 §6.2). */
import type { LucideIcon } from 'lucide-vue-next'
import { Inbox } from 'lucide-vue-next'

const props = withDefaults(defineProps<{ icon?: LucideIcon; title: string; desc?: string; compact?: boolean }>(), { compact: false })
</script>

<template>
  <div class="flex flex-col items-center justify-center text-center gap-1.5" :class="props.compact ? 'py-6' : 'py-12'">
    <component :is="props.icon || Inbox" :size="props.compact ? 28 : 40" :stroke-width="1.5" style="color: var(--text-muted);" />
    <div class="text-sm" style="color: var(--text-secondary);">{{ props.title }}</div>
    <p v-if="props.desc" class="text-xs m-0 max-w-md" style="color: var(--text-muted); line-height: 1.5;">{{ props.desc }}</p>
    <div v-if="$slots.default" class="mt-2 flex items-center gap-2"><slot /></div>
  </div>
</template>
