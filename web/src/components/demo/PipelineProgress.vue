<script setup lang="ts">
/**
 * 단계형 진행 표시 — AWR 분석(타이머 연출)·PDF 업로드(SSE) 공통 (설계서 05 §6.4·§6.6).
 * "멈춤"과 "작업 중"을 구분시키는 부품: 링 퍼센트 + 경과 초 + 단계별 상태.
 */
import { Check } from 'lucide-vue-next'
import { fmtNum } from '@/lib/format'

interface Step { label: string; detail?: string; time?: string }
const props = withDefaults(defineProps<{
  title: string
  subtitle?: string
  steps: Step[]
  /** 1부터 시작하는 진행 중 단계. steps.length 보다 크면 전부 완료 */
  current: number
  percent?: number | null
  elapsedSec?: number | null
  /** 진행 중 단계 아래 막대 (0~100) — 추정치일 때 `~` 를 붙인다 */
  barPercent?: number | null
  barEstimated?: boolean
  /** 막대 옆 글자 — 생략하면 % */
  barLabel?: string
}>(), { percent: null, elapsedSec: null, barPercent: null, barEstimated: false, barLabel: undefined })
const state = (i: number) => (i + 1 < props.current ? 'done' : i + 1 === props.current ? 'running' : 'pending')
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="flex items-center gap-4">
      <div v-if="percent !== null" class="ring shrink-0" :style="{ '--pct': `${Math.min(100, Math.max(0, percent)) * 3.6}deg` }">
        <div class="ring-inner"><span class="text-sm font-semibold" style="color: var(--text-primary);">{{ Math.round(percent) }}%</span></div>
      </div>
      <div class="min-w-0">
        <div class="text-base font-semibold" style="color: var(--text-primary);">{{ title }}</div>
        <div v-if="subtitle" class="text-sm mt-0.5" style="color: var(--text-secondary);">{{ subtitle }}</div>
        <div v-if="elapsedSec !== null" class="text-xs mt-1 font-medium" style="color: var(--accent-primary);">⏱ {{ fmtNum(elapsedSec) }}초</div>
      </div>
    </div>
    <ol class="m-0 p-0 list-none flex flex-col gap-2.5">
      <li v-for="(s, i) in steps" :key="s.label" class="flex items-start gap-3">
        <div class="mt-0.5 w-5 h-5 rounded-full flex items-center justify-center shrink-0 text-[11px]" :class="`dot-${state(i)}`">
          <Check v-if="state(i) === 'done'" :size="12" :stroke-width="3" />
          <span v-else-if="state(i) === 'running'" class="pulse" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="text-sm font-medium flex items-center gap-2" :style="{ color: state(i) === 'pending' ? 'var(--text-muted)' : 'var(--text-primary)' }">{{ i + 1 }}단계: {{ s.label }}<span v-if="state(i) === 'done' && s.time" class="text-[11px] font-normal tabular-nums" style="color: var(--text-muted);">{{ s.time }}</span></div>
          <div v-if="state(i) === 'done' && s.detail" class="text-xs mt-0.5" style="color: var(--text-muted);">{{ s.detail }}</div>
          <div v-if="state(i) === 'running' && s.detail" class="text-xs mt-0.5" style="color: var(--text-secondary);">{{ s.detail }}</div>
          <div v-if="state(i) === 'running' && barPercent !== null" class="flex items-center gap-2 mt-1.5">
            <div class="flex-1 h-1.5 rounded-full overflow-hidden" style="background: var(--bg-surface);">
              <div class="h-full rounded-full transition-all duration-1000" :style="{ width: `${Math.min(100, barPercent)}%`, background: 'var(--accent-primary)' }" />
            </div>
            <span class="text-[11px] tabular-nums" style="color: var(--text-muted);">{{ barLabel ?? `${barEstimated ? '~' : ''}${Math.round(Math.min(100, barPercent))}%` }}</span>
          </div>
        </div>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.ring { width: 64px; height: 64px; border-radius: 9999px; background: conic-gradient(var(--accent-primary) var(--pct), var(--bg-surface) 0); display: flex; align-items: center; justify-content: center; }
.ring-inner { width: 50px; height: 50px; border-radius: 9999px; background: var(--bg-elevated); display: flex; align-items: center; justify-content: center; }
.dot-done { background: var(--accent-positive); color: var(--text-on-accent); }
.dot-running { background: var(--accent-primary-soft); border: 1px solid var(--accent-primary); }
.dot-pending { border: 1px solid var(--border-strong); background: var(--bg-elevated); }
.pulse { width: 8px; height: 8px; border-radius: 9999px; background: var(--accent-primary); animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { transform: scale(0.8); opacity: 0.6; } 50% { transform: scale(1.2); opacity: 1; } }
</style>
