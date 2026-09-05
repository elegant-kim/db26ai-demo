<script setup lang="ts">
/** 검색 가능한 셀렉트 (investhub 이식). 쿼리·프로필·모델 선택. */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ChevronDown, Search } from 'lucide-vue-next'

interface Opt { value: string; label: string; sub?: string }
const props = defineProps<{ modelValue: string; options: Opt[]; placeholder?: string; searchable?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()

const open = ref(false)
const q = ref('')
const root = ref<HTMLElement | null>(null)
const selected = computed(() => props.options.find((o) => o.value === props.modelValue))
const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return props.options
  return props.options.filter((o) => o.label.toLowerCase().includes(s) || (o.sub || '').toLowerCase().includes(s) || o.value.toLowerCase().includes(s))
})
function toggle() { open.value = !open.value; if (open.value) q.value = '' }
function pick(v: string) { emit('update:modelValue', v); open.value = false }
function onDocClick(e: MouseEvent) { if (root.value && !root.value.contains(e.target as Node)) open.value = false }
onMounted(() => document.addEventListener('mousedown', onDocClick))
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))
</script>

<template>
  <div ref="root" class="relative w-full">
    <button type="button" class="w-full px-2.5 py-2 rounded-md text-sm flex items-center justify-between gap-2 text-left"
      style="background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-default);" @click="toggle">
      <span class="truncate">{{ selected ? selected.label : (placeholder || '선택') }}</span>
      <ChevronDown :size="15" class="shrink-0" style="color: var(--text-muted);" />
    </button>
    <div v-if="open" class="absolute z-50 mt-1 rounded-md overflow-hidden shadow-lg"
      style="background: var(--bg-elevated); border: 1px solid var(--border-strong); min-width: 100%; width: max(100%, 20rem); max-width: 30rem;">
      <div v-if="searchable !== false && options.length > 6" class="flex items-center gap-1.5 px-2 py-1.5 border-b" style="border-color: var(--border-default);">
        <Search :size="13" style="color: var(--text-muted);" />
        <input v-model="q" :placeholder="`검색 (${options.length}개)`" autofocus class="w-full bg-transparent text-sm outline-none" style="color: var(--text-primary);" />
      </div>
      <div class="max-h-80 overflow-auto">
        <button v-for="o in filtered" :key="o.value" type="button" class="w-full text-left px-2.5 py-1.5 block"
          :style="{ background: o.value === modelValue ? 'var(--accent-primary-soft)' : 'transparent' }" @click="pick(o.value)">
          <div class="text-[13px] font-medium truncate" :style="{ color: o.value === modelValue ? 'var(--accent-primary)' : 'var(--text-primary)' }">{{ o.label }}</div>
          <div v-if="o.sub" class="text-[11px] mt-0.5" style="color: var(--text-muted); line-height: 1.45;">{{ o.sub }}</div>
        </button>
        <div v-if="!filtered.length" class="px-2.5 py-3 text-[13px] text-center" style="color: var(--text-muted);">결과 없음</div>
      </div>
    </div>
  </div>
</template>
