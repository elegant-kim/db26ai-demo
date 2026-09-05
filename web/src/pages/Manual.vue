<script setup lang="ts">
import { Map as MapIcon, BookOpen, Activity, type LucideIcon } from 'lucide-vue-next'
import PageHeader from '@/components/demo/PageHeader.vue'
import SubTabs from '@/components/demo/SubTabs.vue'
import { useSubTab } from '@/composables/useSubTab'
import FeatureMap from './manual/FeatureMap.vue'
import ManualDocs from './manual/ManualDocs.vue'

type TabId = 'features' | 'guide' | 'status'
const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: 'features', label: '기능 지도', icon: MapIcon },
  { id: 'guide', label: '사용 설명서', icon: BookOpen },
  { id: 'status', label: '현재 상태 · 계획', icon: Activity },
]
const { sub, set } = useSubTab<TabId>(['features', 'guide', 'status'], 'features')
</script>

<template>
  <div class="flex flex-col gap-5">
    <PageHeader menu="manual" desc="소스 폴더를 뒤지지 않아도 이 화면에서 기능의 위치와 사용법, 지금 상태와 계획을 읽을 수 있습니다. 문서는 docs/ 의 마크다운을 그대로 보여줍니다." />
    <SubTabs :tabs="TABS" :model-value="sub" @update:model-value="(v: string) => set(v as TabId)" />
    <KeepAlive>
      <FeatureMap v-if="sub === 'features'" />
      <ManualDocs v-else-if="sub === 'guide'" kind="guides" key="guides" />
      <ManualDocs v-else kind="docs" key="docs" />
    </KeepAlive>
  </div>
</template>
