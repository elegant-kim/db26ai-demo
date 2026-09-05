<script setup lang="ts">
/**
 * 좌우 비교 ★ — 이 앱의 서사 "같은 질문을 두 방식으로" (06 문서 §5.7).
 * 열 헤더(방식 이름·소요·상태) + 슬롯 left/right. 두 결과가 같으면 positive 배너, 다르면 warm 배너.
 */
import { computed } from 'vue'
import Badge from '@/components/ui/Badge.vue'
import { fmtMs, fmtNum } from '@/lib/format'
import { CheckCircle2, AlertTriangle } from 'lucide-vue-next'

interface Side { title: string; elapsedMs?: number | null; error?: string | null; rowCount?: number | null; badge?: string }
interface Props { left: Side; right: Side; equal?: boolean | null; equalText?: string; differentText?: string }
const props = withDefaults(defineProps<Props>(), { equal: null })

const banner = computed(() => {
  if (props.left.error || props.right.error) return { tone: 'negative', text: '한쪽에서 오류가 났습니다 — 아래 상세를 보세요.' }
  if (props.equal === true) return { tone: 'positive', text: props.equalText || `두 결과가 동일합니다 (${fmtNum(props.left.rowCount ?? 0)}행 · ${props.left.title} ${fmtMs(props.left.elapsedMs)} · ${props.right.title} ${fmtMs(props.right.elapsedMs)})` }
  if (props.equal === false) return { tone: 'warm', text: props.differentText || '두 결과가 다릅니다 — 정렬이나 집계 방식을 확인하세요.' }
  return null
})
const bannerStyle = (tone: string) => ({
  background: `var(--accent-${tone}-soft)`, borderLeft: `3px solid var(--accent-${tone})`, color: 'var(--text-primary)',
})
</script>

<template>
  <div class="flex flex-col gap-3">
    <div v-if="banner" class="flex items-center gap-2 px-3 py-2 rounded-md text-sm" :style="bannerStyle(banner.tone)">
      <component :is="banner.tone === 'positive' ? CheckCircle2 : AlertTriangle" :size="16" :stroke-width="1.75" :style="{ color: `var(--accent-${banner.tone})` }" />
      <span>{{ banner.text }}</span>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-3 items-start">
      <div v-for="(side, key) in { left, right }" :key="key" class="flex flex-col gap-2 min-w-0">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2 min-w-0">
            <span class="text-sm font-semibold truncate" style="color: var(--text-primary);">{{ side.title }}</span>
            <Badge v-if="side.badge" tone="primary">{{ side.badge }}</Badge>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <Badge v-if="side.rowCount != null && !side.error" tone="default">{{ fmtNum(side.rowCount) }}행</Badge>
            <Badge v-if="side.elapsedMs != null" tone="code">{{ fmtMs(side.elapsedMs) }}</Badge>
            <Badge v-if="side.error" tone="negative">오류</Badge>
          </div>
        </div>
        <slot :name="key" />
      </div>
    </div>
  </div>
</template>
