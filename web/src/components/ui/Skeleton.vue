<script setup lang="ts">
const props = withDefaults(defineProps<{ height?: string; width?: string }>(), { height: '16px', width: '100%' })
</script>

<template>
  <div class="animate-pulse rounded" :style="`height: ${props.height}; width: ${props.width}; background: var(--bg-hover);`" />
</template>
