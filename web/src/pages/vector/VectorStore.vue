<script setup lang="ts">
import { ref } from 'vue'
import { Database, Table2, ListTree } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import ResultTable from '@/components/demo/ResultTable.vue'
import Segmented from '@/components/demo/Segmented.vue'
import VersusBox from '@/components/demo/VersusBox.vue'
import { useVectorStore } from '@/stores/vector'

const v = useVectorStore()
const confirmDrop = ref(false)
const TARGETS = [{ value: 'DOC_CHUNKS', label: 'DOC_CHUNKS' }, { value: 'DOCUMENTS', label: 'DOCUMENTS' }]
const tone = (s: string) => (s === 'created' ? 'positive' : s === 'existing' ? 'info' : s === 'dropped' ? 'negative' : 'default')
const KINDS = [{ k: 'def', label: '컬럼 정의', hint: 'USER_TAB_COLUMNS' }, { k: 'data', label: '데이터 조회', hint: '앞 50행 · VECTOR 컬럼은 타입만' }, { k: 'idx', label: '인덱스 조회', hint: 'USER_INDEXES — HNSW + Oracle Text' }] as const
</script>

<template>
  <div class="flex flex-col gap-5">
    <Card title="Oracle AI Vector Search — 의미 기반 검색을 SQL 안에서" :icon="Database">
      <VersusBox left-title="기존 키워드 검색" left-desc="정확한 단어 매칭만. 별도 검색 엔진(Elasticsearch 등) 필요. 검색과 트랜잭션이 분리된다."
        right-title="Oracle AI Vector Search" right-desc="의미적 유사성으로 검색. DB 안에서 SQL 로 벡터 검색 — 한 SQL 에 검색 + 비즈니스 로직.">
        텍스트의 뜻을 벡터로 바꿔 <strong style="color: var(--text-primary);">VECTOR 타입</strong>에 저장하고, <code class="font-mono">VECTOR_DISTANCE</code> 로 가까운 것을 찾습니다.
        <code class="font-mono">VECTOR_EMBEDDING</code> 이 ONNX 모델을 DB 안에서 돌리므로 외부 API 없이 임베딩되고, 26ai 의 하이브리드 검색은 키워드 점수까지 한 SQL 에서 합칩니다.
        <template #footer>doc_chunks(chunk_text CLOB, embedding VECTOR) · HNSW 인덱스(COSINE) · Oracle Text 인덱스(WORLD_LEXER) — 정본은 CLAUDE.md 「DB 테이블·인덱스 구조」</template>
      </VersusBox>
    </Card>

    <Card title="테이블 생성 · 초기화" subtitle="documents · doc_chunks 가 없으면 만들고, 있으면 그대로 연결합니다. 초기화는 두 테이블을 지웁니다" :icon="Table2">
      <div class="flex flex-wrap gap-2">
        <Button :busy="v.tableBusy === 'create'" :disabled="v.tableBusy !== '' && v.tableBusy !== 'create'" @click="v.manageTables('create')">테이블 연결 / 생성</Button>
        <Button variant="danger" :busy="v.tableBusy === 'drop'" :disabled="v.tableBusy !== '' && v.tableBusy !== 'drop'" @click="confirmDrop = true">전체 삭제 (초기화)</Button>
      </div>
      <div v-if="v.tableAction" class="mt-4 flex flex-col gap-3">
        <div v-if="v.tableAction.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);"><span class="font-mono text-xs break-all">{{ v.tableAction.error }}</span></div>
        <div v-if="v.tableAction.tables?.length" class="flex flex-wrap gap-1.5">
          <span v-for="t in v.tableAction.tables" :key="t.table" class="inline-flex items-center gap-1.5 text-xs"><Badge :tone="tone(t.status)">{{ t.table }} · {{ t.status }}</Badge><span v-if="t.message" style="color: var(--text-muted);">{{ t.message }}</span></span>
        </div>
        <SqlBlock v-if="v.tableAction.sql_executed" :code="v.tableAction.sql_executed" label="실행된 SQL" line-numbers max-height="420px" />
      </div>
    </Card>

    <Card title="테이블 조회" subtitle="정의 · 데이터 · 인덱스를 카탈로그 뷰로 확인합니다" :icon="ListTree">
      <template #actions><Segmented :model-value="v.inspectTarget" :options="TARGETS" size="sm" @update:model-value="(t: string) => (v.inspectTarget = t as 'DOC_CHUNKS' | 'DOCUMENTS')" /></template>
      <div class="flex flex-wrap gap-2">
        <Button v-for="k in KINDS" :key="k.k" variant="secondary" size="sm" :title="k.hint" :busy="v.inspectBusy === k.k" :disabled="v.inspectBusy !== '' && v.inspectBusy !== k.k" @click="v.runInspect(k.k)">{{ k.label }}</Button>
      </div>
      <div v-for="k in KINDS" :key="'r' + k.k" class="mt-4 flex flex-col gap-2">
        <template v-if="v.inspect[k.k]">
          <div class="text-xs font-semibold" style="color: var(--text-secondary);">{{ k.label }} — {{ v.inspectTarget }}</div>
          <SqlBlock :code="v.inspect[k.k]!.sql" label="SQL" max-height="180px" />
          <ResultTable :rows="v.inspect[k.k]!" dense max-height="360px" />
        </template>
      </div>
    </Card>

    <Card title="벡터 검색 실행계획 (EXPLAIN PLAN)" subtitle="VECTOR_DISTANCE 정렬 + FETCH APPROX FIRST 가 HNSW 인덱스를 타는지 본다">
      <template #actions><Button size="sm" :busy="v.planBusy" @click="v.loadPlan()">실행계획 조회</Button></template>
      <div v-if="v.plan" class="flex flex-col gap-2">
        <div v-if="v.plan.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ v.plan.error }}</div>
        <SqlBlock v-if="v.plan.target_sql" :code="v.plan.target_sql" label="EXPLAIN PLAN FOR" max-height="220px" />
        <SqlBlock v-if="v.plan.plan_text" :code="v.plan.plan_text" lang="text" label="실행 계획 (DBMS_XPLAN)" max-height="480px" />
      </div>
      <p v-else class="text-sm m-0" style="color: var(--text-muted);">버튼을 누르면 대표 벡터 검색 SQL 의 계획을 보여줍니다.</p>
    </Card>

    <ConfirmModal :open="confirmDrop" title="Vector Store 를 초기화할까요?" danger confirm-label="전체 삭제" :busy="v.tableBusy === 'drop'" @confirm="confirmDrop = false; v.manageTables('drop')" @cancel="confirmDrop = false">
      documents · doc_chunks 테이블과 모든 청크·임베딩이 삭제됩니다. 문서를 다시 올려야 합니다.
    </ConfirmModal>
  </div>
</template>
