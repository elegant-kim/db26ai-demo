<script setup lang="ts">
/**
 * 「피드백 · Few-shot」 서브탭 (PoC 2-A, 2026-09-30) — 고객이 만든 (질문, SQL, 설명) 파일을 positive 피드백으로 일괄 등록.
 * 업로드 → 미리보기 → 검증(EXPLAIN PLAN) → 등록(SSE, 행당 SELECT AI 1회라 수 초씩) → 실패만 재시도. 아래는 등록된 피드백 목록 + 개별/전체 삭제.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Upload, FileDown, CheckCircle2, XCircle, Play, RotateCcw, Trash2, ThumbsUp, ThumbsDown, Eraser, ChevronDown, ChevronRight } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import { fmtDateTime, fmtMs } from '@/lib/format'
import { TEMPLATE_URL } from '@/lib/fewshot'
import { useFewshotStore } from '@/stores/fewshot'
import { useNl2sqlStore } from '@/stores/nl2sql'

const f = useFewshotStore()
const s = useNl2sqlStore()
const route = useRoute()
const fileInput = ref<HTMLInputElement | null>(null)
const openSql = ref<Record<number, boolean>>({})
const confirmPurge = ref(false)
const purging = ref(false)
onMounted(() => { void s.init(route.query.profile).then(() => f.loadFeedback(s.profile)) })
watch(() => s.profile, (p) => { if (p && f.feedbackFor !== p) void f.loadFeedback(p) })

function onFile(e: Event) { const file = (e.target as HTMLInputElement).files?.[0]; if (file) void f.load(file); (e.target as HTMLInputElement).value = '' }
function onDrop(e: DragEvent) { const file = e.dataTransfer?.files?.[0]; if (file) void f.load(file) }
const percent = computed(() => (f.rows.length && f.registering ? Math.round((f.doneCount / Math.max(1, f.validRows.length)) * 100) : null))
const stateOf = (r: { row: number; valid: boolean | null; error: string | null }) => {
  const res = f.results[r.row]
  if (res) return res.ok ? { label: `등록 ${fmtMs(res.elapsed_ms)}`, tone: 'positive' as const, title: `feedback #${res.feedback_id}` } : { label: '등록 실패', tone: 'negative' as const, title: res.error }
  if (r.valid === true) return { label: '검증 통과', tone: 'info' as const, title: '' }
  if (r.valid === false || r.error) return { label: '검증 실패', tone: 'negative' as const, title: r.error ?? '' }
  return { label: '미검증', tone: 'default' as const, title: '' }
}
async function doPurge() { purging.value = true; await f.purge(s.profile); purging.value = false; confirmPurge.value = false }
</script>

<template>
  <div class="flex flex-col gap-4">
    <div v-if="f.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ f.error }}</div>

    <!-- ① 파일 → 미리보기 → 검증 → 등록 -->
    <Card title="Few-shot 일괄 등록" subtitle="고객이 작성한 (질문, 정답 SQL, 설명) 파일을 positive 피드백으로 한꺼번에 — 유사 질문의 프롬프트에 예시로 주입된다" :icon="Upload">
      <template #actions>
        <a :href="TEMPLATE_URL" class="inline-flex items-center gap-1 text-xs" style="color: var(--accent-primary);"><FileDown :size="13" :stroke-width="1.75" /> 템플릿 CSV</a>
        <Badge tone="code">{{ s.profile || '—' }}</Badge>
      </template>
      <div class="rounded-md px-4 py-5 text-center text-sm mb-3" style="border: 1px dashed var(--border-strong); background: var(--bg-surface); color: var(--text-secondary);" @dragover.prevent @drop.prevent="onDrop">
        <input ref="fileInput" type="file" accept=".csv,.json,.xlsx" class="hidden" @change="onFile" />
        <div class="flex flex-wrap items-center justify-center gap-2">
          <Button size="sm" :busy="f.parsing" @click="fileInput?.click()"><Upload :size="14" :stroke-width="1.75" /> 파일 선택</Button>
          <span>또는 여기에 끌어다 놓기 — CSV · JSON · XLSX, 헤더 <code class="font-mono">question,sql,note</code> (질문/SQL/설명 도 됨)</span>
        </div>
        <div v-if="f.filename" class="mt-2 text-xs" style="color: var(--text-muted);">{{ f.filename }} · {{ f.rows.length }}행 · 헤더 {{ f.headers.join(', ') }}</div>
      </div>

      <template v-if="f.rows.length">
        <div class="flex flex-wrap items-center gap-2 mb-3">
          <Button size="sm" variant="secondary" :busy="f.validating" :disabled="f.registering" title="각 SQL 을 EXPLAIN PLAN 으로 문법·객체 검증 (실행하지 않는다)" @click="f.validate()"><CheckCircle2 :size="14" :stroke-width="1.75" /> 검증</Button>
          <Button size="sm" :busy="f.registering" :disabled="!f.validated || !f.validRows.length" :title="`검증 통과 ${f.validRows.length}건을 ${s.profile} 에 positive 피드백으로 등록 — 행마다 SELECT AI showsql 1회(수 초)`" @click="f.register(s.profile)"><Play :size="14" :stroke-width="1.75" /> 일괄 등록 ({{ f.validRows.length }})</Button>
          <Button v-if="f.failedRows.length && !f.registering" size="sm" variant="secondary" @click="f.register(s.profile, f.failedRows)"><RotateCcw :size="14" :stroke-width="1.75" /> 실패만 재시도 ({{ f.failedRows.length }})</Button>
          <Button v-if="f.registering" size="sm" variant="ghost" @click="f.cancel()">중단</Button>
          <Button size="sm" variant="ghost" :disabled="f.registering" title="미리보기 비우기" @click="f.clear()"><Eraser :size="14" :stroke-width="1.75" /></Button>
          <span v-if="f.registering" class="text-xs" style="color: var(--accent-primary);">등록 중 {{ f.doneCount }} / {{ f.validRows.length }} · ⏱ {{ f.elapsedSec }}초</span>
          <span v-else-if="f.summary" class="text-xs" style="color: var(--text-secondary);">등록 {{ f.summary.ok }} · 실패 {{ f.summary.failed }} · {{ fmtMs(f.summary.elapsed_ms) }}</span>
        </div>
        <div v-if="percent !== null" class="h-1.5 rounded-full mb-3 overflow-hidden" style="background: var(--bg-surface);"><div class="h-full transition-all" :style="{ width: percent + '%', background: 'var(--accent-primary)' }" /></div>

        <div class="rounded-md overflow-auto" style="border: 1px solid var(--border-default); max-height: 480px;">
          <table class="w-full text-sm" style="border-collapse: collapse;">
            <thead><tr style="background: var(--bg-surface); color: var(--text-muted);"><th v-for="c in ['#', '질문', 'SQL', '설명', '상태']" :key="c" class="text-left text-[11px] font-semibold px-3 py-2 whitespace-nowrap">{{ c }}</th></tr></thead>
            <tbody>
              <template v-for="r in f.rows" :key="r.row">
                <tr class="row">
                  <td class="px-3 py-2 font-mono text-xs" style="color: var(--text-muted);">{{ r.row }}</td>
                  <td class="px-3 py-2 max-w-[340px]" style="color: var(--text-primary);">{{ r.question || '—' }}</td>
                  <td class="px-3 py-2 max-w-[360px]"><button type="button" class="inline-flex items-center gap-1 font-mono text-xs text-left" style="color: var(--text-secondary);" @click="openSql[r.row] = !openSql[r.row]"><component :is="openSql[r.row] ? ChevronDown : ChevronRight" :size="12" :stroke-width="2" class="shrink-0" /><span class="truncate max-w-[320px] inline-block align-bottom">{{ r.sql || '—' }}</span></button></td>
                  <td class="px-3 py-2 text-xs max-w-[220px] truncate" style="color: var(--text-secondary);">{{ r.note || '—' }}</td>
                  <td class="px-3 py-2 whitespace-nowrap"><Badge :tone="stateOf(r).tone" :title="stateOf(r).title">{{ stateOf(r).label }}</Badge><div v-if="(r.valid === false && r.error) || f.results[r.row]?.error" class="text-[11px] font-mono mt-0.5 max-w-[280px] truncate" style="color: var(--accent-negative);" :title="f.results[r.row]?.error || r.error || ''">{{ f.results[r.row]?.error || r.error }}</div></td>
                </tr>
                <tr v-if="openSql[r.row]"><td colspan="5" class="px-3 pb-3"><SqlBlock :code="r.sql" label="정답 SQL" max-height="220px" /></td></tr>
              </template>
            </tbody>
          </table>
        </div>
      </template>
      <EmptyState v-else :icon="Upload" compact title="파일을 올리면 미리보기가 뜹니다" desc="템플릿 CSV 를 내려받아 채우면 됩니다. 등록 전에 「검증」이 각 SQL 을 EXPLAIN PLAN 으로 확인합니다." />
    </Card>

    <!-- ② 등록된 피드백 -->
    <Card title="등록된 피드백" :subtitle="`${s.profile || '—'} — 인라인 👍/👎 · 이력 편집 · Few-shot 일괄 등록이 전부 여기 모인다 (AI_FEEDBACK_LOG)`" :icon="ThumbsUp">
      <template #actions>
        <Badge>{{ f.feedback.length }}</Badge>
        <Button size="sm" variant="ghost" :busy="f.feedbackLoading" @click="f.loadFeedback(s.profile)">새로고침</Button>
        <Button size="sm" variant="danger" :disabled="!f.feedback.length" @click="confirmPurge = true"><Trash2 :size="13" :stroke-width="1.75" /> 프로필 전체 삭제</Button>
      </template>
      <LoadingBlock v-if="f.feedbackLoading && !f.feedback.length" compact label="피드백을 읽는 중…" />
      <EmptyState v-else-if="!f.feedback.length" :icon="ThumbsUp" compact title="등록된 피드백이 없습니다" desc="답변 아래 👍/👎 로 남기거나 위에서 파일로 일괄 등록하세요." />
      <div v-else class="rounded-md overflow-auto" style="border: 1px solid var(--border-default); max-height: 420px;">
        <table class="w-full text-sm" style="border-collapse: collapse;">
          <thead><tr style="background: var(--bg-surface); color: var(--text-muted);"><th v-for="c in ['유형', '질문', '사유', '정답 SQL', '출처', '등록일', '']" :key="c" class="text-left text-[11px] font-semibold px-3 py-2 whitespace-nowrap">{{ c }}</th></tr></thead>
          <tbody>
            <tr v-for="r in f.feedback" :key="r.ID" class="row">
              <td class="px-3 py-2"><component :is="r.FEEDBACK_TYPE === 'positive' ? ThumbsUp : ThumbsDown" :size="14" :stroke-width="1.75" :style="{ color: r.FEEDBACK_TYPE === 'positive' ? 'var(--accent-positive)' : 'var(--accent-negative)' }" /></td>
              <td class="px-3 py-2 max-w-[360px] truncate" style="color: var(--text-primary);" :title="r.QUESTION ?? ''">{{ r.QUESTION }}</td>
              <td class="px-3 py-2 text-xs max-w-[240px] truncate" style="color: var(--text-secondary);" :title="r.FEEDBACK_CONTENT ?? ''">{{ r.FEEDBACK_CONTENT || '—' }}</td>
              <td class="px-3 py-2 text-xs" style="color: var(--text-muted);">{{ r.HAS_CORRECTED ? '있음' : '—' }}</td>
              <td class="px-3 py-2"><Badge tone="code">{{ r.SOURCE }}</Badge></td>
              <td class="px-3 py-2 text-xs whitespace-nowrap" style="color: var(--text-muted);">{{ fmtDateTime(r.CREATED_AT) }}</td>
              <td class="px-3 py-2 text-right"><button type="button" class="p-1 rounded" style="color: var(--text-muted);" title="삭제 (Oracle FEEDBACK delete + 앱 행)" @click="f.remove(r.ID, s.profile)"><XCircle :size="14" :stroke-width="1.75" /></button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <ConfirmModal :open="confirmPurge" title="프로필 피드백 전체 삭제" confirm-label="전부 삭제" danger :busy="purging" @confirm="doPurge" @cancel="confirmPurge = false">
      <b>{{ s.profile }}</b> 의 피드백 벡터 인덱스에 든 질문 전부에 <code class="font-mono">FEEDBACK(operation => 'delete')</code> 를 보내고 앱 기록도 지웁니다. 되돌릴 수 없습니다.
    </ConfirmModal>
  </div>
</template>

<style scoped>
.row + .row td { border-top: 1px solid var(--border-default); }
</style>
