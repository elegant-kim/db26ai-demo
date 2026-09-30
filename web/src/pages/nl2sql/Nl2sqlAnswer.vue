<script setup lang="ts">
/** NL2SQL 어시스턴트 메시지 — 레거시 bubble-assistant 의 결과 블록 8종을 카드 없는 블록으로 (06 §5.12). */
import { computed } from 'vue'
import { Bot, Copy } from 'lucide-vue-next'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import BarChart from '@/components/ui/BarChart.vue'
import LineChart from '@/components/ui/LineChart.vue'
import DonutChart from '@/components/ui/DonutChart.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import ResultTable from '@/components/demo/ResultTable.vue'
import Segmented from '@/components/demo/Segmented.vue'
import FeedbackBox from '@/components/demo/FeedbackBox.vue'
import AccuracyScenario from './AccuracyScenario.vue'
import { renderMarkdown } from '@/lib/markdown'
import { fmtMs, isNumeric } from '@/lib/format'
import { RESET_NOTE, shortConv } from '@/lib/nl2sql'
import { useSystemStore } from '@/stores/system'
import { useNl2sqlStore, type ChartType, type Nl2sqlMessage } from '@/stores/nl2sql'

const props = defineProps<{ msg: Nl2sqlMessage }>()
const s = useNl2sqlStore()
const system = useSystemStore()
const CHART_TYPES = [{ value: 'bar', label: '막대' }, { value: 'line', label: '라인' }, { value: 'pie', label: '파이' }]
const isPrompt = computed(() => props.msg.action === 'showprompt')
/** 접기(결정 ⑥): 다른 액션으로 이미 받아 둔 SQL·프롬프트는 버튼을 다시 누르지 않아도 접힌 채로 붙어 있다 */
const foldedSql = computed(() => (props.msg.action !== 'showsql' && props.msg.action !== 'explainplan' ? (props.msg.cached?.showsql as string | undefined) ?? null : null))
const foldedPrompt = computed(() => (props.msg.action !== 'showprompt' ? (props.msg.cached?.showprompt as string | undefined) ?? null : null))
const isGreeting = computed(() => props.msg.action === 'greeting')
const hasMeta = computed(() => !isGreeting.value && !props.msg.loading && (props.msg.conversationId !== undefined || props.msg.model || props.msg.logId))
async function copyConv() { const id = props.msg.conversationId; if (!id) return; try { await navigator.clipboard.writeText(id); system.toast('conversation_id 복사', 'success') } catch { system.toast(id, 'info') } }

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
      <AccuracyScenario v-else-if="msg.action === 'scenario' && msg.scenario" :sc="msg.scenario" />
      <template v-else>
        <div v-if="msg.errorText" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);"><strong>오류:</strong> <span class="font-mono text-xs break-all">{{ msg.errorText }}</span></div>

        <!-- SQL 직접 실행 -->
        <template v-if="msg.sqlResult">
          <SqlBlock :code="msg.sqlResult.sql" label="직접 실행한 SQL" :badge="msg.profileName ? `SELECT AI · ${msg.profileName}` : undefined" />
          <ResultTable v-if="!msg.aiDirect" :rows="msg.sqlResult" dense />
        </template>

        <SqlBlock v-if="msg.sql && !foldedSql" :code="msg.sql" label="생성된 SQL" badge="Select AI" line-numbers />
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

        <!-- 접기 — 이미 받아 둔 SQL / 프롬프트 (버튼은 그대로, 결정 ⑥) -->
        <details v-if="foldedSql" class="fold"><summary class="text-xs cursor-pointer select-none" style="color: var(--text-secondary);">생성 SQL 보기</summary><SqlBlock :code="foldedSql" label="생성된 SQL" badge="Select AI" line-numbers class="mt-2" /></details>
        <details v-if="foldedPrompt" class="fold"><summary class="text-xs cursor-pointer select-none" style="color: var(--text-secondary);">프롬프트 보기</summary><SqlBlock :code="foldedPrompt" lang="text" label="LLM 프롬프트" max-height="360px" class="mt-2" /></details>

        <div class="flex flex-wrap items-center gap-1.5">
          <Badge v-if="msg.elapsedMs" tone="code">{{ fmtMs(msg.elapsedMs) }}</Badge>
          <template v-if="!msg.errorText && msg.action !== 'profile' && msg.action !== 'rawsql'">
            <Button v-for="b in s.buttonsFor(msg)" :key="b.action" size="sm" :variant="msg.cached?.[b.action] !== undefined || (b.action === 'chart' && msg.showChart) ? 'primary' : 'secondary'"
              :disabled="msg.actionLoading" @click="s.runAction(msg, b.action)">{{ b.label }}</Button>
          </template>
          <span v-if="msg.actionLoading" class="text-xs" style="color: var(--text-muted);">{{ msg.actionLoadingText }}</span>
          <span class="text-[11px] ml-auto" style="color: var(--text-muted);">AI · {{ msg.timestamp }}</span>
        </div>
        <!-- 답변 메타 (PoC 1-A) — conversation_id · elapsed · 액션 · 프로필 · multi turn -->
        <div v-if="hasMeta" class="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px]" style="color: var(--text-muted);">
          <button v-if="msg.conversationId" type="button" class="inline-flex items-center gap-1 font-mono" :title="`conversation_id ${msg.conversationId} — 클릭하면 복사`" @click="copyConv"><Copy :size="10" :stroke-width="1.75" />{{ shortConv(msg.conversationId) }}</button>
          <span v-else>conversation 없음</span>
          <span>·</span><span v-if="msg.elapsedMs">elapsed {{ msg.elapsedMs.toLocaleString() }} ms</span><span v-else>elapsed —</span>
          <span>·</span><span>액션 <span class="font-mono">{{ msg.action }}</span></span>
          <span>·</span><span>프로필 {{ msg.profileName || s.profile }}</span>
          <span v-if="msg.model">·</span><span v-if="msg.model">모델 {{ msg.model }}</span>
          <span>·</span><span>multi turn {{ msg.multiTurn ? 'ON' : 'OFF' }}</span>
          <span v-if="msg.logId">·</span><span v-if="msg.logId" title="AI_QUERY_LOG.id">log #{{ msg.logId }}</span>
        </div>
        <div v-if="msg.resetNote" class="text-[11px] px-2.5 py-1.5 rounded-md" style="background: var(--accent-info-soft); color: var(--text-secondary);">{{ RESET_NOTE }}</div>
        <!-- 인라인 피드백 (1-B) — 이력 id 가 있는 성공 답변에만. DBMS_CLOUD_AI.FEEDBACK 은 프로필 벡터 인덱스에 들어가 유사 질문의 프롬프트에 주입된다 -->
        <FeedbackBox v-if="msg.logId && !msg.errorText && !isGreeting" :log-id="msg.logId" :existing="msg.feedback ?? null" source="INLINE" @saved="(f) => (msg.feedback = f)" @deleted="msg.feedback = null" />
      </template>
    </div>
  </div>
</template>

<style scoped>
.fold { border: 1px solid var(--border-default); border-radius: var(--radius-control); padding: 6px 10px; background: var(--bg-surface); }
.fold[open] summary { margin-bottom: 2px; }
</style>
