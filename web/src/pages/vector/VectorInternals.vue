<script setup lang="ts">
/** 「내부」 서브탭 — 증명·관리 도구: 실행계획 전/후 · 테이블 생성/조회 · ONNX 모델·임베딩 소스 관리. 시연 중 자주 안 열지만 DBA 가 반드시 묻는 것들 (2026-09-09 재편 P1) */
import { ref } from 'vue'
import { Table2, ListTree, Layers } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import ResultTable from '@/components/demo/ResultTable.vue'
import Segmented from '@/components/demo/Segmented.vue'
import VectorEmbedding from './VectorEmbedding.vue'
import CompareView from '@/components/demo/CompareView.vue'
import { fmtNum } from '@/lib/format'
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

    <!-- P4: 인덱스 하나가 실제로는 테이블 여러 개 — 무엇이 들어 있나 -->
    <Card title="Hybrid Vector Index 안 들여다보기" subtitle="인덱스 하나를 만들면 DB 가 테이블 여러 개를 만든다 — 단어는 어디에, 벡터는 어디에 있나" :icon="Layers">
      <template #actions><Button size="sm" :busy="v.hviInternalsBusy" @click="v.loadHviInternals()">{{ v.hviInternals ? '새로고침' : '들여다보기' }}</Button></template>
      <p v-if="!v.hviInternals" class="text-sm m-0" style="color: var(--text-muted);">버튼을 누르면 내부 테이블 목록, 가장 자주 나온 단어 15개, 조각 표본 5개를 보여줍니다.</p>
      <div v-else-if="v.hviInternals.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ v.hviInternals.error }}</div>
      <p v-else-if="!v.hviInternals.exists" class="text-sm m-0" style="color: var(--text-muted);">Hybrid Vector Index 가 없습니다 — 「환경」 서브탭에서 만드세요.</p>
      <div v-else class="grid grid-cols-1 xl:grid-cols-3 gap-4 items-start">
        <div>
          <div class="text-xs font-semibold mb-1.5" style="color: var(--text-secondary);">내부 테이블 {{ v.hviInternals.tables?.length }}개</div>
          <div class="rounded-md overflow-hidden" style="border: 1px solid var(--border-default);">
            <div v-for="t in v.hviInternals.tables" :key="t.name" class="row px-2.5 py-1.5" style="background: var(--bg-elevated);">
              <div class="flex items-baseline gap-2"><span class="font-mono text-xs truncate" style="color: var(--text-primary);" :title="t.name">{{ t.name.replace('VECTOR$DR$DOC_CHUNKS_HVI$VI$', 'VECTOR$…$').replace('DR$DOC_CHUNKS_HVI', 'DR$…') }}</span><span class="ml-auto text-xs tabular-nums shrink-0" style="color: var(--text-secondary);">{{ t.rows == null ? '—' : fmtNum(t.rows) }}행</span></div>
              <div class="text-[11px]" style="color: var(--text-muted);">{{ t.role }}</div>
            </div>
          </div>
        </div>
        <div>
          <div class="text-xs font-semibold mb-1.5" style="color: var(--text-secondary);">가장 자주 나온 단어 15 — 토큰 {{ fmtNum(v.hviInternals.token_total ?? 0) }}개 중</div>
          <div class="flex flex-wrap gap-1.5">
            <span v-for="tk in v.hviInternals.tokens" :key="tk.text" class="inline-flex items-baseline gap-1 rounded-md px-2 py-1 text-xs" style="background: var(--bg-elevated); border: 1px solid var(--border-default);"><span class="font-mono" style="color: var(--text-primary);">{{ tk.text }}</span><span class="tabular-nums" style="color: var(--text-muted);">{{ tk.count }}</span></span>
          </div>
          <p class="text-[11px] mt-2 m-0" style="color: var(--text-secondary); line-height: 1.5;">단어가 <span class="font-mono">카드사는</span> · <span class="font-mono">회원이</span> 처럼 <strong style="color: var(--text-primary);">조사가 붙은 채</strong> 저장됩니다(공백 단위). 그래서 키워드 검색은 <span class="font-mono">카드%</span> 처럼 앞부분으로 묻습니다 — 「검색」의 실행된 SQL 에 그 변환이 보입니다.</p>
        </div>
        <div>
          <div class="text-xs font-semibold mb-1.5" style="color: var(--text-secondary);">조각 표본 5 — 인덱스가 스스로 자르고 벡터로 바꾼 것</div>
          <div class="flex flex-col gap-1.5">
            <div v-for="p in v.hviInternals.pieces" :key="p.chunk_id" class="rounded-md px-2.5 py-1.5 text-xs" style="background: var(--bg-elevated); border: 1px solid var(--border-default);">
              <div class="flex items-center gap-1.5 mb-0.5"><Badge tone="code">#{{ p.chunk_id }}</Badge><span style="color: var(--text-muted);">{{ p.length }}자 → 숫자 {{ p.dims }}개</span></div>
              <div class="line-clamp-2" style="color: var(--text-primary);">{{ p.text }}</div>
            </div>
          </div>
        </div>
      </div>
      <template v-if="v.hviInternals?.exists && v.hviInternals.sql">
        <p class="text-xs mt-3 mb-2" style="color: var(--text-secondary); line-height: 1.5;"><strong style="color: var(--text-primary);">이게 있어서:</strong> <span class="font-mono">CONTAINS</span> 는 $I 에서 단어를, 벡터 검색은 $VR 에서 조각을 찾습니다. 둘을 한 인덱스가 갖고 있어서 <span class="font-mono">DBMS_HYBRID_VECTOR.SEARCH</span> 의 융합이 DB 안에서 끝납니다.</p>
        <details class="text-xs"><summary class="cursor-pointer" style="color: var(--text-muted);">조회 SQL 3개</summary>
          <div class="mt-2 flex flex-col gap-2"><SqlBlock :code="v.hviInternals.sql.tables" label="내부 테이블" max-height="100px" /><SqlBlock :code="v.hviInternals.sql.tokens" label="상위 토큰 ($I)" max-height="100px" /><SqlBlock :code="v.hviInternals.sql.pieces" label="조각 표본 ($VR)" max-height="100px" /></div>
        </details>
      </template>
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

<style scoped>
.row + .row { border-top: 1px solid var(--border-default); }
</style>
