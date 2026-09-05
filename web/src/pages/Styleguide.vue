<script setup lang="ts">
/**
 * 디자인 토대 검증 화면 (5-0). 메뉴에 없다 — /styleguide 로만 진입.
 * 06 문서의 캡처(captures/investhub_*.png)와 나란히 놓고 헤더·카드·서브탭·표·SQL 블록을 대조한다.
 */
import { ref } from 'vue'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import Stat from '@/components/ui/Stat.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import Skeleton from '@/components/ui/Skeleton.vue'
import InfoTip from '@/components/ui/InfoTip.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import Pagination from '@/components/ui/Pagination.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import LineChart from '@/components/ui/LineChart.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import ResultTable from '@/components/demo/ResultTable.vue'
import CompareView from '@/components/demo/CompareView.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import SubTabs from '@/components/demo/SubTabs.vue'
import Segmented from '@/components/demo/Segmented.vue'
import { useSystemStore } from '@/stores/system'
import { fmtNum } from '@/lib/format'
import type { Rows } from '@/lib/normalize'
import { Database, Palette, Type, Table2, Code2, GitCompareArrows, Boxes, Search } from 'lucide-vue-next'

const system = useSystemStore()
const sub = ref('compare')
const seg = ref('hybrid')
const page = ref(1)
const sel = ref('q0')
const modal = ref(false)

const rows: Rows = {
  columns: ['PROD_NAME', 'PROD_CATEGORY', 'AMOUNT_SOLD'],
  rows: [
    { PROD_NAME: 'Envoy Ambassador', PROD_CATEGORY: 'Hardware', AMOUNT_SOLD: 1758.11 },
    { PROD_NAME: 'Mini DV Camcorder with 3.5" Swivel LCD', PROD_CATEGORY: 'Photo', AMOUNT_SOLD: 1550.99 },
    { PROD_NAME: '17" LCD w/built-in HDTV Tuner', PROD_CATEGORY: 'Peripherals and Accessories', AMOUNT_SOLD: 1495.99 },
  ],
  elapsedMs: 53,
}
const SQL = `SELECT chunk_id, chunk_text, source_file, page_num,
       VECTOR_DISTANCE(embedding,
           (SELECT VECTOR_EMBEDDING(MULTILINGUAL_E5_BASE USING :q AS data) FROM dual),
           COSINE) AS distance
FROM doc_chunks
WHERE embedding IS NOT NULL   -- 임베딩이 있는 청크만
ORDER BY distance
FETCH FIRST 5 ROWS ONLY`
const PGQ = `SELECT product_name, category, amount
FROM GRAPH_TABLE (sales_graph
    MATCH (c IS customers) -[s IS sales]-> (p IS products)
    WHERE c.cust_id = 524
    COLUMNS (p.prod_name AS product_name, p.prod_category AS category, s.amount_sold AS amount)
)
ORDER BY amount DESC FETCH FIRST 10 ROWS ONLY`
const TOKENS = ['--bg-base','--bg-surface','--bg-elevated','--bg-hover','--border-default','--border-strong','--text-primary','--text-secondary','--text-muted','--accent-primary','--accent-primary-soft','--accent-positive','--accent-negative','--accent-warm','--accent-info','--header-bg','--code-bg']
</script>

<template>
  <div class="flex flex-col gap-5">
    <div>
      <h1 class="text-2xl font-semibold m-0 flex items-center gap-2" style="color: var(--text-primary);">
        <Palette :size="24" :stroke-width="1.75" /> 디자인 토대
        <span class="text-base font-normal" style="color: var(--text-muted);">(5-0 검증 화면 · 06 문서와 대조)</span>
      </h1>
      <p class="text-sm mt-1 m-0" style="color: var(--text-muted);">헤더 · 토큰 · 타이포 · 서브탭 · 카드 · 표 · SQL 블록 · 비교 · 상태 표현</p>
    </div>

    <SubTabs v-model="sub" :tabs="[{ id: 'manage', label: '그래프 관리', icon: Boxes }, { id: 'compare', label: 'SQL vs SQL/PGQ', icon: GitCompareArrows }, { id: 'pattern', label: '패턴 탐색', icon: Search, badge: 3 }]" />

    <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
      <Stat label="SALES 행 수" :value="fmtNum(918843)" hint="SH 샘플 · 2026-04-14 이관" :icon="Database" />
      <Stat label="임베딩된 청크" :value="system.health ? `${system.health.embedded_count} / ${system.health.chunk_count}` : '—'" hint="/api/health 실시간" tone="positive" :icon="Table2" />
      <Stat label="하이브리드 SQL" value="0.1초" hint="스칼라 서브쿼리 적용 후 (100배)" tone="warm" :icon="Code2" />
    </div>

    <Card title="토큰" subtitle="tokens.css — 색은 여기서만 정한다" :icon="Palette">
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        <div v-for="t in TOKENS" :key="t" class="rounded-md border overflow-hidden" style="border-color: var(--border-default);">
          <div class="h-9" :style="{ background: `var(${t})` }"></div>
          <div class="px-2 py-1 text-[11px] font-mono truncate" style="color: var(--text-secondary);">{{ t }}</div>
        </div>
      </div>
    </Card>

    <Card title="타이포 · 버튼 · 배지" :icon="Type">
      <template #actions><Button variant="secondary" size="sm">실행 쿼리 확인</Button></template>
      <div class="flex flex-col gap-3">
        <div class="text-sm" style="color: var(--text-secondary);">본문 14px / 1.55 · 카드 제목 16/600 · 소제목 14/600 · 보조 12 <InfoTip term="HNSW" /></div>
        <div class="flex flex-wrap gap-2 items-center">
          <Button size="sm">primary sm</Button><Button>primary md</Button><Button size="lg">primary lg</Button>
          <Button variant="secondary">secondary</Button><Button variant="ghost">ghost</Button><Button variant="danger">danger</Button>
          <Button :busy="true">처리 중…</Button><Button :disabled="true">disabled</Button>
        </div>
        <div class="flex flex-wrap gap-2 items-center">
          <Badge>default</Badge><Badge tone="primary">hybrid</Badge><Badge tone="positive">VALID</Badge><Badge tone="negative">ORA-51932</Badge>
          <Badge tone="warm">LIKE 폴백</Badge><Badge tone="info">안내</Badge><Badge tone="code">53ms</Badge>
        </div>
        <div class="flex items-center gap-3 flex-wrap">
          <Segmented v-model="seg" :options="[{ value: 'vector', label: '벡터' }, { value: 'keyword', label: '키워드' }, { value: 'hybrid', label: '하이브리드' }, { value: 'compare', label: '비교' }]" />
          <div class="w-64"><SearchableSelect v-model="sel" :options="[{ value: 'q0', label: '고객 524가 구매한 제품 목록', sub: '1-hop' }, { value: 'q1', label: '제품별 구매 고객 수 Top-10', sub: '집계는 바깥에서' }, { value: 'q2', label: '고객 524와 같은 제품을 산 고객', sub: '2-hop · 추천' }]" /></div>
          <Button variant="secondary" size="sm" @click="modal = true">확인 모달</Button>
        </div>
      </div>
    </Card>

    <Card title="SQL 블록 ★" subtitle="라이트·다크 모두 다크 터미널 — 사용자 확인 포인트 ②" :icon="Code2">
      <SqlBlock :code="SQL" label="실행된 SQL" badge="vector" :elapsed-ms="95" line-numbers />
    </Card>

    <Card title="결과 표 ★" :icon="Table2">
      <ResultTable :rows="rows" />
    </Card>

    <Card title="좌우 비교 ★" subtitle="같은 질문을 두 방식으로 — 이 앱의 서사" :icon="GitCompareArrows">
      <CompareView :left="{ title: '기존 SQL (JOIN)', elapsedMs: 210, rowCount: 3 }" :right="{ title: 'SQL/PGQ (그래프 질의)', elapsedMs: 56, rowCount: 3, badge: '26ai' }" :equal="true">
        <template #left><SqlBlock :code="SQL.replace('doc_chunks', 'admin.sales s JOIN admin.products p ON s.prod_id = p.prod_id')" label="SQL" max-height="180px" /><div class="mt-2"><ResultTable :rows="rows" hide-footer dense /></div></template>
        <template #right><SqlBlock :code="PGQ" label="SQL/PGQ" max-height="180px" /><div class="mt-2"><ResultTable :rows="rows" hide-footer dense /></div></template>
      </CompareView>
    </Card>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <Card title="로딩" compact><LoadingBlock compact label="분석 중…" hint="LLM 이 답변을 생성하고 있습니다 (2~4초)" /></Card>
      <Card title="빈 상태" compact><EmptyState :icon="Search" title="문서가 없습니다" desc="PDF 를 업로드하면 여기서 검색할 수 있습니다." compact><Button size="sm">PDF 업로드</Button></EmptyState></Card>
      <Card title="스켈레톤 · 페이지네이션" compact>
        <div class="flex flex-col gap-2 mb-3"><Skeleton /><Skeleton width="70%" /><Skeleton width="40%" /></div>
        <Pagination :total="79" :page="page" :page-size="10" @update:page="(p: number) => (page = p)" />
      </Card>
    </div>

    <Card title="차트" subtitle="첫 색 = 액센트 (테마 따라 읽음)">
      <LineChart :labels="['08/02', '08/08', '08/12', '08/16', '08/20', '08/24', '08/28', '09/01']" :datasets="[{ label: '검색 응답(ms)', data: [95, 88, 102, 91, 97, 90, 93, 95] }, { label: 'LLM(ms)', data: [3100, 2900, 3400, 3000, 3200, 2800, 3100, 3000] }]" height="200px" dual-axis />
    </Card>

    <ConfirmModal :open="modal" title="Property Graph 를 삭제할까요?" danger confirm-label="삭제" @confirm="modal = false" @cancel="modal = false">
      기존 테이블 위의 뷰라 데이터는 안전합니다. 정의를 바꿨다면 삭제 후 재생성해야 반영됩니다.
    </ConfirmModal>
  </div>
</template>
