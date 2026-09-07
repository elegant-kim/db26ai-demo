-- =============================================================================
-- 53_selectai_adb_teardown.sql — Select AI 환경 원복 (Autonomous Database 전용)
-- =============================================================================
-- 목적 : 51_selectai_adb_setup.sql 이 만든 것을 되돌린다.
--        반복 시연으로 상태가 지저분해졌을 때, 또는 다른 테넌시로 옮길 때 쓴다.
-- 대상 : ADMIN 으로 접속. §1 → §4 순서로, 필요한 절만 골라 실행한다.
--
-- ▣ 위험도 순서 (위가 안전)
--   §1 AI 프로필 삭제        — 되돌리기 쉽다 (51번 §4 재실행)
--   §2 크리덴셜 삭제         — 되돌리려면 API 키가 다시 필요하다
--   §3 Annotation 제거       — 되돌리기 쉽다 (51번 §5 재실행)
--   §4 네트워크 ACL 회수     — 다른 기능(다른 프로필·DBMS_CLOUD 호출)도 같이 막힐 수 있다
--   §5 ADMIN 복제 테이블 삭제 — ⚠ 기본으로 주석 처리했다. 아래 경고를 읽고 직접 해제할 것
--
-- ⚠ 이 DB 를 앱(db26ai-demo)이 함께 쓰고 있다면 앱도 같이 망가진다.
--   §5 는 Property Graph · Duality View 등 다른 탭의 기반 테이블이기도 하다.
--
-- 2026-09-07 작성.
-- =============================================================================
SET SERVEROUTPUT ON
SET DEFINE OFF


-- =============================================================================
-- §0. 지우기 전에 현재 상태를 남긴다
-- =============================================================================
SELECT profile_name, status FROM user_cloud_ai_profiles ORDER BY profile_name;

SELECT credential_name, username, enabled
FROM   user_credentials
WHERE  credential_name IN ('GROQ_CRED','GEMINI_CRED');

SELECT COUNT(*) AS display_annotations
FROM   user_annotations_usage WHERE annotation_name = 'DISPLAY';

SELECT host, principal, privilege
FROM   dba_host_aces
WHERE  host IN ('api.groq.com','generativelanguage.googleapis.com')
ORDER  BY host, privilege;


-- =============================================================================
-- §1. AI 프로필 삭제
-- =============================================================================
-- 세션에 물려 있으면 먼저 푼다 (없어도 에러 나지 않는다)
BEGIN
    DBMS_CLOUD_AI.CLEAR_PROFILE;
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('clear_profile skip: ' || SQLERRM);
END;
/

-- 하나씩 지운다. 한 블록에 묶으면 첫 실패가 나머지를 막는다.
BEGIN
    DBMS_CLOUD_AI.DROP_PROFILE(profile_name => 'GROQ_SH_PROFILE');
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('GROQ_SH_PROFILE: ' || SQLERRM);
END;
/
BEGIN
    DBMS_CLOUD_AI.DROP_PROFILE(profile_name => 'GEMINI_SH_PROFILE');
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('GEMINI_SH_PROFILE: ' || SQLERRM);
END;
/

SELECT profile_name FROM user_cloud_ai_profiles ORDER BY profile_name;
-- 기대: 0행


-- =============================================================================
-- §2. 크리덴셜 삭제
--     ※ 되돌리려면 API 키를 다시 구해야 한다. 키를 잃어버렸다면 여기서 멈춘다.
-- =============================================================================
BEGIN
    DBMS_CLOUD.DROP_CREDENTIAL(credential_name => 'GROQ_CRED');
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('GROQ_CRED: ' || SQLERRM);
END;
/
BEGIN
    DBMS_CLOUD.DROP_CREDENTIAL(credential_name => 'GEMINI_CRED');
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('GEMINI_CRED: ' || SQLERRM);
END;
/


-- =============================================================================
-- §3. Display Annotation 제거
--     51번 §5 를 다시 돌리면 그대로 복구된다.
-- =============================================================================
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

SELECT COUNT(*) AS remaining
FROM   user_annotations_usage WHERE annotation_name = 'DISPLAY';
-- 기대: 0


-- =============================================================================
-- §4. 네트워크 ACL 회수
--     ⚠ 같은 호스트를 쓰는 다른 프로필·DBMS_CLOUD 호출도 함께 막힌다.
--       이 ADB 에서 Groq/Gemini 를 다른 용도로도 쓰고 있다면 건너뛴다.
-- =============================================================================
BEGIN
    DBMS_NETWORK_ACL_ADMIN.REMOVE_HOST_ACE(
        host       => 'api.groq.com',
        ace        => xs$ace_type(
                          privilege_list => xs$name_list('connect','resolve'),
                          principal_name => 'ADMIN',
                          principal_type => xs_acl.ptype_db),
        remove_empty_acl => TRUE);
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('groq ace: ' || SQLERRM);
END;
/

BEGIN
    DBMS_NETWORK_ACL_ADMIN.REMOVE_HOST_ACE(
        host       => 'generativelanguage.googleapis.com',
        ace        => xs$ace_type(
                          privilege_list => xs$name_list('connect','resolve'),
                          principal_name => 'ADMIN',
                          principal_type => xs_acl.ptype_db),
        remove_empty_acl => TRUE);
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('gemini ace: ' || SQLERRM);
END;
/

SELECT host, principal, privilege
FROM   dba_host_aces
WHERE  host IN ('api.groq.com','generativelanguage.googleapis.com')
ORDER  BY host, privilege;
-- 기대: 0행. 남아 있다면 위 privilege 목록이 실제 부여분과 달랐던 것이다
--       (예: 과거에 'http' 로 부여된 ACE 는 여기서 안 지워진다 → §0 결과를 보고 맞춰 지운다)


-- =============================================================================
-- §5. ADMIN 복제 테이블 삭제 — ⚠ 기본 비활성. 읽고 나서 직접 주석을 푼다
-- =============================================================================
-- 이 8개 테이블은 Select AI 만 쓰는 게 아니다. 같은 ADB 에서 앱(db26ai-demo)의
-- Property Graph · JSON Duality · 개발생산성 탭이 이 테이블들을 기반으로 돈다.
-- 지우면 그 탭들이 전부 깨지고, 복구하려면 51번 §1 을 다시 돌려야 한다(수 분 소요).
--
-- 정말 지우려면 아래 블록의 주석을 직접 해제할 것.
--
-- BEGIN
--     FOR t IN (SELECT table_name FROM user_tables
--               WHERE table_name IN ('CHANNELS','COSTS','COUNTRIES','CUSTOMERS',
--                                    'PRODUCTS','PROMOTIONS','SALES','TIMES')) LOOP
--         EXECUTE IMMEDIATE 'DROP TABLE ' || t.table_name || ' CASCADE CONSTRAINTS PURGE';
--         DBMS_OUTPUT.PUT_LINE('dropped: ' || t.table_name);
--     END LOOP;
-- END;
-- /
