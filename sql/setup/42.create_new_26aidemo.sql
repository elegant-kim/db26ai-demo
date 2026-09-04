-- ⚠️ 이 파일은 시크릿이 제거된 공개 버전입니다 (2026-09-04 정제).
-- <...> 자리표시자의 실제 값은 저장소에 없습니다:
--   <GROQ_API_KEY> / <GOOGLE_API_KEY>  → .env 의 GROQ_API_KEY / GOOGLE_API_KEY
--   <OCI_*> / <TENANCY_OCID> / <USER_OCID> / <FINGERPRINT> / <OS_NAMESPACE>
--                                      → OCI 콘솔에서 확인·재발급
-- 원본(시크릿 포함)은 sql/setup/_private/ 에 있으며 .gitignore 로 제외됩니다.
--
-- Step 1. Credential 생성
--신규 테넌시의 Object Storage에 접근하기 위한 인증 정보
BEGIN
    DBMS_CLOUD.CREATE_CREDENTIAL(
        credential_name => 'MIGRATION_CRED',
        username        => '<OCI_ACCOUNT_EMAIL>',   -- 신규 테넌시 로그인 이메일
        password        => '<OCI_AUTH_TOKEN>'            -- Step 2에서 생성한 토큰
    );
END;
/

-- Step 2. Import 실행
DECLARE
    l_dp_handle NUMBER;
BEGIN
    l_dp_handle := DBMS_DATAPUMP.OPEN(
        operation   => 'IMPORT',
        job_mode    => 'TABLE',
        remote_link => NULL,
        job_name    => 'DB26AI_IMPORT'
    );

    DBMS_DATAPUMP.ADD_FILE(
        handle    => l_dp_handle,
        filename  => 'https://objectstorage.ap-chuncheon-1.oraclecloud.com/n/<OS_NAMESPACE>/b/investhub-migration/o/db26ai_export_%U.dmp',
        directory => 'MIGRATION_CRED',
        filetype  => DBMS_DATAPUMP.KU$_FILE_TYPE_URIDUMP_FILE
    );

    DBMS_DATAPUMP.ADD_FILE(
        handle    => l_dp_handle,
        filename  => 'db26ai_import.log',
        directory => 'DATA_PUMP_DIR',
        filetype  => DBMS_DATAPUMP.KU$_FILE_TYPE_LOG_FILE
    );

    DBMS_DATAPUMP.SET_PARAMETER(
        handle => l_dp_handle,
        name   => 'TABLE_EXISTS_ACTION',
        value  => 'REPLACE'
    );

    DBMS_DATAPUMP.START_JOB(handle => l_dp_handle);
    DBMS_DATAPUMP.DETACH(handle => l_dp_handle);
END;
/

-- Step 3. 진행 상태 확인
SELECT job_name, state FROM DBA_DATAPUMP_JOBS;

-- 완료 후 검증:
SELECT table_name, num_rows FROM all_tables 
WHERE owner = 'ADMIN' ORDER BY table_name;

-- Step 4. Data Pump 이후 재설정 (신규 LH, ADMIN으로)
-- 4-1. Network ACL
BEGIN
    DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE(
        host => 'api.groq.com',
        ace  => xs$ace_type(
            privilege_list => xs$name_list('http','connect','resolve'),
            principal_name => 'ADMIN',
            principal_type => xs_acl.ptype_db));
END;
/

BEGIN
    DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE(
        host => 'generativelanguage.googleapis.com',
        ace  => xs$ace_type(
            privilege_list => xs$name_list('http','connect','resolve'),
            principal_name => 'ADMIN',
            principal_type => xs_acl.ptype_db));
END;
/

-- 4-2. Credential 생성 (신규 LH, ADMIN으로)
BEGIN
    DBMS_CLOUD.CREATE_CREDENTIAL(
        credential_name => 'GROQ_CRED',
        username => 'GROQ',
        password => '<GROQ_API_KEY>'
    );
END;
/

BEGIN
    DBMS_CLOUD.CREATE_CREDENTIAL(
        credential_name => 'GEMINI_CRED',
        username => 'GEMINI',
        password => '<GOOGLE_API_KEY>'
    );
END;
/

-- 4.3 Select AI Profiles (SH용 2개)
BEGIN
    DBMS_CLOUD_AI.CREATE_PROFILE(
        profile_name => 'GROQ_SH_PROFILE',
        attributes => '{
            "provider": "openai",
            "credential_name": "GROQ_CRED",
            "model": "llama-3.3-70b-versatile",
            "provider_endpoint": "https://api.groq.com/openai/v1",
            "object_list": [
              {"owner":"ADMIN","name":"CHANNELS"},
              {"owner":"ADMIN","name":"COSTS"},
              {"owner":"ADMIN","name":"COUNTRIES"},
              {"owner":"ADMIN","name":"CUSTOMERS"},
              {"owner":"ADMIN","name":"PRODUCTS"},
              {"owner":"ADMIN","name":"PROMOTIONS"},
              {"owner":"ADMIN","name":"SALES"},
              {"owner":"ADMIN","name":"TIMES"}
            ],
            "annotations": true, "comments": true,
            "constraints": true, "conversation": true
        }');
END;
/

BEGIN
    DBMS_CLOUD_AI.CREATE_PROFILE(
        profile_name => 'GEMINI_SH_PROFILE',
        attributes => '{
            "provider": "openai",
            "credential_name": "GEMINI_CRED",
            "model": "gemini-2.5-flash",
            "provider_endpoint": "https://generativelanguage.googleapis.com/v1beta/openai/v1",
            "object_list": [
              {"owner":"ADMIN","name":"CHANNELS"},
              {"owner":"ADMIN","name":"COSTS"},
              {"owner":"ADMIN","name":"COUNTRIES"},
              {"owner":"ADMIN","name":"CUSTOMERS"},
              {"owner":"ADMIN","name":"PRODUCTS"},
              {"owner":"ADMIN","name":"PROMOTIONS"},
              {"owner":"ADMIN","name":"SALES"},
              {"owner":"ADMIN","name":"TIMES"}
            ],
            "annotations": true, "comments": true,
            "constraints": true, "conversation": true
        }');
END;
/

-- 
-- 4.4 ONNX 모델은 OCI Object Storage에서 다시 로드
DECLARE
    ONNX_MOD_FILE VARCHAR2(100) := 'multilingual_e5_small.onnx';
    MODNAME VARCHAR2(500);
    LOCATION_URI VARCHAR2(200) := 'https://adwc4pm.objectstorage.us-ashburn-1.oci.customer-oci.com/p/J7h8Bo3aoIjgHx8WiBRANi2nd3BNpAMx4v33nVnDhU6mIdrhE57hwpNZfupYAS9L/n/adwc4pm/b/OML-ai-models/o/';
BEGIN
    SELECT UPPER(REGEXP_SUBSTR(ONNX_MOD_FILE, '[^.]+')) INTO MODNAME FROM dual;
    BEGIN DBMS_DATA_MINING.DROP_MODEL(model_name => MODNAME); 
    EXCEPTION WHEN OTHERS THEN NULL; END;
    
    DBMS_CLOUD.GET_OBJECT(
        credential_name => NULL,
        directory_name  => 'DATA_PUMP_DIR',
        object_uri      => LOCATION_URI || ONNX_MOD_FILE);
    
    DBMS_VECTOR.LOAD_ONNX_MODEL(
        directory  => 'DATA_PUMP_DIR',
        file_name  => ONNX_MOD_FILE,
        model_name => MODNAME);
END;
/


-- 4.5 통계 수집 (선택적)
BEGIN
    DBMS_STATS.GATHER_TABLE_STATS('ADMIN', 'CHANNELS');
    DBMS_STATS.GATHER_TABLE_STATS('ADMIN', 'COSTS');
    DBMS_STATS.GATHER_TABLE_STATS('ADMIN', 'COUNTRIES');
    DBMS_STATS.GATHER_TABLE_STATS('ADMIN', 'CUSTOMERS');
    DBMS_STATS.GATHER_TABLE_STATS('ADMIN', 'PRODUCTS');
    DBMS_STATS.GATHER_TABLE_STATS('ADMIN', 'PROMOTIONS');
    DBMS_STATS.GATHER_TABLE_STATS('ADMIN', 'SALES');
    DBMS_STATS.GATHER_TABLE_STATS('ADMIN', 'TIMES');
END;
/

-- 4.6 테이블 행 수 확인
SELECT table_name, num_rows 
FROM user_tables 
WHERE table_name IN ('CHANNELS','COSTS','COUNTRIES','CUSTOMERS','PRODUCTS','PROMOTIONS','SALES','TIMES','DOCUMENTS','DOC_CHUNKS')
ORDER BY table_name;

-- ONNX 모델 확인
SELECT model_name, algorithm FROM user_mining_models;

-- Select AI 프로필 확인
SELECT profile_name, status FROM user_cloud_ai_profiles;

-- 테스트: Select AI 작동 확인
EXEC DBMS_CLOUD_AI.SET_PROFILE('GROQ_SH_PROFILE');
SELECT DBMS_CLOUD_AI.GENERATE('고객 수는?', action => 'runsql') FROM dual;


-- 작업 완료 후  ADB에서 credential 삭제:
BEGIN
    DBMS_CLOUD.DROP_CREDENTIAL('MIGRATION_CRED');
END;
/

-- 잘못 import된 테이블 삭제
BEGIN
  FOR t IN (
    SELECT table_name FROM dba_tables 
    WHERE owner = 'ADMIN' 
    AND table_name IN ('CHANNELS','COSTS','COUNTRIES','CUSTOMERS',
                       'PRODUCTS','PROMOTIONS','SALES','TIMES',
                       'DOCUMENTS','DOC_CHUNKS','ONNX_TEMP')
  ) LOOP
    EXECUTE IMMEDIATE 'DROP TABLE ADMIN.' || t.table_name || ' CASCADE CONSTRAINTS PURGE';
  END LOOP;
END;
/
