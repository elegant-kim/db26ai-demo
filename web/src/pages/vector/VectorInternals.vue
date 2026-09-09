<script setup lang="ts">
/** 「내부」 서브탭 — 증명·관리 도구: 실행계획 전/후 · 테이블 생성/조회 · ONNX 모델·임베딩 소스 관리. 시연 중 자주 안 열지만 DBA 가 반드시 묻는 것들 (2026-09-09 재편 P1) */
import { ref } from 'vue'
import { Table2, ListTree } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import ResultTable from '@/components/demo/ResultTable.vue'
import Segmented from '@/components/demo/Segmented.vue'
import VectorEmbedding from './VectorEmbedding.vue'
import CompareView from '@/components/demo/CompareView.vue'
import { useVectorStore } from '@/stores/vector'

const v = useVectorStore()
const confirmDrop = ref(false)
const TARGETS = [{ value: 'DOC_CHUNKS', label: 'DOC_CHUNKS' }, { value: 'DOCUMENTS', label: 'DOCUMENTS' }]
const tone = (s: string) => (s === 'created' ? 'positive' : s === 'existing' ? 'info' : s === 'dropped' ? 'negative' : 'default')
const KINDS = [{ k: 'def', label: '컬럼 정의', hint: 'USER_TAB_COLUMNS' }, { k: 'data', label: '데이터 조회', hint: '앞 50행 · VECTOR 컬럼은 타입만' }, { k: 'idx', label: '인덱스 조회', hint: 'USER_INDEXES — HNSW + Oracle Text' }] as const
</script>

<template>
  <div class="flex flex-col gap-5">
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

    <Card title="벡터 검색 실행계획 — 술어 하나가 인덱스를 죽인다" subtitle="같은 검색을 두 가지로 EXPLAIN: 2026-09-08 까지 앱이 돌리던 SQL(WHERE embedding IS NOT NULL) 과 지금 SQL. HNSW 인덱스를 타는 쪽은 하나뿐이다">
      <template #actions><Button size="sm" :busy="v.planBusy" @click="v.loadPlan()">실행계획 조회</Button></template>
      <div v-if="v.plan" class="flex flex-col gap-2">
        <div v-if="v.plan.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ v.plan.error }}</div>
        <CompareView v-if="v.plan.before && v.plan.after"
          :left="{ title: '전(前) · WHERE embedding IS NOT NULL + FETCH FIRST', badge: v.plan.before.access || '—' }"
          :right="{ title: '후(後) · 술어 없음 + FETCH APPROX FIRST', badge: v.plan.after.access || '—' }">
          <template #left>
            <SqlBlock :code="v.plan.before.target_sql" label="EXPLAIN PLAN FOR" max-height="200px" />
            <SqlBlock class="mt-2" :code="v.plan.before.plan_text" lang="text" label="실행 계획" max-height="360px" />
            <p class="text-xs mt-2 mb-0 px-2.5 py-1.5 rounded" style="background: var(--accent-warm-soft); color: var(--text-secondary);">벡터 컬럼에 술어가 붙으면 옵티마이저가 HNSW 를 버리고 전체를 훑는다. NULL 임베딩은 어차피 인덱스에 없어서 이 술어는 필요도 없었다. 수동 하이브리드(가중합 ORDER BY)도 이 길이다.</p>
          </template>
          <template #right>
            <SqlBlock :code="v.plan.after.target_sql" label="EXPLAIN PLAN FOR" max-height="200px" />
            <SqlBlock class="mt-2" :code="v.plan.after.plan_text" lang="text" label="실행 계획" max-height="360px" />
            <p class="text-xs mt-2 mb-0 px-2.5 py-1.5 rounded" :style="{ background: v.plan.after.uses_index ? 'var(--accent-positive-soft)' : 'var(--accent-negative-soft)', color: 'var(--text-secondary)' }">
              {{ v.plan.after.uses_index ? 'VECTOR INDEX HNSW SCAN — 의미 검색 모드가 실제로 도는 길이다. 이 ADB(23.26) 에서는 술어만 없으면 FETCH FIRST 도 HNSW 를 탔다; APPROX 는 의도를 SQL 에 적는 것이다.' : '⚠ 인덱스를 타지 않았다 — 인덱스 상태(위 「인덱스 조회」)를 확인하세요.' }}
            </p>
          </template>
        </CompareView>
        <template v-else-if="v.plan.plan_text">
          <SqlBlock :code="v.plan.target_sql" label="EXPLAIN PLAN FOR" max-height="220px" />
          <SqlBlock :code="v.plan.plan_text" lang="text" label="실행 계획 (DBMS_XPLAN)" max-height="480px" />
        </template>
      </div>
      <p v-else class="text-sm m-0" style="color: var(--text-muted);">버튼을 누르면 같은 벡터 검색을 정확·근사 두 방식으로 EXPLAIN 해 나란히 보여줍니다.</p>
    </Card>

    <!-- 관리: 임베딩 소스·ONNX 모델 적재 — 가끔 손대는 것이라 「내부」 맨 아래 -->
    <VectorEmbedding />

    <ConfirmModal :open="confirmDrop" title="Vector Store 를 초기화할까요?" danger confirm-label="전체 삭제" :busy="v.tableBusy === 'drop'" @confirm="confirmDrop = false; v.manageTables('drop')" @cancel="confirmDrop = false">
      documents · doc_chunks 테이블과 모든 청크·임베딩이 삭제됩니다. 문서를 다시 올려야 합니다.
    </ConfirmModal>
  </div>
</template>
