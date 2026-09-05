<script setup lang="ts">
/**
 * 그래프 시각화 — 패턴 질의 0("고객 → 제품 구매 관계") 결과를 SVG 이분 그래프로 그린다.
 * 레거시는 "향후 구현 예정" 자리표시자였다(2026-09-05 신설, 06 문서 B 도메인 편차).
 * 라이브러리 없이 SVG 만 쓴다 — 정점 2종(고객·제품), 간선 굵기 = 매출, 제품 색 = 카테고리.
 */
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Network } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import Badge from '@/components/ui/Badge.vue'
import { fmtNum } from '@/lib/format'
import { useGraphStore } from '@/stores/graph'

const g = useGraphStore()
const route = useRoute()
const VIZ_INDEX = 0
// `?run=1` 이면 mount 직후 한 번 실행한다 — 기능 지도 딥링크·헤드리스 캡처·시연용 (설계서 05 §3.3)
onMounted(() => { void g.loadQueries().then(() => { if (route.query.run !== undefined && !g.patternResults[VIZ_INDEX]) void g.pattern(VIZ_INDEX) }) })

const rows = computed(() => g.patternResults[VIZ_INDEX] ?? null)
const PALETTE = ['#C74634', '#0a84ff', '#00a82d', '#ff9500', '#7c75ff', '#34c759', '#ffcc00', '#af52de']

interface Edge { product: string; category: string; amount: number; y: number; w: number; color: string }
const model = computed(() => {
  const r = rows.value
  if (!r || !r.rows.length) return null
  const cols = r.columns
  const pick = (row: Record<string, unknown>, names: string[]) => { const c = cols.find((k) => names.includes(k.toUpperCase())); return c ? row[c] : undefined }
  const customer = String(pick(r.rows[0], ['CUSTOMER', 'CUSTOMER1', 'CUST_FIRST_NAME']) ?? '고객')
  const items = r.rows.map((row) => ({
    product: String(pick(row, ['PRODUCT', 'PROD_NAME', 'SHARED_PRODUCT']) ?? ''),
    category: String(pick(row, ['CATEGORY', 'PROD_CATEGORY']) ?? ''),
    amount: Number(pick(row, ['AMOUNT', 'AMOUNT_SOLD']) ?? 0),
  })).filter((x) => x.product)
  // 같은 제품은 합산
  const agg = new Map<string, { category: string; amount: number }>()
  for (const it of items) { const a = agg.get(it.product); if (a) a.amount += it.amount; else agg.set(it.product, { category: it.category, amount: it.amount }) }
  const cats = [...new Set([...agg.values()].map((v) => v.category))]
  const max = Math.max(...[...agg.values()].map((v) => v.amount), 1)
  const list = [...agg.entries()].sort((a, b) => b[1].amount - a[1].amount).slice(0, 20)
  const gap = 34
  const edges: Edge[] = list.map(([product, v], i) => ({
    product, category: v.category, amount: v.amount, y: 40 + i * gap,
    w: 1.5 + (v.amount / max) * 6, color: PALETTE[cats.indexOf(v.category) % PALETTE.length],
  }))
  return { customer, edges, cats: cats.map((c, i) => ({ name: c, color: PALETTE[i % PALETTE.length] })), height: 40 + list.length * gap + 20, total: items.reduce((s, x) => s + x.amount, 0) }
})
</script>

<template>
  <Card title="그래프 시각화" subtitle="패턴 질의 「고객 → 제품 구매 관계」 결과 — 간선 굵기 = 매출, 제품 색 = 카테고리" :icon="Network">
    <template #actions><Button variant="secondary" size="sm" :busy="g.busy === 'pattern'" @click="g.pattern(VIZ_INDEX)">{{ rows ? '다시 실행' : '패턴 질의 실행' }}</Button></template>

    <LoadingBlock v-if="g.busy === 'pattern' && !rows" compact label="그래프를 탐색 중…" />
    <EmptyState v-else-if="!model" :icon="Network" title="아직 그릴 데이터가 없습니다" desc="우상단 [패턴 질의 실행]을 누르면 고객 524 의 구매 관계를 가져와 그립니다." compact />
    <div v-else class="flex flex-col gap-3">
      <div class="flex flex-wrap items-center gap-2 text-xs" style="color: var(--text-muted);">
        <span>정점 {{ fmtNum(model.edges.length + 1) }} · 간선 {{ fmtNum(model.edges.length) }} · 총 매출 {{ fmtNum(Math.round(model.total)) }}</span>
        <span class="mx-1">|</span>
        <span v-for="c in model.cats" :key="c.name" class="inline-flex items-center gap-1"><span class="inline-block w-2.5 h-2.5 rounded-full" :style="{ background: c.color }"></span>{{ c.name }}</span>
      </div>
      <div class="overflow-x-auto rounded-md" style="border: 1px solid var(--border-default); background: var(--bg-surface);">
        <svg :viewBox="`0 0 900 ${model.height}`" :height="model.height" width="100%" preserveAspectRatio="xMinYMin meet" font-family="inherit">
          <!-- 간선 -->
          <path v-for="e in model.edges" :key="'e' + e.product" :d="`M 190 ${model.height / 2} C 380 ${model.height / 2}, 420 ${e.y}, 600 ${e.y}`"
            fill="none" :stroke="e.color" :stroke-width="e.w" stroke-opacity="0.55" stroke-linecap="round">
            <title>{{ model.customer }} → {{ e.product }} · {{ fmtNum(Math.round(e.amount)) }}</title>
          </path>
          <!-- 고객 정점 -->
          <g :transform="`translate(190, ${model.height / 2})`">
            <circle r="26" fill="var(--accent-primary)" />
            <text text-anchor="middle" dy="4" font-size="12" font-weight="600" fill="#fff">고객</text>
            <text text-anchor="end" x="-36" dy="4" font-size="13" font-weight="600" fill="var(--text-primary)">{{ model.customer }}</text>
          </g>
          <!-- 제품 정점 -->
          <g v-for="e in model.edges" :key="'n' + e.product" :transform="`translate(600, ${e.y})`">
            <circle :r="6 + e.w" :fill="e.color" />
            <text x="16" dy="4" font-size="12" fill="var(--text-primary)">{{ e.product }}</text>
            <text x="16" dy="4" :dx="e.product.length * 6.6 + 8" font-size="11" fill="var(--text-muted)">{{ fmtNum(Math.round(e.amount)) }}</text>
            <title>{{ e.product }} ({{ e.category }}) · {{ fmtNum(Math.round(e.amount)) }}</title>
          </g>
        </svg>
      </div>
      <div class="flex items-center gap-2 text-xs" style="color: var(--text-muted);">
        <Badge tone="info">SQL/PGQ</Badge> 같은 데이터가 「관계 탐색」 탭의 표와 「SQL vs SQL/PGQ」 1번 쿼리에도 나옵니다 — 그래프는 기존 테이블 위의 뷰라 세 화면이 한 데이터입니다.
      </div>
    </div>
  </Card>
</template>
