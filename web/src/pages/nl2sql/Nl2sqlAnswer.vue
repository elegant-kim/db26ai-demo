<script setup lang="ts">
/** NL2SQL 어시스턴트 메시지 — 레거시 bubble-assistant 의 결과 블록 8종을 카드 없는 블록으로 (06 §5.12). */
import { computed } from 'vue'
import { Bot } from 'lucide-vue-next'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import BarChart from '@/components/ui/BarChart.vue'
import LineChart from '@/components/ui/LineChart.vue'
import DonutChart from '@/components/ui/DonutChart.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import ResultTable from '@/components/demo/ResultTable.vue'
import Segmented from '@/components/demo/Segmented.vue'
import { renderMarkdown } from '@/lib/markdown'
import { fmtMs, isNumeric } from '@/lib/format'
import { useNl2sqlStore, type ChartType, type Nl2sqlMessage } from '@/stores/nl2sql'

const props = defineProps<{ msg: Nl2sqlMessage }>()
const s = useNl2sqlStore()
const CHART_TYPES = [{ value: 'bar', label: '막대' }, { value: 'line', label: '라인' }, { value: 'pie', label: '파이' }]
const attrs = computed(() => s.profileAttrsRows(props.msg))
const env = computed(() => s.envRows(props.msg))
const isPrompt = computed(() => props.msg.action === 'showprompt')

/** 차트 데이터 — 첫 문자열 컬럼 = 라벨, 첫 숫자 컬럼(라벨 제외) = 값 (레거시 renderChart 규칙) */
const chart = computed(() => {
  const t = props.msg.table
  if (!t || !t.rows.length) return null
  const cols = t.columns
  const first = t.rows[0]
  const labelCol = cols.find((c) => !isNumeric(first[c])) ?? cols[0]
  const valueCol = cols.find((c) => c !== labelCol && isNumeric(first[c])) ?? cols[1] ?? cols[0]
  return { labels: t.rows.map((r) => String(r[labelCol] ?? '')), values: t.rows.map((r) => Number(r[valueCol]) || 0), valueCol }
})
</script>

<template>
  <div class="flex items-start gap-2.5 w-full min-w-0">
    <div class="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5" style="background: var(--bg-surface); border: 1px solid var(--border-default); color: var(--accent-primary);"><Bot :size="15" :stroke-width="1.75" /></div>
    <div class="flex-1 min-w-0 flex flex-col gap-2.5">
      <LoadingBlock v-if="msg.loading" compact :label="msg.loadingText || '처리 중…'" />
      <template v-else>
        <div v-if="msg.errorText" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);"><strong>오류:</strong> <span class="font-mono text-xs break-all">{{ msg.errorText }}</span></div>

        <!-- 프로필 설정 결과 -->
        <template v-if="msg.profileResult">
          <div class="text-sm font-semibold" style="color: var(--text-primary);">프로필 설정 완료 · <span class="font-mono">{{ msg.profileResult.profile_name }}</span></div>
          <div v-if="msg.profileResult.attributes?.error" class="text-xs" style="color: var(--accent-negative);">{{ msg.profileResult.attributes.error }}</div>
          <SqlBlock v-if="msg.profileResult.attributes?.sql_executed" :code="msg.profileResult.attributes.sql_executed" label="프로필 속성 조회 SQL" max-height="140px" />
          <ResultTable v-if="attrs" :rows="attrs" dense hide-footer max-height="260px" />
        </template>

        <!-- 환경 확인 (프로필 속성 · 네트워크 ACL · 크리덴셜) -->
        <template v-if="msg.envResult">
          <div class="text-sm font-semibold" style="color: var(--text-primary);">환경 확인 · <span class="font-mono">{{ msg.envResult.label }}</span></div>
          <SqlBlock v-if="msg.envResult.result?.sql_executed" :code="msg.envResult.result.sql_executed" label="조회 SQL" max-height="160px" />
          <ResultTable v-if="env" :rows="env" dense hide-footer max-height="300px" empty-text="행이 없습니다." />
          <div v-if="msg.envResult.kind === 'credential'" class="text-[11px]" style="color: var(--text-muted);">
            API 키 값은 어떤 뷰에도 노출되지 않습니다. <strong style="color: var(--text-primary);">ENABLED='TRUE' 는 키가 유효하다는 뜻이 아닙니다</strong> — 만료된 키도 TRUE 로 보입니다.
          </div>
          <div v-else-if="msg.envResult.kind === 'acl'" class="text-[11px]" style="color: var(--text-muted);">
            아웃바운드 호출에 필요한 권한은 <code class="font-mono">CONNECT</code>·<code class="font-mono">RESOLVE</code> 입니다. 없으면 <code class="font-mono">ORA-24247</code> 로 실패합니다.
          </div>
        </template>

        <!-- SQL 직접 실행 -->
        <template v-if="msg.sqlResult">
          <SqlBlock :code="msg.sqlResult.sql" label="직접 실행한 SQL" />
          <ResultTable :rows="msg.sqlResult" dense />
        </template>

        <SqlBlock v-if="msg.sql" :code="msg.sql" label="생성된 SQL" badge="Select AI" line-numbers />
        <template v-if="msg.table">
          <ResultTable :rows="msg.table" dense empty-text="결과 행이 없습니다." />
          <div v-if="msg.showChart && chart" class="rounded-md p-3" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="text-xs font-medium" style="color: var(--text-secondary);">{{ chart.valueCol }}</span>
              <Segmented :model-value="msg.chartType || 'bar'" :options="CHART_TYPES" size="sm" @update:model-value="(v: string) => (msg.chartType = v as ChartType)" />
            </div>
            <BarChart v-if="(msg.chartType || 'bar') === 'bar'" :labels="chart.labels" :datasets="[{ label: chart.valueCol, data: chart.values }]" height="260px" hide-legend />
            <LineChart v-else-if="msg.chartType === 'line'" :labels="chart.labels" :datasets="[{ label: chart.valueCol, data: chart.values }]" height="260px" show-points />
            <DonutChart v-else :labels="chart.labels" :values="chart.values" height="260px" />
          </div>
        </template>

        <SqlBlock v-if="msg.textResult && isPrompt" :code="msg.textResult" lang="text" label="LLM 프롬프트" max-height="420px" />
        <div v-else-if="msg.textResult" class="md-body text-sm rounded-md px-3.5 py-3" style="background: var(--bg-surface); color: var(--text-primary);" v-html="renderMarkdown(msg.textResult)" />
        <SqlBlock v-if="msg.explainPlan" :code="msg.explainPlan" lang="text" label="Execution Plan (DBMS_XPLAN)" max-height="420px" />

        <div class="flex flex-wrap items-center gap-1.5">
          <Badge v-if="msg.elapsedMs" tone="code">{{ fmtMs(msg.elapsedMs) }}</Badge>
          <template v-if="!msg.errorText && msg.action !== 'profile' && msg.action !== 'rawsql'">
            <Button v-for="b in s.buttonsFor(msg)" :key="b.action" size="sm" :variant="msg.cached?.[b.action] !== undefined || (b.action === 'chart' && msg.showChart) ? 'primary' : 'secondary'"
              :disabled="msg.actionLoading" @click="s.runAction(msg, b.action)">{{ b.label }}</Button>
          </template>
          <span v-if="msg.actionLoading" class="text-xs" style="color: var(--text-muted);">{{ msg.actionLoadingText }}</span>
          <span class="text-[11px] ml-auto" style="color: var(--text-muted);">{{ msg.timestamp }}</span>
        </div>
      </template>
    </div>
  </div>
</template>
