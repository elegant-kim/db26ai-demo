<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { GitCompareArrows } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import ResultTable from '@/components/demo/ResultTable.vue'
import CompareView from '@/components/demo/CompareView.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import Segmented from '@/components/demo/Segmented.vue'
import { fmtMs, fmtNum } from '@/lib/format'
import { useDualityStore } from '@/stores/duality'

const d = useDualityStore()
const route = useRoute()
const mode = ref<'json' | 'app'>('json')
onMounted(() => { void d.loadViews().then(() => { if (route.query.run !== undefined && !d.compareResult && d.hasViews) void d.compare() }) })

const r = computed(() => d.compareResult)
const isCustomer = computed(() => d.compareView.toUpperCase().includes('CUSTOMER'))
/** 같은 엔티티를 보여주는가 — 관계형 첫 컬럼(PK) 과 JSON _id 를 순서대로 비교 */
const equal = computed(() => {
  const x = r.value; if (!x || x.relational.error || x.jsonError || !x.jsonDocs) return null
  const pk = x.relational.columns[0]
  const a = x.relational.rows.map((row) => String(row[pk])); const b = x.jsonDocs.map((doc) => String(doc._id))
  return a.length === b.length && a.every((v, i) => v === b[i])
})
const equalText = computed(() => r.value ? `같은 ${fmtNum(r.value.relational.rows.length)}행을 두 얼굴로 봅니다 — 관계형 SQL ${fmtMs(r.value.relational.elapsedMs)} · JSON Duality View ${fmtMs(r.value.jsonElapsed)}` : '')
const MODES = [{ value: 'json', label: 'JSON 문서', hint: '_metadata.etag 포함' }, { value: 'app', label: '앱 화면', hint: 'JSON 을 그대로 카드로' }]
const jsonPretty = computed(() => r.value?.jsonDocs ? JSON.stringify(r.value.jsonDocs, null, 2) : '')
const initials = (doc: any) => `${(doc.firstName || '?')[0]}${(doc.lastName || '?')[0]}`
</script>

<template>
  <Card title="관계형 vs JSON 비교" subtitle="같은 행을 관계형 SQL 과 Duality View 의 JSON 문서로 나란히 읽습니다 — 양쪽 다 PK 오름차순이라 같은 엔티티가 마주 보입니다" :icon="GitCompareArrows">
    <div class="flex flex-wrap items-center gap-2 mb-4">
      <div class="w-[260px]"><SearchableSelect v-model="d.compareView" :options="d.viewOptions" placeholder="뷰 선택" :searchable="false" /></div>
      <label class="flex items-center gap-1.5 text-sm" style="color: var(--text-secondary);">건수
        <input v-model.number="d.compareLimit" type="number" min="1" max="50" class="w-16 rounded-md px-2 py-1.5 text-sm" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" />
      </label>
      <Button :busy="d.busy === 'compare'" :disabled="!d.hasViews" @click="d.compare()">비교 실행</Button>
    </div>

    <div v-if="d.lastError" class="px-3 py-2.5 rounded-md text-sm mb-4" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ d.lastError }}</div>
    <EmptyState v-if="d.viewsLoaded && !d.hasViews" :icon="GitCompareArrows" title="Duality View 가 아직 없습니다" desc="「뷰 관리」에서 먼저 생성하세요." compact />
    <LoadingBlock v-else-if="d.busy === 'compare' && !r" compact label="두 방식으로 읽는 중…" />
    <EmptyState v-else-if="!r" :icon="GitCompareArrows" title="뷰를 고르고 [비교 실행]을 누르세요" desc="왼쪽은 SQL 결과 표, 오른쪽은 같은 행의 JSON 문서입니다. 오른쪽을 「앱 화면」으로 바꾸면 그 JSON 을 그대로 카드로 그립니다." compact />

    <CompareView v-else
      :left="{ title: '관계형 SQL', elapsedMs: r.relational.elapsedMs, error: r.relational.error, rowCount: r.relational.rows.length }"
      :right="{ title: 'JSON Duality View', elapsedMs: r.jsonElapsed, error: r.jsonError, rowCount: r.jsonDocs?.length ?? 0, badge: '26ai' }"
      :equal="equal" :equal-text="equalText" different-text="두 쪽의 행이 다릅니다 — 양쪽 PK 정렬을 확인하세요.">
      <template #left>
        <SqlBlock :code="r.relational.sql" label="SQL" max-height="200px" />
        <div class="mt-2"><ResultTable :rows="r.relational" dense max-height="480px" /></div>
      </template>
      <template #right>
        <SqlBlock :code="r.jsonSql" label="SQL (1줄 — JOIN 없음)" max-height="200px" badge="DUALITY" />
        <div class="mt-2 flex items-center gap-2 flex-wrap">
          <Segmented :model-value="mode" :options="MODES" size="sm" @update:model-value="(v: string) => (mode = v as 'json' | 'app')" />
          <span class="text-xs" style="color: var(--text-muted);">{{ mode === 'json' ? '문서마다 _metadata.etag(버전 해시)가 실려 온다' : '이 JSON 을 프론트엔드가 바로 그린 것 — 백엔드 가공 없음' }}</span>
        </div>
        <div v-if="mode === 'json'" class="mt-2"><SqlBlock :code="jsonPretty" lang="json" label="JSON 문서" max-height="480px" /></div>
        <div v-else class="mt-2 grid grid-cols-1 xl:grid-cols-2 gap-2">
          <div v-for="(doc, i) in r.jsonDocs" :key="i" class="flex items-center gap-3 rounded-md px-3 py-2.5" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
            <div class="w-9 h-9 rounded-full flex items-center justify-center text-xs font-semibold shrink-0" style="background: var(--accent-primary); color: var(--text-on-accent);">{{ isCustomer ? initials(doc) : 'P' }}</div>
            <div class="min-w-0">
              <div class="text-sm font-semibold truncate" style="color: var(--text-primary);">{{ isCustomer ? `${doc.firstName} ${doc.lastName}` : doc.prodName }}</div>
              <div class="text-xs truncate" style="color: var(--text-secondary);">{{ isCustomer ? [doc.city, doc.incomeLevel].filter(Boolean).join(' · ') : doc.prodCategory }}</div>
              <div class="text-xs font-medium" style="color: var(--accent-primary);">{{ isCustomer ? `Credit ${fmtNum(doc.creditLimit)}` : `$ ${fmtNum(doc.prodListPrice)}` }}</div>
            </div>
          </div>
        </div>
      </template>
    </CompareView>
  </Card>
</template>
