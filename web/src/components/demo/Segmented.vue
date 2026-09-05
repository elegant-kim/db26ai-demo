<script setup lang="ts">
/** 딥탭 세그먼트 (3단계) — 06 문서 §4.3: 6×12, 테두리 default, 활성 테두리 accent. 검색 모드·실행 모드에 쓴다. */
interface Opt { value: string; label: string; hint?: string }
defineProps<{ options: Opt[]; modelValue: string; size?: 'sm' | 'md' }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
</script>

<template>
  <div class="flex gap-1 flex-wrap">
    <button
      v-for="o in options" :key="o.value" type="button"
      class="rounded-md transition-colors duration-150 flex items-center gap-1.5"
      :class="size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-sm'"
      :title="o.hint"
      :style="{
        background: modelValue === o.value ? 'var(--accent-primary-soft)' : 'transparent',
        color: modelValue === o.value ? 'var(--accent-primary)' : 'var(--text-secondary)',
        border: modelValue === o.value ? '1px solid var(--accent-primary)' : '1px solid var(--border-default)',
      }"
      @click="emit('update:modelValue', o.value)"
    >{{ o.label }}</button>
  </div>
</template>
