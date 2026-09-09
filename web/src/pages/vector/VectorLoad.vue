<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { UploadCloud, FileText, Trash2, ChevronRight, ChevronDown } from 'lucide-vue-next'
import SqlBlock from '@/components/demo/SqlBlock.vue'
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
// 단계별 실행 내역 — 서버가 단계마다 실행한 SQL 과 결과 표본을 보낸다(2026-09-09 P2). 기본은 접힘, 라벨을 누르면 펼친다.
const openStep = ref<Record<number, boolean>>({})
const toggleStep = (n: number) => { openStep.value[n] = !openStep.value[n] }
const stepsWithSql = computed(() => v.pipeline.filter((p) => p.status === 'done' && (p.sql || p.sample)))
const tone = (s: string) => (s === 'indexed' ? 'positive' : s === 'processing' ? 'info' : s === 'error' ? 'negative' : 'default')
</script>

<template>
  <div class="flex flex-col gap-5">
    <Card title="PDF 업로드" subtitle="문서 등록 → 텍스트 추출(앱 · pdfplumber, 쪽 번호 보존) → 청크 분할(DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS) → 임베딩(DB 안 UPDATE … VECTOR_EMBEDDING, 20청크씩) → 인덱싱(HNSW 자동 · Hybrid Vector Index 동기화). 진행은 SSE 로 실시간" :icon="UploadCloud">
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
        <PipelineProgress :title="v.uploading ? 'PDF 처리 파이프라인 실행 중' : '파이프라인 완료'" subtitle="추출만 앱에서, 청킹 · 임베딩 · 인덱싱은 DB 안에서" :steps="steps" :current="current"
          :percent="v.ringPercent" :elapsed-sec="v.uploadElapsedSec" :bar-percent="v.uploading && v.currentStep === 4 && v.progress ? v.progress.percent : null" :bar-label="barLabel" />

        <!-- 단계별 실행 내역 — 어떤 SQL 이 돌았고 무엇이 나왔나 -->
        <div v-if="stepsWithSql.length" class="mt-4 flex flex-col gap-1.5">
          <div class="text-xs font-semibold" style="color: var(--text-secondary);">단계별 실행 내역 — 라벨을 누르면 실행된 SQL 과 결과 표본</div>
          <div v-for="p in stepsWithSql" :key="p.step" class="rounded-md overflow-hidden" style="border: 1px solid var(--border-default);">
            <button type="button" class="w-full flex items-center gap-2 px-3 py-2 text-left text-sm" style="background: var(--bg-elevated);" @click="toggleStep(p.step)">
              <component :is="openStep[p.step] ? ChevronDown : ChevronRight" :size="14" :stroke-width="2" style="color: var(--text-muted);" />
              <span class="font-semibold" style="color: var(--text-primary);">{{ p.step }}. {{ p.label }}</span>
              <span class="text-xs truncate" style="color: var(--text-muted);">{{ p.detail }}</span>
              <Badge v-if="p.duration_ms" tone="code" class="ml-auto">{{ fmtNum(p.duration_ms) }}ms</Badge>
            </button>
            <div v-if="openStep[p.step]" class="px-3 py-3 flex flex-col gap-3" style="background: var(--bg-surface);">
              <SqlBlock v-if="p.sql" :code="p.sql" :label="p.sql.startsWith('--') ? '이 단계는' : '실행된 SQL'" max-height="180px" />
              <!-- 3단계 표본: 청크가 어떻게 잘렸나 -->
              <template v-if="p.step === 3 && p.sample?.chunks">
                <div class="text-xs" style="color: var(--text-secondary);">파라미터 max_chunk_size {{ p.sample.params?.max_chunk_size }} · overlap {{ p.sample.params?.overlap }} · DB 청킹 {{ p.sample.db_chunked_pages }}/{{ p.sample.pages }}쪽 · 앞 {{ p.sample.chunks.length }}청크 표본</div>
                <div v-for="(c, i) in p.sample.chunks" :key="i" class="rounded-md px-3 py-2 text-xs" style="background: var(--bg-elevated); border: 1px solid var(--border-default);">
                  <div class="flex items-center gap-1.5 mb-1"><Badge tone="code">#{{ i + 1 }} · p.{{ c.page_num }}</Badge><span style="color: var(--text-muted);">{{ c.chars }}자</span></div>
                  <div class="whitespace-pre-wrap line-clamp-3" style="color: var(--text-primary);">{{ c.text }}</div>
                </div>
              </template>
              <!-- 4단계 표본: 텍스트가 숫자가 됐다 -->
              <template v-else-if="p.step === 4 && p.sample?.preview">
                <div class="text-xs" style="color: var(--text-secondary);">청크 #{{ p.sample.chunk_id }} (p.{{ p.sample.page_num }}) → <strong style="color: var(--text-primary);">{{ p.sample.dims }}차원</strong> 벡터. 앞 8개:</div>
                <div class="font-mono text-xs px-3 py-2 rounded-md" style="background: var(--bg-elevated); border: 1px solid var(--border-default); color: var(--text-primary);">[{{ p.sample.preview.join(', ') }}, …]</div>
                <div class="text-xs whitespace-pre-wrap line-clamp-2" style="color: var(--text-muted);">"{{ p.sample.text }}…"</div>
                <SqlBlock v-if="p.sample.sample_sql" :code="p.sample.sample_sql" label="표본 조회" max-height="80px" />
              </template>
              <!-- 5단계 표본: 인덱스가 늘었다 -->
              <template v-else-if="p.step === 5 && p.sample">
                <div class="text-xs" style="color: var(--text-secondary);">{{ p.sample.hybrid_index }} 내부 조각 {{ p.sample.pieces_before ?? '—' }} → <strong style="color: var(--text-primary);">{{ p.sample.pieces_after ?? '—' }}</strong> · SYNC {{ fmtNum(p.sample.sync_ms ?? 0) }}ms</div>
              </template>
            </div>
          </div>
        </div>
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
