import { api } from './api'
import { fromColumnsData, type Rows } from './normalize'

export type Action = 'runsql' | 'showsql' | 'narrate' | 'explainsql' | 'showprompt' | 'summarize' | 'chat'
export type FollowAction = Action | 'chart' | 'explainplan'

/** 실행 모드 7종 — 순서는 데모 동선(먼저 SQL 을 보고 → 실행 → 설명…). 정본은 app/routers/nl2sql.py 의 VALID_ACTIONS */
export const ACTIONS: { value: Action; label: string; hint: string }[] = [
  { value: 'showsql', label: 'SQL 보기', hint: '자연어 → SQL 만 생성' },
  { value: 'runsql', label: '실행', hint: 'SQL 을 만들어 실행하고 표로' },
  { value: 'narrate', label: '설명', hint: '결과를 자연어로 서술' },
  { value: 'explainsql', label: 'SQL 해설', hint: '생성된 SQL 을 한국어로 해설' },
  { value: 'showprompt', label: '프롬프트', hint: 'LLM 에 보낸 프롬프트 원문' },
  { value: 'summarize', label: '요약', hint: '결과를 요약' },
  { value: 'chat', label: '대화', hint: 'DB 없이 LLM 과 대화' },
]

export const LOADING_TEXT: Record<Action, string> = {
  showsql: 'AI 가 SQL 을 생성하고 있습니다',
  runsql: 'AI 가 SQL 을 생성하고 실행하고 있습니다',
  narrate: 'AI 가 자연어 설명을 생성하고 있습니다',
  explainsql: 'AI 가 SQL 해설을 작성하고 있습니다',
  showprompt: 'AI 프롬프트를 조회하고 있습니다',
  summarize: 'AI 가 요약을 생성하고 있습니다',
  chat: 'AI 가 응답을 생성하고 있습니다',
}

/** 답변 아래 후속 버튼 — 레거시 actionButtonRules 그대로 */
export const ACTION_BUTTONS: Record<string, { action: FollowAction; label: string }[]> = {
  runsql: [
    { action: 'showsql', label: 'SQL 보기' }, { action: 'chart', label: '차트' }, { action: 'narrate', label: '설명' },
    { action: 'explainsql', label: 'SQL 해설' }, { action: 'explainplan', label: '실행계획' }, { action: 'showprompt', label: '프롬프트 보기' }, { action: 'summarize', label: '요약' },
  ],
  showsql: [
    { action: 'runsql', label: '실행' }, { action: 'narrate', label: '설명' }, { action: 'explainsql', label: 'SQL 해설' },
    { action: 'explainplan', label: '실행계획' }, { action: 'showprompt', label: '프롬프트 보기' },
  ],
  narrate: [{ action: 'showsql', label: 'SQL 보기' }, { action: 'runsql', label: '실행' }, { action: 'showprompt', label: '프롬프트 보기' }],
  explainsql: [{ action: 'showsql', label: 'SQL 보기' }, { action: 'runsql', label: '실행' }, { action: 'showprompt', label: '프롬프트 보기' }],
  showprompt: [{ action: 'showsql', label: 'SQL 보기' }, { action: 'runsql', label: '실행' }],
  summarize: [{ action: 'showsql', label: 'SQL 보기' }, { action: 'runsql', label: '실행' }, { action: 'chart', label: '차트' }, { action: 'showprompt', label: '프롬프트 보기' }],
  explainplan: [{ action: 'showsql', label: 'SQL 보기' }, { action: 'runsql', label: '실행' }, { action: 'narrate', label: '설명' }],
  chat: [],
}

export const EXAMPLE_QUESTIONS: Record<'SH' | 'SSB' | 'DEFAULT', string[]> = {
  SH: [
    '매출 상위 5개 제품을 알려주세요', '월별 매출 추이를 알려주세요', '국가별 고객 수를 알려주세요', '연도별 총 매출액을 알려주세요', '채널별 주문 건수를 알려주세요',
    '2000년 인터넷 채널에서 가장 많이 판매된 제품 카테고리 상위 3개와 매출액을 알려줘',
    '미국 고객 중 연간 구매금액이 가장 높은 상위 10명의 이름과 총 구매금액은?',
    '프로모션 유형별 평균 할인율과 그에 따른 매출 변화를 분석해줘',
    '분기별 매출 성장률을 전년 동기 대비로 보여줘',
    '고객 연령대별 선호 제품 카테고리와 평균 구매단가를 알려줘',
    '유효한 고객 수를 알려줘', '유효하지 않은 고객 중 신용한도가 가장 높은 5명은?', '소득구간별 고객 수와 평균 신용한도를 보여줘', '인터넷 채널과 직접판매 채널의 매출 비교',
  ],
  SSB: [
    '총 매출액이 가장 높은 공급업체 5곳을 알려줘', '연도별 총 주문금액 추이를 보여줘', '지역별 고객 수와 평균 주문금액을 알려줘', '제품 브랜드별 판매수량 순위를 알려줘',
    '월별 주문건수와 평균 할인율을 보여줘', '1997년에 아시아 지역 고객이 주문한 제품 중 매출 상위 5개 브랜드는?', '공급업체 국가별 평균 공급비용과 총 매출을 비교해줘',
    '할인율 20% 이상 적용된 주문의 연도별 매출 비중을 분석해줘', '제품 카테고리별 수익성(매출-공급비용)이 가장 높은 상위 5개 제품은?', '분기별 주문량 추이와 전분기 대비 증감률을 보여줘',
  ],
  DEFAULT: ['테이블 목록을 보여줘', '전체 레코드 수를 알려줘', '최근 데이터 10건을 보여줘'],
}
export function exampleQuestionsFor(profile: string): string[] {
  const p = (profile || '').toUpperCase()
  return p.includes('SSB') ? EXAMPLE_QUESTIONS.SSB : p.includes('SH') ? EXAMPLE_QUESTIONS.SH : EXAMPLE_QUESTIONS.DEFAULT
}

export interface Profile { profile_name: string }
export interface SchemaColumn { column_name: string; data_type: string; nullable?: string; annotation?: string | null }
export interface SchemaTable { owner: string; table_name: string; columns: SchemaColumn[]; column_count: number; num_rows: number | null; annotation?: string | null; error?: string }

export const getProfiles = () => api.get<{ success: boolean; profiles: Profile[] }>('/api/profiles').then((r) => r.data.profiles ?? [])
export const setProfile = (profile_name: string) =>
  api.post<{ success: boolean; profile_name?: string; error?: string; attributes?: any }>('/api/set-profile', { profile_name }).then((r) => r.data)
export const ask = (prompt: string, action: Action, profile_name: string) =>
  api.post<{ success: boolean; action: Action; result: unknown; elapsed_ms: number; error?: string }>('/api/ask', { prompt, action, profile_name }).then((r) => r.data)
export const executeSql = (sql: string) => api.post('/api/execute-sql', { sql }).then((r) => ({ ...r.data, rows: fromColumnsData(r.data) as Rows }))
export const explainPlan = (sql: string) => api.post<{ success: boolean; plan?: string; sql_used?: string; error?: string }>('/api/explain-plan', { sql }).then((r) => r.data)
export const getSchemaInfo = (profile_name: string) => api.post<{ success: boolean; tables: SchemaTable[]; error?: string }>('/api/schema-info', { profile_name }).then((r) => r.data)
export const applyAnnotations = (annotation_set: Record<string, Record<string, string>>) =>
  api.post<{ success: boolean; applied_count: number; error_count: number; errors: string[]; error?: string }>('/api/apply-annotations', { annotation_set }).then((r) => r.data)
export const removeAnnotations = (table_names: string[], owner: string) =>
  api.post<{ success: boolean; removed_count: number; errors?: string[]; error?: string }>('/api/remove-annotations', { table_names, owner }).then((r) => r.data)
