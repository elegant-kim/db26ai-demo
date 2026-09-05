<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { FileJson, Search, ListOrdered, Save } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import { useDualityStore } from '@/stores/duality'

const d = useDualityStore()
onMounted(() => { void d.loadViews() })
const etag = computed(() => d.doc?.etag ?? null)
</script>

<template>
  <div class="flex flex-col gap-5">
    <Card title="JSON 문서 CRUD" subtitle="Duality View 로 문서를 읽고, 고쳐서 저장하면 원본 관계형 테이블이 바뀝니다. 저장은 문서에 실린 ETag 가 현재와 같을 때만 통과합니다" :icon="FileJson">
      <div class="flex flex-wrap items-center gap-2">
        <div class="w-[240px]"><SearchableSelect v-model="d.crudView" :options="d.viewOptions" placeholder="뷰 선택" :searchable="false" /></div>
        <input v-model="d.docId" placeholder="문서 ID (_id)" class="w-36 rounded-md px-2.5 py-1.5 text-sm" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" @keydown.enter="d.fetchDoc()" />
        <Button :busy="d.busy === 'doc'" :disabled="!d.hasViews || !d.docId.trim()" @click="d.fetchDoc()"><Search :size="14" :stroke-width="2" /> 조회</Button>
        <Button variant="secondary" :busy="d.busy === 'docs'" :disabled="!d.hasViews" @click="d.listDocs()"><ListOrdered :size="14" :stroke-width="2" /> 문서 목록</Button>
      </div>
      <div v-if="d.lastError" class="px-3 py-2.5 rounded-md text-sm mt-3" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ d.lastError }}</div>
      <EmptyState v-if="d.viewsLoaded && !d.hasViews" class="mt-3" :icon="FileJson" title="Duality View 가 아직 없습니다" desc="「뷰 관리」에서 먼저 생성하세요." compact />

      <div v-if="d.docList.length" class="mt-4">
        <div class="text-xs font-medium mb-1.5" style="color: var(--text-muted);">문서 목록 (앞 10건 · 클릭하면 조회)</div>
        <div class="rounded-md overflow-hidden" style="border: 1px solid var(--border-default);">
          <button v-for="doc in d.docList" :key="doc.id" class="doc-row w-full flex items-center gap-3 px-3 py-2 text-left text-sm"
            :style="{ background: doc.id === d.docId ? 'var(--accent-primary-soft)' : 'var(--bg-elevated)' }" @click="d.fetchDoc(doc.id)">
            <span class="font-mono text-xs w-16 shrink-0" style="color: var(--text-secondary);">{{ doc.id }}</span>
            <span class="flex-1 truncate" style="color: var(--text-primary);">{{ doc.summary }}</span>
            <span class="text-xs" style="color: var(--accent-primary);">조회</span>
          </button>
        </div>
      </div>
    </Card>

    <Card v-if="d.doc && d.doc.document" title="JSON 문서 편집" :subtitle="`${d.crudView} · _id ${d.doc.document._id}`">
      <template #actions>
        <Badge v-if="etag" tone="code">ETag {{ etag }}</Badge>
        <Button :busy="d.busy === 'update'" @click="d.saveDoc()"><Save :size="14" :stroke-width="2" /> 저장 (UPDATE)</Button>
      </template>
      <textarea v-model="d.docText" spellcheck="false" class="w-full rounded-md p-3 font-mono text-xs leading-relaxed resize-y" style="min-height: 320px; background: var(--code-bg); color: #e6e1dc; border: 1px solid var(--border-default);"></textarea>
      <div v-if="d.updateResult" class="mt-3 px-3 py-2.5 rounded-md text-sm" :style="{ background: d.updateResult.success ? 'var(--accent-positive-soft)' : 'var(--accent-negative-soft)', borderLeft: `3px solid ${d.updateResult.success ? 'var(--accent-positive)' : 'var(--accent-negative)'}`, color: 'var(--text-primary)' }">
        {{ d.updateResult.success ? d.updateResult.message : d.updateResult.error }}
        <span v-if="d.updateResult.success && d.updateResult.new_etag" class="ml-2 font-mono text-xs" style="color: var(--text-secondary);">새 ETag {{ d.updateResult.new_etag }}</span>
      </div>
      <div class="mt-3 flex flex-col gap-2">
        <SqlBlock v-if="d.updateResult?.sql_executed" :code="d.updateResult.sql_executed" label="UPDATE" max-height="140px" />
        <SqlBlock v-else-if="d.doc.sql_executed" :code="d.doc.sql_executed" label="조회 SQL" max-height="140px" />
      </div>
      <p class="text-xs mt-3 mb-0" style="color: var(--text-muted);">예: creditLimit 을 바꿔 저장하면 admin.customers.cust_credit_limit 이 바뀝니다. _metadata.etag 를 옛 값으로 두고 저장하면 ETag 불일치로 거부됩니다.</p>
    </Card>
  </div>
</template>

<style scoped>
.doc-row + .doc-row { border-top: 1px solid var(--border-default); }
.doc-row:hover { background: var(--bg-surface) !important; }
</style>
