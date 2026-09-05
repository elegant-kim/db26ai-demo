<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { UploadCloud, FileText, Trash2 } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import PipelineProgress from '@/components/demo/PipelineProgress.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import { fmtNum, fmtDateTime } from '@/lib/format'
import { useVectorStore } from '@/stores/vector'

const v = useVectorStore()
const input = ref<HTMLInputElement | null>(null)
const over = ref(false)
const pendingDelete = ref<{ doc_id: number; filename: string } | null>(null)
onMounted(() => { void v.loadDocs(); void v.loadConfig() })
function pick(files: FileList | null) { const f = files?.[0]; if (f) void v.upload(f) }
const steps = computed(() => v.pipeline.map((p) => ({ label: p.label, detail: p.detail, time: p.duration_ms ? `${fmtNum(p.duration_ms)}ms` : undefined })))
const current = computed(() => (v.uploading ? v.currentStep : v.pipeline.length + 1))
const barLabel = computed(() => (v.progress ? `${v.progress.current}/${v.progress.total} (${v.progress.percent}%)` : undefined))
const tone = (s: string) => (s === 'indexed' ? 'positive' : s === 'processing' ? 'info' : s === 'error' ? 'negative' : 'default')
</script>

<template>
  <div class="flex flex-col gap-5">
    <Card title="PDF 업로드" subtitle="문서 등록 → 텍스트 추출 → 청크 분할(DBMS_VECTOR_CHAIN, 실패 시 파이썬) → 임베딩 & 저장 → 인덱싱. 진행은 SSE 로 실시간" :icon="UploadCloud">
      <div v-if="v.dimensionWarning" class="mb-3 px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-warm-soft); border-left: 3px solid var(--accent-warm); color: var(--text-primary);">⚠ {{ v.dimensionWarning }}</div>
      <div class="drop rounded-lg flex flex-col items-center justify-center gap-1.5 px-4 py-7 cursor-pointer text-center" :class="{ over, busy: v.uploading }"
        @click="!v.uploading && input?.click()" @dragover.prevent="over = true" @dragleave="over = false" @drop.prevent="over = false; !v.uploading && pick($event.dataTransfer?.files ?? null)">
        <UploadCloud :size="28" :stroke-width="1.5" style="color: var(--accent-primary);" />
        <div class="text-sm font-medium" style="color: var(--text-primary);">PDF 파일을 놓거나 클릭해서 선택</div>
        <div class="text-xs" style="color: var(--text-muted);">최대 10MB · 임베딩 {{ v.sourceLabel }} · {{ v.model || '—' }} (첫 청크는 ONNX 콜드스타트로 수 초 걸릴 수 있음)</div>
        <input ref="input" type="file" accept=".pdf" class="hidden" @change="pick(($event.target as HTMLInputElement).files); ($event.target as HTMLInputElement).value = ''" />
      </div>
      <div v-if="v.uploadError" class="mt-3 px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ v.uploadError }}</div>
      <div v-if="v.pipeline.length" class="mt-4 rounded-md p-4" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
        <PipelineProgress :title="v.uploading ? 'PDF 처리 파이프라인 실행 중' : '파이프라인 완료'" subtitle="문서 → 텍스트 → 청크 → 임베딩 → DB 저장" :steps="steps" :current="current"
          :percent="v.ringPercent" :elapsed-sec="v.uploadElapsedSec" :bar-percent="v.uploading && v.currentStep === 4 && v.progress ? v.progress.percent : null" :bar-label="barLabel" />
        <div v-if="v.uploadResult" class="mt-3 flex flex-wrap items-center gap-1.5 text-xs" style="color: var(--text-secondary);">
          <Badge tone="positive">{{ v.uploadResult.filename }}</Badge>
          <span>{{ v.uploadResult.pages_count ?? '—' }}쪽 · 청크 {{ v.uploadResult.chunks_count }}개 · 임베딩 {{ v.uploadResult.embedded_count ?? v.uploadResult.chunks_count }}개 · {{ ((v.uploadResult.total_ms || 0) / 1000).toFixed(1) }}초</span>
        </div>
        <div v-if="v.uploadResult?.warning" class="mt-2 px-3 py-2 rounded-md text-xs" style="background: var(--accent-warm-soft); border-left: 3px solid var(--accent-warm); color: var(--text-primary);">⚠ {{ v.uploadResult.warning }}</div>
      </div>
    </Card>

    <Card title="업로드된 문서" :subtitle="v.docs.length ? `${v.docs.length}개 · 인덱스 ${v.indexInfo?.embedding_model ?? '—'} (${v.indexInfo?.vector_dimensions ?? '—'}차원) · 임베딩 완료 청크 ${v.indexInfo?.embedded_chunks ?? '—'}/${v.indexInfo?.total_chunks ?? '—'}` : '아직 없습니다'" :icon="FileText">
      <template #actions><Button variant="ghost" size="sm" @click="v.loadDocs(); v.loadConfig(true)">새로고침</Button></template>
      <EmptyState v-if="!v.docs.length" :icon="FileText" title="문서가 없습니다" desc="위에서 PDF 를 올리세요. 예시 질문은 자동차보험약관 · 카드 개인회원약관 · 공공언어바로쓰기 PDF 를 전제로 합니다." compact />
      <div v-else class="rounded-md overflow-hidden" style="border: 1px solid var(--border-default);">
        <div v-for="d in v.docs" :key="d.doc_id" class="row flex items-center gap-3 px-3 py-2 text-sm" style="background: var(--bg-elevated);">
          <FileText :size="16" :stroke-width="1.75" class="shrink-0" style="color: var(--text-muted);" />
          <span class="flex-1 min-w-0 truncate font-medium" style="color: var(--text-primary);">{{ d.filename }}</span>
          <Badge :tone="tone(d.status)">{{ d.status }}</Badge>
          <span class="text-xs tabular-nums" style="color: var(--text-secondary);">{{ fmtNum(d.chunks_count) }}청크<template v-if="d.embed_dim"> · {{ d.embed_dim }}차원</template></span>
          <span class="text-xs hidden md:inline" style="color: var(--text-muted);">{{ fmtDateTime(d.upload_date) }}</span>
          <button class="p-1 rounded" style="color: var(--text-muted);" title="삭제" @click="pendingDelete = { doc_id: d.doc_id, filename: d.filename }"><Trash2 :size="15" :stroke-width="1.75" /></button>
        </div>
      </div>
    </Card>

    <ConfirmModal :open="!!pendingDelete" :title="`문서를 삭제할까요? — ${pendingDelete?.filename ?? ''}`" danger confirm-label="삭제" @confirm="v.removeDoc(pendingDelete!.doc_id); pendingDelete = null" @cancel="pendingDelete = null">
      문서와 청크·임베딩이 함께 지워집니다. 되돌리려면 다시 올려야 합니다.
    </ConfirmModal>
  </div>
</template>

<style scoped>
.drop { border: 2px dashed var(--border-strong); background: var(--bg-surface); transition: border-color 150ms, background 150ms; }
.drop:hover, .drop.over { border-color: var(--accent-primary); background: var(--accent-primary-soft); }
.drop.busy { opacity: 0.6; cursor: progress; }
.row + .row { border-top: 1px solid var(--border-default); }
</style>
