<script setup lang="ts">
/** 사용 설명서(guides) / 현재 상태·계획(docs) — 같은 DocViewer, 목록만 다르다. `?doc=key` 로 딥링크. */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DocViewer from '@/components/demo/DocViewer.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import { useGuideStore } from '@/stores/guide'

const props = defineProps<{ kind: 'guides' | 'docs' }>()
const guide = useGuideStore()
const route = useRoute()
const router = useRouter()
const list = computed(() => (props.kind === 'guides' ? guide.guides : guide.docs))
const key = ref('')
onMounted(() => {
  void guide.load().then(() => {
    const want = typeof route.query.doc === 'string' ? route.query.doc : ''
    const first = list.value.find((d) => d.available)?.key ?? ''
    key.value = list.value.some((d) => d.key === want && d.available) ? want : first
  })
})
watch(key, (k) => { if (k && route.query.doc !== k) void router.replace({ query: { ...route.query, doc: k } }) })
</script>

<template>
  <LoadingBlock v-if="!guide.loaded" compact label="문서 목록을 읽는 중…" />
  <DocViewer v-else v-model="key" :docs="list" />
</template>
