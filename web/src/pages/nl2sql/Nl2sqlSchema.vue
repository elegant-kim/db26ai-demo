<script setup lang="ts">
import { onMounted } from 'vue'
import { Table2, ChevronRight, ChevronDown, Tags, Eraser } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import { fmtNum } from '@/lib/format'
import { useNl2sqlStore } from '@/stores/nl2sql'

const s = useNl2sqlStore()
onMounted(() => { void s.init().then(() => { if (!s.schema && !s.schemaLoading && s.profile) void s.loadSchema() }) })
</script>

<template>
  <Card title="참조 테이블 · Display Annotation" :subtitle="`프로필 ${s.profile || '—'} 의 object_list — 테이블·컬럼에 붙인 Annotation 이 Select AI 프롬프트에 들어가 정확도를 올립니다`" :icon="Table2">
    <template #actions>
      <Button v-if="s.hasAnnotationSet" size="sm" :busy="s.annoBusy === 'apply'" :disabled="s.annoBusy !== '' && s.annoBusy !== 'apply'" @click="s.annotate('apply')"><Tags :size="14" :stroke-width="1.75" /> Annotation 적용</Button>
      <Button v-if="s.hasAnnotationSet" size="sm" variant="secondary" :busy="s.annoBusy === 'remove'" :disabled="s.annoBusy !== '' && s.annoBusy !== 'remove'" @click="s.annotate('remove')"><Eraser :size="14" :stroke-width="1.75" /> 제거</Button>
      <Button size="sm" variant="ghost" :busy="s.schemaLoading" @click="s.loadSchema()">새로고침</Button>
    </template>
    <LoadingBlock v-if="s.schemaLoading" compact label="스키마를 읽는 중…" />
    <EmptyState v-else-if="!s.schema || !s.schema.length" :icon="Table2" title="참조 테이블이 없습니다" desc="프로필의 object_list 가 비었거나 프로필이 선택되지 않았습니다." compact />
    <div v-else class="flex flex-col gap-1.5">
      <div v-for="t in s.schema" :key="t.table_name" class="rounded-md overflow-hidden" style="border: 1px solid var(--border-default);">
        <button class="w-full flex items-center gap-2 px-3 py-2 text-left" style="background: var(--bg-surface);" @click="s.toggleTable(t.table_name)">
          <component :is="s.expanded[t.table_name] ? ChevronDown : ChevronRight" :size="14" :stroke-width="2" style="color: var(--text-muted);" />
          <span class="font-mono text-sm font-semibold" style="color: var(--text-primary);">{{ t.owner }}.{{ t.table_name }}</span>
          <span class="text-xs" style="color: var(--text-muted);">{{ t.column_count }}컬럼<template v-if="t.num_rows != null"> · {{ fmtNum(t.num_rows) }}행</template></span>
          <Badge v-if="t.annotation" tone="info" class="ml-1 truncate max-w-[50%]">{{ t.annotation }}</Badge>
          <span v-if="t.error" class="text-xs ml-auto" style="color: var(--accent-negative);">{{ t.error }}</span>
        </button>
        <div v-if="s.expanded[t.table_name]" class="px-3 py-2 grid grid-cols-1 lg:grid-cols-2 gap-x-6" style="background: var(--bg-elevated);">
          <div v-for="c in t.columns" :key="c.column_name" class="col flex items-baseline gap-2 py-1 text-xs">
            <span class="font-mono w-44 shrink-0 truncate" style="color: var(--text-primary);">{{ c.column_name }}</span>
            <span class="font-mono w-28 shrink-0" style="color: var(--text-muted);">{{ c.data_type }}</span>
            <span class="min-w-0 truncate" :style="{ color: c.annotation ? 'var(--accent-info)' : 'var(--text-muted)' }">{{ c.annotation || '—' }}</span>
          </div>
        </div>
      </div>
    </div>
  </Card>
</template>

<style scoped>
.col + .col { border-top: 1px dashed var(--border-default); }
</style>
