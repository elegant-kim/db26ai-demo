<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Zap, Play, Info } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import VersusBox from '@/components/demo/VersusBox.vue'
import StepList from '@/components/demo/StepList.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import { useProductivityStore } from '@/stores/productivity'

const p = useProductivityStore()
const route = useRoute()
const steps = computed(() => p.steps.priority)
const running = computed(() => p.busy === 'priority')
onMounted(() => { if (route.query.run !== undefined && !steps.value) void p.run('priority') })
</script>

<template>
  <div class="flex flex-col gap-5">
    <Card title="Priority Transactions" subtitle="트랜잭션에 HIGH · MEDIUM · LOW 우선순위를 주면, 높은 쪽이 낮은 쪽에 막혔을 때 DB 가 낮은 쪽을 자동으로 롤백합니다" :icon="Zap">
      <VersusBox left-title="기존 방식" left-desc="VIP 든 일반이든 먼저 잠근 쪽이 우선. 중요한 트랜잭션이 하염없이 기다릴 수 있다."
        right-title="Priority Transactions" right-desc="HIGH 가 LOW 에 블로킹되면 대기 시간(PRIORITY_TXNS_HIGH_WAIT_TARGET) 초과 후 LOW 자동 롤백 → HIGH 진행.">
        우선순위는 세션 단위로 선언합니다. 롤백당한 LOW 트랜잭션은 <code class="font-mono">ORA-63300</code> 을 받으므로 애플리케이션은 재시도만 구현하면 됩니다 —
        <strong style="color: var(--text-primary);">DBA 가 개입하지 않아도 비즈니스 우선순위대로 충돌이 풀립니다.</strong>
        <template #footer><code class="font-mono">ALTER SESSION SET TXN_PRIORITY = HIGH | MEDIUM | LOW</code></template>
      </VersusBox>
    </Card>

    <Card title="우선순위 충돌 시뮬레이션" subtitle="LOW 트랜잭션이 주문 행을 잠근 채로 있을 때 HIGH 트랜잭션(VIP 결제)이 같은 행을 요청합니다">
      <template #actions>
        <Button v-if="steps && running" variant="ghost" size="sm" @click="p.revealAll('priority')">바로 보기</Button>
        <Button :busy="running" :disabled="p.busy !== '' && !running" @click="p.run('priority')"><Play :size="14" :stroke-width="2" /> 시뮬레이션 실행</Button>
      </template>
      <div class="flex items-start gap-2 text-xs mb-3" style="color: var(--text-muted);">
        <Info :size="14" :stroke-width="1.75" class="shrink-0 mt-0.5" />
        <span>Autonomous Database 에서는 <code class="font-mono">PRIORITY_TXNS_MODE</code> 를 바꿀 수 없어 1단계(테이블 생성)만 실제 실행이고, 2~6단계는 설정된 환경에서의 동작을 순서대로 설명합니다.</span>
      </div>
      <div v-if="p.error.priority" class="px-3 py-2.5 rounded-md text-sm mb-3" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ p.error.priority }}</div>
      <EmptyState v-if="!steps && !running" :icon="Zap" title="[시뮬레이션 실행]을 누르세요" desc="LOW 가 잠그고 → HIGH 가 요청하고 → DB 가 LOW 를 롤백하는 6단계입니다." compact />
      <StepList v-else-if="steps" :steps="steps" :revealed="p.revealed.priority" :running="running" fail-label="롤백됨" />
      <StepList v-else :steps="[]" running />
    </Card>
  </div>
</template>
