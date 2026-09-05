<script setup lang="ts">
/** 서브탭 pill 행 (2단계) — 06 문서 §4.2 측정값: 8×16, 14/500, 활성 soft 배경 + accent 글자 */
import type { LucideIcon } from 'lucide-vue-next'

interface Tab { id: string; label: string; icon?: LucideIcon; badge?: number | string }
defineProps<{ tabs: Tab[]; modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
</script>

<template>
  <div class="flex gap-1 flex-wrap">
    <button
      v-for="t in tabs" :key="t.id"
      class="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-md transition-colors duration-150"
      :style="{ background: modelValue === t.id ? 'var(--accent-primary-soft)' : 'transparent', color: modelValue === t.id ? 'var(--accent-primary)' : 'var(--text-secondary)' }"
      @click="emit('update:modelValue', t.id)"
    >
      <component v-if="t.icon" :is="t.icon" :size="16" :stroke-width="1.75" />
      {{ t.label }}
      <span v-if="t.badge != null && t.badge !== ''" class="text-xs px-1.5 rounded-full" style="background: var(--accent-primary); color: #fff; min-width: 1.25rem; line-height: 1.25rem;">{{ t.badge }}</span>
    </button>
  </div>
</template>
