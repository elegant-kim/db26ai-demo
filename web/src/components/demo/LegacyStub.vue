<script setup lang="ts">
/** 이식 전 페이지의 자리표시자 — /legacy#tab 으로 안내한다. 탭이 이식되면 이 컴포넌트를 쓰지 않게 된다. */
import { computed } from 'vue'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import PageHeader from './PageHeader.vue'
import { menuById, legacyUrl, type MenuId } from '@/lib/menu'
import { ExternalLink } from 'lucide-vue-next'

const props = defineProps<{ menu: MenuId }>()
const m = computed(() => menuById(props.menu))
</script>

<template>
  <div class="flex flex-col gap-5">
    <PageHeader :menu="menu" desc="이 화면은 아직 새 구조로 옮기기 전입니다." />
    <Card title="기존 화면에서 계속 사용하세요" :icon="ExternalLink">
      <p class="text-sm m-0 mb-3" style="color: var(--text-secondary); line-height: 1.6;">
        SPA 이식은 탭 단위로 진행됩니다(설계서 <code>docs/design/05</code>). 이 탭은 이식되면 여기서 바로 열립니다.
      </p>
      <a :href="legacyUrl(m)"><Button>{{ m.title }} 기존 화면 열기 →</Button></a>
    </Card>
  </div>
</template>
