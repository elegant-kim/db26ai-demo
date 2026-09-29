<script setup lang="ts">
/**
 * 「이력」 서브탭 (PoC 1-C, 2026-09-29) — 모든 Select AI 호출이 AI_QUERY_LOG 에 남는다는 것을 표로.
 * 요약 카드 4 → 필터 → 표(행 클릭 = 상세 모달) → 페이징. 프로필(모델)별 평균 elapsed 는 3-C 의 절반.
 * 피드백 편집(모달 안)은 1-B 의 FeedbackBox 가 들어올 자리 — 지금은 조회만.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { History, Search, RotateCcw, X as XIcon, ThumbsUp, ThumbsDown, Copy, ChevronRight, ChevronDown } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import Stat from '@/components/ui/Stat.vue'
import Pagination from '@/components/ui/Pagination.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import KvGrid from '@/components/demo/KvGrid.vue'
import { fmtDateTime, fmtMs } from '@/lib/format'
import { ACTIONS, shortConv } from '@/lib/nl2sql'
import { FEEDBACK_OPTIONS, STATUS_OPTIONS } from '@/lib/aiLog'
import { useAiLogStore } from '@/stores/aiLog'
import { useNl2sqlStore } from '@/stores/nl2sql'
import { useSystemStore } from '@/stores/system'

const h = useAiLogStore()
const s = useNl2sqlStore()
const system = useSystemStore()
const route = useRoute()
const showSql = ref(false)
onMounted(() => { void s.init(route.query.profile); if (!h.loadedOnce || route.query.run !== undefined) void h.search(); window.addEventListener('keydown', onKey) })
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
function onKey(e: KeyboardEvent) { if (e.key === 'Escape' && h.detail) h.close() }

const profileOptions = computed(() => [{ value: '', label: '프로필 전체' }, ...s.profiles.map((p) => ({ value: p.profile_name, label: p.profile_name }))])
const actionOptions = [{ value: '', label: '액션 전체' }, ...ACTIONS.map((a) => ({ value: a.value, label: a.value }))]
const summaryHint = computed(() => (h.summary?.first_at ? `${fmtDateTime(h.summary.first_at)} 부터` : ''))
async function copy(v: string) { try { await navigator.clipboard.writeText(v); system.toast('복사했습니다', 'success') } catch { system.toast(v, 'info') } }
const detailKv = computed(() => {
  const d = h.detail; if (!d) return {}
  return { 시작: fmtDateTime(d.STARTED_AT), 출처: d.SOURCE, 프로필: d.PROFILE_NAME ?? '—', 모델: d.MODEL ?? '—', 액션: d.ACTION ?? '—', 상태: d.STATUS,
    소요: fmtMs(d.ELAPSED_MS), 행수: d.ROW_COUNT ?? '—', conversation_id: d.CONVERSATION_ID ?? '—', sql_id: d.SQL_ID ?? '—', 실행자: d.CREATED_BY ?? '—' }
})
</script>

<template>
  <div class="flex flex-col gap-4">
    <div v-if="h.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ h.error }}</div>

    <!-- 요약 카드 -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Stat label="총 질의" :value="h.summary ? h.summary.total.toLocaleString() : '—'" :hint="summaryHint" :icon="History" />
      <Stat label="성공률" :value="h.summary?.success_rate != null ? `${h.summary.success_rate}%` : '—'" :hint="h.summary ? `성공 ${h.summary.succeeded} · 실패 ${h.summary.failed}` : ''" :tone="h.summary && h.summary.failed ? 'warm' : 'positive'" />
      <Stat label="평균 / 최대 소요" :value="h.summary ? `${fmtMs(h.summary.avg_ms)} / ${fmtMs(h.summary.max_ms)}` : '—'" hint="성공한 호출만 평균" />
      <Stat label="피드백 비율" :value="h.summary?.feedback_rate != null ? `${h.summary.feedback_rate}%` : '—'" :hint="h.summary ? `👍 ${h.summary.positive} · 👎 ${h.summary.negative}` : ''" />
    </div>

    <!-- 프로필(모델)별 -->
    <Card v-if="h.summary && h.summary.by_profile.length" compact title="프로필(모델)별 소요" subtitle="같은 질문이라도 모델에 따라 시간이 다르다 — 성공한 호출의 평균">
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2 text-sm">
        <div v-for="p in h.summary.by_profile" :key="(p.PROFILE_NAME ?? '') + (p.MODEL ?? '')" class="rounded-md px-3 py-2 flex items-center justify-between gap-3" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
          <div class="min-w-0"><div class="font-medium truncate" style="color: var(--text-primary);">{{ p.PROFILE_NAME ?? '—' }}</div><div class="text-[11px] truncate" style="color: var(--text-muted);">{{ p.MODEL ?? '—' }} · {{ p.N }}건 · 성공 {{ p.SUCCEEDED }}</div></div>
          <div class="text-right shrink-0"><div class="font-mono text-sm" style="color: var(--text-primary);">{{ fmtMs(p.AVG_MS) }}</div><div class="text-[11px]" style="color: var(--text-muted);">최대 {{ fmtMs(p.MAX_MS) }}</div></div>
        </div>
      </div>
    </Card>

    <!-- 필터 + 표 -->
    <Card title="질의 이력" subtitle="모든 Select AI 호출 — 화면의 질문 · 후속 버튼 · SELECT AI 직접 실행이 전부 AI_QUERY_LOG 에 남는다" :icon="History">
      <template #actions><Badge tone="info">{{ h.total.toLocaleString() }}건</Badge></template>
      <form class="flex flex-wrap items-center gap-2 mb-3" @submit.prevent="h.search()">
        <label class="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 flex-1 min-w-[220px]" style="background: var(--bg-elevated); border: 1px solid var(--border-strong);"><Search :size="14" :stroke-width="1.75" style="color: var(--text-muted);" /><input v-model="h.filter.q" placeholder="질문 검색 (대소문자 무시)" class="bg-transparent outline-none text-sm w-full" style="color: var(--text-primary);" /></label>
        <input v-model="h.filter.date_from" type="datetime-local" class="rounded-md px-2 py-1.5 text-sm" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" title="시작일시" />
        <span class="text-xs" style="color: var(--text-muted);">~</span>
        <input v-model="h.filter.date_to" type="datetime-local" class="rounded-md px-2 py-1.5 text-sm" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" title="종료일시" />
        <div class="w-[190px]"><SearchableSelect v-model="h.filter.profile" :options="profileOptions" :searchable="false" placeholder="프로필 전체" /></div>
        <div class="w-[140px]"><SearchableSelect v-model="h.filter.action" :options="actionOptions" :searchable="false" placeholder="액션 전체" /></div>
        <div class="w-[120px]"><SearchableSelect v-model="h.filter.status" :options="STATUS_OPTIONS" :searchable="false" placeholder="상태 전체" /></div>
        <div class="w-[140px]"><SearchableSelect v-model="h.filter.feedback" :options="FEEDBACK_OPTIONS" :searchable="false" placeholder="피드백 전체" /></div>
        <Button type="submit" :busy="h.loading"><Search :size="14" :stroke-width="2" /> 조회</Button>
        <Button variant="ghost" size="sm" title="필터 초기화" @click="h.reset(); h.search()"><RotateCcw :size="14" :stroke-width="1.75" /></Button>
      </form>

      <LoadingBlock v-if="h.loading && !h.rows.length" compact label="이력을 읽는 중…" />
      <EmptyState v-else-if="!h.rows.length" :icon="History" title="이력이 없습니다" desc="「질문」 탭에서 질문하면 여기 한 줄씩 쌓입니다. 필터를 걸었다면 풀어 보세요." compact />
      <div v-else class="rounded-md overflow-auto" style="border: 1px solid var(--border-default);">
        <table class="w-full text-sm" style="border-collapse: collapse;">
          <thead><tr style="background: var(--bg-surface); color: var(--text-muted);">
            <th v-for="c in ['시작시각', '프로필', '액션', '질문', '상태', '소요', '피드백', 'conversation']" :key="c" class="text-left text-[11px] font-semibold px-3 py-2 whitespace-nowrap">{{ c }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in h.rows" :key="r.ID" class="row cursor-pointer" :title="`#${r.ID} 상세 보기`" @click="h.open(r.ID)">
              <td class="px-3 py-2 whitespace-nowrap font-mono text-xs" style="color: var(--text-secondary);">{{ fmtDateTime(r.STARTED_AT) }}</td>
              <td class="px-3 py-2 whitespace-nowrap text-xs" style="color: var(--text-secondary);">{{ r.PROFILE_NAME ?? '—' }}<span v-if="r.SOURCE !== 'GENERATE'" class="ml-1 text-[10px] font-mono" style="color: var(--text-muted);">{{ r.SOURCE }}</span></td>
              <td class="px-3 py-2"><Badge tone="code">{{ r.ACTION ?? '—' }}</Badge></td>
              <td class="px-3 py-2 max-w-[420px] truncate" style="color: var(--text-primary);">{{ r.QUESTION }}</td>
              <td class="px-3 py-2"><Badge :tone="r.STATUS === 'SUCCEEDED' ? 'positive' : 'negative'">{{ r.STATUS }}</Badge></td>
              <td class="px-3 py-2 font-mono text-xs text-right whitespace-nowrap" style="color: var(--text-secondary);">{{ fmtMs(r.ELAPSED_MS) }}</td>
              <td class="px-3 py-2 text-center"><ThumbsUp v-if="r.FEEDBACK_TYPE === 'positive'" :size="14" :stroke-width="1.75" style="color: var(--accent-positive);" /><ThumbsDown v-else-if="r.FEEDBACK_TYPE === 'negative'" :size="14" :stroke-width="1.75" style="color: var(--accent-negative);" /><span v-else style="color: var(--text-muted);">—</span></td>
              <td class="px-3 py-2 whitespace-nowrap"><button v-if="r.CONVERSATION_ID" type="button" class="inline-flex items-center gap-1 font-mono text-[11px]" style="color: var(--text-muted);" :title="`${r.CONVERSATION_ID} — 클릭하면 복사`" @click.stop="copy(r.CONVERSATION_ID!)"><Copy :size="10" :stroke-width="1.75" />{{ shortConv(r.CONVERSATION_ID) }}</button><span v-else class="text-[11px]" style="color: var(--text-muted);">—</span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <Pagination :total="h.total" :page="h.page" :page-size="h.size" class="mt-2" @update:page="(p: number) => h.load(p)" />
      <button v-if="h.sql" type="button" class="mt-2 inline-flex items-center gap-1 text-xs" style="color: var(--text-secondary);" @click="showSql = !showSql"><component :is="showSql ? ChevronDown : ChevronRight" :size="13" :stroke-width="2" /> 조회 SQL</button>
      <SqlBlock v-if="showSql && h.sql" :code="h.sql" label="AI_QUERY_LOG 조회 SQL (바인드 값 대입)" max-height="260px" class="mt-2" />
    </Card>

    <!-- 상세 모달 -->
    <Teleport to="body">
      <div v-if="h.detail || h.detailLoading" class="fixed inset-0 z-[60] flex items-center justify-center p-4" style="background: rgba(0,0,0,0.5);" @click.self="h.close()">
        <div class="w-full max-w-[860px] max-h-[90vh] flex flex-col rounded-md" style="background: var(--bg-elevated); box-shadow: var(--shadow-elevated);" role="dialog" aria-label="이력 상세">
          <header class="flex items-center justify-between px-5 py-3 shrink-0" style="border-bottom: 1px solid var(--border-default);">
            <div class="flex items-center gap-2"><History :size="18" :stroke-width="1.75" style="color: var(--accent-primary);" /><span class="font-semibold" style="color: var(--text-primary);">이력 #{{ h.detail?.ID ?? '' }}</span><Badge v-if="h.detail" :tone="h.detail.STATUS === 'SUCCEEDED' ? 'positive' : 'negative'">{{ h.detail.STATUS }}</Badge></div>
            <button class="p-1.5 rounded-md" style="color: var(--text-secondary);" @click="h.close()"><XIcon :size="18" :stroke-width="1.75" /></button>
          </header>
          <div class="flex-1 overflow-auto p-5 flex flex-col gap-4">
            <LoadingBlock v-if="h.detailLoading" compact label="상세를 읽는 중…" />
            <template v-else-if="h.detail">
              <div class="rounded-xl px-3.5 py-2.5 text-sm whitespace-pre-wrap" style="background: var(--accent-primary); color: var(--text-on-accent);">{{ h.detail.QUESTION }}</div>
              <KvGrid :data="detailKv" />
              <SqlBlock v-if="h.detail.GENERATED_SQL" :code="h.detail.GENERATED_SQL" label="생성된 SQL" badge="Select AI" line-numbers max-height="300px" />
              <div v-if="h.detail.ERROR_MSG" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);"><strong>오류:</strong> <span class="font-mono text-xs break-all whitespace-pre-wrap">{{ h.detail.ERROR_MSG }}</span></div>
              <SqlBlock v-if="h.detail.RESPONSE_TEXT" :code="h.detail.RESPONSE_TEXT" lang="text" label="답변 앞부분 (4000자까지)" max-height="240px" />
              <div class="rounded-md px-3 py-2.5 text-sm" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
                <div class="flex items-center gap-2 mb-1"><span class="font-medium" style="color: var(--text-primary);">피드백</span><Badge>{{ h.detail.feedback.length }}</Badge></div>
                <div v-if="h.detail.feedback.length" class="flex flex-col gap-1.5">
                  <div v-for="f in h.detail.feedback" :key="f.ID" class="flex items-start gap-2 text-xs"><component :is="f.FEEDBACK_TYPE === 'positive' ? ThumbsUp : ThumbsDown" :size="13" :stroke-width="1.75" :style="{ color: f.FEEDBACK_TYPE === 'positive' ? 'var(--accent-positive)' : 'var(--accent-negative)' }" class="mt-0.5 shrink-0" /><div class="min-w-0"><span style="color: var(--text-primary);">{{ f.FEEDBACK_CONTENT || '(사유 없음)' }}</span><span class="ml-2" style="color: var(--text-muted);">{{ fmtDateTime(f.CREATED_AT) }} · {{ f.SOURCE }}</span></div></div>
                </div>
                <p v-else class="text-xs m-0" style="color: var(--text-muted);">아직 피드백이 없습니다. 답변 아래 👍/👎 (1-B) 로 남기면 여기서도 보입니다.</p>
              </div>
            </template>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.row + .row td { border-top: 1px solid var(--border-default); }
.row:hover td { background: var(--bg-surface); }
</style>
