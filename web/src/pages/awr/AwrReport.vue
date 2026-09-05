<script setup lang="ts">
import { computed, ref } from 'vue'
import { Gauge, ListChecks, MessageSquareText, ExternalLink, BarChart3 } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import ChatThread from '@/components/demo/ChatThread.vue'
import ChatComposer from '@/components/demo/ChatComposer.vue'
import AwrSection from './AwrSection.vue'
import { SECTION_KEYS, awrSourceUrl } from '@/lib/awr'
import { fmtNum } from '@/lib/format'
import { useAwrStore } from '@/stores/awr'
import type { AwrSession } from '@/stores/awr'

const props = defineProps<{ session: AwrSession }>()
const awr = useAwrStore()
const question = ref('')
const showSource = ref(false)

const a = computed(() => props.session.analysis)
const scores = computed(() => Object.entries(a.value.categoryScores ?? {}).map(([key, v]) => ({ key, ...v })))
const overall = computed(() => scores.value.length ? Math.round(scores.value.reduce((s, x) => s + (Number(x.score) || 0), 0) / scores.value.length) : null)
const tone = (s: number) => (s >= 80 ? 'positive' : s >= 60 ? 'info' : s >= 40 ? 'warm' : 'negative')
const sections = computed(() => SECTION_KEYS.map((k, i) => ({ key: k, index: i + 1, section: a.value[k] })).filter((x) => x.section))
const FALLBACK = ['시스템 개요', '핵심 병목 진단', 'Top SQL 분석', 'I/O 분석', 'Hot Segments', '메모리 분석', 'Host CPU', '종합 권고사항']
const ptone = (p: string) => (p.includes('긴급') ? 'negative' : p.includes('높음') ? 'warm' : p.includes('중간') ? 'info' : 'default')
const info = computed(() => props.session.parseInfo)
function send() { const q = question.value; question.value = ''; void awr.ask(q) }
</script>

<template>
  <div class="flex flex-col gap-5">
    <!-- 분석 정보 (옛 사이드바 「분석 정보」) -->
    <div class="flex flex-wrap items-center gap-2">
      <Badge tone="code">{{ session.filename }}</Badge>
      <Badge>섹션 {{ info.section_count }}개</Badge>
      <Badge :tone="info.is_rac ? 'info' : 'default'">RAC {{ info.is_rac ? '예' : '아니오' }}</Badge>
      <Badge :tone="info.is_exadata ? 'info' : 'default'">Exadata {{ info.is_exadata ? '예' : '아니오' }}</Badge>
      <Badge tone="primary">{{ session.provider }} · {{ (session.elapsedMs / 1000).toFixed(1) }}초</Badge>
      <Badge v-if="info.raw_text_length">원문 {{ fmtNum(info.raw_text_length) }}자 / 입력 제한 {{ fmtNum(info.max_input_chars ?? 0) }}자</Badge>
      <span class="flex-1" />
      <Button variant="secondary" size="sm" @click="showSource = true"><ExternalLink :size="13" :stroke-width="2" /> AWR 원문 보기</Button>
    </div>

    <!-- ① 카테고리별 성능 점수 -->
    <Card v-if="scores.length" title="카테고리별 성능 점수" :subtitle="overall !== null ? `7개 카테고리 평균 ${overall}점 — 80 이상 양호 · 60 주의 · 40 미만 위험` : undefined" :icon="Gauge">
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        <div v-for="s in scores" :key="s.key" class="rounded-md px-3.5 py-3" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
          <div class="flex items-baseline justify-between gap-2">
            <span class="text-sm font-semibold" style="color: var(--text-primary);">{{ s.label }}</span>
            <span class="text-lg font-bold tabular-nums" :style="{ color: `var(--accent-${tone(Number(s.score))})` }">{{ s.score }}</span>
          </div>
          <div class="h-1.5 rounded-full overflow-hidden mt-2" style="background: var(--bg-elevated);">
            <div class="h-full rounded-full" :style="{ width: `${Math.min(100, Math.max(0, Number(s.score)))}%`, background: `var(--accent-${tone(Number(s.score))})` }" />
          </div>
          <p v-if="s.detail" class="text-xs m-0 mt-2" style="color: var(--text-secondary); line-height: 1.55;">{{ s.detail }}</p>
        </div>
      </div>
    </Card>

    <!-- ② 8개 섹션 -->
    <AwrSection v-for="s in sections" :key="s.key" :index="s.index" :section="s.section" :fallback-title="FALLBACK[s.index - 1]" />

    <!-- ③ 액션 아이템 -->
    <Card v-if="a.actionItems?.length" title="액션 아이템 (우선순위순)" :subtitle="`${a.actionItems.length}건 — 근거 수치와 기대 효과를 함께 적었습니다`" :icon="ListChecks">
      <ol class="m-0 p-0 list-none flex flex-col gap-2.5">
        <li v-for="(it, i) in a.actionItems" :key="i" class="flex items-start gap-3 rounded-md px-3.5 py-3" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
          <Badge :tone="ptone(it.priority)" class="shrink-0 mt-0.5">{{ it.priority.replace(/[\[\]]/g, '') }}</Badge>
          <div class="min-w-0 flex-1">
            <div class="text-sm font-semibold" style="color: var(--text-primary);">{{ it.action }}</div>
            <div v-if="it.evidence" class="flex items-start gap-1.5 text-xs mt-1" style="color: var(--text-secondary); line-height: 1.6;"><BarChart3 :size="13" :stroke-width="1.75" class="shrink-0 mt-0.5" /><span>{{ it.evidence }}</span></div>
            <div class="flex flex-wrap items-center gap-2 mt-1.5 text-xs">
              <Badge v-if="it.category" tone="default">{{ it.category }}</Badge>
              <span v-if="it.expectedImpact" style="color: var(--accent-positive);">{{ it.expectedImpact }}</span>
            </div>
          </div>
        </li>
      </ol>
    </Card>

    <!-- ④ 후속 질문 -->
    <Card title="추가 질문" :subtitle="session.imported ? '가져온 결과 — 서버에 분석 세션이 남아 있을 때만 답할 수 있습니다' : '이 리포트의 수치를 근거로 답합니다 — 같은 LLM 에게 이어서 묻는 것'" :icon="MessageSquareText">
      <ChatThread :messages="session.messages" empty-text="예: 「Top SQL 1번의 실행계획에서 먼저 볼 것은?」 「Buffer Cache 를 늘리면 얼마나 좋아지나?」" />
      <div class="mt-3"><ChatComposer v-model="question" :busy="awr.asking" placeholder="분석 결과에 대해 추가로 질문하세요…" @send="send" /></div>
    </Card>

    <!-- 원문 보기 모달 -->
    <Teleport to="body">
      <div v-if="showSource" class="fixed inset-0 z-[60] flex items-center justify-center p-4" style="background: rgba(0,0,0,0.5);" @click.self="showSource = false">
        <div class="w-full max-w-[1280px] h-[88vh] rounded-lg overflow-hidden flex flex-col" style="background: var(--bg-elevated); box-shadow: var(--shadow-elevated);">
          <div class="flex items-center justify-between px-4 shrink-0" style="height: 48px; border-bottom: 1px solid var(--border-default);">
            <span class="text-sm font-semibold" style="color: var(--text-primary);">AWR 원문 — {{ session.filename }}</span>
            <div class="flex items-center gap-2">
              <a :href="awrSourceUrl(session.sessionId)" target="_blank" rel="noopener" class="text-xs" style="color: var(--accent-primary);">새 탭에서 열기</a>
              <Button variant="ghost" size="sm" @click="showSource = false">닫기</Button>
            </div>
          </div>
          <iframe :src="awrSourceUrl(session.sessionId)" class="flex-1 w-full border-0" style="background: #fff;" title="AWR 원문" />
        </div>
      </div>
    </Teleport>
  </div>
</template>
