<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Map as MapIcon, ArrowRight, Search } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import { menuById } from '@/lib/menu'
import { tabToMenuId, type FeatureItem } from '@/lib/guide'
import { useGuideStore } from '@/stores/guide'

const guide = useGuideStore()
const router = useRouter()
const q = ref('')
onMounted(() => { void guide.load() })
const hit = (f: FeatureItem) => { const t = q.value.trim().toLowerCase(); if (!t) return true; return `${f.name} ${f.desc} ${f.how} ${f.keyword}`.toLowerCase().includes(t) }
const groups = computed(() => guide.groups.map((g) => ({ ...g, menu: menuById(tabToMenuId(g.tab)), items: g.items.filter(hit) })).filter((g) => g.items.length))
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="flex flex-wrap items-center gap-3">
      <p class="text-sm m-0 flex-1 min-w-[260px]" style="color: var(--text-secondary);">이 앱의 모든 기능이 어디에 있고 언제 쓰는지 한눈에. 정본은 <code class="font-mono">app/feature_registry.py</code> 이며 새 기능은 거기 한 줄로 추가합니다. [이동]은 해당 화면의 서브탭으로 바로 갑니다 — ⌘K 로도 같은 목록을 검색할 수 있습니다.</p>
      <label class="flex items-center gap-1.5 rounded-md px-2.5 py-1.5" style="background: var(--bg-elevated); border: 1px solid var(--border-strong);"><Search :size="14" :stroke-width="1.75" style="color: var(--text-muted);" /><input v-model="q" placeholder="기능 검색…" class="bg-transparent outline-none text-sm w-44" style="color: var(--text-primary);" /></label>
      <Badge tone="info">총 {{ guide.total }}개</Badge>
    </div>
    <LoadingBlock v-if="!guide.loaded && !guide.error" compact label="기능 지도를 읽는 중…" />
    <div v-else-if="guide.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ guide.error }}</div>
    <Card v-for="g in groups" :key="g.tab" :title="g.tab_label" :subtitle="g.menu?.subtitle" :icon="g.menu?.icon ?? MapIcon">
      <template #actions><Badge>{{ g.items.length }}</Badge></template>
      <div class="rounded-md overflow-hidden" style="border: 1px solid var(--border-default);">
        <div v-for="f in g.items" :key="f.name" class="row grid grid-cols-1 md:grid-cols-[180px_minmax(0,1fr)_minmax(0,1fr)_auto] gap-x-4 gap-y-1 items-center px-3 py-2.5 text-sm" style="background: var(--bg-elevated);">
          <div class="font-semibold" style="color: var(--text-primary);">{{ f.name }}</div>
          <div style="color: var(--text-secondary);">{{ f.desc }}</div>
          <div class="text-xs" style="color: var(--text-muted);">{{ f.how }}</div>
          <div class="flex items-center gap-2 justify-end"><code class="text-[11px] font-mono hidden xl:inline" style="color: var(--text-muted);">{{ f.path }}</code><Button size="sm" variant="secondary" @click="router.push(f.path)">이동 <ArrowRight :size="13" :stroke-width="2" /></Button></div>
        </div>
      </div>
    </Card>
  </div>
</template>

<style scoped>
.row + .row { border-top: 1px solid var(--border-default); }
</style>
