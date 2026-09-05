<script setup lang="ts">
/** 용어 툴팁 — 물음표 hover 시 설명. `term`(26ai 용어집) 또는 `text` 직접. 용어집 정본: 사용자 가이드 부록 */
import { computed, ref } from 'vue'
import { HelpCircle } from 'lucide-vue-next'

const props = defineProps<{ term?: string; text?: string }>()
const GLOSSARY: Record<string, string> = {
  청크: '문서를 검색 단위로 자른 조각(약 500자, 50자 겹침). DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS 가 자른다.',
  임베딩: '텍스트를 숫자 벡터로 바꾼 것. 여기서는 DB 안의 ONNX 모델이 768차원으로 만든다.',
  '코사인 유사도': '두 벡터가 이루는 각도로 재는 의미 유사도. 1에 가까울수록 비슷하다.',
  HNSW: '벡터 근사 최근접 탐색 인덱스. 전수 비교 없이 빠르게 찾는다. 첫 데이터의 차원으로 고정된다.',
  RAG: '검색으로 찾은 근거를 LLM 에 주고 답을 만들게 하는 방식. 근거(청크)를 함께 보여준다.',
  'SQL/PGQ': 'SQL 표준의 그래프 질의 확장(SQL:2023). GRAPH_TABLE(… MATCH …) 로 관계를 따라간다.',
  ETag: '문서 버전 표식. 남이 먼저 고쳤으면 내 수정을 거부한다(낙관적 동시성 제어).',
  'Duality View': '관계형 테이블 위의 JSON 문서 뷰. JSON 을 고치면 테이블이 바뀐다 — 복제본이 아니다.',
  'Select AI': 'DBMS_CLOUD_AI — LLM 이 DB 안에서 호출되어 자연어를 SQL 로 바꾼다.',
  'Oracle Text': '전문검색 엔진. CONTAINS/SCORE 로 키워드 검색. 인덱스가 없으면 LIKE 로 폴백된다.',
}
const open = ref(false)
const body = computed(() => props.text || (props.term ? GLOSSARY[props.term] : '') || '')
</script>

<template>
  <span class="relative inline-flex align-middle" @mouseenter="open = true" @mouseleave="open = false" @click.stop="open = !open">
    <HelpCircle :size="13" class="cursor-help" style="color: var(--text-muted);" />
    <span v-if="open && body" class="absolute z-50 left-1/2 -translate-x-1/2 bottom-full mb-1.5 w-64 p-2 rounded-md text-[11px] text-left"
      style="background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid var(--border-strong); box-shadow: var(--shadow-card); line-height: 1.5;">
      <strong v-if="term" style="color: var(--text-primary);">{{ term }}</strong><span v-if="term"> — </span>{{ body }}
    </span>
  </span>
</template>
