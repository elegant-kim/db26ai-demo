<script setup lang="ts">
/**
 * "기존 방식 vs 26ai" 두 칸 비교 상자 — 각 탭 첫 화면의 차별성 설명 (graph 관리·lockfree·priority·duality·vector 공통).
 * 기본 슬롯 = 도입 문단, right 슬롯 = 오른쪽 설명(강조 태그가 필요할 때), footer 슬롯 = 보조 한 줄.
 */
defineProps<{ leftTitle: string; leftDesc: string; rightTitle: string; rightDesc?: string }>()
</script>

<template>
  <div>
    <p v-if="$slots.default" class="text-sm m-0 mb-3" style="color: var(--text-secondary); line-height: 1.7;"><slot /></p>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <div class="rounded-md px-3.5 py-3" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
        <div class="text-sm font-semibold mb-1" style="color: var(--text-primary);">{{ leftTitle }}</div>
        <div class="text-xs" style="color: var(--text-secondary); line-height: 1.6;">{{ leftDesc }}</div>
      </div>
      <div class="rounded-md px-3.5 py-3" style="background: var(--accent-primary-soft); border: 1px solid var(--accent-primary);">
        <div class="text-sm font-semibold mb-1" style="color: var(--accent-primary);">{{ rightTitle }}</div>
        <div class="text-xs" style="color: var(--text-secondary); line-height: 1.6;"><slot name="right">{{ rightDesc }}</slot></div>
      </div>
    </div>
    <div v-if="$slots.footer" class="mt-3 text-xs" style="color: var(--text-muted);"><slot name="footer" /></div>
  </div>
</template>
