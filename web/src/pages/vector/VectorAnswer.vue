<script setup lang="ts">
/** Vector 검색 어시스턴트 메시지 — 답변 · 청크 카드 · SQL · 후속(임베딩 과정/키워드 비교/인덱스/시각화) · 비교 모드는 CompareView */
import { computed } from 'vue'
import { Bot, FileText } from 'lucide-vue-next'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import ScatterChart from '@/components/ui/ScatterChart.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import CompareView from '@/components/demo/CompareView.vue'
import ChunkCard from '@/components/demo/ChunkCard.vue'
import KvGrid from '@/components/demo/KvGrid.vue'
import { renderMarkdown } from '@/lib/markdown'
import { fmtMs, fmtNum } from '@/lib/format'
import { useVectorStore, type VectorMessage } from '@/stores/vector'

const props = defineProps<{ msg: VectorMessage; readonly?: boolean }>()
const v = useVectorStore()
const chunkMode = computed(() => (props.msg.mode === 'hybrid' ? 'hybrid' : props.msg.mode === 'keyword' ? 'keyword' : 'vector'))
const embeddingKv = computed(() => props.msg.embeddingInfo ? { '모델': props.msg.embeddingInfo.model, '소스': props.msg.embeddingInfo.source, '차원 수': props.msg.embeddingInfo.dimensions, '처리 시간': `${props.msg.embeddingInfo.processing_ms}ms`, '벡터 미리보기': props.msg.embeddingInfo.vector_preview } : null)
const indexKv = computed(() => { const i = props.msg.indexInfo; if (!i) return null; return { '총 문서': `${i.total_documents}개`, '총 청크': `${i.total_chunks}개`, '임베딩 완료': `${i.embedded_chunks}개`, '임베딩 모델': i.embedding_model, '벡터 차원': i.vector_dimensions, '거리 메트릭': i.distance_metric, '인덱스명': i.index?.index_name ?? '—', '인덱스 타입': i.index?.index_type ?? '—', '상태': i.index?.status ?? '—' } })
function readVar(name: string, fb: string) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fb }
const vizDatasets = computed(() => {
  const z = props.msg.viz; if (!z) return []
  const pt = (p: any) => ({ x: p.x, y: p.y, meta: `${p.source_file} p.${p.page_num} (유사도 ${Number(p.x).toFixed(3)})` })
  const ds: any[] = [
    { label: '기타 청크', data: z.points.filter((p) => !p.matched).map(pt), color: readVar('--border-strong', '#cbd5e1'), radius: 4 },
    { label: '매칭 청크 (Top-K)', data: z.points.filter((p) => p.matched).map(pt), color: readVar('--accent-positive', '#16a34a'), radius: 7 },
  ]
  if (z.query_point) ds.push({ label: '검색 쿼리', data: [{ x: z.query_point.x, y: z.query_point.y, meta: `쿼리: ${z.query_point.label}` }], color: readVar('--accent-primary', '#C74634'), radius: 7, pointStyle: 'rectRot' })
  return ds
})
</script>

<template>
  <div class="flex items-start gap-2.5 w-full min-w-0">
    <div class="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5" style="background: var(--bg-surface); border: 1px solid var(--border-default); color: var(--accent-primary);"><Bot :size="15" :stroke-width="1.75" /></div>
    <div class="flex-1 min-w-0 flex flex-col gap-2.5">
      <LoadingBlock v-if="msg.loading" compact :label="msg.loadingText || '검색 중…'" hint="임베딩 → 검색 → RAG 답변 (LLM 2~6초)" />
      <template v-else>
        <div v-if="msg.errorText" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);"><strong>오류:</strong> <span class="font-mono text-xs break-all">{{ msg.errorText }}</span></div>

        <!-- 비교 모드 -->
        <CompareView v-else-if="msg.mode === 'compare'"
          :left="{ title: '키워드 검색 (CONTAINS)', rowCount: msg.keywordResults?.match_count ?? 0, elapsedMs: msg.keywordResults?.elapsed_ms }"
          :right="{ title: '의미 검색 (VECTOR_DISTANCE)', rowCount: msg.vectorResults?.match_count ?? 0, elapsedMs: msg.vectorResults?.elapsed_ms, badge: 'VECTOR' }">
          <template #left>
            <SqlBlock :code="msg.keywordResults?.sql_executed" label="SQL" max-height="180px" />
            <div class="mt-2 flex flex-col gap-2"><ChunkCard v-for="(c, i) in msg.keywordResults?.chunks ?? []" :key="i" :chunk="c" mode="keyword" :rank="i + 1" /></div>
            <p class="text-xs mt-2 mb-0 px-2.5 py-1.5 rounded" style="background: var(--accent-warm-soft); color: var(--text-secondary);">정확한 단어만 매칭 — 의미적으로 관련된 내용은 놓친다.</p>
          </template>
          <template #right>
            <SqlBlock :code="msg.vectorResults?.sql_executed" label="SQL" max-height="180px" />
            <div class="mt-2 flex flex-col gap-2"><ChunkCard v-for="(c, i) in msg.vectorResults?.chunks ?? []" :key="i" :chunk="c" mode="vector" :rank="i + 1" /></div>
            <p class="text-xs mt-2 mb-0 px-2.5 py-1.5 rounded" style="background: var(--accent-positive-soft); color: var(--text-secondary);">단어가 없어도 의미적 유사성으로 포착한다.</p>
          </template>
        </CompareView>

        <template v-else>
          <div v-if="msg.answer" class="md-body text-sm rounded-md px-3.5 py-3" style="background: var(--bg-surface); color: var(--text-primary);" v-html="renderMarkdown(msg.answer)" />
          <div v-if="msg.hybridNote" class="px-3 py-2 rounded-md text-xs" style="background: var(--accent-warm-soft); border-left: 3px solid var(--accent-warm); color: var(--text-primary);">⚠ {{ msg.hybridNote }}</div>
          <div v-if="msg.chunks?.length" class="flex flex-col gap-2">
            <div class="flex items-center gap-1.5 text-xs font-medium" style="color: var(--text-secondary);"><FileText :size="14" :stroke-width="1.75" /> 참조 문서 청크 ({{ msg.mode === 'hybrid' ? '하이브리드 점수 순' : msg.mode === 'keyword' ? 'Oracle Text 점수 순' : '유사도 순' }} · {{ msg.chunks.length }}건)<span v-if="msg.mode === 'hybrid'" class="ml-1" style="color: var(--text-muted);">hybrid = {{ msg.vectorWeight }} × vector + {{ msg.keywordWeight }} × keyword/100</span></div>
            <ChunkCard v-for="(c, i) in msg.chunks" :key="i" :chunk="c" :mode="chunkMode" :rank="i + 1" />
          </div>
          <p v-else-if="!msg.errorText" class="text-sm m-0" style="color: var(--text-muted);">매칭된 청크가 없습니다 — 문서를 올렸는지, 검색 모드가 맞는지 확인하세요.</p>
          <SqlBlock v-if="msg.sql" :code="msg.sql" label="실행된 SQL" max-height="260px" :badge="msg.mode === 'hybrid' ? 'CONTAINS + VECTOR_DISTANCE' : msg.mode === 'keyword' ? 'CONTAINS' : 'VECTOR_DISTANCE'" />

          <div v-if="!readonly" class="flex flex-wrap items-center gap-1.5">
            <Badge v-if="msg.elapsedMs" tone="code">{{ fmtMs(msg.elapsedMs) }}</Badge>
            <Button size="sm" :variant="msg.embeddingInfo ? 'primary' : 'secondary'" :busy="msg.extraBusy === 'embedding'" :disabled="!!msg.extraBusy" @click="v.toggleExtra(msg, 'embedding')">임베딩 과정</Button>
            <Button v-if="msg.mode === 'vector'" size="sm" :variant="msg.keywordCompare ? 'primary' : 'secondary'" :busy="msg.extraBusy === 'keyword'" :disabled="!!msg.extraBusy" @click="v.toggleExtra(msg, 'keyword')">키워드 비교</Button>
            <Button size="sm" :variant="msg.indexInfo ? 'primary' : 'secondary'" :busy="msg.extraBusy === 'index'" :disabled="!!msg.extraBusy" @click="v.toggleExtra(msg, 'index')">벡터 인덱스 정보</Button>
            <Button v-if="msg.mode !== 'keyword'" size="sm" :variant="msg.viz ? 'primary' : 'secondary'" :busy="msg.extraBusy === 'viz'" :disabled="!!msg.extraBusy" @click="v.toggleExtra(msg, 'viz')">{{ msg.viz ? '시각화 닫기' : '벡터 시각화' }}</Button>
            <span class="text-[11px] ml-auto" style="color: var(--text-muted);">{{ msg.timestamp }}</span>
          </div>
          <Badge v-else-if="msg.elapsedMs" tone="code">{{ fmtMs(msg.elapsedMs) }}</Badge>

          <div v-if="msg.viz" class="rounded-md p-3" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
            <div class="text-sm font-semibold" style="color: var(--text-primary);">임베딩 벡터 2D 시각화 (쿼리 중심 투영)</div>
            <div class="text-[11px] mb-2" style="color: var(--text-muted);">X축 = 쿼리와의 코사인 유사도 (오른쪽이 관련 높음) · 총 {{ fmtNum(msg.viz.total_chunks ?? msg.viz.points.length) }}개 청크</div>
            <ScatterChart :datasets="vizDatasets" x-title="← 관련 낮음   코사인 유사도   관련 높음 →" y-title="의미적 분포" height="340px" />
          </div>
          <div v-if="embeddingKv" class="rounded-md p-3" style="background: var(--bg-surface); border: 1px solid var(--border-default);"><div class="text-sm font-semibold mb-1" style="color: var(--text-primary);">임베딩 과정 — 질문이 벡터가 되는 순간</div><KvGrid :data="embeddingKv" /></div>
          <div v-if="indexKv" class="rounded-md p-3" style="background: var(--bg-surface); border: 1px solid var(--border-default);"><div class="text-sm font-semibold mb-1" style="color: var(--text-primary);">벡터 인덱스 정보 (HNSW)</div><KvGrid :data="indexKv" /></div>
          <div v-if="msg.keywordCompare" class="rounded-md p-3 flex flex-col gap-2" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
            <div class="text-sm font-semibold" style="color: var(--text-primary);">같은 질문을 키워드 검색으로 — 매칭 {{ msg.keywordCompare.match_count }}건 · {{ fmtMs(msg.keywordCompare.elapsed_ms) }}</div>
            <ChunkCard v-for="(c, i) in msg.keywordCompare.chunks" :key="i" :chunk="c" mode="keyword" :rank="i + 1" />
            <SqlBlock :code="msg.keywordCompare.sql_executed" label="SQL (CONTAINS)" max-height="180px" />
          </div>
        </template>
      </template>
    </div>
  </div>
</template>
