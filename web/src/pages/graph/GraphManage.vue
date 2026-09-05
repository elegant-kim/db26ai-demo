<script setup lang="ts">
import { ref } from 'vue'
import { Boxes, CheckCircle2, AlertTriangle } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import VersusBox from '@/components/demo/VersusBox.vue'
import { useGraphStore } from '@/stores/graph'

const g = useGraphStore()
const confirmDrop = ref(false)
</script>

<template>
  <div class="flex flex-col gap-5">
    <!-- 26ai 의 차별성 — 레거시의 초록 안내 박스를 토큰으로 -->
    <Card title="SQL Property Graph — Oracle 26ai 의 차별성" :icon="Boxes">
      <VersusBox left-title="기존 그래프 DB (Neo4j 등)" left-desc="별도 DB 에 데이터 복제 필요. Cypher 등 전용 언어. 트랜잭션 일관성 보장 어려움."
        right-title="Oracle Property Graph (SQL/PGQ)">
        기존 관계형 테이블 위에 <strong style="color: var(--text-primary);">그래프 모델을 정의</strong>하면, 별도 그래프 DB 없이
        <strong style="color: var(--text-primary);">ISO 표준 SQL/PGQ</strong> 문법으로 관계를 탐색할 수 있습니다.
        데이터 복제·동기화가 필요 없고, Oracle 의 트랜잭션 일관성이 그대로 보장됩니다.
        <template #right><strong>기존 테이블 그대로 사용 — 복제 없음.</strong> ISO 표준 SQL/PGQ. MVCC 트랜잭션 일관성. JSON/VECTOR 와 통합.</template>
      </VersusBox>
    </Card>

    <Card title="그래프 생성 · 삭제" subtitle="SH 스키마의 CUSTOMERS(정점) · PRODUCTS(정점) · SALES(간선) 위에 SALES_GRAPH 를 정의합니다">
      <div class="flex flex-wrap gap-2">
        <Button :busy="g.busy === 'create'" :disabled="g.busy !== '' && g.busy !== 'create'" @click="g.create()">그래프 생성</Button>
        <Button variant="danger" :busy="g.busy === 'drop'" :disabled="g.busy !== '' && g.busy !== 'drop'" @click="confirmDrop = true">그래프 삭제</Button>
      </div>

      <div v-if="g.manageResult" class="mt-4 flex flex-col gap-3">
        <div v-if="g.manageResult.error" class="flex items-start gap-2 px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">
          <AlertTriangle :size="16" :stroke-width="1.75" class="shrink-0 mt-0.5" style="color: var(--accent-negative);" />
          <span class="font-mono text-xs break-all">{{ g.manageResult.error }}</span>
        </div>
        <div v-else-if="g.manageResult.message" class="flex items-center gap-2 px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-positive-soft); border-left: 3px solid var(--accent-positive); color: var(--text-primary);">
          <CheckCircle2 :size="16" :stroke-width="1.75" style="color: var(--accent-positive);" />
          {{ g.manageResult.message }}
        </div>
        <SqlBlock v-if="g.manageResult.sql_executed" :code="g.manageResult.sql_executed" label="실행된 DDL" line-numbers />
      </div>
    </Card>

    <ConfirmModal :open="confirmDrop" title="Property Graph 를 삭제할까요?" danger confirm-label="삭제" :busy="g.busy === 'drop'"
      @confirm="confirmDrop = false; g.drop()" @cancel="confirmDrop = false">
      기존 테이블 위의 뷰라 데이터는 안전합니다. 정의를 바꿨다면 삭제 후 재생성해야 반영됩니다.
    </ConfirmModal>
  </div>
</template>
