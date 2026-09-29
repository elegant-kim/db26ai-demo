<script setup lang="ts">
/** 매뉴얼 › 장표 — 덱 목록(썸네일 · 쪽 수 · 꼬리표 · 변환 여부) + 앵커 표 + 준비 규칙 요약. 정본: docs/slides/README.md · app/slides.py. 2026-09-29 P5. */
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Presentation, FileText, ExternalLink, AlertTriangle } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import { useSlidesStore } from '@/stores/slides'

const slides = useSlidesStore()
const router = useRouter()
onMounted(() => { void slides.load(true) })
const anchors = computed(() => slides.anchors)
const unresolved = computed(() => slides.catalog?.unresolved ?? [])
const tagCount = (d: { tags: Record<string, number> }) => Object.keys(d.tags ?? {}).length
function openAnchor(a: { path: string; tag: string }) { void router.push(`${a.path}${a.path.includes('?') ? '&' : '?'}slide=${a.tag}`) }
</script>

<template>
  <div class="flex flex-col gap-4">
    <p class="text-sm m-0" style="color: var(--text-secondary);">
      발표 자료를 <b>앱 화면 옆에</b> 띄웁니다. PowerPoint · Keynote 에서 <b>PDF 로 내보내</b> <code class="font-mono">docs/slides/src/&lt;deck&gt;.pdf</code> 에 놓으면 바로 열리고,
      <code class="font-mono">scripts/slides_import.py</code> 를 한 번 돌리면 쪽 이미지와 꼬리표(<code class="font-mono">VS-12</code>) 표가 생깁니다.
      앱은 쪽 번호가 아니라 <b>꼬리표</b>로 장표를 가리키므로 슬라이드 순서를 바꿔도 링크가 안 깨집니다. 어느 기능에 어느 장표를 붙일지는 <code class="font-mono">app/feature_registry.py</code> 의 <code class="font-mono">slides</code> 자리가 정본입니다.
    </p>

    <LoadingBlock v-if="!slides.loaded && !slides.error" compact label="장표 카탈로그를 읽는 중…" />
    <div v-else-if="slides.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ slides.error }}</div>

    <template v-else>
      <Card title="덱" :subtitle="slides.decks.length ? `${slides.decks.length}개 · docs/slides/` : '아직 덱이 없습니다'" :icon="Presentation">
        <template #actions><Badge tone="info">{{ slides.decks.length }}</Badge></template>
        <div v-if="!slides.decks.length" class="rounded-md px-4 py-6 text-sm text-center" style="background: var(--bg-surface); color: var(--text-secondary);">
          <div class="mb-2">덱을 넣으면 여기 나타나고, 페이지 헤더의 「장표」 버튼과 ⌘K 에도 자동으로 붙습니다.</div>
          <code class="font-mono text-xs">docs/slides/src/vector.pdf → ./venv/bin/python scripts/slides_import.py</code>
        </div>
        <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          <div v-for="d in slides.decks" :key="d.deck" class="rounded-md overflow-hidden flex flex-col" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
            <button class="block w-full aspect-video overflow-hidden" style="background: var(--bg-base);" :title="`${d.title} 열기`" @click="slides.openDeck(d, 1)">
              <img v-if="d.thumb" :src="d.thumb" :alt="d.title" class="w-full h-full object-cover" />
              <div v-else class="w-full h-full flex flex-col items-center justify-center gap-1 text-xs" style="color: var(--text-muted);"><FileText :size="28" :stroke-width="1.5" />PDF · 변환 전</div>
            </button>
            <div class="p-3 flex flex-col gap-2 flex-1">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0"><div class="font-semibold text-sm truncate" style="color: var(--text-primary);">{{ d.title }}</div><div class="text-[11px] font-mono" style="color: var(--text-muted);">{{ d.deck }}<span v-if="d.code"> · {{ d.code }}-nn</span></div></div>
                <Badge :tone="d.mode === 'images' ? 'positive' : 'warm'">{{ d.mode === 'images' ? '이미지' : 'PDF' }}</Badge>
              </div>
              <div class="text-xs flex flex-wrap gap-x-3 gap-y-0.5" style="color: var(--text-secondary);">
                <span v-if="d.pages != null">{{ d.pages }}쪽</span><span v-else>쪽 수 미상(변환 전)</span>
                <span>꼬리표 {{ tagCount(d) }}</span>
                <span v-if="d.generated_at">변환 {{ d.generated_at.slice(0, 16).replace('T', ' ') }}</span>
              </div>
              <div class="flex items-center gap-2 mt-auto">
                <Button size="sm" @click="slides.openDeck(d, 1)"><Presentation :size="13" :stroke-width="1.75" /> 열기</Button>
                <a v-if="d.pdf" :href="d.pdf" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-xs" style="color: var(--text-secondary);">PDF <ExternalLink :size="11" :stroke-width="1.75" /></a>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <Card title="기능에 연결된 장표" :subtitle="anchors.length ? `${anchors.length}개 — 페이지 헤더 「장표」 버튼과 ⌘K 가 이 표를 본다` : '아직 없음 — feature_registry.py 의 slides 자리에 꼬리표를 적으면 여기 나타난다'">
        <template #actions><Badge>{{ anchors.length }}</Badge></template>
        <div v-if="anchors.length" class="rounded-md overflow-hidden" style="border: 1px solid var(--border-default);">
          <div v-for="a in anchors" :key="a.tag + a.feature" class="row grid grid-cols-[90px_minmax(0,1fr)_minmax(0,1fr)_auto] gap-x-4 items-center px-3 py-2 text-sm" style="background: var(--bg-elevated);">
            <Badge tone="code">{{ a.tag }}</Badge>
            <div class="truncate"><span class="font-medium" style="color: var(--text-primary);">{{ a.feature }}</span> <span class="text-xs" style="color: var(--text-muted);">{{ a.tab_label }}</span></div>
            <div class="text-xs truncate" style="color: var(--text-secondary);">{{ a.deck_title }} · {{ a.page }}쪽</div>
            <Button size="sm" variant="secondary" @click="openAnchor(a)">화면 + 장표</Button>
          </div>
        </div>
        <div v-if="unresolved.length" class="mt-3 rounded-md px-3 py-2.5 text-sm flex gap-2" style="background: var(--accent-warm-soft); border-left: 3px solid var(--accent-warm); color: var(--text-primary);">
          <AlertTriangle :size="16" :stroke-width="1.75" class="shrink-0 mt-0.5" />
          <div><b>덱에 없는 꼬리표 {{ unresolved.length }}</b> — 레지스트리에는 있는데 어느 덱에서도 못 찾았습니다(덱이 아직 없거나 꼬리표 오타). 화면에서는 조용히 빠집니다.
            <div class="mt-1 flex flex-wrap gap-1"><Badge v-for="u in unresolved" :key="u.tag + u.feature" tone="code" :title="u.feature">{{ u.tag }} · {{ u.feature }}</Badge></div></div>
        </div>
      </Card>
    </template>
  </div>
</template>

<style scoped>
.row + .row { border-top: 1px solid var(--border-default); }
</style>
