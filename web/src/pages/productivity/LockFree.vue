<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Lock, Play } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import VersusBox from '@/components/demo/VersusBox.vue'
import StepList from '@/components/demo/StepList.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import { useProductivityStore } from '@/stores/productivity'

const p = useProductivityStore()
const route = useRoute()
const steps = computed(() => p.steps.lockfree)
const running = computed(() => p.busy === 'lockfree')
// `?run=1` 이면 mount 직후 한 번 실행한다 — 기능 지도 딥링크·헤드리스 캡처·시연용 (설계서 05 §3.3)
onMounted(() => { if (route.query.run !== undefined && !steps.value) void p.run('lockfree') })
</script>

<template>
  <div class="flex flex-col gap-5">
    <Card title="Lock-Free Column Value Reservations" subtitle="숫자 컬럼에 RESERVABLE 을 붙이면 같은 행·같은 컬럼을 여러 트랜잭션이 동시에 차감·추가할 수 있습니다" :icon="Lock">
      <VersusBox left-title="기존 방식" left-desc="Session A 가 UPDATE → Session B 는 대기(블로킹) → A 커밋 후에야 B 진행."
        right-title="Lock-Free Reservations" right-desc="Session A·B·C 가 동시에 차감. 잔액이 모자랄 때만 CHECK 제약으로 거부된다.">
        기존에는 한 트랜잭션이 행을 잠그면 다른 트랜잭션은 커밋될 때까지 기다려야 했습니다. 예약(reservation) 방식은
        <strong style="color: var(--text-primary);">값의 증감만 기록</strong>해 두고 커밋 시점에 합산하므로, 잠금 없이도 잔액 제약이 지켜집니다.
        <template #footer><code class="font-mono">balance NUMBER RESERVABLE CONSTRAINT min_balance CHECK (balance &gt;= 0)</code></template>
      </VersusBox>
    </Card>

    <Card title="동시 차감 시뮬레이션 (계좌 잔액 500)" subtitle="세 세션이 200 · 100 · 300 을 차례로 차감합니다. A 는 커밋하지 않은 채로 B 가 성공해야 하고, C 는 잔액 부족으로 거부돼야 정상입니다">
      <template #actions>
        <Button v-if="steps && running" variant="ghost" size="sm" @click="p.revealAll('lockfree')">바로 보기</Button>
        <Button :busy="running" :disabled="p.busy !== '' && !running" @click="p.run('lockfree')"><Play :size="14" :stroke-width="2" /> 시뮬레이션 실행</Button>
      </template>
      <div v-if="p.error.lockfree" class="px-3 py-2.5 rounded-md text-sm mb-3" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ p.error.lockfree }}</div>
      <EmptyState v-if="!steps && !running" :icon="Lock" title="[시뮬레이션 실행]을 누르세요" desc="데모 테이블을 만들고 세 세션을 실제로 실행합니다. 끝나면 테이블은 지웁니다 (약 2초)." compact />
      <StepList v-else-if="steps" :steps="steps" :revealed="p.revealed.lockfree" :running="running" fail-label="거부" />
      <StepList v-else :steps="[]" running />
    </Card>
  </div>
</template>
