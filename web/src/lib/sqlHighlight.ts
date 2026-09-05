/**
 * Oracle SQL 하이라이터 — 레거시 app.js highlightOracleSQL() 이식.
 * 차이: 인라인 색 대신 토큰 클래스(tk-*)를 쓰고 색은 tokens.css 의 --code-* 가 정한다.
 *       단일 패스 토크나이저라 문자열 안의 키워드·주석 안의 함수가 이중으로 감싸이지 않는다.
 */
const KEYWORDS = new Set([
  'SELECT','FROM','WHERE','ORDER','BY','FETCH','FIRST','NEXT','ROWS','ONLY','INSERT','INTO','VALUES','UPDATE','SET',
  'DELETE','CREATE','OR','REPLACE','TABLE','INDEX','VIEW','ON','AS','AND','NOT','NULL','IS','IN','LIKE','BEGIN','END',
  'DECLARE','USING','DESC','ASC','JOIN','INNER','LEFT','RIGHT','OUTER','CROSS','GROUP','HAVING','DISTINCT','LOWER','UPPER',
  'COSINE','EUCLIDEAN','ORGANIZATION','NEIGHBOR','PARTITIONS','DISTANCE','VECTOR','CLOB','NUMBER','VARCHAR2','TIMESTAMP',
  'IDENTITY','PRIMARY','KEY','INMEMORY','GRAPH','WITH','TARGET','ACCURACY','CASCADE','CONSTRAINTS','PURGE','DROP','EXPLAIN',
  'PLAN','FOR','CASE','WHEN','THEN','ELSE','APPROX','PROPERTY','VERTEX','EDGE','TABLES','SOURCE','DESTINATION','REFERENCES',
  'PROPERTIES','COLUMNS','JSON','RELATIONAL','DUALITY','ALWAYS','GENERATED','DEFAULT','ALTER','ANNOTATIONS','ADD','EXISTS',
  'UNION','ALL','LIMIT','OVER','PARTITION','BETWEEN','EXCEPTION','OTHERS','RAISE','RETURN','RETURNING','COMMIT','ROLLBACK',
  'INDEXTYPE','PARAMETERS','TRUE','FALSE','SAMPLE','DUAL','RESERVABLE','CHECK','PRIORITY',
])
const FUNCTIONS = new Set([
  'VECTOR_DISTANCE','VECTOR_EMBEDDING','VECTOR_SERIALIZE','VECTOR_INDEX_TRANSFORM','VECTOR_DIMENSION_COUNT','TO_VECTOR',
  'CONTAINS','SCORE','GRAPH_TABLE','MATCH','JSON_VALUE','JSON_OBJECT','JSON_SERIALIZE','JSON_TABLE','JSON_QUERY',
  'COUNT','SUM','AVG','MAX','MIN','ROUND','NVL','COALESCE','LISTAGG','SUBSTR','TO_CHAR','TO_DATE','SYSTIMESTAMP',
  'UTL_TO_CHUNKS','GENERATE','SET_PROFILE','DISPLAY','LOAD_ONNX_MODEL','IMPORT_ONNX_MODEL','CREATE_CREDENTIAL',
  'DBMS_CLOUD_AI','DBMS_VECTOR','DBMS_VECTOR_CHAIN','DBMS_XPLAN','DBMS_LOB','DBMS_DATA_MINING','CTXSYS',
])

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

// 주석 | 문자열 | 바인드 | 숫자 | 식별자(점 포함)
const TOKEN = /(--[^\n]*)|('(?:[^']|'')*')|(:[A-Za-z_]\w*)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][\w$#]*(?:\.[A-Za-z_][\w$#]*)*)/g

export function highlightSql(sql: string | null | undefined): string {
  if (!sql) return ''
  const src = esc(sql)
  return src.replace(TOKEN, (m, cmt, str, bind, num, ident) => {
    if (cmt) return `<span class="tk-cmt">${m}</span>`
    if (str) return `<span class="tk-str">${m}</span>`
    if (bind) return `<span class="tk-bind">${m}</span>`
    if (num) return `<span class="tk-num">${m}</span>`
    if (ident) {
      const up = m.toUpperCase()
      const last = up.split('.').pop() || up
      if (FUNCTIONS.has(up) || FUNCTIONS.has(last) || up.split('.').some((p) => FUNCTIONS.has(p))) return `<span class="tk-fn">${m}</span>`
      if (KEYWORDS.has(up)) return `<span class="tk-kw">${m}</span>`
    }
    return m
  })
}

/** 줄번호 포함 렌더 */
export function highlightSqlLines(sql: string | null | undefined): string {
  if (!sql) return ''
  return sql.split('\n').map((line, i) => `<div><span class="ln">${i + 1}</span>${highlightSql(line) || '&nbsp;'}</div>`).join('')
}

/** JSON 프리티 + 최소 하이라이트 (Duality 용) */
export function highlightJson(v: unknown): string {
  let text: string
  try { text = typeof v === 'string' ? JSON.stringify(JSON.parse(v), null, 2) : JSON.stringify(v, null, 2) } catch { text = String(v) }
  return esc(text)
    .replace(/("(?:[^"\\]|\\.)*")(\s*:)?/g, (_m, s, colon) => colon ? `<span class="tk-kw">${s}</span>${colon}` : `<span class="tk-str">${s}</span>`)
    .replace(/\b(-?\d+(?:\.\d+)?)\b/g, '<span class="tk-num">$1</span>')
    .replace(/\b(true|false|null)\b/g, '<span class="tk-bind">$1</span>')
}
