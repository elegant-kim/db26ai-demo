<script setup lang="ts">
/**
 * 단계 카드 목록 — 시뮬레이션·파이프라인처럼 "순서가 내용"인 결과를 그린다 (설계서 05 §6.2).
 * 레거시 step-card(성공=초록/실패=빨강 hex) 를 토큰으로. 실패는 오류가 아니라 "거부됨" 서사일 때가 많아
 * 라벨을 props 로 바꿀 수 있다.
 */
import { computed } from 'vue'
import { CheckCircle2, XCircle } from 'lucide-vue-next'
import type { Step } from '@/lib/productivity'
import SqlBlock from './SqlBlock.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'

const props = withDefaults(defineProps<{
  steps: Step[]
  /** 지금까지 드러낼 단계 수 — 생략하면 전부 */
  revealed?: number
  running?: boolean
  okLabel?: string
  failLabel?: string
}>(), { revealed: undefined, running: false, okLabel: '성공', failLabel: '거부' })

const shown = computed(() => props.revealed === undefined ? props.steps : props.steps.slice(0, props.revealed))
const pending = computed(() => props.running && shown.value.length < props.steps.length)
</script>

<template>
  <ol class="m-0 p-0 list-none flex flex-col gap-2.5">
    <li v-for="(s, i) in shown" :key="i" class="step rounded-md px-3.5 py-3"
      :style="{ background: s.success ? 'var(--accent-positive-soft)' : 'var(--accent-negative-soft)', borderLeft: `3px solid ${s.success ? 'var(--accent-positive)' : 'var(--accent-negative)'}` }">
      <div class="flex items-start gap-2.5">
        <component :is="s.success ? CheckCircle2 : XCircle" :size="16" :stroke-width="1.75" class="shrink-0 mt-0.5"
          :style="{ color: s.success ? 'var(--accent-positive)' : 'var(--accent-negative)' }" />
        <div class="min-w-0 flex-1">
          <div class="text-sm" style="color: var(--text-primary); line-height: 1.6;">
            <span class="font-semibold mr-1.5">Step {{ i + 1 }}</span>
            <span class="text-[11px] font-medium px-1.5 py-0.5 rounded mr-2 align-middle"
              :style="{ background: 'var(--bg-elevated)', color: s.success ? 'var(--accent-positive)' : 'var(--accent-negative)' }">{{ s.success ? okLabel : failLabel }}</span>
            <span>{{ s.description }}</span>
          </div>
          <div v-if="s.sql" class="mt-2"><SqlBlock :code="s.sql" label="SQL" max-height="220px" /></div>
        </div>
      </div>
    </li>
    <li v-if="pending"><LoadingBlock compact label="다음 단계 실행 중…" hint="세션 간 순서를 보여주기 위해 한 단계씩 드러냅니다" /></li>
  </ol>
</template>
