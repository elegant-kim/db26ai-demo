<script setup lang="ts">
import { computed, ref } from 'vue'
import { UploadCloud, FileText } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import { useAwrStore } from '@/stores/awr'
import { useSystemStore } from '@/stores/system'

const awr = useAwrStore()
const system = useSystemStore()
const input = ref<HTMLInputElement | null>(null)
const over = ref(false)
const providerOptions = computed(() => [
  { value: '', label: '서버 기본', sub: system.llmModel },
  ...system.providers.map((p) => ({ value: p.id, label: p.name, sub: p.model as string })),
])
function pick(files: FileList | null) { const f = files?.[0]; if (f) void awr.analyze(f) }
</script>

<template>
  <Card title="AWR 리포트 업로드 & AI 분석" subtitle="AWR HTML 을 올리면 23개 핵심 섹션을 추출해 8개 보고서(시스템 개요 · 병목 · Top SQL · I/O · Hot Segments · 메모리 · Host CPU · 종합 권고)와 카테고리 점수·액션아이템을 만듭니다" :icon="FileText">
    <template #actions>
      <label class="text-xs" style="color: var(--text-muted);">LLM</label>
      <div class="w-[240px]"><SearchableSelect v-model="awr.provider" :options="providerOptions" placeholder="LLM 제공자" :searchable="false" /></div>
    </template>
    <div class="drop rounded-lg flex flex-col items-center justify-center gap-1.5 px-4 py-8 cursor-pointer text-center" :class="{ over, busy: awr.loading }"
      @click="!awr.loading && input?.click()" @dragover.prevent="over = true" @dragleave="over = false" @drop.prevent="over = false; !awr.loading && pick($event.dataTransfer?.files ?? null)">
      <UploadCloud :size="30" :stroke-width="1.5" style="color: var(--accent-primary);" />
      <div class="text-sm font-medium" style="color: var(--text-primary);">AWR HTML 파일을 놓거나 클릭해서 선택</div>
      <div class="text-xs" style="color: var(--text-muted);">최대 20MB · 분석은 30~120초 걸리고 결과는 한 번에 옵니다 (현재 LLM: {{ awr.providerLabel }})</div>
      <input ref="input" type="file" accept=".html,.htm" class="hidden" @change="pick(($event.target as HTMLInputElement).files); ($event.target as HTMLInputElement).value = ''" />
    </div>
  </Card>
</template>

<style scoped>
.drop { border: 2px dashed var(--border-strong); background: var(--bg-surface); transition: border-color 150ms, background 150ms; }
.drop:hover, .drop.over { border-color: var(--accent-primary); background: var(--accent-primary-soft); }
.drop.busy { opacity: 0.6; cursor: progress; }
</style>
