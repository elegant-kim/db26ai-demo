<script setup lang="ts">
// 공통 확인 모달 — native confirm() 대체 (investhub 이식). DROP·삭제 전 필수.
import Button from '@/components/ui/Button.vue'
import { AlertTriangle } from 'lucide-vue-next'

interface Props { open: boolean; title: string; confirmLabel?: string; danger?: boolean; busy?: boolean }
const props = withDefaults(defineProps<Props>(), { confirmLabel: '확인', danger: false, busy: false })
const emit = defineEmits<{ confirm: []; cancel: [] }>()
</script>

<template>
  <div v-if="props.open" class="fixed inset-0 z-[60] flex items-center justify-center p-4" style="background: rgba(0, 0, 0, 0.5);" @click.self="emit('cancel')">
    <div class="w-full max-w-sm rounded-md" style="background: var(--bg-elevated); box-shadow: var(--shadow-elevated);" role="alertdialog" :aria-label="props.title">
      <div class="px-5 pt-4 pb-1 flex items-center gap-2">
        <AlertTriangle v-if="props.danger" :size="18" :stroke-width="1.75" style="color: var(--accent-negative);" />
        <h3 class="font-semibold m-0 text-base" style="color: var(--text-primary);">{{ props.title }}</h3>
      </div>
      <div class="px-5 py-3 text-sm" style="color: var(--text-secondary); line-height: 1.6;"><slot /></div>
      <footer class="flex items-center justify-end gap-2 px-5 py-3">
        <Button variant="secondary" :disabled="props.busy" @click="emit('cancel')">취소</Button>
        <Button :variant="props.danger ? 'danger' : 'primary'" :busy="props.busy" @click="emit('confirm')">{{ props.busy ? '처리 중…' : props.confirmLabel }}</Button>
      </footer>
    </div>
  </div>
</template>
