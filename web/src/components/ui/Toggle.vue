<script setup lang="ts">
/** 스위치 토글 (role=switch) — Multi Turn 같은 ON/OFF 설정. 색은 토큰만. 2026-09-29 (PoC 확장 1-A). */
defineProps<{ modelValue: boolean; label?: string; disabled?: boolean; hint?: string }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()
</script>

<template>
  <button type="button" role="switch" :aria-checked="modelValue" :disabled="disabled" :title="hint"
    class="inline-flex items-center gap-1.5 text-xs select-none" :style="{ opacity: disabled ? 0.5 : 1, color: 'var(--text-secondary)', cursor: disabled ? 'not-allowed' : 'pointer' }"
    @click="!disabled && emit('update:modelValue', !modelValue)">
    <span class="relative inline-block w-8 h-[18px] rounded-full transition-colors duration-150" :style="{ background: modelValue ? 'var(--accent-primary)' : 'var(--border-strong)' }">
      <span class="absolute top-[2px] w-[14px] h-[14px] rounded-full transition-all duration-150" :style="{ left: modelValue ? '16px' : '2px', background: 'var(--text-on-accent)' }" />
    </span>
    <span v-if="label" :style="{ color: modelValue ? 'var(--text-primary)' : 'var(--text-secondary)' }">{{ label }}</span>
  </button>
</template>
