<script setup lang="ts">
/**
 * 답변 인라인 피드백 (PoC 1-B, 2026-09-30) — 👍 좋음 / 👎 나쁨 + 사유(선택) + 👎 면 올바른 SQL(접기) + 저장.
 * 저장 = 서버가 DBMS_CLOUD_AI.FEEDBACK(벡터 인덱스) 과 AI_FEEDBACK_LOG 를 한 트랜잭션으로. 등록 후엔 배지(👍 등록됨 · 사유) — 클릭하면 수정(=delete 후 add), 삭제 버튼.
 * 답변 말풍선(Nl2sqlAnswer)과 이력 모달(Nl2sqlHistory)이 같이 쓴다 — 다른 것은 source 뿐.
 */
import { computed, ref, watch } from 'vue'
import { ThumbsUp, ThumbsDown, Trash2, Pencil, ChevronRight, ChevronDown } from 'lucide-vue-next'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import { errorMessage } from '@/lib/api'
import { deleteFeedback, submitFeedback, type FeedbackInfo, type FeedbackType } from '@/lib/nl2sql'
import { useSystemStore } from '@/stores/system'

const props = withDefaults(defineProps<{ logId: number; existing?: FeedbackInfo | null; source?: 'INLINE' | 'HISTORY'; compact?: boolean }>(), { existing: null, source: 'INLINE', compact: false })
const emit = defineEmits<{ saved: [FeedbackInfo]; deleted: [] }>()
const system = useSystemStore()

const editing = ref(!props.existing)
const type = ref<FeedbackType | ''>(props.existing?.type ?? '')
const content = ref(props.existing?.content ?? '')
const corrected = ref(props.existing?.correctedSql ?? '')
const showSql = ref(!!props.existing?.correctedSql)
const busy = ref(false)
const err = ref('')
watch(() => props.existing, (e) => { editing.value = !e; type.value = e?.type ?? ''; content.value = e?.content ?? ''; corrected.value = e?.correctedSql ?? ''; showSql.value = !!e?.correctedSql })
const canSave = computed(() => !!type.value && !busy.value)

async function save() {
  if (!type.value) return
  busy.value = true; err.value = ''
  try {
    const r = await submitFeedback({ log_id: props.logId, feedback_type: type.value, feedback_content: content.value.trim(), corrected_sql: type.value === 'negative' ? corrected.value.trim() : '', source: props.source })
    if (!r.success) { err.value = r.error || '저장 실패'; return }
    const info: FeedbackInfo = { id: r.feedback_id!, type: type.value, content: content.value.trim(), correctedSql: type.value === 'negative' ? corrected.value.trim() : '' }
    system.toast(`${type.value === 'positive' ? '👍' : '👎'} 피드백을 ${r.replaced ? '다시 ' : ''}등록했습니다 (${(r.elapsed_ms! / 1000).toFixed(1)}초)`, 'success')
    editing.value = false; emit('saved', info)
  } catch (e) { err.value = errorMessage(e) } finally { busy.value = false }
}
async function remove() {
  if (!props.existing) return
  busy.value = true; err.value = ''
  try {
    const r = await deleteFeedback(props.existing.id)
    if (!r.success) { err.value = r.error || '삭제 실패'; return }
    system.toast('피드백을 삭제했습니다', 'success'); type.value = ''; content.value = ''; corrected.value = ''; editing.value = true; emit('deleted')
  } catch (e) { err.value = errorMessage(e) } finally { busy.value = false }
}
</script>

<template>
  <div class="rounded-md px-3 py-2 flex flex-col gap-2" style="background: var(--bg-surface); border: 1px dashed var(--border-default);">
    <!-- 등록됨 -->
    <div v-if="existing && !editing" class="flex flex-wrap items-center gap-2 text-xs">
      <Badge :tone="existing.type === 'positive' ? 'positive' : 'negative'">{{ existing.type === 'positive' ? '👍 등록됨' : '👎 등록됨' }}</Badge>
      <span v-if="existing.content" class="truncate max-w-[420px]" style="color: var(--text-secondary);" :title="existing.content">{{ existing.content }}</span>
      <span v-else style="color: var(--text-muted);">사유 없음</span>
      <span v-if="existing.correctedSql" class="font-mono text-[11px]" style="color: var(--text-muted);">· 올바른 SQL 첨부</span>
      <span class="ml-auto flex items-center gap-1">
        <Button size="sm" variant="ghost" :disabled="busy" title="수정 (삭제 후 재등록)" @click="editing = true"><Pencil :size="12" :stroke-width="1.75" /></Button>
        <Button size="sm" variant="ghost" :busy="busy" title="삭제" @click="remove"><Trash2 :size="12" :stroke-width="1.75" /></Button>
      </span>
    </div>
    <!-- 입력 -->
    <template v-else>
      <div class="flex flex-wrap items-center gap-2 text-xs">
        <span style="color: var(--text-secondary);">이 답변 평가:</span>
        <button type="button" class="inline-flex items-center gap-1 px-2 py-1 rounded-md" :style="{ background: type === 'positive' ? 'var(--accent-positive-soft)' : 'transparent', color: type === 'positive' ? 'var(--accent-positive)' : 'var(--text-secondary)', boxShadow: 'inset 0 0 0 1px var(--border-default)' }" @click="type = 'positive'"><ThumbsUp :size="13" :stroke-width="1.75" /> 좋음</button>
        <button type="button" class="inline-flex items-center gap-1 px-2 py-1 rounded-md" :style="{ background: type === 'negative' ? 'var(--accent-negative-soft)' : 'transparent', color: type === 'negative' ? 'var(--accent-negative)' : 'var(--text-secondary)', boxShadow: 'inset 0 0 0 1px var(--border-default)' }" @click="type = 'negative'"><ThumbsDown :size="13" :stroke-width="1.75" /> 나쁨</button>
        <input v-model="content" placeholder="사유 (선택)" class="flex-1 min-w-[180px] rounded-md px-2.5 py-1 text-xs" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" @keydown.enter.prevent="save" />
        <Button size="sm" :busy="busy" :disabled="!canSave" title="DBMS_CLOUD_AI.FEEDBACK + AI_FEEDBACK_LOG (질문의 SELECT AI 문장이 없으면 1회 실행 — 수 초)" @click="save">저장</Button>
        <Button v-if="existing" size="sm" variant="ghost" :disabled="busy" @click="editing = false">취소</Button>
      </div>
      <div v-if="type === 'negative'">
        <button type="button" class="inline-flex items-center gap-1 text-[11px]" style="color: var(--text-muted);" @click="showSql = !showSql"><component :is="showSql ? ChevronDown : ChevronRight" :size="12" :stroke-width="2" /> 올바른 SQL 직접 제시 (선택 — FEEDBACK 의 response 로 전달)</button>
        <textarea v-if="showSql" v-model="corrected" rows="3" placeholder="SELECT …" class="mt-1 w-full rounded-md px-2.5 py-1.5 text-xs font-mono" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" />
      </div>
      <div v-if="err" class="text-xs px-2 py-1.5 rounded" style="background: var(--accent-negative-soft); color: var(--text-primary);"><span class="font-mono break-all">{{ err }}</span> — <RouterLink to="/nl2sql?sub=env" style="color: var(--accent-primary);">환경 탭에서 확인</RouterLink></div>
    </template>
  </div>
</template>
