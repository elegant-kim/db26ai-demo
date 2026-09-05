<script setup lang="ts">
/**
 * ⌘K 빠른 이동 — investhub CommandPalette 이식(설계서 05 §6.7, D5). 데이터는 메뉴 7개 + `/api/guide/features` 의 기능 34개.
 * 권한(RBAC)은 이 앱에 없으므로 뺐고, 최근 항목은 localStorage 에 5개.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search, CornerDownLeft } from 'lucide-vue-next'
import { MENUS, menuById } from '@/lib/menu'
import { tabToMenuId } from '@/lib/guide'
import { useGuideStore } from '@/stores/guide'

interface Item { label: string; desc: string; path: string; keyword: string; group: '메뉴' | '기능'; tab?: string }
const guide = useGuideStore()
const router = useRouter()
const query = ref('')
const selected = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)

const menuItems: Item[] = MENUS.map((m) => ({ label: m.title, desc: m.subtitle, path: m.path, keyword: `${m.label} ${m.title} ${m.subtitle}`, group: '메뉴' }))
const featureItems = computed<Item[]>(() => guide.features.map((f) => ({
  label: f.name, desc: f.desc, path: f.path, keyword: `${f.keyword} ${f.how} ${f.tab_label}`, group: '기능', tab: menuById(tabToMenuId(f.tab))?.label ?? f.tab_label,
})))

const RECENT_KEY = 'db26ai.cmdk.recent'
const recents = ref<Item[]>([])
function loadRecents() { try { const raw = localStorage.getItem(RECENT_KEY); if (raw) recents.value = JSON.parse(raw) } catch { /* noop */ } }
function pushRecent(item: Item) {
  recents.value = [item, ...recents.value.filter((it) => it.path !== item.path || it.label !== item.label)].slice(0, 5)
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(recents.value)) } catch { /* noop */ }
}

function matches(it: Item, q: string) {
  if (!q) return true
  const hay = `${it.label} ${it.desc} ${it.keyword}`.toLowerCase()
  return q.toLowerCase().split(/\s+/).filter(Boolean).every((t) => hay.includes(t))
}
const q = computed(() => query.value.trim())
const showRecents = computed(() => !q.value && recents.value.length > 0)
const menus = computed(() => menuItems.filter((it) => matches(it, q.value)))
const feats = computed(() => featureItems.value.filter((it) => matches(it, q.value)).slice(0, q.value ? 14 : 8))
const all = computed<Item[]>(() => [...(showRecents.value ? recents.value : []), ...menus.value, ...feats.value])
const offMenus = computed(() => (showRecents.value ? recents.value.length : 0))
const offFeats = computed(() => offMenus.value + menus.value.length)
watch(all, () => { selected.value = 0 })

function execute(item: Item) { pushRecent(item); guide.hidePalette(); query.value = ''; void router.push(item.path) }
function onKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); guide.togglePalette(); return }
  if (!guide.paletteOpen) return
  if (e.key === 'Escape') { e.preventDefault(); guide.hidePalette() }
  else if (e.key === 'ArrowDown') { e.preventDefault(); selected.value = Math.min(all.value.length - 1, selected.value + 1) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); selected.value = Math.max(0, selected.value - 1) }
  else if (e.key === 'Enter') { e.preventDefault(); const it = all.value[selected.value]; if (it) execute(it) }
}
watch(() => guide.paletteOpen, async (v) => { if (v) { void guide.load(); await nextTick(); inputRef.value?.focus() } else { query.value = ''; selected.value = 0 } })
onMounted(() => { loadRecents(); window.addEventListener('keydown', onKeydown) })
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div v-if="guide.paletteOpen" class="fixed inset-0 z-[1100] flex items-start justify-center pt-[14vh] px-4" style="background: rgba(0,0,0,0.42); backdrop-filter: blur(2px);" @click.self="guide.hidePalette()">
      <div class="w-full max-w-[620px] rounded-xl overflow-hidden" style="background: var(--bg-elevated); border: 1px solid var(--border-default); box-shadow: var(--shadow-elevated);">
        <div class="flex items-center gap-2 px-3 py-2.5" style="border-bottom: 1px solid var(--border-default);">
          <Search :size="18" :stroke-width="1.75" style="color: var(--text-muted);" />
          <input ref="inputRef" v-model="query" type="text" placeholder="메뉴·기능 검색 (예: 하이브리드, ETag, 실행계획, AWR)" class="flex-1 bg-transparent outline-none text-sm" style="color: var(--text-primary);" autocomplete="off" />
          <kbd class="text-[10px] px-1.5 py-0.5 rounded font-mono" style="background: var(--bg-surface); color: var(--text-muted);">ESC</kbd>
        </div>
        <div class="max-h-[60vh] overflow-y-auto py-1">
          <template v-if="showRecents">
            <div class="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">최근</div>
            <button v-for="(it, i) in recents" :key="'r' + i" class="w-full flex items-center gap-2 px-3 py-2 text-left" :style="{ background: selected === i ? 'var(--accent-primary-soft)' : 'transparent', color: 'var(--text-primary)' }" @mouseenter="selected = i" @click="execute(it)">
              <span class="text-sm flex-1">{{ it.label }}</span><span class="text-[11px]" style="color: var(--text-muted);">{{ it.group }}</span>
            </button>
          </template>
          <template v-if="menus.length">
            <div class="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">메뉴</div>
            <button v-for="(it, i) in menus" :key="'m' + it.path" class="w-full flex items-start gap-2 px-3 py-2 text-left" :style="{ background: selected === offMenus + i ? 'var(--accent-primary-soft)' : 'transparent', color: 'var(--text-primary)' }" @mouseenter="selected = offMenus + i" @click="execute(it)">
              <div class="flex-1 min-w-0"><div class="text-sm font-medium">{{ it.label }}</div><div class="text-xs truncate" style="color: var(--text-muted);">{{ it.desc }}</div></div>
              <span class="text-[11px] font-mono" style="color: var(--text-muted);">{{ it.path }}</span>
            </button>
          </template>
          <template v-if="feats.length">
            <div class="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">기능 {{ q ? '' : '(일부 — 검색어를 입력하면 34개 전부)' }}</div>
            <button v-for="(it, i) in feats" :key="'f' + it.path + it.label" class="w-full flex items-start gap-2 px-3 py-2 text-left" :style="{ background: selected === offFeats + i ? 'var(--accent-primary-soft)' : 'transparent', color: 'var(--text-primary)' }" @mouseenter="selected = offFeats + i" @click="execute(it)">
              <div class="flex-1 min-w-0"><div class="text-sm font-medium">{{ it.label }} <span class="text-[11px] font-normal ml-1" style="color: var(--text-muted);">{{ it.tab }}</span></div><div class="text-xs truncate" style="color: var(--text-muted);">{{ it.desc }}</div></div>
              <CornerDownLeft v-if="selected === offFeats + i" :size="13" :stroke-width="1.75" class="mt-1 shrink-0" style="color: var(--text-muted);" />
            </button>
          </template>
          <div v-if="all.length === 0" class="px-3 py-8 text-center text-sm" style="color: var(--text-muted);">{{ guide.loaded ? '결과 없음' : '카탈로그를 읽는 중…' }}</div>
        </div>
        <div class="px-3 py-1.5 flex items-center justify-between text-[10px]" style="background: var(--bg-surface); border-top: 1px solid var(--border-default); color: var(--text-muted);">
          <span>↑↓ 이동 · Enter 실행 · ESC 닫기</span><span>⌘/Ctrl + K 로 어디서든</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>
