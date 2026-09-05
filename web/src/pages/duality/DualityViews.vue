<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Layers, CheckCircle2, AlertTriangle } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import VersusBox from '@/components/demo/VersusBox.vue'
import { useDualityStore } from '@/stores/duality'

const d = useDualityStore()
const confirmDrop = ref(false)
onMounted(() => { void d.loadViews() })
const VALUES = [
  { t: 'ORM 이 필요 없다', s: 'DB 가 JSON ↔ 관계형 매핑을 직접 한다. 복잡한 JOIN 성능 이슈와 테이블 변경 때의 매핑 코드 수정이 사라진다' },
  { t: '앱에서 바로 쓴다', s: 'JSON 문서를 받아 프론트엔드가 카드·리스트로 바로 그린다 — 백엔드 가공 없음' },
  { t: '자동 동기화', s: 'JSON 을 고치면 원본 테이블이 갱신된다. 충돌은 ETag 로 DB 가 잡는다' },
]
</script>

<template>
  <div class="flex flex-col gap-5">
    <Card title="JSON Relational Duality View — 한 데이터, 두 얼굴" :icon="Layers">
      <VersusBox left-title="기존 방식" left-desc="DB 테이블 → 백엔드가 JOIN SQL 작성 → API 엔드포인트 → JSON 변환 → 프론트엔드"
        right-title="Duality View" right-desc="DB 테이블 → Duality View → JSON 문서 → 프론트엔드. 백엔드 코드가 거의 없다">
        관계형 테이블 위에 <strong style="color: var(--text-primary);">JSON 문서 모양의 뷰</strong>를 GraphQL 문법으로 정의합니다.
        같은 데이터를 SQL 로도, 문서(REST/JSON)로도 읽고 쓰며, 어느 쪽으로 고쳐도 다른 쪽에 즉시 반영됩니다.
      </VersusBox>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
        <div v-for="v in VALUES" :key="v.t" class="rounded-md px-3.5 py-3" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
          <div class="text-sm font-semibold mb-1" style="color: var(--text-primary);">{{ v.t }}</div>
          <div class="text-xs" style="color: var(--text-secondary); line-height: 1.6;">{{ v.s }}</div>
        </div>
      </div>
    </Card>

    <Card title="뷰 생성 · 삭제 · 목록" subtitle="SH 스키마의 CUSTOMERS · PRODUCTS 위에 CUSTOMERS_DV · PRODUCTS_DV 를 만듭니다 (정의는 app/duality.py 의 DUALITY_VIEW_DDLS)">
      <template #actions>
        <span v-if="d.viewsLoaded" class="text-xs" style="color: var(--text-muted);">현재 {{ d.views.length }}개</span>
        <Badge v-for="v in d.views" :key="v.name" tone="positive">{{ v.name }}</Badge>
      </template>
      <div class="flex flex-wrap gap-2">
        <Button :busy="d.busy === 'create'" :disabled="d.busy !== '' && d.busy !== 'create'" @click="d.act('create')">Duality View 생성</Button>
        <Button variant="danger" :busy="d.busy === 'drop'" :disabled="d.busy !== '' && d.busy !== 'drop'" @click="confirmDrop = true">Duality View 삭제</Button>
        <Button variant="secondary" :busy="d.busy === 'views'" :disabled="d.busy !== '' && d.busy !== 'views'" @click="d.act('views')">목록 조회</Button>
      </div>
      <div v-if="d.manageResult" class="mt-4 flex flex-col gap-3">
        <div v-if="d.manageResult.error" class="flex items-start gap-2 px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">
          <AlertTriangle :size="16" :stroke-width="1.75" class="shrink-0 mt-0.5" style="color: var(--accent-negative);" /><span class="font-mono text-xs break-all">{{ d.manageResult.error }}</span>
        </div>
        <div v-else-if="d.manageResult.message" class="flex items-center gap-2 px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-positive-soft); border-left: 3px solid var(--accent-positive); color: var(--text-primary);">
          <CheckCircle2 :size="16" :stroke-width="1.75" style="color: var(--accent-positive);" />{{ d.manageResult.message }}
        </div>
        <SqlBlock v-if="d.manageResult.sql_executed" :code="d.manageResult.sql_executed" label="실행된 SQL" line-numbers max-height="420px" />
      </div>
    </Card>

    <ConfirmModal :open="confirmDrop" title="Duality View 를 삭제할까요?" danger confirm-label="삭제" :busy="d.busy === 'drop'"
      @confirm="confirmDrop = false; d.act('drop')" @cancel="confirmDrop = false">
      뷰만 지워지고 원본 테이블(CUSTOMERS · PRODUCTS)은 그대로입니다. 비교·CRUD·ETag 탭은 뷰가 있어야 동작합니다.
    </ConfirmModal>
  </div>
</template>
