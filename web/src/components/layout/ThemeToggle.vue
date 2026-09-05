<script setup lang="ts">
import { computed, ref } from 'vue'
import { Monitor, Moon, Sun } from 'lucide-vue-next'
import { getThemePref, setThemePref, type ThemePref } from '@/lib/theme'

const pref = ref<ThemePref>(getThemePref())
const ORDER: ThemePref[] = ['system', 'light', 'dark']
const LABEL: Record<ThemePref, string> = { system: '시스템', light: '라이트', dark: '다크' }
const icon = computed(() => (pref.value === 'dark' ? Moon : pref.value === 'light' ? Sun : Monitor))

function cycle() {
  const next = ORDER[(ORDER.indexOf(pref.value) + 1) % ORDER.length]
  pref.value = next
  setThemePref(next)
}
</script>

<template>
  <button
    class="inline-flex items-center justify-center px-2 py-1.5 rounded-md transition-colors duration-150"
    :title="`테마: ${LABEL[pref]} (클릭하면 전환)`"
    style="color: var(--header-text);"
    @click="cycle"
    @mouseenter="(e) => ((e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)')"
    @mouseleave="(e) => ((e.currentTarget as HTMLElement).style.background = 'transparent')"
  >
    <component :is="icon" :size="18" :stroke-width="1.75" />
  </button>
</template>
