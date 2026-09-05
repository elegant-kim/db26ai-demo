<script setup lang="ts">
/** label:value 그리드 — AWR 섹션의 data 유형. ⚠️ 가 든 값은 경고색 (레거시 awr-kv-warn). */
defineProps<{ data: Record<string, string | number | null | undefined> }>()
const warn = (v: unknown) => typeof v === 'string' && v.includes('⚠')
</script>

<template>
  <dl class="m-0 grid grid-cols-1 lg:grid-cols-2 gap-x-8 gap-y-1">
    <div v-for="(v, k) in data" :key="k" class="kv flex items-baseline gap-3 py-1.5 text-sm">
      <dt class="shrink-0 w-40 truncate" style="color: var(--text-muted);" :title="String(k)">{{ k }}</dt>
      <dd class="m-0 min-w-0 break-words" :class="warn(v) ? 'font-semibold' : ''" :style="{ color: warn(v) ? 'var(--accent-warm)' : 'var(--text-primary)' }">{{ v ?? '—' }}</dd>
    </div>
  </dl>
</template>

<style scoped>
.kv { border-bottom: 1px solid var(--border-default); }
</style>
