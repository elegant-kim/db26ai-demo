<script setup lang="ts">
import { useSystemStore } from '@/stores/system'
import { CheckCircle2, Info, AlertTriangle, XCircle } from 'lucide-vue-next'

const system = useSystemStore()
const ICON = { success: CheckCircle2, info: Info, warn: AlertTriangle, error: XCircle } as const
const COLOR = { success: 'var(--accent-positive)', info: 'var(--accent-info)', warn: 'var(--accent-warm)', error: 'var(--accent-negative)' } as const
</script>

<template>
  <div class="fixed bottom-5 right-5 z-[70] flex flex-col gap-2 pointer-events-none">
    <div
      v-for="t in system.toasts" :key="t.id"
      class="flex items-center gap-2 px-3.5 py-2.5 rounded-md text-sm border pointer-events-auto"
      style="background: var(--bg-elevated); border-color: var(--border-strong); box-shadow: var(--shadow-elevated); color: var(--text-primary); min-width: 240px; max-width: 420px;"
    >
      <component :is="ICON[t.type]" :size="16" :stroke-width="1.75" :style="{ color: COLOR[t.type], flexShrink: 0 }" />
      <span>{{ t.message }}</span>
    </div>
  </div>
</template>
