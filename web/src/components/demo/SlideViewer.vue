<script setup lang="ts">
/**
 * 장표 뷰어 — 오른쪽 슬라이드오버(「실행 쿼리 확인」과 같은 자리·같은 부품). AppShell 에 하나만 둔다. 2026-09-29 P5.
 * 이미지 모드(변환한 덱: /slides/out/<deck>/001.webp)와 PDF 모드(변환 전: 브라우저 내장 뷰어 iframe)를 한 컴포넌트가 받는다.
 * URL 의 `?slide=` 와 양방향 동기화 — 앵커·⌘K·시연 대본 링크가 전부 이 쿼리로 들어오고, 쪽을 넘기면 쿼리가 따라간다.
 */
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Presentation, ChevronLeft, ChevronRight, X as XIcon, FileText, ExternalLink } from 'lucide-vue-next'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import { pageImage, pdfUrl } from '@/lib/slides'
import { useSlidesStore } from '@/stores/slides'

const slides = useSlidesStore()
const route = useRoute()
const router = useRouter()

const img = computed(() => (slides.deck ? pageImage(slides.deck, slides.page) : null))
const pdf = computed(() => (slides.deck ? pdfUrl(slides.deck, slides.page) : null))
const pdfOnly = computed(() => slides.deck?.mode === 'pdf')
/** 지금 열린 쪽을 가리키는 딥링크 값 — 꼬리표가 있으면 꼬리표, 없으면 deck:page */
const currentRef = computed(() => (slides.deck ? slides.currentTag ?? `${slides.deck.deck}:${slides.page}` : null))
const pages = computed(() => Array.from({ length: slides.pageCount }, (_, i) => i + 1))

function onKey(e: KeyboardEvent) {
  if (!slides.open) return
  if (e.key === 'Escape') { e.preventDefault(); slides.close() }
  else if (e.key === 'ArrowRight' || e.key === 'PageDown') { e.preventDefault(); slides.go(1) }
  else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); slides.go(-1) }
}
onMounted(() => { window.addEventListener('keydown', onKey); void slides.load() })
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

// 뷰어 → URL: 연 쪽이 바뀌면 ?slide= 를 맞춘다. 닫으면 지운다.
watch([() => slides.open, currentRef], ([open, ref_]) => {
  const cur = typeof route.query.slide === 'string' ? route.query.slide : undefined
  if (open && ref_ && cur !== ref_) void router.replace({ query: { ...route.query, slide: ref_ } })
  else if (!open && cur !== undefined) { const q = { ...route.query }; delete q.slide; void router.replace({ query: q }) }
})
// URL → 뷰어: 딥링크로 들어오거나 ⌘K 가 path 를 바꾸면 연다. 페이지를 옮겨 ?slide= 가 사라지면 닫는다.
watch(() => route.query.slide, async (v) => {
  const s = typeof v === 'string' ? v : ''
  if (!s) { if (slides.open) slides.close(); return }
  if (slides.open && currentRef.value === s) return
  const ctx = slides.anchorsFor(route.path, typeof route.query.sub === 'string' ? route.query.sub : null)
  const ok = await slides.openRef(s, ctx)
  if (!ok) { const q = { ...route.query }; delete q.slide; void router.replace({ query: q }) }
}, { immediate: true })
</script>

<template>
  <Teleport to="body">
    <div v-if="slides.open && slides.deck" class="fixed inset-0 z-[60]" style="background: rgba(0,0,0,0.4);" @click.self="slides.close()">
      <aside class="absolute right-0 top-0 bottom-0 w-full max-w-[1040px] flex flex-col" style="background: var(--bg-base); box-shadow: var(--shadow-elevated);">
        <header class="flex items-center justify-between gap-3 px-5 shrink-0" style="height: 56px; border-bottom: 1px solid var(--border-default);">
          <div class="flex items-center gap-2 min-w-0">
            <Presentation :size="18" :stroke-width="1.75" style="color: var(--accent-primary);" />
            <span class="font-semibold text-base truncate" style="color: var(--text-primary);">{{ slides.deck.title }}</span>
            <Badge v-if="slides.currentTag" tone="code">{{ slides.currentTag }}</Badge>
            <Badge v-if="pdfOnly" tone="warm">PDF · 변환 전</Badge>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <Button variant="secondary" size="sm" :disabled="slides.page <= 1" title="이전 쪽 (←)" @click="slides.go(-1)"><ChevronLeft :size="14" :stroke-width="2" /></Button>
            <span class="text-sm tabular-nums px-1" style="color: var(--text-secondary);">{{ slides.page }}<span v-if="slides.pageCount"> / {{ slides.pageCount }}</span></span>
            <Button variant="secondary" size="sm" :disabled="!!slides.pageCount && slides.page >= slides.pageCount" title="다음 쪽 (→)" @click="slides.go(1)"><ChevronRight :size="14" :stroke-width="2" /></Button>
            <a v-if="slides.deck.pdf" :href="slides.deck.pdf" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-xs px-2 py-1.5 rounded-md ml-1" style="color: var(--text-secondary);" title="원본 PDF 를 새 탭에서"><FileText :size="14" :stroke-width="1.75" /> PDF <ExternalLink :size="11" :stroke-width="1.75" /></a>
            <button class="p-1.5 rounded-md ml-1" style="color: var(--text-secondary);" title="닫기 (ESC)" @click="slides.close()"><XIcon :size="18" :stroke-width="1.75" /></button>
          </div>
        </header>

        <div class="flex-1 overflow-auto p-5 flex flex-col gap-4">
          <!-- 장표 본체 -->
          <div class="rounded-lg overflow-hidden flex items-center justify-center" style="background: var(--bg-surface); border: 1px solid var(--border-default); min-height: 200px;">
            <img v-if="img" :src="img" :alt="`${slides.deck.title} ${slides.page}쪽`" class="block w-full h-auto" style="max-height: calc(100vh - 260px); object-fit: contain;" />
            <iframe v-else-if="pdf" :key="pdf" :src="pdf" class="block w-full" style="height: calc(100vh - 260px); border: 0;" :title="`${slides.deck.title} ${slides.page}쪽`" />
          </div>

          <!-- 쪽 이동 줄 — 꼬리표가 있는 쪽은 툴팁에 꼬리표 -->
          <div v-if="pages.length > 1" class="flex flex-wrap gap-1">
            <button v-for="p in pages" :key="p" class="text-[11px] tabular-nums px-1.5 py-0.5 rounded" :title="slides.deck.page_tags?.[p - 1] ?? `${p}쪽`"
              :style="{ background: p === slides.page ? 'var(--accent-primary)' : 'var(--bg-surface)', color: p === slides.page ? 'var(--text-on-accent)' : 'var(--text-secondary)', boxShadow: p === slides.page ? 'none' : 'inset 0 0 0 1px var(--border-default)' }"
              @click="slides.goto(p)">{{ p }}</button>
          </div>

          <!-- 이 화면에 연결된 장표 -->
          <div v-if="slides.context.length > 1" class="rounded-md px-3 py-2.5 text-sm" style="background: var(--bg-elevated); border: 1px solid var(--border-default);">
            <div class="text-[11px] font-semibold uppercase tracking-wider mb-1.5" style="color: var(--text-muted);">이 화면에 연결된 장표</div>
            <div class="flex flex-col gap-1">
              <button v-for="a in slides.context" :key="a.tag" class="flex items-center gap-2 text-left px-2 py-1 rounded"
                :style="{ background: a.tag === slides.currentTag ? 'var(--accent-primary-soft)' : 'transparent', color: 'var(--text-primary)' }"
                @click="slides.openTag(a.tag, slides.context)">
                <Badge tone="code">{{ a.tag }}</Badge><span class="flex-1 truncate">{{ a.feature }}</span><span class="text-xs" style="color: var(--text-muted);">{{ a.deck_title }} · {{ a.page }}쪽</span>
              </button>
            </div>
          </div>
          <p v-if="pdfOnly" class="text-xs m-0" style="color: var(--text-muted);">변환 전 PDF 라 브라우저 내장 뷰어로 엽니다 — 쪽 지정은 Chrome 계열에서만 확실합니다. <code class="font-mono">scripts/slides_import.py</code> 를 돌리면 이미지 뷰어로 바뀝니다.</p>
        </div>

        <footer class="px-5 py-1.5 flex items-center justify-between text-[10px] shrink-0" style="background: var(--bg-surface); border-top: 1px solid var(--border-default); color: var(--text-muted);">
          <span>← → 쪽 이동 · ESC 닫기</span><span class="font-mono">?slide={{ currentRef }}</span>
        </footer>
      </aside>
    </div>
  </Teleport>
</template>
