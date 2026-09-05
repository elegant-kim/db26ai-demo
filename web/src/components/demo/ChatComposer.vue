<script setup lang="ts">
/** 질문 입력줄 — Enter 로 전송. 위에 슬롯(프로필·모드 세그먼트 등)을 둘 수 있다. */
import { SendHorizontal } from 'lucide-vue-next'
import Button from '@/components/ui/Button.vue'

const props = withDefaults(defineProps<{ modelValue: string; placeholder?: string; busy?: boolean; disabled?: boolean; sendLabel?: string }>(),
  { placeholder: '질문을 입력하세요…', busy: false, disabled: false, sendLabel: '질문' })
const emit = defineEmits<{ 'update:modelValue': [string]; send: [] }>()
function submit() { if (!props.busy && !props.disabled && props.modelValue.trim()) emit('send') }
</script>

<template>
  <div class="flex flex-col gap-2">
    <slot />
    <div class="flex items-center gap-2">
      <input :value="modelValue" :placeholder="placeholder" :disabled="disabled || busy" class="flex-1 min-w-0 rounded-md px-3 py-2 text-sm"
        style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);"
        @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)" @keydown.enter.prevent="submit" />
      <Button :busy="busy" :disabled="disabled || !modelValue.trim()" @click="submit"><SendHorizontal :size="14" :stroke-width="2" /> {{ sendLabel }}</Button>
    </div>
  </div>
</template>
