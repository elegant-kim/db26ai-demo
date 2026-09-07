-- =============================================================================
-- 52_selectai_adb_demo.sql — Select AI 시연 대본 (Autonomous Database 전용)
-- =============================================================================
-- 선행 : 51_selectai_adb_setup.sql 을 먼저 끝까지 실행하고 §6 검증을 통과할 것.
-- 대상 : SQLcl 또는 SQL Developer 에서 ADMIN 으로 접속. 위에서 아래로 한 절씩 실행.
-- 원복 : 53_selectai_adb_teardown.sql
--
-- ▣ 시연 순서 (30~40분)
--   §1 지금 무엇을 보고 있나        — 프로필·대상 스키마 확인
--   §2 액션 6종 한 바퀴             — 같은 질문을 6가지로 물어본다
--   §3 한국어 질문 세트             — 기초 → 집계 → 분석함수
--   §4 Annotation 효과 ★           — 이 데모의 핵심. 붙였다 떼며 SQL 품질 변화를 본다
--   §5 대화 이어가기                — conversation 속성
--   §6 함수 호출 형태               — 앱이 축약구문 대신 이걸 쓰는 이유
--   §7 실행계획 · 프로필 전환
--
-- ▣ select AI 축약구문에 대해
--   `select AI <액션> <질문>` 은 세션에 SET_PROFILE 이 되어 있어야 동작한다(§0).
--   액션 6종(runsql·showsql·narrate·explainsql·showprompt·summarize)이 모두 이
--   축약구문에서 동작하는 것을 2026-09-07 SQLcl 로 실측 확인했다.
--   ※ 축약구문의 질문은 문자열 리터럴이 아니다 — 따옴표로 감싸지 않고, 작은따옴표를
--     쓰면 그대로 LLM 에 전달된다. 세미콜론 앞까지가 질문이다.
--
-- 2026-09-07 작성. 다른 환경에서 쓰던 selectAI_demo.sql 은 손대지 않고 그대로 둔다.
-- =============================================================================
SET SERVEROUTPUT ON
SET DEFINE OFF
SET LINESIZE 200
SET PAGESIZE 100
SET LONG 100000


-- =============================================================================
-- §0. 세션 프로필 지정 + 워밍업
-- =============================================================================
-- 이 한 줄이 안 돌면 아래 select AI 는 전부 ORA-20046 으로 죽는다.
-- 세션 단위라 접속이 끊기면 다시 실행해야 한다.
EXEC DBMS_CLOUD_AI.SET_PROFILE('GEMINI_SH_PROFILE');

-- 워밍업 — 첫 호출은 커넥션·TLS·모델 로딩 때문에 느리다. 시연 전에 한 번 흘려보낸다.
SELECT AI chat 준비됐나요;


-- =============================================================================
-- §1. 지금 무엇을 보고 있나
-- =============================================================================
-- 1-1. 이 DB 에 있는 프로필
SELECT profile_name, status FROM user_cloud_ai_profiles ORDER BY profile_name;

-- 1-2. 지금 세션이 쓰는 프로필의 설정 — 특히 object_list 가 무엇을 가리키는지
SELECT attribute_name, attribute_value
FROM   user_cloud_ai_profile_attributes
WHERE  profile_name = 'GEMINI_SH_PROFILE'
ORDER  BY attribute_name;
-- ★ object_list 가 ADMIN 을 가리킨다. SH 가 아니다.
--   ADB 의 SH 는 읽기 전용이라 Annotation 을 못 붙여서 ADMIN 으로 복제했다(51번 §1).

-- 1-3. LLM 이 보게 될 테이블들
SELECT table_name, num_rows
FROM   user_tables
WHERE  table_name IN ('CHANNELS','COSTS','COUNTRIES','CUSTOMERS',
                      'PRODUCTS','PROMOTIONS','SALES','TIMES')
ORDER  BY table_name;


-- =============================================================================
-- §2. 액션 6종 한 바퀴 — 같은 질문을 여섯 가지 방식으로
-- =============================================================================
-- 2-1. showsql — SQL 만 생성한다 (실행하지 않는다). 가장 안전한 첫 시연.
SELECT AI showsql 고객이 몇 명인가요;

-- 2-2. runsql — SQL 을 만들어 실행까지 하고 결과를 돌려준다 (액션 생략 시 기본값)
SELECT AI runsql 고객이 몇 명인가요;
SELECT AI 상품이 몇 개인가요;

-- 2-3. narrate — 결과를 문장으로 서술한다. 표가 아니라 답변이 나온다.
SELECT AI narrate 판매 채널별 총 판매 금액을 알려주세요;

-- 2-4. explainsql — 생성한 SQL 을 해설한다
--      ※ 그냥 두면 영어로 답한다. 한국어 지시를 질문에 직접 붙여야 한다.
--        (앱은 이 문구를 자동으로 덧붙인다 — app/routers/nl2sql.py)
SELECT AI explainsql 2001년 분기별 판매 금액 (한국어로 설명해 주세요);

-- 2-5. showprompt ★ — LLM 에 실제로 보낸 프롬프트 원문을 보여준다
--      Select AI 가 "스키마를 어떻게 증강해서 보내는지"가 그대로 드러난다.
--      CREATE TABLE 문 + ANNOTATIONS + FK 제약이 system 메시지에 실려 있는 것을 확인한다.
SELECT AI showprompt 고객이 몇 명인가요;

-- 2-6. summarize — 주어진 텍스트를 요약한다
--      ※ 2026-09-07 실측: 질의 '결과'가 아니라 '프롬프트 텍스트'를 요약한다.
--        짧은 질문에 쓰면 쓸모가 없다. 긴 문서를 넣을 때 의미가 있는 액션이다.
SELECT AI summarize 이 데이터베이스에는 고객, 상품, 판매, 채널, 프로모션, 시간, 국가, 원가 정보가 들어 있고 1998년부터 2001년까지의 판매 실적을 담고 있다;

-- 2-7. chat — DB 를 보지 않고 LLM 과 그냥 대화한다 (스키마 증강 없음)
SELECT AI chat Oracle Select AI 를 한 문장으로 설명해줘;


-- =============================================================================
-- §3. 한국어 질문 세트 — 기초 → 집계 → 분석함수
-- =============================================================================
-- 3-1. 기초
SELECT AI 얼마나 많은 고객이 있나요;
SELECT AI 아시아에 있는 모든 국가의 이름을 알 수 있을까요;
SELECT AI 결혼 상태별로 고객 수가 어떻게 되는지 알고 싶어요;

-- 3-2. 집계 — showsql 로 SQL 을 먼저 보여주고, 같은 질문을 실행해 결과를 보여주는
--       2단 구성이 시연에서 잘 먹힌다.
SELECT AI showsql 2000년도의 총 판매량은 얼마인가요;
SELECT AI 2000년도의 총 판매량은 얼마인가요;

SELECT AI showsql 2001년도의 분기별 판매량을 알려주세요;
SELECT AI 2001년도의 분기별 판매량을 알려주세요;

SELECT AI showsql 각 판매 채널별 총 판매 금액이 얼마인지 알고 싶어요;
SELECT AI 각 판매 채널별 총 판매 금액이 얼마인지 알고 싶어요;

SELECT AI showsql 가장 많이 팔린 상위 5개 제품의 이름과 판매량은 무엇인가요;
SELECT AI 가장 많이 팔린 상위 5개 제품의 이름과 판매량은 무엇인가요;

-- 3-3. 조인이 필요한 질문 — FK 를 프롬프트에 실어 보낸 효과가 드러나는 자리
SELECT AI showsql 각 도시별로 평균 판매 금액이 얼마인지 알고 싶어요;
SELECT AI showsql 총 구매 금액이 100000을 초과한 고객의 이름과 구매 금액을 알고 싶어요;

-- 3-4. 분석함수 — LLM 이 RANK/윈도우 함수를 쓰는지 본다
SELECT AI showsql 각 상품별 총 매출과 매출 순위는 무엇인가요;
SELECT AI narrate 각 상품별 총 매출과 매출 순위는 무엇인가요;
SELECT AI showsql 각 상품별 누적 매출과 전체 매출 대비 해당 상품의 누적 매출 비율은 무엇인가요;

-- ⚠ 아래는 SALES 전체(약 92만 행)를 훑어 시연 중 30초 이상 걸린다. 시간 여유가 있을 때만.
-- SELECT AI 상품 카테고리별 총 매출과 평균 판매 가격은 얼마인가요;


-- =============================================================================
-- §4. ★ Annotation 효과 — 이 데모의 핵심
-- =============================================================================
-- 프로필의 "annotations": true 는 스키마에 새겨진 한국어 설명을 프롬프트에 실어 준다.
-- 붙였다 떼면서 같은 질문의 SQL 이 어떻게 달라지는지 보는 것이 이 절의 목적이다.
--
-- ⚠ 이 절은 스키마를 실제로 바꾼다. 앱이 같은 DB 를 보고 있다면 앱 화면에도 반영된다.
--   반드시 4-5 까지 끝내 원상 복구할 것.

-- 4-1. 지금 붙어 있는 설명 (기대: 59건)
SELECT object_name, NVL(column_name,'(table)') AS col, annotation_value
FROM   user_annotations_usage
WHERE  annotation_name = 'DISPLAY' AND object_name = 'CUSTOMERS'
ORDER  BY column_name NULLS FIRST;

-- 4-2. Annotation 이 있는 상태의 프롬프트와 SQL — 이 결과를 화면에 남겨 둔다
SELECT AI showprompt 신용한도가 높은 고객 5명을 알려주세요;
SELECT AI showsql   신용한도가 높은 고객 5명을 알려주세요;

-- 4-3. 전부 제거
DECLARE
    v_cnt PLS_INTEGER := 0;
BEGIN
    FOR t IN (SELECT column_value AS tab FROM TABLE(sys.odcivarchar2list(
                  'CHANNELS','COUNTRIES','CUSTOMERS','PRODUCTS',
                  'PROMOTIONS','TIMES','COSTS','SALES'))) LOOP
        FOR c IN (SELECT DISTINCT column_name FROM user_annotations_usage
                  WHERE object_name = t.tab AND annotation_name = 'DISPLAY'
                    AND column_name IS NOT NULL) LOOP
            BEGIN
                EXECUTE IMMEDIATE 'ALTER TABLE ' || t.tab || ' MODIFY (' ||
                                  c.column_name || ' ANNOTATIONS (DROP Display))';
                v_cnt := v_cnt + 1;
            EXCEPTION WHEN OTHERS THEN
                DBMS_OUTPUT.PUT_LINE('  FAIL ' || t.tab || '.' || c.column_name || ': ' || SQLERRM);
            END;
        END LOOP;
        BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE ' || t.tab || ' ANNOTATIONS (DROP Display)';
            v_cnt := v_cnt + 1;
        EXCEPTION WHEN OTHERS THEN NULL;   -- 테이블 레벨이 없을 수 있다 (정상)
        END;
    END LOOP;
    DBMS_OUTPUT.PUT_LINE('annotations removed=' || v_cnt);
END;
/

SELECT COUNT(*) AS remaining FROM user_annotations_usage WHERE annotation_name = 'DISPLAY';
-- 기대: 0

-- 4-4. 같은 질문을 다시 — 4-2 와 나란히 놓고 비교한다
--      · 프롬프트에서 ANNOTATIONS(...) 가 사라진 것
--      · 컬럼 선택·별칭이 달라지는지 (CUST_CREDIT_LIMIT 의 의미를 몰라 다른 컬럼을 고르기도 한다)
SELECT AI showprompt 신용한도가 높은 고객 5명을 알려주세요;
SELECT AI showsql   신용한도가 높은 고객 5명을 알려주세요;

-- 4-5. ★ 원상 복구 — 51_selectai_adb_setup.sql 의 §5 블록을 다시 실행한다.
--      (목록 정본은 web/src/lib/annotations.ts 이고 51번 §5 가 그것을 담고 있다)
SELECT COUNT(*) AS restored FROM user_annotations_usage WHERE annotation_name = 'DISPLAY';
-- 기대: 59


-- =============================================================================
-- §5. 대화 이어가기 — "conversation": true
-- =============================================================================
-- 직전 문답이 프롬프트에 누적되므로 대명사로 이어 물을 수 있다.
-- 순서대로 실행해야 의미가 있다.
SELECT AI 판매 채널별 총 판매 금액을 알려주세요;
SELECT AI 그 중에서 금액이 가장 큰 채널만 보여주세요;
SELECT AI showprompt 그 중에서 금액이 가장 큰 채널만 보여주세요;
-- ★ 마지막 showprompt 에서 앞선 질문과 답변이 messages 배열에 쌓여 있는 것을 확인한다.


-- =============================================================================
-- §6. 함수 호출 형태 — 앱이 축약구문을 쓰지 않는 이유
-- =============================================================================
-- 축약구문은 세션에 SET_PROFILE 이 되어 있어야 한다. 그런데 웹 앱은 커넥션 풀을 쓰고,
-- 요청마다 다른 세션이 배정되므로 SET_PROFILE 한 세션으로 다시 돌아온다는 보장이 없다.
-- → 실제로 ORA-20046 (AI profile is not enabled in the session) 이 났다.
-- 그래서 앱(app/select_ai.py)은 매 호출에 profile_name 을 명시하는 함수 형태를 쓴다.
DECLARE
    v_result CLOB;
BEGIN
    v_result := DBMS_CLOUD_AI.GENERATE(
        prompt       => 'Mouse Pad의 월별 판매량은 얼마인가요',
        profile_name => 'GEMINI_SH_PROFILE',   -- 세션 설정과 무관하게 매번 지정
        action       => 'showsql');
    DBMS_OUTPUT.PUT_LINE(v_result);
END;
/


-- =============================================================================
-- §7. 실행계획 · 프로필 전환
-- =============================================================================
-- 7-1. 생성된 SQL 의 실행계획 — Select AI 기능은 아니지만 "이 SQL 이 쓸 만한가"를
--      보여주는 자리다. 위 showsql 결과를 붙여 넣어 실행한다.
EXPLAIN PLAN FOR
SELECT p."PROD_NAME", SUM(s."AMOUNT_SOLD") AS "총_매출"
FROM   "ADMIN"."SALES" s
JOIN   "ADMIN"."PRODUCTS" p ON s."PROD_ID" = p."PROD_ID"
GROUP  BY p."PROD_NAME"
ORDER  BY 2 DESC
FETCH FIRST 5 ROWS ONLY;

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY());

-- 7-2. LLM 을 바꿔 같은 질문을 던져 본다 (모델별 SQL 품질 비교)
EXEC DBMS_CLOUD_AI.SET_PROFILE('GROQ_SH_PROFILE');
SELECT AI showsql 가장 많이 팔린 상위 5개 제품의 이름과 판매량은 무엇인가요;
-- ⚠ 2026-09-07 현재 이 프로필은 ORA-20404 (Object not found - bearer://api.groq.com/...)
--   로 실패한다. 네트워크 ACL 은 정상이므로(51번 §6-2) 원인은 GROQ_CRED 의 API 키다.
--   → 키를 재발급해 51번 §3 의 GROQ_CRED 만 다시 만든다.

-- 7-3. 원래 프로필로 복귀
EXEC DBMS_CLOUD_AI.SET_PROFILE('GEMINI_SH_PROFILE');

-- 7-4. 최근에 어떤 SQL 이 돌았나 (앱의 「실행 쿼리 확인」 패널과 같은 소스)
SELECT sql_id, ROUND(elapsed_time/1000) AS elapsed_ms, executions, sql_text
FROM   v$sql
WHERE  parsing_schema_name = USER
  AND  UPPER(sql_text) LIKE '%ADMIN%"SALES"%'
  AND  sql_text NOT LIKE '%v$sql%'
ORDER  BY last_active_time DESC
FETCH FIRST 10 ROWS ONLY;
