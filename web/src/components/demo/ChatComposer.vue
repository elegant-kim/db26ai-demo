<script setup lang="ts">
/**
 * 입력줄 — Enter 로 전송. 위에 슬롯(프로필·모드 세그먼트 등)을 둘 수 있다.
 * NL2SQL 은 자연어 줄과 SQL 직접 실행 줄이 **같은 부품**을 써서 높이·글자 크기·버튼 크기가 같다(2026-09-07).
 * 차이는 성격을 말하는 것만: 앞 아이콘(말풍선 vs `>_`), mono 글꼴, 버튼 변형(primary 질문 vs secondary 실행).
 */
import { SendHorizontal, type LucideIcon } from 'lucide-vue-next'
import Button from '@/components/ui/Button.vue'

const props = withDefaults(defineProps<{
  modelValue: string; placeholder?: string; busy?: boolean; disabled?: boolean; sendLabel?: string
  icon?: LucideIcon; sendIcon?: LucideIcon; mono?: boolean; sendVariant?: 'primary' | 'secondary'
}>(), { placeholder: '질문을 입력하세요…', busy: false, disabled: false, sendLabel: '질문', mono: false, sendVariant: 'primary' })
const emit = defineEmits<{ 'update:modelValue': [string]; send: [] }>()
function submit() { if (!props.busy && !props.disabled && props.modelValue.trim()) emit('send') }
</script>

<template>
  <div class="flex flex-col gap-2">
    <slot />
    <div class="flex items-center gap-2">
      <div class="relative flex-1 min-w-0">
        <component v-if="icon" :is="icon" :size="15" :stroke-width="1.75" class="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style="color: var(--text-muted);" />
        <input :value="modelValue" :placeholder="placeholder" :disabled="disabled || busy" class="w-full min-w-0 rounded-md py-2 pr-3 text-sm"
          :class="[icon ? 'pl-9' : 'pl-3', mono ? 'font-mono' : '']"
          style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);"
          @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)" @keydown.enter.prevent="submit" />
      </div>
      <Button :variant="sendVariant" :busy="busy" :disabled="disabled || !modelValue.trim()" @click="submit"><component :is="sendIcon || SendHorizontal" :size="14" :stroke-width="2" /> {{ sendLabel }}</Button>
    </div>
  </div>
</template>
