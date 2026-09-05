<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { MENUS, type MenuDef } from '@/lib/menu'

const route = useRoute()
const router = useRouter()

function go(m: MenuDef) {
  router.push(m.path)
}
const isActive = (m: MenuDef) => route.path.startsWith(m.path)
</script>

<template>
  <nav class="flex items-center gap-1">
    <button
      v-for="m in MENUS"
      :key="m.id"
      class="relative flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-150 whitespace-nowrap shrink-0"
      :style="{
        color: isActive(m) ? '#ffffff' : 'rgba(255,255,255,0.78)',
        background: isActive(m) ? 'var(--header-active-bg)' : 'transparent',
      }"
      :title="m.title"
      @mouseenter="(e) => { if (!isActive(m)) (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)' }"
      @mouseleave="(e) => { if (!isActive(m)) (e.currentTarget as HTMLElement).style.background = 'transparent' }"
      @click="go(m)"
    >
      <span v-if="isActive(m)" class="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r" style="background: var(--header-active-bar);"></span>
      <component :is="m.icon" :size="16" :stroke-width="1.75" />
      <span>{{ m.label }}</span>
    </button>
  </nav>
</template>
