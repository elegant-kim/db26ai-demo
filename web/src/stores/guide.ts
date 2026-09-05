import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { errorMessage } from '@/lib/api'
import { getFeatures, getGuideDocs, type DocMeta, type FeatureGroup } from '@/lib/guide'

/** 매뉴얼 탭과 ⌘K 팔레트가 같이 쓰는 카탈로그 — 한 번만 읽는다. */
export const useGuideStore = defineStore('guide', () => {
  const guides = ref<DocMeta[]>([])
  const docs = ref<DocMeta[]>([])
  const groups = ref<FeatureGroup[]>([])
  const total = ref(0)
  const loaded = ref(false)
  const error = ref<string | null>(null)
  let inflight: Promise<void> | null = null

  function load(): Promise<void> {
    if (loaded.value) return Promise.resolve()
    if (inflight) return inflight
    inflight = (async () => {
      try {
        const [d, f] = await Promise.all([getGuideDocs(), getFeatures()])
        guides.value = d.guides ?? []; docs.value = d.docs ?? []; groups.value = f.groups ?? []; total.value = f.total ?? 0
        loaded.value = true; error.value = null
      } catch (e) { error.value = errorMessage(e) } finally { inflight = null }
    })()
    return inflight
  }
  const features = computed(() => groups.value.flatMap((g) => g.items))

  // ⌘K 팔레트
  const paletteOpen = ref(false)
  const togglePalette = () => { paletteOpen.value = !paletteOpen.value }
  const showPalette = () => { paletteOpen.value = true }
  const hidePalette = () => { paletteOpen.value = false }

  return { guides, docs, groups, total, loaded, error, load, features, paletteOpen, togglePalette, showPalette, hidePalette }
})
