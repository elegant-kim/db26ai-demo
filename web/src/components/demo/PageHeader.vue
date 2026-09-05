<script setup lang="ts">
/** 페이지 h1 블록 — 아이콘 + 제목 + 괄호 부제 + 한 줄 설명 (06 문서 §4.1, investhub Invest.vue 패턴). */
import { menuById, type MenuId } from '@/lib/menu'
import { computed } from 'vue'

const props = defineProps<{ menu: MenuId; desc?: string }>()
const m = computed(() => menuById(props.menu))
</script>

<template>
  <div class="flex items-start justify-between gap-3 flex-wrap">
    <div>
      <h1 class="text-2xl font-semibold m-0 flex items-center gap-2" style="color: var(--text-primary);">
        <component :is="m.icon" :size="24" :stroke-width="1.75" />
        {{ m.title }}
        <span class="text-base font-normal" style="color: var(--text-muted);">({{ m.subtitle }})</span>
      </h1>
      <p v-if="desc" class="text-sm mt-1 m-0" style="color: var(--text-muted);">{{ desc }}</p>
    </div>
    <div v-if="$slots.actions" class="shrink-0 flex items-center gap-2"><slot name="actions" /></div>
  </div>
</template>
