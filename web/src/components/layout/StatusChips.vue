<script setup lang="ts">
/**
 * 헤더 상태 칩 — 레거시 사이드바 "시스템 상태"의 새 자리 (설계서 05 §3.2 ④, 06 §5.14).
 * investhub MarketStatusBar 의 KR/NY 칩과 같은 위치·크기. 호버하면 /api/health 스냅샷 전체.
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSystemStore } from '@/stores/system'
import { menuById } from '@/lib/menu'
import { fmtNum } from '@/lib/format'

const system = useSystemStore()
const router = useRouter()
const hovered = ref(false)

const dbColor = computed(() => system.health ? (system.dbOk ? 'var(--accent-positive)' : 'var(--accent-negative)') : 'var(--text-muted)')
const version = computed(() => (system.health?.db_version || '').split('\n')[0].replace('Oracle AI Database ', '').replace(' Enterprise Edition Release', '') || '—')
const indexOk = computed(() => (system.health?.vector_index_status || []).some((x) => /HNSW/i.test(x.name) && x.status === 'VALID'))

function goStatus() {
  const m = menuById('manual')
  router.push({ path: m.path, query: { sub: 'status' } })
}
</script>

<template>
  <div class="relative flex items-center gap-1.5" @mouseenter="hovered = true" @mouseleave="hovered = false">
    <button class="chip inline-flex" :title="system.dbOk ? 'DB 연결됨' : 'DB 연결 안됨'" @click="goStatus">
      <span class="dot" :style="{ background: dbColor }"></span><span class="hidden md:inline">DB</span>
    </button>
    <button class="chip hidden xl:inline-flex" :title="`임베딩: ${system.embeddingSource} · ${system.embeddingModel}`" @click="goStatus">{{ system.embeddingLabel }}</button>
    <button class="chip hidden 2xl:inline-flex" title="LLM 모델 (RAG · AWR)" @click="goStatus">{{ system.llmModel }}</button>

    <div
      v-if="hovered"
      class="absolute right-0 top-full mt-1 z-30 min-w-[260px] rounded-md border px-3 py-2 text-xs leading-relaxed"
      style="background: var(--bg-elevated); border-color: var(--border-default); box-shadow: var(--shadow-elevated); color: var(--text-primary);"
    >
      <template v-if="system.health">
        <div class="font-semibold mb-1 flex items-center gap-1.5">
          <span class="dot" :style="{ background: dbColor }"></span>
          {{ system.dbOk ? '데이터베이스 연결됨' : '데이터베이스 연결 안됨' }}
        </div>
        <dl class="grid grid-cols-[88px_1fr] gap-x-2 gap-y-0.5" style="color: var(--text-secondary);">
          <dt style="color: var(--text-muted);">스키마</dt><dd>{{ system.health.schema || '—' }}</dd>
          <dt style="color: var(--text-muted);">버전</dt><dd>{{ version }}</dd>
          <dt style="color: var(--text-muted);">AI 프로필</dt><dd>{{ system.health.profile_count }}개</dd>
          <dt style="color: var(--text-muted);">문서 / 청크</dt><dd>{{ system.health.doc_count }} / {{ fmtNum(system.health.chunk_count) }} (임베딩 {{ fmtNum(system.health.embedded_count) }})</dd>
          <dt style="color: var(--text-muted);">ONNX 모델</dt><dd>{{ system.health.onnx_models.map((m) => m.model_name).join(', ') || '없음' }}</dd>
          <dt style="color: var(--text-muted);">HNSW 인덱스</dt><dd :style="{ color: indexOk ? 'var(--accent-positive)' : 'var(--accent-warm)' }">{{ indexOk ? 'VALID' : '확인 필요' }}</dd>
          <dt style="color: var(--text-muted);">임베딩</dt><dd>{{ system.embeddingSource }} · {{ system.embeddingModel }}</dd>
          <dt style="color: var(--text-muted);">LLM</dt><dd>{{ system.llmModel }}</dd>
        </dl>
        <div class="mt-1.5 pt-1.5 text-[10px]" style="color: var(--text-muted); border-top: 1px solid var(--border-default);">
          /api/health · 30초마다 갱신 · 클릭하면 매뉴얼 › 현재 상태
        </div>
      </template>
      <div v-else-if="system.lastError" style="color: var(--accent-negative);">{{ system.lastError }}</div>
      <div v-else style="color: var(--text-muted);">상태를 불러오는 중…</div>
    </div>
  </div>
</template>

<style scoped>
/* display 는 템플릿의 Tailwind 클래스(inline-flex / hidden xl:inline-flex)가 정한다.
   여기서 display 를 주면 scoped 특이도가 `hidden` 을 이겨 반응형 숨김이 깨진다(2026-09-05 실측). */
.chip {
  align-items: center; gap: 5px;
  padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 500; white-space: nowrap;
  background: rgba(255, 255, 255, 0.10); color: var(--header-text);
  transition: background 150ms;
}
.chip:hover { background: rgba(255, 255, 255, 0.18); }
.dot { width: 6px; height: 6px; border-radius: 999px; display: inline-block; }
</style>
