<script setup lang="ts">
interface Props {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  busy?: boolean
  type?: 'button' | 'submit' | 'reset'
}
const props = withDefaults(defineProps<Props>(), { variant: 'primary', size: 'md', disabled: false, busy: false, type: 'button' })

const sizeStyle: Record<string, string> = {
  sm: 'padding: 6px 10px; font-size: 12px;',
  md: 'padding: 8px 14px; font-size: 14px;',
  lg: 'padding: 10px 18px; font-size: 15px;',
}
const variantStyle: Record<string, string> = {
  primary: 'background: var(--accent-primary); color: var(--text-on-accent);',
  secondary: 'background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-strong);',
  ghost: 'background: transparent; color: var(--text-primary);',
  danger: 'background: var(--accent-negative); color: var(--text-on-accent);',
}
</script>

<template>
  <button
    :type="props.type"
    :disabled="props.disabled || props.busy"
    class="rounded-md font-medium transition-opacity inline-flex items-center justify-center gap-1.5 whitespace-nowrap"
    :style="`${sizeStyle[props.size]} ${variantStyle[props.variant]} border-radius: var(--radius-control); ${props.disabled || props.busy ? 'opacity: 0.5; cursor: not-allowed;' : ''}`"
  >
    <span v-if="props.busy" class="inline-block w-3.5 h-3.5 rounded-full border-2 animate-spin" style="border-color: currentColor; border-top-color: transparent;"></span>
    <slot />
  </button>
</template>
