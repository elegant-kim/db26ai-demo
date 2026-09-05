<script setup lang="ts">
import type { LucideIcon } from 'lucide-vue-next'

interface Props { title?: string; subtitle?: string; icon?: LucideIcon; compact?: boolean }
defineProps<Props>()
</script>

<template>
  <section
    class="border"
    :style="{
      background: 'var(--bg-elevated)',
      borderColor: 'var(--border-default)',
      borderRadius: 'var(--radius-card)',
      boxShadow: 'var(--shadow-card)',
      padding: compact ? 'var(--space-4)' : 'var(--space-5)',
    }"
  >
    <header v-if="title || subtitle || $slots.header || $slots.actions" class="mb-3 flex items-start justify-between gap-3">
      <div class="min-w-0">
        <slot name="header">
          <h3 v-if="title" class="font-semibold text-base m-0 flex items-center gap-1.5" style="color: var(--text-primary);">
            <component v-if="icon" :is="icon" :size="18" :stroke-width="1.75" />
            {{ title }}
          </h3>
          <p v-if="subtitle" class="text-sm m-0 mt-1" style="color: var(--text-muted);">{{ subtitle }}</p>
        </slot>
      </div>
      <!-- db26ai 추가: 우상단 보조 버튼 영역 (예: 실행 쿼리 확인) -->
      <div v-if="$slots.actions" class="shrink-0 flex items-center gap-2"><slot name="actions" /></div>
    </header>
    <slot />
  </section>
</template>
