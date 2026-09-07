-- =============================================================================
-- 51_selectai_adb_setup.sql — Select AI 환경 세팅 (Autonomous Database 전용)
-- =============================================================================
-- 목적 : 앱(web UI) 없이 SQLcl / SQL Developer 만으로 Select AI 데모 환경을 만든다.
-- 대상 : Oracle Autonomous AI Database (ADB-S). ADMIN 으로 접속해 위에서 아래로 실행.
-- 짝   : 52_selectai_adb_demo.sql (시연) · 53_selectai_adb_teardown.sql (원복)
--
-- ▣ 이 스크립트가 끝나면 만들어져 있는 것
--   1. ADMIN 스키마에 SH 샘플 8개 테이블 복제본 + PK/FK + 통계
--   2. 네트워크 ACL 2건 — api.groq.com · generativelanguage.googleapis.com
--   3. 크리덴셜 2개    — GROQ_CRED · GEMINI_CRED
--   4. AI 프로필 2개   — GROQ_SH_PROFILE · GEMINI_SH_PROFILE (둘 다 ADMIN 8개 테이블을 본다)
--   5. Display Annotation 59건 (한국어 설명 → LLM 프롬프트에 그대로 실린다)
--   6. §6 검증 쿼리가 위 다섯 가지를 한 번에 확인해 준다
--
-- ▣ 왜 SH 가 아니라 ADMIN 인가
--   ADB 의 SH 는 읽기 전용 샘플이라 ALTER TABLE ... ANNOTATIONS 가 안 된다.
--   Annotation 시연(§5, 52번 §4)을 하려면 쓰기 가능한 스키마로 복제해야 한다.
--   그래서 프로필의 object_list 도 ADMIN 을 가리킨다. §1 을 §4 보다 먼저 실행하는 이유다.
--
-- ⚠ 시크릿 : <...> 는 자리표시자다. 이 저장소는 GitHub 공개다.
--            <GROQ_API_KEY>   → https://console.groq.com/keys
--            <GOOGLE_API_KEY> → https://aistudio.google.com/apikey
--            값을 채운 사본은 sql/setup/_private/ (gitignore) 에 두고 거기서 실행한다.
--
-- ⚠ ADB 전용 : 온프레미스·Base DB 는 DBMS_CLOUD 계열이 기본 탑재가 아니라 수동 설치가
--            필요하다(26ai 23.7+ 동봉 스크립트 → C##CLOUD$SERVICE + 인증서 wallet).
--            이 스크립트는 그 경우를 다루지 않는다.
--
-- 2026-09-07 작성. 다른 환경에서 쓰던 selectAI_설정.sql 은 손대지 않고 그대로 둔다.
-- =============================================================================
SET SERVEROUTPUT ON
SET DEFINE OFF


-- =============================================================================
-- §0. 사전 확인 — 여기서 기대와 다르면 아래를 실행하지 말 것
-- =============================================================================
-- 0-1. ADB 인가, 버전은 26ai 인가
SELECT banner_full FROM v$version;

-- 0-2. 지금 누구로 붙어 있나 (ADMIN 이어야 한다)
SELECT USER AS db_user,
       SYS_CONTEXT('USERENV','CURRENT_SCHEMA') AS current_schema
FROM   dual;

-- 0-3. DBMS_CLOUD_AI 를 쓸 수 있나 (ADMIN 은 기본 보유)
SELECT COUNT(*) AS can_execute_dbms_cloud_ai
FROM   all_objects
WHERE  object_name = 'DBMS_CLOUD_AI' AND object_type = 'PACKAGE';

-- 0-4. 복제 원본인 SH 샘플 스키마가 있나 (0 이면 §1 을 실행할 수 없다 - ADB 프로비저닝 시
--      샘플 스키마를 포함시켰는지 확인할 것)
SELECT COUNT(*) AS sh_table_count FROM all_tables WHERE owner = 'SH';


-- =============================================================================
-- §1. SH → ADMIN 복제 (8개 테이블 + PK/FK + 통계)
--     ※ 프로필(§4)이 이 테이블들을 가리키므로 반드시 먼저 실행한다.
-- =============================================================================
-- 1-1. 기존 복제본 정리 (최초 실행 시 아무것도 안 지운다)
BEGIN
    FOR t IN (SELECT table_name FROM user_tables
              WHERE table_name IN ('CHANNELS','COSTS','COUNTRIES','CUSTOMERS',
                                   'PRODUCTS','PROMOTIONS','SALES','TIMES')) LOOP
        EXECUTE IMMEDIATE 'DROP TABLE ' || t.table_name || ' CASCADE CONSTRAINTS PURGE';
        DBMS_OUTPUT.PUT_LINE('dropped: ' || t.table_name);
    END LOOP;
END;
/

-- 1-2. 데이터 포함 복사 (차원 → 팩트 순서)
CREATE TABLE CHANNELS    AS SELECT * FROM SH.CHANNELS;
CREATE TABLE COUNTRIES   AS SELECT * FROM SH.COUNTRIES;
CREATE TABLE CUSTOMERS   AS SELECT * FROM SH.CUSTOMERS;
CREATE TABLE PRODUCTS    AS SELECT * FROM SH.PRODUCTS;
CREATE TABLE PROMOTIONS  AS SELECT * FROM SH.PROMOTIONS;
CREATE TABLE TIMES       AS SELECT * FROM SH.TIMES;
CREATE TABLE COSTS       AS SELECT * FROM SH.COSTS;
CREATE TABLE SALES       AS SELECT * FROM SH.SALES;

-- 1-3. PK
--      ※ SALES·COSTS 에는 PK 를 만들지 않는다(원본 SH 도 없다. 복합키 팩트 테이블).
ALTER TABLE CHANNELS   ADD CONSTRAINT PK_CHANNELS   PRIMARY KEY (CHANNEL_ID);
ALTER TABLE COUNTRIES  ADD CONSTRAINT PK_COUNTRIES  PRIMARY KEY (COUNTRY_ID);
ALTER TABLE CUSTOMERS  ADD CONSTRAINT PK_CUSTOMERS  PRIMARY KEY (CUST_ID);
ALTER TABLE PRODUCTS   ADD CONSTRAINT PK_PRODUCTS   PRIMARY KEY (PROD_ID);
ALTER TABLE PROMOTIONS ADD CONSTRAINT PK_PROMOTIONS PRIMARY KEY (PROMO_ID);
ALTER TABLE TIMES      ADD CONSTRAINT PK_TIMES      PRIMARY KEY (TIME_ID);

-- 1-4. FK — 프로필 속성 "constraints": true 가 이 관계를 프롬프트에 실어 준다.
--      FK 가 없으면 LLM 이 조인 키를 추측해야 하고, 그때부터 SQL 품질이 흔들린다.
ALTER TABLE SALES ADD CONSTRAINT FK_SALES_CUST  FOREIGN KEY (CUST_ID)    REFERENCES CUSTOMERS(CUST_ID);
ALTER TABLE SALES ADD CONSTRAINT FK_SALES_PROD  FOREIGN KEY (PROD_ID)    REFERENCES PRODUCTS(PROD_ID);
ALTER TABLE SALES ADD CONSTRAINT FK_SALES_TIME  FOREIGN KEY (TIME_ID)    REFERENCES TIMES(TIME_ID);
ALTER TABLE SALES ADD CONSTRAINT FK_SALES_CHAN  FOREIGN KEY (CHANNEL_ID) REFERENCES CHANNELS(CHANNEL_ID);
ALTER TABLE SALES ADD CONSTRAINT FK_SALES_PROMO FOREIGN KEY (PROMO_ID)   REFERENCES PROMOTIONS(PROMO_ID);
ALTER TABLE COSTS ADD CONSTRAINT FK_COSTS_PROD  FOREIGN KEY (PROD_ID)    REFERENCES PRODUCTS(PROD_ID);
ALTER TABLE COSTS ADD CONSTRAINT FK_COSTS_TIME  FOREIGN KEY (TIME_ID)    REFERENCES TIMES(TIME_ID);

-- 1-5. 통계 수집
BEGIN
    FOR t IN (SELECT column_value AS tab FROM TABLE(sys.odcivarchar2list(
                  'CHANNELS','COUNTRIES','CUSTOMERS','PRODUCTS',
                  'PROMOTIONS','TIMES','COSTS','SALES'))) LOOP
        DBMS_STATS.GATHER_TABLE_STATS(USER, t.tab);
    END LOOP;
END;
/


-- =============================================================================
-- §2. 네트워크 ACL — DB 가 LLM 엔드포인트로 아웃바운드 호출을 할 수 있게 한다
--     없으면 GENERATE 호출이 ORA-24247 (network access denied) 로 죽는다.
-- =============================================================================
-- 아웃바운드에 필요한 권한은 connect(접속) 과 resolve(DNS) 두 개다.
-- (참고: 'http' 는 XDB 인바운드용이라 여기서는 불필요하다. 옛 스크립트가 groq 에
--        'http' 만 줬던 것은 잘못이고, 그래서 두 호스트 설정이 비대칭이었다.)

BEGIN
    DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE(
        host => 'api.groq.com',
        ace  => xs$ace_type(
            privilege_list => xs$name_list('connect','resolve'),
            principal_name => 'ADMIN',              -- 대소문자 구분한다. 소문자면 안 붙는다
            principal_type => xs_acl.ptype_db));
END;
/

BEGIN
    DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE(
        host => 'generativelanguage.googleapis.com',
        ace  => xs$ace_type(
            privilege_list => xs$name_list('connect','resolve'),
            principal_name => 'ADMIN',
            principal_type => xs_acl.ptype_db));
END;
/


-- =============================================================================
-- §3. 크리덴셜 — LLM API 키를 DB 안에 보관한다
--     OpenAI 호환 엔드포인트는 username 에 아무 라벨, password 에 API 키를 넣는다.
-- =============================================================================

-- 3-1. 기존 크리덴셜 제거 (없으면 사유를 찍고 넘어간다 — 조용히 삼키지 않는다)

BEGIN
    DBMS_CLOUD.DROP_CREDENTIAL(credential_name => 'GROQ_CRED');
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('GROQ_CRED drop skip: ' || SQLERRM);
END;
/
BEGIN
    DBMS_CLOUD.DROP_CREDENTIAL(credential_name => 'GEMINI_CRED');
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('GEMINI_CRED drop skip: ' || SQLERRM);
END;
/

-- 3-2. 생성
BEGIN
    DBMS_CLOUD.CREATE_CREDENTIAL(
        credential_name => 'GROQ_CRED',
        username        => 'GROQ',
        password        => '<GROQ_API_KEY>');
END;
/
BEGIN
    DBMS_CLOUD.CREATE_CREDENTIAL(
        credential_name => 'GEMINI_CRED',
        username        => 'GEMINI',
        password        => '<GOOGLE_API_KEY>');
END;
/


-- =============================================================================
-- §4. AI 프로필 — "어느 LLM 이 어느 테이블을 보는가"의 정의
-- =============================================================================
-- provider "openai" + provider_endpoint 조합이 이 데모의 핵심이다.
-- Groq·Gemini 모두 OpenAI 호환 API 를 내주므로, OCI GenAI 를 쓰지 않고도 붙는다.
--
-- 속성 4개가 프롬프트 품질을 좌우한다 (52번 §4 에서 효과를 눈으로 확인한다):
--   annotations  : ALTER TABLE ... ANNOTATIONS 로 붙인 한국어 설명을 프롬프트에 포함
--   comments     : COMMENT ON 주석 포함
--   constraints  : PK/FK 를 포함 → 조인 키를 추측하지 않게 된다
--   conversation : 직전 문답을 프롬프트에 누적 → 멀티턴("그 중 상위 3개는?")이 된다

-- 4-1. 기존 프로필 제거 — 반드시 하나씩. 한 블록에 묶으면 첫 실패가 나머지를 막는다.
BEGIN
    DBMS_CLOUD_AI.DROP_PROFILE(profile_name => 'GROQ_SH_PROFILE');
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('GROQ_SH_PROFILE drop skip: ' || SQLERRM);
END;
/
BEGIN
    DBMS_CLOUD_AI.DROP_PROFILE(profile_name => 'GEMINI_SH_PROFILE');
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('GEMINI_SH_PROFILE drop skip: ' || SQLERRM);
END;
/

-- 4-2. Groq (Llama 3.3 70B)
BEGIN
    DBMS_CLOUD_AI.CREATE_PROFILE(
        profile_name => 'GROQ_SH_PROFILE',
        attributes   => '{
            "provider": "openai",
            "credential_name": "GROQ_CRED",
            "model": "llama-3.3-70b-versatile",
            "provider_endpoint": "https://api.groq.com/openai/v1",
            "object_list": [
              {"owner": "ADMIN","name":"CHANNELS"},
              {"owner": "ADMIN","name":"COSTS"},
              {"owner": "ADMIN","name":"COUNTRIES"},
              {"owner": "ADMIN","name":"CUSTOMERS"},
              {"owner": "ADMIN","name":"PRODUCTS"},
              {"owner": "ADMIN","name":"PROMOTIONS"},
              {"owner": "ADMIN","name":"SALES"},
              {"owner": "ADMIN","name":"TIMES"}
            ],
            "annotations": true,
            "comments": true,
            "constraints": true,
            "conversation": true
        }');
END;
/

-- 4-3. Google Gemini 2.5 Flash
BEGIN
    DBMS_CLOUD_AI.CREATE_PROFILE(
        profile_name => 'GEMINI_SH_PROFILE',
        attributes   => '{
            "provider": "openai",
            "credential_name": "GEMINI_CRED",
            "model": "gemini-2.5-flash",
            "provider_endpoint": "https://generativelanguage.googleapis.com/v1beta/openai/v1",
            "object_list": [
              {"owner": "ADMIN","name":"CHANNELS"},
              {"owner": "ADMIN","name":"COSTS"},
              {"owner": "ADMIN","name":"COUNTRIES"},
              {"owner": "ADMIN","name":"CUSTOMERS"},
              {"owner": "ADMIN","name":"PRODUCTS"},
              {"owner": "ADMIN","name":"PROMOTIONS"},
              {"owner": "ADMIN","name":"SALES"},
              {"owner": "ADMIN","name":"TIMES"}
            ],
            "annotations": true,
            "comments": true,
            "constraints": true,
            "conversation": true
        }');
END;
/


-- =============================================================================
-- §5. Display Annotation 59건 — 한국어 컬럼 설명을 스키마에 새긴다
-- =============================================================================
-- 프로필의 "annotations": true 는 이게 있어야 의미가 있다. 붙이면 LLM 이
-- "CUST_CREDIT_LIMIT" 을 "신용한도(USD)"로 이해한다 → 한국어 질문 정답률이 올라간다.
--
-- ⚠ 2026-09-07 실측: ANNOTATIONS(ADD Display ...) 는 기존 값을 덮어쓰지 않고
--   같은 컬럼에 DISPLAY 를 하나 더 만든다(중복 누적). 반드시 DROP 후 ADD 한다.
--   DROP Display 는 그 컬럼의 DISPLAY 를 전부 지운다.
--
-- 목록 정본은 web/src/lib/annotations.ts 의 SH 세트다. 아래는 거기서 생성한 것이므로
-- 내용을 바꿀 때는 그쪽을 먼저 고치고 이 블록을 다시 만든다.
DECLARE
    TYPE r_ann IS RECORD (tab VARCHAR2(128), col VARCHAR2(128), txt VARCHAR2(400));
    TYPE t_ann IS TABLE OF r_ann;
    v_list  t_ann;
    v_owner VARCHAR2(128) := USER;
    v_ok    PLS_INTEGER := 0;
    v_err   PLS_INTEGER := 0;

    PROCEDURE put(p_tab VARCHAR2, p_col VARCHAR2, p_txt VARCHAR2) IS
        v_fqn  VARCHAR2(300) := v_owner || '.' || p_tab;
        v_safe VARCHAR2(800) := REPLACE(p_txt, '''', '''''');
    BEGIN
        BEGIN
            IF p_col IS NULL THEN
                EXECUTE IMMEDIATE 'ALTER TABLE ' || v_fqn || ' ANNOTATIONS (DROP Display)';
            ELSE
                EXECUTE IMMEDIATE 'ALTER TABLE ' || v_fqn || ' MODIFY (' || p_col ||
                                  ' ANNOTATIONS (DROP Display))';
            END IF;
        EXCEPTION WHEN OTHERS THEN NULL;  -- 아직 없으면 지울 것도 없다 (정상 경로)
        END;

        IF p_col IS NULL THEN
            EXECUTE IMMEDIATE 'ALTER TABLE ' || v_fqn ||
                              ' ANNOTATIONS (ADD Display ''' || v_safe || ''')';
        ELSE
            EXECUTE IMMEDIATE 'ALTER TABLE ' || v_fqn || ' MODIFY (' || p_col ||
                              ' ANNOTATIONS (ADD Display ''' || v_safe || '''))';
        END IF;
        v_ok := v_ok + 1;
    EXCEPTION WHEN OTHERS THEN
        v_err := v_err + 1;
        DBMS_OUTPUT.PUT_LINE('  FAIL ' || p_tab || '.' || NVL(p_col,'(table)') || ': ' || SQLERRM);
    END put;
BEGIN
    v_list := t_ann(
    r_ann('CUSTOMERS', NULL, '고객 마스터 테이블 - 인구통계 및 신용정보 포함'),
    r_ann('CUSTOMERS', 'CUST_ID', '고객 고유 식별자 (PK)'),
    r_ann('CUSTOMERS', 'CUST_FIRST_NAME', '고객 이름 (First Name)'),
    r_ann('CUSTOMERS', 'CUST_LAST_NAME', '고객 성 (Last Name)'),
    r_ann('CUSTOMERS', 'CUST_GENDER', '성별: M=Male, F=Female'),
    r_ann('CUSTOMERS', 'CUST_YEAR_OF_BIRTH', '출생연도 (4자리)'),
    r_ann('CUSTOMERS', 'CUST_MARITAL_STATUS', '결혼상태: married, single 등'),
    r_ann('CUSTOMERS', 'CUST_STREET_ADDRESS', '거주지 주소'),
    r_ann('CUSTOMERS', 'CUST_POSTAL_CODE', '우편번호'),
    r_ann('CUSTOMERS', 'CUST_CITY', '거주 도시'),
    r_ann('CUSTOMERS', 'CUST_STATE_PROVINCE', '거주 주/도'),
    r_ann('CUSTOMERS', 'CUST_MAIN_PHONE_NUMBER', '주요 전화번호'),
    r_ann('CUSTOMERS', 'CUST_INCOME_LEVEL', '소득구간: A: Under 30,000 ~ L: 300,000 and above'),
    r_ann('CUSTOMERS', 'CUST_CREDIT_LIMIT', '신용한도 (USD)'),
    r_ann('CUSTOMERS', 'CUST_EMAIL', '이메일 주소'),
    r_ann('CUSTOMERS', 'CUST_VALID', '고객 유효 상태: A=Active, I=Inactive'),
    r_ann('SALES', NULL, '판매 트랜잭션 팩트 테이블'),
    r_ann('SALES', 'PROD_ID', '제품 ID (FK: PRODUCTS.PROD_ID)'),
    r_ann('SALES', 'CUST_ID', '고객 ID (FK: CUSTOMERS.CUST_ID)'),
    r_ann('SALES', 'TIME_ID', '판매 일자 (FK: TIMES.TIME_ID)'),
    r_ann('SALES', 'CHANNEL_ID', '판매 채널 ID (FK: CHANNELS.CHANNEL_ID)'),
    r_ann('SALES', 'PROMO_ID', '프로모션 ID (FK: PROMOTIONS.PROMO_ID)'),
    r_ann('SALES', 'QUANTITY_SOLD', '판매 수량'),
    r_ann('SALES', 'AMOUNT_SOLD', '판매 금액 (USD)'),
    r_ann('PRODUCTS', NULL, '제품 마스터 테이블'),
    r_ann('PRODUCTS', 'PROD_ID', '제품 고유 식별자 (PK)'),
    r_ann('PRODUCTS', 'PROD_NAME', '제품명'),
    r_ann('PRODUCTS', 'PROD_DESC', '제품 설명'),
    r_ann('PRODUCTS', 'PROD_SUBCATEGORY', '제품 소분류'),
    r_ann('PRODUCTS', 'PROD_CATEGORY', '제품 대분류'),
    r_ann('PRODUCTS', 'PROD_STATUS', '제품 상태: Status 값으로 활성여부 판단'),
    r_ann('PRODUCTS', 'PROD_LIST_PRICE', '정가 (USD)'),
    r_ann('PRODUCTS', 'PROD_MIN_PRICE', '최저가 (USD)'),
    r_ann('CHANNELS', NULL, '판매 채널 (Direct Sales, Internet, Catalog, Partners)'),
    r_ann('CHANNELS', 'CHANNEL_ID', '채널 고유 식별자 (PK)'),
    r_ann('CHANNELS', 'CHANNEL_DESC', '채널명: Direct Sales, Internet, Catalog, Partners'),
    r_ann('CHANNELS', 'CHANNEL_CLASS', '채널 분류: Direct, Indirect, Others'),
    r_ann('TIMES', NULL, '시간 차원 테이블 (1998~2001년)'),
    r_ann('TIMES', 'TIME_ID', '날짜 (PK)'),
    r_ann('TIMES', 'DAY_NAME', '요일명 (Monday~Sunday)'),
    r_ann('TIMES', 'CALENDAR_MONTH_DESC', '월 (예: 2000-01)'),
    r_ann('TIMES', 'CALENDAR_QUARTER_DESC', '분기 (예: 2000-Q1)'),
    r_ann('TIMES', 'CALENDAR_YEAR', '연도 (예: 2000)'),
    r_ann('TIMES', 'FISCAL_YEAR', '회계연도'),
    r_ann('PROMOTIONS', NULL, '프로모션 정보'),
    r_ann('PROMOTIONS', 'PROMO_ID', '프로모션 ID (PK)'),
    r_ann('PROMOTIONS', 'PROMO_NAME', '프로모션명'),
    r_ann('PROMOTIONS', 'PROMO_SUBCATEGORY', '프로모션 소분류'),
    r_ann('PROMOTIONS', 'PROMO_CATEGORY', '프로모션 대분류'),
    r_ann('COUNTRIES', NULL, '국가 정보 (고객 국가 참조)'),
    r_ann('COUNTRIES', 'COUNTRY_ID', '국가 ID (PK)'),
    r_ann('COUNTRIES', 'COUNTRY_NAME', '국가명'),
    r_ann('COUNTRIES', 'COUNTRY_REGION', '대륙/지역 (Americas, Europe, Asia 등)'),
    r_ann('COUNTRIES', 'COUNTRY_SUBREGION', '세부지역'),
    r_ann('COSTS', NULL, '제품 원가 테이블'),
    r_ann('COSTS', 'PROD_ID', '제품 ID (FK)'),
    r_ann('COSTS', 'TIME_ID', '날짜 (FK)'),
    r_ann('COSTS', 'UNIT_COST', '단위 원가 (USD)'),
    r_ann('COSTS', 'UNIT_PRICE', '단위 판매가 (USD)')
    );

    FOR i IN 1 .. v_list.COUNT LOOP
        put(v_list(i).tab, v_list(i).col, v_list(i).txt);
    END LOOP;
    DBMS_OUTPUT.PUT_LINE('annotations applied=' || v_ok || ' failed=' || v_err);
END;
/


-- =============================================================================
-- §6. 검증 — 여기까지 전부 통과해야 52번(시연)으로 넘어간다
-- =============================================================================
-- 6-1. 복제 테이블 8개와 행 수
SELECT table_name, num_rows
FROM   user_tables
WHERE  table_name IN ('CHANNELS','COSTS','COUNTRIES','CUSTOMERS',
                      'PRODUCTS','PROMOTIONS','SALES','TIMES')
ORDER  BY table_name;
-- 기대: 8행. 2026-09-07 실측 기준선 —
--   CHANNELS 5 · COUNTRIES 23 · PRODUCTS 72 · PROMOTIONS 503 · TIMES 1,826
--   COSTS 82,112 · CUSTOMERS 55,500 · SALES 918,843

-- 6-2. 네트워크 ACL — 두 호스트가 대칭이어야 한다
SELECT host, principal, privilege
FROM   dba_host_aces
WHERE  host IN ('api.groq.com','generativelanguage.googleapis.com')
ORDER  BY host, privilege;
-- 기대: 호스트별로 CONNECT · RESOLVE (principal = ADMIN), 총 4행.
--   ※ 이 데모 ADB 에는 과거 작업 때문에 HTTP 도 함께 부여돼 있어 6행이 나온다.
--     HTTP 는 XDB 인바운드용이라 아웃바운드 호출과 무관하다 — 있어도 문제 없다.

-- 6-3. 크리덴셜
SELECT credential_name, username, enabled
FROM   user_credentials
WHERE  credential_name IN ('GROQ_CRED','GEMINI_CRED')
ORDER  BY credential_name;
-- 기대: 2행, enabled=TRUE
-- ⚠ enabled=TRUE 는 "키가 유효하다"는 뜻이 아니다. 키가 만료돼도 TRUE 로 보인다.
--   실제 유효성은 6-6 의 호출로만 확인된다.

-- 6-4. AI 프로필
SELECT profile_name, status FROM user_cloud_ai_profiles ORDER BY profile_name;
-- 기대: GEMINI_SH_PROFILE · GROQ_SH_PROFILE 2행

SELECT profile_name, attribute_name, attribute_value
FROM   user_cloud_ai_profile_attributes
WHERE  profile_name = 'GEMINI_SH_PROFILE'
ORDER  BY attribute_name;
-- 기대: 9행 (provider · credential_name · model · provider_endpoint · object_list
--             · annotations · comments · constraints · conversation)

-- 6-5. Annotation — 개수와 중복 여부
SELECT COUNT(*) AS display_annotations
FROM   user_annotations_usage
WHERE  annotation_name = 'DISPLAY';
-- 기대: 59

SELECT object_name, NVL(column_name,'(table)') AS col, COUNT(*) AS dup
FROM   user_annotations_usage
WHERE  annotation_name = 'DISPLAY'
GROUP  BY object_name, column_name
HAVING COUNT(*) > 1;
-- 기대: 0행. 행이 나오면 DROP 없이 ADD 를 두 번 돌린 것이다 (§5 주의 참조)

-- 6-6. 실제 호출 — 여기까지 오면 세팅이 끝난 것이다
SET SERVEROUTPUT ON
DECLARE
    v_result CLOB;
BEGIN
    v_result := DBMS_CLOUD_AI.GENERATE(
        prompt       => '고객이 몇 명인가요',
        profile_name => 'GEMINI_SH_PROFILE',
        action       => 'showsql');
    DBMS_OUTPUT.PUT_LINE(v_result);
END;
/
-- 기대: "ADMIN"."CUSTOMERS" 를 세는 SELECT 문.
-- ORA-20404 (Object not found - bearer://...) 가 나오면 API 키가 잘못된 것이다 →
--   §3 에서 해당 크리덴셜만 다시 만든다. ACL 문제가 아니다(6-2 가 이미 통과했으므로).
-- ORA-24247 이 나오면 ACL 문제다 → §2 를 다시 본다.
