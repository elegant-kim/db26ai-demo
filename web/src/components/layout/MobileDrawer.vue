<script setup lang="ts">
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { X as XIcon } from 'lucide-vue-next'
import { MENUS, type MenuDef } from '@/lib/menu'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const route = useRoute()
const router = useRouter()

watch(() => route.path, () => emit('close'))

function go(m: MenuDef) {
  router.push(m.path)
  emit('close')
}
</script>

<template>
  <div v-if="open" class="md:hidden fixed inset-0 z-40" style="background: rgba(0, 0, 0, 0.4);" @click="emit('close')">
    <aside class="absolute left-0 top-0 bottom-0 w-72 p-4 overflow-y-auto" style="background: var(--bg-elevated); box-shadow: var(--shadow-elevated);" @click.stop>
      <div class="flex items-center justify-between mb-4 pb-3 border-b" style="border-color: var(--border-default);">
        <div class="font-semibold text-lg" style="color: var(--accent-primary);">26ai 데모</div>
        <button class="p-2 inline-flex items-center justify-center" style="color: var(--text-secondary);" @click="emit('close')"><XIcon :size="18" :stroke-width="1.75" /></button>
      </div>
      <nav class="flex flex-col gap-1">
        <button
          v-for="m in MENUS" :key="m.id"
          class="relative text-left flex items-center gap-2 px-3 py-2.5 rounded-md text-sm font-medium transition-colors duration-150"
          :style="{
            color: route.path.startsWith(m.path) ? 'var(--accent-primary)' : 'var(--text-primary)',
            background: route.path.startsWith(m.path) ? 'var(--accent-primary-soft)' : 'transparent',
          }"
          @click="go(m)"
        >
          <span v-if="route.path.startsWith(m.path)" class="absolute left-0 top-2 bottom-2 w-1 rounded-r" style="background: var(--accent-primary);"></span>
          <component :is="m.icon" :size="18" :stroke-width="1.75" />
          <span>{{ m.title }}</span>
        </button>
      </nav>
    </aside>
  </div>
</template>
