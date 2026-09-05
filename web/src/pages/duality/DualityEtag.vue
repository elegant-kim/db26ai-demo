<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ShieldCheck, Play } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import VersusBox from '@/components/demo/VersusBox.vue'
import StepList from '@/components/demo/StepList.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import { useDualityStore } from '@/stores/duality'

const d = useDualityStore()
const route = useRoute()
const running = computed(() => d.busy === 'etag')
onMounted(() => { void d.loadViews().then(() => { if (route.query.run !== undefined && !d.etagSteps && d.hasViews) void d.runEtag() }) })
</script>

<template>
  <div class="flex flex-col gap-5">
    <Card title="ETag 기반 동시성 제어 (낙관적 잠금)" subtitle="모든 문서에 _metadata.etag(버전 해시)가 자동으로 실립니다. 수정할 때 문서에 든 ETag 가 현재와 다르면 DB 가 ORA-42699 로 거부합니다" :icon="ShieldCheck">
      <VersusBox left-title="MongoDB (앱에서 직접 구현)" left-desc="ETag 를 DB 가 주지 않는다. 개발자가 version 필드를 만들고 앱 코드에서 조건부 업데이트를 직접 구현해야 한다."
        right-title="Oracle Duality View (DB 가 자동 관리)" right-desc="DB 가 ETag 를 생성·비교·갱신한다. 문서를 그대로 PUT/UPDATE 하면 충돌을 DB 가 잡는다. @nocheck 로 특정 필드는 제외할 수 있다.">
        락(Lock) 을 잡지 않고도 동시 수정 충돌을 감지합니다 — 두 사용자가 같은 문서를 읽고, 한쪽이 먼저 저장하면 다른 쪽의 저장은 <strong style="color: var(--text-primary);">옛 ETag 라서 거부</strong>됩니다 (Lost Update 방지).
        <template #footer>동작 순서: A 조회(ETag E1) → B 조회(E1) → A 수정 성공(새 ETag E2) → <strong style="color: var(--accent-negative);">B 수정 시도 → E1 ≠ E2 → ORA-42699 거부</strong></template>
      </VersusBox>
    </Card>

    <Card title="ETag 충돌 시뮬레이션" subtitle="CUSTOMERS_DV 의 첫 문서로 두 사용자가 동시에 수정하는 상황을 실제 UPDATE 로 재현합니다. 끝나면 원본으로 되돌립니다">
      <template #actions>
        <Button v-if="d.etagSteps && running" variant="ghost" size="sm" @click="d.revealEtag()">바로 보기</Button>
        <Button :busy="running" :disabled="!d.hasViews || (d.busy !== '' && !running)" @click="d.runEtag()"><Play :size="14" :stroke-width="2" /> 시뮬레이션 실행</Button>
      </template>
      <div v-if="d.etagError" class="px-3 py-2.5 rounded-md text-sm mb-3" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);"><span class="font-mono text-xs break-all">{{ d.etagError }}</span></div>
      <EmptyState v-if="d.viewsLoaded && !d.hasViews" :icon="ShieldCheck" title="Duality View 가 아직 없습니다" desc="「뷰 관리」에서 먼저 생성하세요." compact />
      <EmptyState v-else-if="!d.etagSteps && !running" :icon="ShieldCheck" title="[시뮬레이션 실행]을 누르세요" desc="5단계 — 4단계에서 DB 가 직접 ORA-42699 로 거부하는 것을 봅니다." compact />
      <StepList v-else-if="d.etagSteps" :steps="d.etagSteps" :revealed="d.etagRevealed" :running="running" fail-label="거부" />
      <StepList v-else :steps="[]" running />
    </Card>
  </div>
</template>
