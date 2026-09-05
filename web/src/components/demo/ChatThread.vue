<script setup lang="ts">
/**
 * 대화 스레드 — AWR 후속 질문·NL2SQL·RAG 공통 (설계서 05 §6.5). 사용자 말풍선은 우측 액센트,
 * 어시스턴트 답은 카드 없는 블록(md-body 마크다운). 새 메시지가 오면 바닥으로 스크롤.
 */
import { nextTick, ref, watch } from 'vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import { renderMarkdown } from '@/lib/markdown'
import type { ChatMessage } from '@/lib/types/chat'

const props = withDefaults(defineProps<{ messages: ChatMessage[]; emptyText?: string; maxHeight?: string; minHeight?: string; loadingText?: string }>(),
  { emptyText: '', maxHeight: '460px', minHeight: '0px', loadingText: '답변 생성 중…' })
const box = ref<HTMLElement | null>(null)
watch(() => [props.messages.length, props.messages[props.messages.length - 1]?.loading], async () => {
  await nextTick(); if (box.value) box.value.scrollTop = box.value.scrollHeight
})
</script>

<template>
  <div ref="box" class="overflow-auto flex flex-col gap-3 pr-1" :style="{ maxHeight, minHeight }">
    <p v-if="!messages.length && emptyText" class="text-sm m-0 py-2" style="color: var(--text-muted);">{{ emptyText }}</p>
    <div v-for="(m, i) in messages" :key="i" class="flex" :class="m.role === 'user' ? 'justify-end' : 'justify-start'">
      <slot v-if="m.role === 'user'" name="user" :msg="m">
        <div class="max-w-[80%] rounded-xl px-3.5 py-2 text-sm whitespace-pre-wrap" style="background: var(--accent-primary); color: var(--text-on-accent);">{{ m.content }}</div>
      </slot>
      <slot v-else name="assistant" :msg="m">
        <div class="max-w-[92%] min-w-0">
          <LoadingBlock v-if="m.loading" compact :label="loadingText" />
          <div v-else class="md-body text-sm" :style="{ color: m.error ? 'var(--accent-negative)' : 'var(--text-primary)' }" v-html="renderMarkdown(m.content)" />
          <div v-if="!m.loading && m.elapsedMs" class="text-[11px] mt-1" style="color: var(--text-muted);">{{ (m.elapsedMs / 1000).toFixed(1) }}초</div>
        </div>
      </slot>
    </div>
  </div>
</template>
