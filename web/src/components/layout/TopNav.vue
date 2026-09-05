<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { MENUS, legacyUrl, type MenuDef } from '@/lib/menu'

const route = useRoute()
const router = useRouter()

// 이식된 메뉴는 라우터, 아직 레거시인 메뉴는 /legacy#tab 으로 전체 이동 (설계서 05 §5.2)
function go(m: MenuDef) {
  if (m.migrated) router.push(m.path)
  else window.location.href = legacyUrl(m)
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
      :title="m.migrated ? m.title : `${m.title} — 아직 기존 화면에서 열립니다`"
      @mouseenter="(e) => { if (!isActive(m)) (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)' }"
      @mouseleave="(e) => { if (!isActive(m)) (e.currentTarget as HTMLElement).style.background = 'transparent' }"
      @click="go(m)"
    >
      <span v-if="isActive(m)" class="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r" style="background: var(--header-active-bar);"></span>
      <component :is="m.icon" :size="16" :stroke-width="1.75" />
      <span>{{ m.label }}</span>
      <span v-if="!m.migrated" class="w-1.5 h-1.5 rounded-full" style="background: rgba(255,255,255,0.35);" title="기존 화면"></span>
    </button>
  </nav>
</template>
