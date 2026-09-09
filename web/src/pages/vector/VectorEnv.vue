<script setup lang="ts">
/**
 * 「환경」 서브탭 (P3, 2026-09-09) — 시연의 시작점. 설계 원칙은 사용자 피드백 그대로:
 * "보는 사람이 이 카드에서 무엇을 이해할 수 있는가". 값을 나열하지 않는다 — 값마다 뜻을, 카드마다 "이게 있어서 무엇이 되는가"를 적는다.
 * 사슬: ① 벡터를 담는 테이블 → ② 텍스트를 벡터로 바꾸는 모델(DB 안) → ③ 빨리 찾는 인덱스 2종. 끝에 「이 문장을 벡터로」 실제 호출.
 */
import { computed, onMounted, ref } from 'vue'
import { Database, Cpu, Layers, Zap, ChevronRight, ChevronDown, CheckCircle2, XCircle } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import VersusBox from '@/components/demo/VersusBox.vue'
import { fmtNum } from '@/lib/format'
import { useVectorStore } from '@/stores/vector'

const v = useVectorStore()
const confirmHvi = ref(false)
const showDdl = ref<Record<string, boolean>>({})
const toggle = (k: string) => { showDdl.value[k] = !showDdl.value[k] }
onMounted(() => { void v.loadConfig(); if (!v.docsLoaded) void v.loadDocs(); if (!v.hvi) void v.loadHvi() })

const info = computed(() => v.indexInfo)
const allEmbedded = computed(() => !!info.value && (info.value.total_chunks ?? 0) > 0 && info.value.embedded_chunks === info.value.total_chunks)
const hnswOk = computed(() => (info.value?.index?.status ?? '') === 'VALID')
const hviOk = computed(() => !!v.hvi?.exists && (v.hvi?.status ?? 'VALID') === 'VALID')
const ready = computed(() => allEmbedded.value && hnswOk.value)

// ① 테이블 — 스키마는 앱 코드가 정하므로 고정 목록. 카탈로그 원문은 「내부」에서
const COLUMNS = [
  { name: 'chunk_text', type: 'CLOB', meaning: '원문 조각 (500자 안팎)' },
  { name: 'embedding', type: 'VECTOR', meaning: '그 조각의 뜻을 숫자로 — 검색은 이 컬럼끼리의 거리' },
  { name: 'page_num · source_file', type: 'NUMBER · VARCHAR2', meaning: '어느 문서 몇 쪽에서 왔나 — 결과 카드의 p.N' },
  { name: 'doc_id · chunk_id', type: 'NUMBER', meaning: '보통 테이블처럼 PK/FK — 조인·트랜잭션·백업이 그대로' },
]
</script>

<template>
  <div class="flex flex-col gap-5">
    <!-- 개요 -->
    <Card title="Oracle AI Vector Search — 의미 기반 검색을 SQL 안에서" :icon="Database">
      <VersusBox left-title="기존 키워드 검색" left-desc="정확한 단어가 있어야 찾는다. 검색엔진을 따로 두면 데이터가 두 곳에 있고 트랜잭션과 분리된다."
        right-title="Oracle AI Vector Search" right-desc="뜻이 비슷하면 찾는다. 벡터가 테이블 컬럼에 있어 한 SQL 에 검색 + 비즈니스 로직, 트랜잭션도 하나.">
        텍스트의 뜻을 숫자 묶음(벡터)으로 바꿔 <strong style="color: var(--text-primary);">VECTOR 타입</strong> 컬럼에 저장하고, <code class="font-mono">VECTOR_DISTANCE</code> 로 가까운 것을 찾습니다.
        바꾸는 계산(<code class="font-mono">VECTOR_EMBEDDING</code>)이 <strong style="color: var(--text-primary);">DB 안</strong>에서 돌아 데이터가 밖으로 나가지 않습니다. 아래 세 가지가 그것을 가능하게 하는 부품입니다.
      </VersusBox>
    </Card>

    <!-- 준비 상태 — 한눈에. 값 + 뜻 -->
    <Card compact>
      <template #header>
        <div class="flex items-center gap-2">
          <component :is="ready ? CheckCircle2 : XCircle" :size="18" :stroke-width="1.75" :style="{ color: ready ? 'var(--accent-positive)' : 'var(--accent-warm)' }" />
          <h3 class="font-semibold text-base m-0" style="color: var(--text-primary);">{{ ready ? '검색 준비 완료' : '준비 확인 중' }}</h3>
          <span class="text-sm" style="color: var(--text-muted);">— 이 DB 안에 지금 있는 것</span>
        </div>
      </template>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-1">
        <div>
          <div class="text-xs mb-1" style="color: var(--text-muted);">검색 대상</div>
          <div class="text-lg font-semibold tabular-nums" style="color: var(--text-primary);">문서 {{ v.docs.length }} · 청크 {{ fmtNum(info?.total_chunks ?? 0) }}</div>
          <div class="text-xs mt-1" style="color: var(--text-secondary);">{{ allEmbedded ? '전부 벡터화됨' : `벡터화 ${info?.embedded_chunks ?? 0} / ${info?.total_chunks ?? 0}` }} — 의미 검색이 볼 수 있는 조각의 수</div>
        </div>
        <div>
          <div class="text-xs mb-1" style="color: var(--text-muted);">텍스트 → 벡터</div>
          <div class="text-lg font-semibold font-mono" style="color: var(--text-primary);">{{ v.model || '—' }}</div>
          <div class="text-xs mt-1" style="color: var(--text-secondary);">{{ v.source === 'database' ? 'DB 안 ONNX 모델' : '외부 API' }} · 벡터 하나 = 숫자 <strong style="color: var(--text-primary);">{{ info?.vector_dimensions ?? '—' }}개</strong>{{ info?.dimensions_measured ? ' (저장된 벡터에서 실측)' : ' (설정값)' }}</div>
        </div>
        <div>
          <div class="text-xs mb-1" style="color: var(--text-muted);">빨리 찾는 구조</div>
          <div class="flex flex-wrap gap-1.5 mt-1"><Badge :tone="hnswOk ? 'positive' : 'negative'">HNSW {{ hnswOk ? '✓' : '✗' }}</Badge><Badge :tone="hviOk ? 'positive' : 'default'">Hybrid Vector Index {{ hviOk ? '✓' : '없음' }}</Badge></div>
          <div class="text-xs mt-1" style="color: var(--text-secondary);">{{ fmtNum(info?.total_chunks ?? 0) }}개면 없어도 되지만, 수백만 개에서도 ms 단위로 찾게 하는 것</div>
        </div>
      </div>
    </Card>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
      <!-- ① 테이블 -->
      <Card title="① 벡터를 담는 테이블" subtitle="doc_chunks — 벡터가 검색엔진이 아니라 보통 테이블의 컬럼에 있다" :icon="Database">
        <div class="flex flex-col">
          <div v-for="c in COLUMNS" :key="c.name" class="py-1.5 text-sm" style="border-bottom: 1px solid var(--border-default);">
            <div class="flex items-baseline gap-2"><span class="font-mono font-semibold" style="color: var(--text-primary);">{{ c.name }}</span><span class="font-mono text-xs" style="color: var(--text-muted);">{{ c.type }}</span></div>
            <div class="text-xs mt-0.5" style="color: var(--text-secondary);">{{ c.meaning }}</div>
          </div>
        </div>
        <p class="text-xs mt-3 m-0" style="color: var(--text-secondary); line-height: 1.5;">
          <strong style="color: var(--text-primary);">이게 있어서:</strong> 벡터 검색 결과를 다른 테이블과 <em>같은 SQL</em> 에서 조인하고, 문서를 지우면 벡터도 같은 트랜잭션으로 사라집니다. 지금 {{ fmtNum(info?.embedded_chunks ?? 0) }}개 조각이 {{ info?.vector_dimensions ?? '—' }}개 숫자를 각각 들고 있습니다.
        </p>
        <span class="text-xs mt-2 inline-block" style="color: var(--text-muted);">카탈로그 원문(컬럼 정의 · 데이터)은 「내부」 서브탭</span>
      </Card>

      <!-- ② 모델 -->
      <Card title="② 텍스트를 벡터로 바꾸는 모델" subtitle="DB 안에 적재된 ONNX 모델 — 문서도, 질문도 이 모델로 벡터가 된다" :icon="Cpu">
        <div class="text-sm" style="color: var(--text-primary);">
          <div class="flex items-baseline gap-2"><span class="font-mono font-semibold">{{ v.model || '—' }}</span><Badge tone="code">{{ info?.vector_dimensions ?? '—' }}차원</Badge></div>
          <div class="text-xs mt-1" style="color: var(--text-secondary);">{{ v.source === 'database' ? 'VECTOR_EMBEDDING() 이 DB 프로세스 안에서 실행 — 외부 API 호출 없음' : '외부 임베딩 API 사용 중 (데이터가 DB 밖으로 나간다)' }}</div>
        </div>
        <p class="text-xs mt-3 m-0" style="color: var(--text-secondary); line-height: 1.5;">
          <strong style="color: var(--text-primary);">이게 있어서:</strong> 문서 원문이 DB 밖으로 나가지 않고, 질문과 문서가 <em>같은 모델</em>로 벡터가 되어 서로 비교할 수 있습니다. 모델을 바꾸면 숫자의 개수가 달라져 다시 적재해야 합니다.
        </p>
        <div class="mt-3 pt-3 flex flex-col gap-2" style="border-top: 1px solid var(--border-default);">
          <div class="text-xs font-semibold" style="color: var(--text-secondary);"><Zap :size="12" :stroke-width="2" class="inline -mt-0.5" /> 이 문장을 벡터로 — 지금 실제로</div>
          <input v-model="v.envEmbedText" :disabled="v.envEmbedBusy" class="w-full rounded-md px-2.5 py-1.5 text-sm" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" @keydown.enter.prevent="v.testEmbed()" />
          <div><Button size="sm" :busy="v.envEmbedBusy" :disabled="!v.model || v.source !== 'database'" @click="v.testEmbed()">VECTOR_EMBEDDING 실행</Button></div>
          <LoadingBlock v-if="v.envEmbedBusy" compact label="DB 안에서 벡터를 만드는 중…" />
          <template v-else-if="v.envEmbed">
            <div v-if="v.envEmbed.error" class="px-3 py-2 rounded-md text-xs font-mono break-all" style="background: var(--accent-negative-soft); color: var(--text-primary);">{{ v.envEmbed.error }}</div>
            <template v-else>
              <div class="text-xs" style="color: var(--text-secondary);">문장 하나 → 숫자 <strong style="color: var(--text-primary);">{{ v.envEmbed.dimensions }}개</strong>, {{ v.envEmbed.processing_ms }}ms. 앞부분:</div>
              <div class="font-mono text-xs px-2.5 py-2 rounded-md break-all" style="background: var(--bg-elevated); border: 1px solid var(--border-default); color: var(--text-primary);">{{ v.envEmbed.vector_preview }}</div>
              <SqlBlock :code="v.envEmbed.sql_executed" label="실행된 SQL" max-height="90px" />
            </template>
          </template>
        </div>
      </Card>

      <!-- ③ 인덱스 -->
      <Card title="③ 빨리 찾는 인덱스 2종" subtitle="서로 다른 컬럼에 선다 — 하나는 벡터, 하나는 텍스트 + 벡터" :icon="Layers">
        <template #actions><Button size="sm" variant="ghost" :busy="v.hviBusy === 'load'" @click="v.loadHvi(); v.loadConfig(true)">새로고침</Button></template>
        <div class="flex flex-col gap-3">
          <div class="rounded-md px-3 py-2.5" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
            <div class="flex flex-wrap items-center gap-1.5"><span class="font-mono text-sm font-semibold" style="color: var(--text-primary);">HNSW</span><Badge :tone="hnswOk ? 'positive' : 'negative'">{{ info?.index?.status ?? '없음' }}</Badge><span class="text-xs" style="color: var(--text-muted);">embedding 컬럼 · COSINE</span></div>
            <div class="text-xs mt-1" style="color: var(--text-secondary);">벡터끼리 가까운 것을 그래프로 찾는다 — <strong style="color: var(--text-primary);">의미 검색</strong>이 타는 길. 전부 비교하지 않고도 거의 같은 답을 준다(정확도 95% 목표).</div>
            <button type="button" class="mt-1.5 inline-flex items-center gap-1 text-xs" style="color: var(--text-muted);" @click="toggle('hnsw')"><component :is="showDdl.hnsw ? ChevronDown : ChevronRight" :size="12" :stroke-width="2" /> 만든 문장</button>
            <SqlBlock v-if="showDdl.hnsw && info?.hnsw_ddl" class="mt-1.5" :code="info.hnsw_ddl" label="CREATE VECTOR INDEX" max-height="120px" />
          </div>
          <div class="rounded-md px-3 py-2.5" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
            <div class="flex flex-wrap items-center gap-1.5"><span class="font-mono text-sm font-semibold" style="color: var(--text-primary);">Hybrid Vector Index</span><Badge tone="primary">26ai</Badge><Badge :tone="hviOk ? 'positive' : 'default'">{{ v.hvi?.exists ? (v.hvi.status || 'VALID') : '없음' }}</Badge><span class="text-xs" style="color: var(--text-muted);">chunk_text 컬럼</span></div>
            <div class="text-xs mt-1" style="color: var(--text-secondary);">텍스트 컬럼 하나만 주면 DB 가 <em>스스로</em> 잘라 벡터로 바꾸고 텍스트 인덱스까지 같이 만든다 — <strong style="color: var(--text-primary);">키워드 검색과 Hybrid Vector Index 모드</strong>가 타는 길. 26ai 에서 새로 생긴 것.</div>
            <div v-if="v.hvi?.exists" class="text-xs mt-1" style="color: var(--text-secondary);">지금 인덱스 안에 조각 <strong style="color: var(--text-primary);">{{ fmtNum(v.hvi.indexed_chunks ?? 0) }}개</strong> — 청크 {{ fmtNum(info?.total_chunks ?? 0) }}개를 인덱스가 다시 잘라 넣은 수. 새 문서를 올리면 「적재」 5단계에서 동기화된다.</div>
            <div class="mt-1.5 flex items-center gap-3">
              <button type="button" class="inline-flex items-center gap-1 text-xs" style="color: var(--text-muted);" @click="toggle('hvi')"><component :is="showDdl.hvi ? ChevronDown : ChevronRight" :size="12" :stroke-width="2" /> 만든 문장</button>
              <Button size="sm" :variant="v.hvi?.exists ? 'secondary' : 'primary'" :busy="v.hviBusy === 'create'" :disabled="v.hviBusy !== ''" @click="confirmHvi = true">{{ v.hvi?.exists ? '재생성' : '생성' }}</Button>
            </div>
            <SqlBlock v-if="showDdl.hvi && v.hvi?.create_sql" class="mt-1.5" :code="v.hvi.create_sql" label="CREATE HYBRID VECTOR INDEX" max-height="120px" />
            <div v-if="v.hviResult" class="mt-2 flex flex-col gap-2">
              <div v-if="v.hviResult.error" class="px-3 py-2 rounded-md text-xs font-mono break-all" style="background: var(--accent-negative-soft); color: var(--text-primary);">{{ v.hviResult.error }}</div>
              <SqlBlock v-for="(st, i) in v.hviResult.steps ?? []" :key="i" :code="st.sql" :label="st.note" :elapsed-ms="st.duration_ms" max-height="120px" />
            </div>
          </div>
        </div>
        <p class="text-xs mt-3 m-0" style="color: var(--text-secondary); line-height: 1.5;"><strong style="color: var(--text-primary);">이게 있어서:</strong> 문서가 늘어도 검색 시간이 늘지 않습니다. 「내부」의 실행계획 카드가 인덱스를 타는 SQL 과 못 타는 SQL 을 나란히 보여줍니다.</p>
      </Card>
    </div>

    <ConfirmModal :open="confirmHvi" title="Hybrid Vector Index 를 만들까요?" confirm-label="생성" :busy="v.hviBusy === 'create'" @confirm="confirmHvi = false; v.createHvi(!!v.hvi?.exists)" @cancel="confirmHvi = false">
      청크 수 × 약 0.3초가 걸립니다 (DB 가 모든 청크를 다시 잘라 임베딩합니다). 같은 컬럼의 옛 Oracle Text 인덱스(DOC_CHUNKS_TEXT_IDX)는 지워지고, 이 인덱스가 CONTAINS 도 대신 서빙합니다.
    </ConfirmModal>
  </div>
</template>
