/**
 * D11 어댑터 — 결과 배열 키가 엔드포인트마다 다르다(data / chunks / sql_data·pgq_data / models …).
 * 백엔드는 두고(레거시 UI 와 공존) 여기 한 층이 흡수한다. ResultTable·CompareView 는 Rows 만 받는다.
 * 키 이름을 아는 곳은 이 파일뿐이어야 한다.
 */
export type Cell = string | number | boolean | null
export interface Rows {
  columns: string[]
  rows: Record<string, Cell>[]
  elapsedMs?: number | null
  sql?: string
  error?: string
}

interface Keys { columns?: string; data: string; elapsed?: string; sql?: string; error?: string }

export function rowsFrom(o: any, k: Keys): Rows {
  const data: Record<string, Cell>[] = Array.isArray(o?.[k.data]) ? o[k.data] : []
  const columns: string[] = (k.columns && Array.isArray(o?.[k.columns]) && o[k.columns].length)
    ? o[k.columns]
    : (data[0] ? Object.keys(data[0]) : [])
  return {
    columns,
    rows: data,
    elapsedMs: k.elapsed ? (o?.[k.elapsed] ?? null) : null,
    sql: k.sql ? o?.[k.sql] : undefined,
    error: k.error ? o?.[k.error] : undefined,
  }
}

/** POST /api/execute-sql · GET /api/{tab}/recent-queries · duality/graph 의 columns+data 형 */
export const fromColumnsData = (r: any): Rows =>
  rowsFrom(r, { columns: 'columns', data: 'data', elapsed: 'elapsed_ms', sql: 'sql_executed', error: 'error' })

/** POST /api/graph/compare — sql_* / pgq_* 평면 구조 */
export const fromGraphSide = (r: any, side: 'sql' | 'pgq'): Rows =>
  rowsFrom(r, { columns: `${side}_columns`, data: `${side}_data`, elapsed: `${side}_elapsed`, sql: `${side}_query`, error: `${side}_error` })

/** POST /api/duality/compare — relational_* 평면 구조 (json_* 쪽은 문서 배열이라 Rows 가 아니다) */
export const fromDualityRelational = (r: any): Rows =>
  rowsFrom(r, { columns: 'relational_columns', data: 'relational_data', elapsed: 'relational_elapsed', sql: 'relational_sql', error: 'relational_error' })

/** 두 Rows 의 값이 순서까지 같은가 — CompareView 의 "동일" 배너 판정 */
export function rowsEqual(a: Rows, b: Rows): boolean {
  if (a.rows.length !== b.rows.length) return false
  for (let i = 0; i < a.rows.length; i++) {
    const va = Object.values(a.rows[i]).map(String)
    const vb = Object.values(b.rows[i]).map(String)
    if (va.length !== vb.length || va.some((v, j) => v !== vb[j])) return false
  }
  return true
}
