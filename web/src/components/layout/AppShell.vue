<script setup lang="ts">
import { ref } from 'vue'
import TopNav from './TopNav.vue'
import MobileDrawer from './MobileDrawer.vue'
import StatusChips from './StatusChips.vue'
import ThemeToggle from './ThemeToggle.vue'
import Toast from './Toast.vue'
import CommandPalette from './CommandPalette.vue'
import { HelpCircle, Search } from 'lucide-vue-next'
import { useGuideStore } from '@/stores/guide'
import { menuById } from '@/lib/menu'
import { useHealth } from '@/composables/useHealth'
import { useRouter } from 'vue-router'

useHealth()
const router = useRouter()
const guide = useGuideStore()
const drawerOpen = ref(false)

// 헤더 ? = 매뉴얼 (확인 포인트 ⑤)
function goManual() { router.push(menuById('manual').path) }
</script>

<template>
  <div class="min-h-screen flex flex-col" style="background: var(--bg-base);">
    <header
      class="flex items-center px-5 shrink-0"
      style="height: var(--nav-h); background: var(--header-bg); box-shadow: var(--shadow-card); border-bottom: 1px solid rgba(255,255,255,0.06);"
    >
      <button
        class="md:hidden mr-3 p-2 rounded"
        style="color: var(--header-text);"
        aria-label="메뉴 열기"
        @click="drawerOpen = true"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      <!-- 로고: Oracle 링 + 앱명 (레거시 헤더 계승, 06 문서 §4.1) -->
      <div class="font-semibold text-lg mr-5 flex items-center gap-2 shrink-0" style="color: #ffffff;">
        <svg width="26" height="17" viewBox="0 0 100 64" aria-hidden="true">
          <path d="M32,2 L68,2 C84.6,2 98,15.4 98,32 C98,48.6 84.6,62 68,62 L32,62 C15.4,62 2,48.6 2,32 C2,15.4 15.4,2 32,2 Z M32,12 C21,12 12,21 12,32 C12,43 21,52 32,52 L68,52 C79,52 88,43 88,32 C88,21 79,12 68,12 L32,12 Z" fill="#C74634"/>
        </svg>
        <!-- 1400px 미만에서는 짧은 이름 — 메뉴 7개 + 상태칩이 한 줄에 들어가는 폭의 경계(실측) -->
        <span class="hidden min-[1400px]:inline">Oracle AI Database 26ai 데모</span>
        <span class="min-[1400px]:hidden">26ai 데모</span>
      </div>

      <TopNav class="hidden md:flex flex-1 min-w-0 overflow-x-auto" />
      <div class="flex-1 md:hidden" />

      <div class="flex items-center gap-2 shrink-0">
        <StatusChips />
        <button
          class="inline-flex items-center gap-1.5 px-2 py-1.5 rounded-md transition-colors duration-150"
          title="빠른 이동 · 기능 검색 (⌘K)"
          style="color: var(--header-text);"
          @click="guide.showPalette()"
          @mouseenter="(e) => ((e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)')"
          @mouseleave="(e) => ((e.currentTarget as HTMLElement).style.background = 'transparent')"
        >
          <Search :size="17" :stroke-width="1.75" />
          <kbd class="hidden lg:inline text-[10px] font-mono px-1 py-0.5 rounded" style="background: rgba(255,255,255,0.1); color: var(--header-text);">⌘K</kbd>
        </button>
        <ThemeToggle />
        <button
          class="inline-flex items-center justify-center px-2 py-1.5 rounded-md transition-colors duration-150"
          title="매뉴얼 · 기능 지도"
          style="color: var(--header-text);"
          @click="goManual"
          @mouseenter="(e) => ((e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)')"
          @mouseleave="(e) => ((e.currentTarget as HTMLElement).style.background = 'transparent')"
        >
          <HelpCircle :size="18" :stroke-width="1.75" />
        </button>
      </div>
    </header>

    <main class="flex-1 px-5 py-6" style="background: var(--bg-base);">
      <div class="max-w-[1400px] mx-auto">
        <slot />
      </div>
    </main>

    <MobileDrawer :open="drawerOpen" @close="drawerOpen = false" />
    <CommandPalette />
    <Toast />
  </div>
</template>
