<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Activity } from 'lucide-vue-next'
import PageHeader from '@/components/demo/PageHeader.vue'
import Card from '@/components/ui/Card.vue'
import PipelineProgress from '@/components/demo/PipelineProgress.vue'
import SessionTabs from '@/components/demo/SessionTabs.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import AwrUpload from './awr/AwrUpload.vue'
import AwrReport from './awr/AwrReport.vue'
import { useAwrStore } from '@/stores/awr'

const awr = useAwrStore()
const route = useRoute()
// `?load=<json url>` — 저장해 둔 분석 응답을 그대로 연다 (시연·캡처용, 설계서 05 §3.3)
onMounted(() => { const u = route.query.load; if (typeof u === 'string' && u && !awr.sessions.length) void awr.loadFromUrl(u) })

const STEPS = [
  { label: 'HTML 파싱', detail: '23개 섹션 제목을 찾아 표 데이터를 추출하고 있습니다…' },
  { label: 'AI 분석', detail: 'LLM 이 8개 보고서와 점수·액션아이템을 작성하고 있습니다 — 가장 오래 걸리는 단계 (30~120초)' },
  { label: '결과 정리', detail: '보고서를 정리하고 있습니다…' },
]
const tabs = computed(() => awr.sessions.map((s) => ({ id: s.id, label: s.filename, sub: s.provider, time: s.timestamp })))
</script>

<template>
  <div class="flex flex-col gap-5">
    <PageHeader menu="awr" desc="AWR HTML 리포트를 LLM 이 읽고, DBA 가 보는 순서대로 8개 보고서 · 카테고리 점수 · 우선순위 액션아이템으로 정리합니다." />
    <AwrUpload />

    <Card v-if="awr.loading">
      <PipelineProgress title="AWR 리포트 AI 분석 중" subtitle="23개 섹션 추출 → 8개 분석 보고서 생성" :steps="STEPS" :current="awr.step"
        :percent="awr.percent" :elapsed-sec="awr.elapsedSec" :bar-percent="awr.step === 2 ? awr.percent : null" bar-estimated />
    </Card>
    <div v-if="awr.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ awr.error }}</div>

    <template v-if="awr.sessions.length">
      <SessionTabs :tabs="tabs" :model-value="awr.active" closable @update:model-value="awr.select" @close="awr.remove" />
      <AwrReport v-if="awr.current" :key="awr.current.id" :session="awr.current" />
    </template>
    <EmptyState v-else-if="!awr.loading" :icon="Activity" title="아직 분석한 리포트가 없습니다" desc="위에 AWR HTML 을 올리면 됩니다. 여러 리포트를 올리면 탭으로 나란히 비교할 수 있습니다." compact />
  </div>
</template>
