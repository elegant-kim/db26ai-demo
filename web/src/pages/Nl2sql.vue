<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { MessageSquareText, Settings2, Table2, type LucideIcon } from 'lucide-vue-next'
import PageHeader from '@/components/demo/PageHeader.vue'
import SubTabs from '@/components/demo/SubTabs.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import { useSubTab } from '@/composables/useSubTab'
import { useNl2sqlStore } from '@/stores/nl2sql'
import Nl2sqlEnv from './nl2sql/Nl2sqlEnv.vue'
import Nl2sqlAsk from './nl2sql/Nl2sqlAsk.vue'
import Nl2sqlSchema from './nl2sql/Nl2sqlSchema.vue'

/**
 * 서브탭 순서 = 시연 순서 (2026-09-07 재설계, 사용자 확정): 환경(세팅을 보여준다) → 질문(주인공) → 스키마·Annotation(심화).
 * 프로필은 페이지 공통 — 헤더 우측 셀렉트 하나를 세 서브탭이 같이 본다.
 */
type TabId = 'env' | 'ask' | 'schema'
const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: 'env', label: '환경', icon: Settings2 },
  { id: 'ask', label: '질문', icon: MessageSquareText },
  { id: 'schema', label: '스키마 · Annotation', icon: Table2 },
]
const { sub, set } = useSubTab<TabId>(['env', 'ask', 'schema'], 'env')
const s = useNl2sqlStore()
const route = useRoute()
onMounted(() => { void s.init(route.query.profile) })
</script>

<template>
  <div class="flex flex-col gap-5">
    <PageHeader menu="nl2sql" desc="먼저 「환경」에서 프로필 · 크리덴셜 · 네트워크 ACL 이 맞아 있는지 보고, 「질문」에서 같은 질문을 7가지 모드로 풀어 봅니다.">
      <template #actions>
        <span class="text-xs" style="color: var(--text-muted);">AI 프로필</span>
        <div class="w-[260px]"><SearchableSelect :model-value="s.profile" :options="s.profileOptions" placeholder="AI 프로필" :searchable="false" @update:model-value="(v: string) => s.selectProfile(v)" /></div>
      </template>
    </PageHeader>
    <SubTabs :tabs="TABS" :model-value="sub" @update:model-value="(v: string) => set(v as TabId)" />
    <KeepAlive>
      <Nl2sqlEnv v-if="sub === 'env'" />
      <Nl2sqlAsk v-else-if="sub === 'ask'" />
      <Nl2sqlSchema v-else />
    </KeepAlive>
  </div>
</template>
