<script setup lang="ts">
/** 문서 뷰어 — 왼쪽 목록 + 오른쪽 md-body 본문. 매뉴얼 탭의 「사용 설명서」·「현재 상태·계획」 공용. */
import { ref, watch } from 'vue'
import { FileText } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import { errorMessage } from '@/lib/api'
import { getGuideDoc, type DocMeta, type GuideDoc } from '@/lib/guide'
import { renderMarkdown } from '@/lib/markdown'

const props = defineProps<{ docs: DocMeta[]; modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
const doc = ref<GuideDoc | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const cache = new Map<string, GuideDoc>()

async function load(key: string) {
  if (!key) { doc.value = null; return }
  if (cache.has(key)) { doc.value = cache.get(key)!; return }
  loading.value = true; error.value = null
  try { const d = await getGuideDoc(key); if (!d.success) throw new Error(d.error || '문서를 찾을 수 없습니다.'); cache.set(key, d); doc.value = d }
  catch (e) { error.value = errorMessage(e); doc.value = null } finally { loading.value = false }
}
watch(() => props.modelValue, (k) => { void load(k) }, { immediate: true })
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-[250px_minmax(0,1fr)] gap-4 items-start">
    <div class="rounded-md overflow-hidden lg:sticky lg:top-4" style="border: 1px solid var(--border-default);">
      <button v-for="d in docs" :key="d.key" class="item w-full text-left px-3 py-2.5" :disabled="!d.available"
        :style="{ background: d.key === modelValue ? 'var(--accent-primary-soft)' : 'var(--bg-elevated)', opacity: d.available ? 1 : 0.5 }" @click="emit('update:modelValue', d.key)">
        <div class="text-sm font-medium" :style="{ color: d.key === modelValue ? 'var(--accent-primary)' : 'var(--text-primary)' }">{{ d.title }}<span v-if="!d.available" class="text-xs ml-1" style="color: var(--text-muted);">(미작성)</span></div>
        <div class="text-xs mt-0.5" style="color: var(--text-muted);">{{ d.subtitle }}</div>
      </button>
    </div>
    <Card :title="doc?.title" :subtitle="doc?.subtitle" :icon="FileText">
      <LoadingBlock v-if="loading" compact label="문서를 읽는 중…" />
      <div v-else-if="error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ error }}</div>
      <div v-else-if="doc" class="md-body text-sm doc-body" style="color: var(--text-primary);" v-html="renderMarkdown(doc.content)" />
      <EmptyState v-else :icon="FileText" title="왼쪽에서 문서를 고르세요" compact />
    </Card>
  </div>
</template>

<style scoped>
.item + .item { border-top: 1px solid var(--border-default); }
.item:hover:not(:disabled) { background: var(--bg-surface) !important; }
.doc-body :deep(h1) { font-size: 1.35em; padding-bottom: 0.3em; border-bottom: 1px solid var(--border-default); }
</style>
