<script setup lang="ts">
/**
 * 「환경」 서브탭 — 시연의 시작점: 이 DB 안에 무엇이 준비돼 있나 (2026-09-09 재편 P1).
 * P1 은 옛 Vector Store 의 소개 카드와 Hybrid Vector Index 카드를 옮기고 현재 설정 요약을 붙인 것.
 * P3 에서 NL2SQL 환경 탭과 같은 상태 스트립 + 카드 사슬(VECTOR 테이블 → ONNX 모델 → 인덱스 2종)로 다시 짠다.
 */
import { computed, onMounted, ref } from 'vue'
import { Database, Layers, Cpu } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import VersusBox from '@/components/demo/VersusBox.vue'
import { useVectorStore } from '@/stores/vector'
const v = useVectorStore()
const confirmHvi = ref(false)
onMounted(() => { void v.loadConfig(); if (!v.docsLoaded) void v.loadDocs(); if (!v.hvi) void v.loadHvi() })
const embeddedRatio = computed(() => `${v.indexInfo?.embedded_chunks ?? '—'} / ${v.indexInfo?.total_chunks ?? '—'}`)
</script>

<template>
  <div class="flex flex-col gap-5">
    <Card title="Oracle AI Vector Search — 의미 기반 검색을 SQL 안에서" :icon="Database">
      <VersusBox left-title="기존 키워드 검색" left-desc="정확한 단어 매칭만. 별도 검색 엔진(Elasticsearch 등) 필요. 검색과 트랜잭션이 분리된다."
        right-title="Oracle AI Vector Search" right-desc="의미적 유사성으로 검색. DB 안에서 SQL 로 벡터 검색 — 한 SQL 에 검색 + 비즈니스 로직.">
        텍스트의 뜻을 벡터로 바꿔 <strong style="color: var(--text-primary);">VECTOR 타입</strong>에 저장하고, <code class="font-mono">VECTOR_DISTANCE</code> 로 가까운 것을 찾습니다.
        <code class="font-mono">VECTOR_EMBEDDING</code> 이 ONNX 모델을 DB 안에서 돌리므로 외부 API 없이 임베딩되고, 26ai 의 <strong style="color: var(--text-primary);">Hybrid Vector Index</strong> 는 인덱스 하나로 텍스트·벡터 융합 검색까지 DB 가 합니다.
        <template #footer>doc_chunks(chunk_text CLOB, embedding VECTOR) · HNSW 인덱스(COSINE, 의미 검색) · Hybrid Vector Index(26ai — 텍스트 + 벡터, CONTAINS 도 여기서) — 정본은 CLAUDE.md 「DB 테이블·인덱스 구조」</template>
      </VersusBox>
    </Card>

    <Card title="지금 설정" subtitle="검색과 적재가 따르는 현재 값 — 바꾸는 것은 「내부」 서브탭에서" :icon="Cpu">
      <div class="flex flex-wrap items-center gap-1.5">
        <Badge tone="primary">임베딩 {{ v.sourceLabel }}</Badge>
        <Badge tone="code">{{ v.model || '—' }}</Badge>
        <Badge tone="info">인덱스 모델 {{ v.indexInfo?.embedding_model ?? '—' }} · {{ v.indexInfo?.vector_dimensions ?? '—' }}차원</Badge>
        <Badge :tone="(v.indexInfo?.embedded_chunks ?? 0) > 0 ? 'positive' : 'default'">임베딩된 청크 {{ embeddedRatio }}</Badge>
        <Badge tone="info">문서 {{ v.docs.length }}</Badge>
        <Badge v-if="v.dimensionWarning" tone="warm">⚠ 인덱스 차원 ≠ 현재 모델</Badge>
      </div>
    </Card>

    <Card title="Hybrid Vector Index (26ai)" subtitle="텍스트 컬럼 하나에 인덱스 하나 — 청킹 · 임베딩 · 텍스트 인덱스 · 벡터 인덱스를 DB 가 스스로 만들고, DBMS_HYBRID_VECTOR.SEARCH 가 융합까지 한다. 「검색 · RAG」의 Hybrid Vector Index 모드가 이것을 탄다" :icon="Layers">
      <template #actions>
        <Button size="sm" variant="ghost" :busy="v.hviBusy === 'load'" @click="v.loadHvi()">새로고침</Button>
        <Button size="sm" :busy="v.hviBusy === 'create'" :disabled="v.hviBusy !== ''" @click="confirmHvi = true">{{ v.hvi?.exists ? '재생성' : '생성' }}</Button>
      </template>
      <div v-if="v.hvi" class="flex flex-wrap items-center gap-1.5 text-xs" style="color: var(--text-secondary);">
        <Badge :tone="v.hvi.exists ? 'positive' : 'default'">{{ v.hvi.index_name }} · {{ v.hvi.exists ? (v.hvi.status || 'VALID') : '없음' }}</Badge>
        <Badge v-if="v.hvi.exists" tone="code">MODEL {{ v.hvi.model }}</Badge>
        <Badge v-if="v.hvi.exists && v.hvi.indexed_chunks != null" tone="info">인덱스 내부 임베딩 {{ v.hvi.indexed_chunks }}조각</Badge>
        <Badge v-if="v.hvi.legacy_text_index" tone="warm">옛 CONTEXT 인덱스 DOC_CHUNKS_TEXT_IDX 남아 있음 — 생성 시 대체된다</Badge>
        <span v-if="v.hvi.exists" style="color: var(--text-muted);">인덱스가 청크를 다시 잘라 임베딩하므로 조각 수가 청크 수보다 많다. 업로드마다 CTX_DDL.SYNC_INDEX 로 반영된다.</span>
        <span v-else style="color: var(--text-muted);">생성은 청크 수 × 약 0.3초 (180청크 실측 57초). 업로드마다 CTX_DDL.SYNC_INDEX 로 새 청크가 반영된다.</span>
      </div>
      <div v-if="v.hviResult" class="mt-3 flex flex-col gap-2">
        <div v-if="v.hviResult.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);"><span class="font-mono text-xs break-all">{{ v.hviResult.error }}</span></div>
        <template v-for="(st, i) in v.hviResult.steps ?? []" :key="i">
          <SqlBlock :code="st.sql" :label="st.note" :elapsed-ms="st.duration_ms" max-height="160px" />
        </template>
      </div>
      <SqlBlock v-else-if="v.hvi && !v.hvi.exists" class="mt-3" :code="v.hvi.create_sql" label="생성 버튼이 실행하는 DDL" max-height="120px" />
    </Card>

        <ConfirmModal :open="confirmHvi" title="Hybrid Vector Index 를 만들까요?" confirm-label="생성" :busy="v.hviBusy === 'create'" @confirm="confirmHvi = false; v.createHvi(!!v.hvi?.exists)" @cancel="confirmHvi = false">
      청크 수 × 약 0.3초가 걸립니다 (DB 가 모든 청크를 다시 잘라 임베딩합니다). 같은 컬럼의 옛 Oracle Text 인덱스(DOC_CHUNKS_TEXT_IDX)는 지워지고, 이 인덱스가 CONTAINS 도 대신 서빙합니다.
    </ConfirmModal>
  </div>
</template>
