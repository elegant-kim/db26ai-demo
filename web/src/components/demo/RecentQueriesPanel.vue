<script setup lang="ts">
/**
 * "실행 쿼리 확인" — 모든 탭 공통 (설계서 05 §3.2 ⑤). 페이지 우상단 보조 버튼 → 슬라이드 패널.
 * V$SQL 에서 방금 화면 뒤에서 돈 SQL 원문을 보여준다 — "진짜 SQL 로 도는구나"를 확인시키는 지점.
 */
import { ref } from 'vue'
import { ScrollText, X as XIcon } from 'lucide-vue-next'
import Button from '@/components/ui/Button.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import SqlBlock from './SqlBlock.vue'
import ResultTable from './ResultTable.vue'
import { api, errorMessage } from '@/lib/api'
import { fromColumnsData, type Rows } from '@/lib/normalize'

const props = withDefaults(defineProps<{ endpoint: string; title?: string; hint?: string }>(), { title: '실행 쿼리 확인', hint: 'V$SQL 최근 10건' })

const open = ref(false)
const loading = ref(false)
const rows = ref<Rows | null>(null)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try { rows.value = fromColumnsData((await api.get(props.endpoint)).data) }
  catch (e) { error.value = errorMessage(e) }
  finally { loading.value = false }
}
function show() { open.value = true; if (!rows.value) void load() }
</script>

<template>
  <Button variant="secondary" size="sm" :title="hint" @click="show"><ScrollText :size="14" :stroke-width="1.75" /> {{ title }}</Button>

  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-[55]" style="background: rgba(0,0,0,0.35);" @click.self="open = false">
      <aside class="absolute right-0 top-0 bottom-0 w-full max-w-[880px] flex flex-col" style="background: var(--bg-base); box-shadow: var(--shadow-elevated);">
        <header class="flex items-center justify-between px-5 shrink-0" style="height: 56px; border-bottom: 1px solid var(--border-default);">
          <div class="flex items-center gap-2">
            <ScrollText :size="18" :stroke-width="1.75" style="color: var(--accent-primary);" />
            <span class="font-semibold text-base" style="color: var(--text-primary);">{{ title }}</span>
            <span class="text-xs" style="color: var(--text-muted);">{{ hint }}</span>
          </div>
          <div class="flex items-center gap-2">
            <Button variant="secondary" size="sm" :busy="loading" @click="load">새로고침</Button>
            <button class="p-1.5 rounded-md" style="color: var(--text-secondary);" @click="open = false"><XIcon :size="18" :stroke-width="1.75" /></button>
          </div>
        </header>
        <div class="flex-1 overflow-auto p-5 flex flex-col gap-4">
          <LoadingBlock v-if="loading && !rows" compact hint="V$SQL 을 읽고 있습니다" />
          <div v-else-if="error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ error }}</div>
          <template v-else-if="rows">
            <SqlBlock :code="rows.sql" label="V$SQL 조회 SQL" max-height="200px" />
            <ResultTable :rows="rows" max-height="calc(100vh - 380px)" empty-text="최근 실행된 관련 쿼리가 없습니다." />
          </template>
        </div>
      </aside>
    </div>
  </Teleport>
</template>
