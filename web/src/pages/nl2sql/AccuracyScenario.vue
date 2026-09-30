<script setup lang="ts">
/** 정확도 개선 시나리오 결과 블록 (PoC 2-B·2-C) — 3열 카드(SQL·결과 요약·elapsed) + ②/③ 프롬프트 diff + 복원 안내. 대화 스레드 안의 어시스턴트 메시지로 그린다. */
import { computed, ref } from 'vue'
import { ChevronDown, ChevronRight } from 'lucide-vue-next'
import Badge from '@/components/ui/Badge.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import ResultTable from '@/components/demo/ResultTable.vue'
import DiffBlock from '@/components/demo/DiffBlock.vue'
import { fmtMs } from '@/lib/format'
import type { ScenarioState } from '@/stores/nl2sql'

const props = defineProps<{ sc: ScenarioState }>()
const showPrompt = ref(false)
const steps = computed(() => [1, 2, 3].map((n) => ({ n, meta: props.sc.meta.find((m) => m.n === n), r: props.sc.steps[n] })))
const p2 = computed(() => props.sc.steps[2]?.prompt ?? '')
const p3 = computed(() => props.sc.steps[3]?.prompt ?? '')
</script>

<template>
  <div class="flex flex-col gap-3 w-full">
    <div class="text-xs" style="color: var(--text-secondary);">
      같은 질문 <b style="color: var(--text-primary);">「{{ sc.question }}」</b> 을 세 조건으로 풉니다. 프로필 속성 <code class="font-mono">annotations</code>·<code class="font-mono">comments</code> 를 <code class="font-mono">SET_ATTRIBUTE</code> 로 잠시 끄고 켜며(테이블 DDL 은 건드리지 않음), 끝나면 원래 값으로 되돌립니다.
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-3 items-start">
      <div v-for="s in steps" :key="s.n" class="rounded-md p-3 flex flex-col gap-2 min-w-0" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0"><div class="font-semibold text-sm" style="color: var(--text-primary);">{{ s.meta?.title ?? `단계 ${s.n}` }}</div><div class="text-[11px]" style="color: var(--text-muted);">{{ s.meta?.desc }}</div></div>
          <Badge v-if="s.r?.status === 'done' && s.r.elapsed_ms != null" tone="code">{{ fmtMs(s.r.elapsed_ms) }}</Badge>
        </div>
        <LoadingBlock v-if="!s.r || s.r.status === 'running'" compact :label="s.r?.note || (s.r ? '풀이 중…' : '대기')" />
        <template v-else>
          <div v-if="s.r.error" class="text-xs px-2 py-1.5 rounded" style="background: var(--accent-negative-soft); color: var(--text-primary);"><span class="font-mono break-all">{{ s.r.error }}</span></div>
          <SqlBlock v-if="s.r.sql" :code="s.r.sql" label="생성된 SQL" max-height="220px" />
          <div v-if="s.r.run_error" class="text-[11px] px-2 py-1.5 rounded font-mono break-all" style="background: var(--accent-warm-soft); color: var(--text-primary);">실행 오류: {{ s.r.run_error }}</div>
          <template v-else-if="s.r.rows">
            <div class="text-[11px]" style="color: var(--text-muted);">결과 {{ s.r.row_count ?? s.r.rows.rows.length }}행 — 앞 {{ s.r.rows.rows.length }}행</div>
            <ResultTable :rows="s.r.rows" dense hide-footer max-height="180px" empty-text="결과 행이 없습니다." />
          </template>
          <div v-if="s.n === 3 && s.r.feedback_id" class="text-[11px]" style="color: var(--text-muted);">피드백 #{{ s.r.feedback_id }} 등록 후 다시 물었습니다</div>
        </template>
      </div>
    </div>

    <div v-if="sc.done" class="flex flex-wrap items-center gap-2 text-xs px-3 py-2 rounded-md" :style="{ background: sc.done.same_2_3 ? 'var(--accent-positive-soft)' : 'var(--accent-info-soft)', color: 'var(--text-primary)' }">
      <span v-if="sc.done.same_2_3">③ 이 ②의 SQL 을 <b>그대로</b> 돌려줬습니다 — 프롬프트에 주입된 예시를 LLM 이 따른 것입니다.</span>
      <span v-else>③ 의 SQL 이 ②와 다릅니다 — 예시는 주입됐지만 LLM 이 다르게 썼습니다(아래 diff 로 주입은 확인).</span>
      <span class="ml-auto" style="color: var(--text-muted);">총 {{ fmtMs(sc.done.elapsed_ms) }} · 피드백 {{ sc.done.feedback_kept ? `#${sc.done.feedback_id} 유지` : '삭제(원상복구)' }} · 속성 복원 {{ Object.entries(sc.done.restored).map(([k, v]) => `${k}=${v}`).join(', ') }}</span>
    </div>

    <template v-if="p2 && p3">
      <button type="button" class="inline-flex items-center gap-1 text-xs self-start" style="color: var(--text-secondary);" @click="showPrompt = !showPrompt"><component :is="showPrompt ? ChevronDown : ChevronRight" :size="13" :stroke-width="2" /> 프롬프트 diff — ② 피드백 전 vs ③ 피드백 후 (showprompt)</button>
      <DiffBlock v-if="showPrompt" :before="p2" :after="p3" label="showprompt ② → ③ : 초록 줄이 피드백으로 주입된 예시" max-height="420px" />
    </template>
    <div v-if="sc.error" class="text-xs px-3 py-2 rounded-md" style="background: var(--accent-negative-soft); color: var(--text-primary);">{{ sc.error }}</div>
  </div>
</template>
