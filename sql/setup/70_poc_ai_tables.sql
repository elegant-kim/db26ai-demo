-- 70_poc_ai_tables.sql — 고객사 PoC 대응 확장 Phase 1 (2026-09-29)
-- Select AI 호출 이력 · 답변 피드백 · 저장 질문 프리셋. 초안·근거: docs/POC_PHASE0_갭보고.md §4
-- 실행: SQLcl / SQL Developer 에서 ADMIN 으로. 롤백: 71_poc_ai_tables_rollback.sql
-- 권한: ADMIN 은 DBMS_CLOUD_AI EXECUTE · V_$MAPPED_SQL SELECT 를 이미 갖고 있어 추가 GRANT 없음.
-- 한글 컬럼은 CHAR 단위(VARCHAR2(n CHAR)) — BYTE 단위면 ORA-12899 (개발노하우 3.3).

-- ① 모든 Select AI 호출 (GENERATE · SELECT AI 직접 실행 · Phase 4 RUN_TEAM)
CREATE TABLE ai_query_log (
  id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  started_at      TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
  source          VARCHAR2(16)  DEFAULT 'GENERATE' NOT NULL,     -- GENERATE | RAWSQL | RUN_TEAM
  profile_name    VARCHAR2(128),
  action          VARCHAR2(16),
  question        CLOB,
  generated_sql   CLOB,                                           -- showsql/explainsql 결과, 또는 나중에 붙인 SQL
  response_text   VARCHAR2(4000 CHAR),                            -- 답변 앞부분(표는 JSON 앞부분)
  status          VARCHAR2(10)  NOT NULL,                         -- SUCCEEDED | FAILED
  error_msg       VARCHAR2(4000 CHAR),
  elapsed_ms      NUMBER,
  conversation_id VARCHAR2(36),
  row_count       NUMBER,
  model           VARCHAR2(128),
  sql_id          VARCHAR2(13),
  created_by      VARCHAR2(128) DEFAULT SYS_CONTEXT('USERENV','SESSION_USER')
);
CREATE INDEX ai_query_log_ix1 ON ai_query_log (started_at DESC);
CREATE INDEX ai_query_log_ix2 ON ai_query_log (profile_name, action, status);
COMMENT ON TABLE ai_query_log IS 'Select AI 호출 이력 — 앱 서비스 계층(app/select_ai.py run_select_ai)이 매 호출 기록';

-- ② 답변 피드백 — DBMS_CLOUD_AI.FEEDBACK 과 한 트랜잭션으로 기록 (수정 = delete 후 add)
CREATE TABLE ai_feedback_log (
  id               NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  log_id           NUMBER REFERENCES ai_query_log(id),
  profile_name     VARCHAR2(128) NOT NULL,
  conversation_id  VARCHAR2(36),
  question         CLOB,
  generated_sql    CLOB,
  sql_id           VARCHAR2(13),
  feedback_type    VARCHAR2(8)  NOT NULL CHECK (feedback_type IN ('positive','negative')),
  feedback_content VARCHAR2(4000 CHAR),
  corrected_sql    CLOB,
  source           VARCHAR2(16) DEFAULT 'INLINE',                 -- INLINE | HISTORY | FEWSHOT
  created_at       TIMESTAMP DEFAULT SYSTIMESTAMP,
  updated_at       TIMESTAMP
);
CREATE INDEX ai_feedback_log_ix1 ON ai_feedback_log (log_id);
COMMENT ON TABLE ai_feedback_log IS 'Select AI 답변 피드백 — Oracle FEEDBACK(벡터 인덱스) 호출과 같이 기록';

-- ③ 저장 질문 프리셋 (예시 질문 드롭다운의 DB 판 — 시드는 Phase 1-D)
CREATE TABLE ai_prompt_preset (
  id           NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  profile_name VARCHAR2(128),                                     -- NULL = 모든 프로필. 'SH%' 같은 LIKE 패턴 허용
  title        VARCHAR2(200 CHAR) NOT NULL,
  question     VARCHAR2(2000 CHAR) NOT NULL,
  action       VARCHAR2(16) DEFAULT 'runsql',
  sort_order   NUMBER DEFAULT 100,
  created_at   TIMESTAMP DEFAULT SYSTIMESTAMP
);
COMMENT ON TABLE ai_prompt_preset IS 'Select AI 예시 질문 프리셋 — 화면에서 추가·수정·삭제';
