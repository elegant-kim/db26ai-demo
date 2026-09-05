<script setup lang="ts">
/**
 * 로딩 표시 공용 블록 (investhub 이식). 핵심은 시간 경과 안내다:
 *   0~4초  스피너 + 기본 문구 / 4초~ + (N초) + hint / 20초~ "예상보다 오래 걸립니다"
 * db26ai 표준 hint 예: "LLM 이 답변을 생성하고 있습니다(2~4초)", "재기동 직후에는 임베딩 모델 예열로 첫 질의가 5초 걸립니다"
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Loader2 } from 'lucide-vue-next'

const props = withDefaults(defineProps<{ label?: string; hint?: string; compact?: boolean }>(), { label: '불러오는 중…', compact: false })

const elapsed = ref(0)
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => { timer = setInterval(() => { elapsed.value += 1 }, 1000) })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })

const slow = computed(() => elapsed.value >= 4)
const tooSlow = computed(() => elapsed.value >= 20)
const text = computed(() => (tooSlow.value ? '예상보다 오래 걸립니다' : props.label))
</script>

<template>
  <div class="flex flex-col items-center justify-center text-center gap-1.5" :class="compact ? 'py-5' : 'py-10'">
    <Loader2 :size="compact ? 18 : 22" class="animate-spin" :style="{ color: tooSlow ? 'var(--accent-warm)' : 'var(--accent-primary)' }" />
    <div class="text-sm" :style="{ color: tooSlow ? 'var(--accent-warm)' : 'var(--text-secondary)' }">
      {{ text }} <span v-if="slow" class="tabular-nums" style="color: var(--text-muted);">({{ elapsed }}초)</span>
    </div>
    <p v-if="slow && hint" class="text-xs m-0 max-w-md" style="color: var(--text-muted); line-height: 1.5;">{{ hint }}</p>
    <p v-if="tooSlow" class="text-xs m-0 max-w-md" style="color: var(--text-muted); line-height: 1.5;">화면은 멈추지 않았습니다 — 계속 기다리거나, 그대로면 새로고침해 보세요.</p>
  </div>
</template>
