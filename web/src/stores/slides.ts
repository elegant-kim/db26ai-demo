import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { errorMessage } from '@/lib/api'
import { getSlides, parseSlideRef, pathBelongsTo, type Deck, type SlideAnchor, type SlidesCatalog } from '@/lib/slides'

/**
 * 장표 뷰어 상태 — 카탈로그(한 번 읽음) + 열린 덱/쪽. 뷰어 컴포넌트(SlideViewer)는 AppShell 에 하나만 있고,
 * 페이지 헤더 「장표」 버튼 · ⌘K · `?slide=` 딥링크 · 매뉴얼 › 장표 가 전부 이 스토어의 open* 을 부른다.
 */
export const useSlidesStore = defineStore('slides', () => {
  const catalog = ref<SlidesCatalog | null>(null)
  const loaded = ref(false)
  const error = ref<string | null>(null)
  let inflight: Promise<void> | null = null

  function load(force = false): Promise<void> {
    if (loaded.value && !force) return Promise.resolve()
    if (inflight) return inflight
    inflight = (async () => {
      try { catalog.value = await getSlides(); loaded.value = true; error.value = null }
      catch (e) { error.value = errorMessage(e) }
      finally { inflight = null }
    })()
    return inflight
  }

  const decks = computed<Deck[]>(() => catalog.value?.decks ?? [])
  const anchors = computed<SlideAnchor[]>(() => catalog.value?.anchors ?? [])
  const available = computed(() => !!catalog.value?.available)
  const deckById = (id: string) => decks.value.find((d) => d.deck === id) ?? null
  /** 꼬리표 → (덱, 쪽). 여러 덱에 같은 꼬리표가 있으면 첫 덱 */
  function locate(tag: string): { deck: Deck; page: number } | null {
    for (const d of decks.value) { const p = d.tags?.[tag]; if (p) return { deck: d, page: p } }
    return null
  }
  /** 지금 화면(경로 + 서브탭)에 연결된 앵커 — 같은 꼬리표는 한 번만 */
  function anchorsFor(routePath: string, routeSub: string | null): SlideAnchor[] {
    const seen = new Set<string>()
    return anchors.value.filter((a) => pathBelongsTo(a.path, routePath, routeSub) && !seen.has(a.tag) && seen.add(a.tag))
  }

  // ── 뷰어 ──
  const open = ref(false)
  const deck = ref<Deck | null>(null)
  const page = ref(1)
  /** 뷰어 하단에 보여줄 "이 화면의 장표" 목록 — 연 쪽의 문맥 */
  const context = ref<SlideAnchor[]>([])
  const currentTag = computed(() => (deck.value ? deck.value.page_tags?.[page.value - 1] ?? null : null))
  const pageCount = computed(() => deck.value?.pages ?? 0)

  function openDeck(d: Deck, p = 1, ctx: SlideAnchor[] = []) {
    deck.value = d; page.value = Math.min(Math.max(1, p), d.pages ?? p); context.value = ctx; open.value = true
  }
  /** 꼬리표로 연다. 덱에 없으면 false (호출자가 토스트 등으로 알린다) */
  function openTag(tag: string, ctx: SlideAnchor[] = []): boolean {
    const hit = locate(tag)
    if (!hit) return false
    openDeck(hit.deck, hit.page, ctx)
    return true
  }
  /** `?slide=` 값(꼬리표 또는 deck:page)으로 연다 */
  async function openRef(v: unknown, ctx: SlideAnchor[] = []): Promise<boolean> {
    const ref_ = parseSlideRef(v)
    if (!ref_) return false
    await load()
    if (ref_.tag) return openTag(ref_.tag, ctx)
    const d = ref_.deck ? deckById(ref_.deck) : null
    if (!d) return false
    openDeck(d, ref_.page ?? 1, ctx)
    return true
  }
  function close() { open.value = false }
  function go(delta: number) {
    if (!deck.value) return
    const max = deck.value.pages ?? page.value
    page.value = Math.min(max, Math.max(1, page.value + delta))
  }
  function goto(p: number) { if (deck.value) page.value = Math.min(deck.value.pages ?? p, Math.max(1, p)) }

  return { catalog, loaded, error, load, decks, anchors, available, deckById, locate, anchorsFor,
    open, deck, page, context, currentTag, pageCount, openDeck, openTag, openRef, close, go, goto }
})
