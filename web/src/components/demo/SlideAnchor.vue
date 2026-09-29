<script setup lang="ts">
/**
 * 「장표 n」 버튼 — 지금 화면(경로 + ?sub=)에 연결된 장표(기능 레지스트리 `slides`)를 슬라이드오버로 연다. 2026-09-29 P5.
 * 연결된 장표가 없으면 렌더하지 않는다(덱이 없어도 앱은 그대로). `tags` 를 주면 그 꼬리표만(카드 단위 앵커용).
 * PageHeader 가 자동으로 하나 넣으므로 페이지마다 따로 붙일 필요가 없다.
 */
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Presentation } from 'lucide-vue-next'
import Button from '@/components/ui/Button.vue'
import { useSlidesStore } from '@/stores/slides'
import type { SlideAnchor } from '@/lib/slides'

const props = defineProps<{ tags?: string[]; label?: string }>()
const slides = useSlidesStore()
const route = useRoute()
onMounted(() => { void slides.load() })

const list = computed<SlideAnchor[]>(() => {
  const sub = typeof route.query.sub === 'string' ? route.query.sub : null
  if (props.tags?.length) {
    const want = new Set(props.tags)
    const found = slides.anchors.filter((a) => want.has(a.tag))
    // 레지스트리에 없는 꼬리표라도 덱에 있으면 연다
    const extra = props.tags.filter((t) => !found.some((a) => a.tag === t)).map((t) => { const l = slides.locate(t); return l ? { tag: t, feature: l.deck.title, tab: '', tab_label: '', path: route.fullPath, deck: l.deck.deck, deck_title: l.deck.title, page: l.page } : null }).filter((x): x is SlideAnchor => !!x)
    return [...found, ...extra]
  }
  return slides.anchorsFor(route.path, sub)
})
function show() { const first = list.value[0]; if (first) slides.openTag(first.tag, list.value) }
</script>

<template>
  <Button v-if="list.length" variant="secondary" size="sm" :title="list.map((a) => `${a.tag} · ${a.feature}`).join('\n')" @click="show">
    <Presentation :size="14" :stroke-width="1.75" /> {{ label ?? '장표' }}
    <span class="text-[11px] px-1.5 rounded-full" style="background: var(--accent-primary-soft); color: var(--accent-primary); min-width: 1.25rem; line-height: 1.25rem;">{{ list.length }}</span>
  </Button>
</template>
