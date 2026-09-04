-- ⚠️ 이 파일은 시크릿이 제거된 공개 버전입니다 (2026-09-04 정제).
-- <...> 자리표시자의 실제 값은 저장소에 없습니다:
--   <GROQ_API_KEY> / <GOOGLE_API_KEY>  → .env 의 GROQ_API_KEY / GOOGLE_API_KEY
--   <OCI_*> / <TENANCY_OCID> / <USER_OCID> / <FINGERPRINT> / <OS_NAMESPACE>
--                                      → OCI 콘솔에서 확인·재발급
-- 원본(시크릿 포함)은 sql/setup/_private/ 에 있으며 .gitignore 로 제외됩니다.
--
-- 메일ID : <OCI_ACCOUNT_EMAIL>
-- OCID : <TENANCY_OCID>
-- Object storage namespace : <OS_NAMESPACE>
-- Auth Token : <OCI_AUTH_TOKEN>

-- 소스 테이블 확인
-- 1. ADMIN 소유 테이블 전체 목록 + 행 수
SELECT table_name, num_rows 
FROM dba_tables 
WHERE owner = 'ADMIN' 
ORDER BY table_name;

-- 2. SSB 스키마 테이블 존재 여부 (ADMIN에 복제했는지)
SELECT table_name, num_rows 
FROM dba_tables 
WHERE owner = 'ADMIN' 
AND table_name IN ('CUSTOMER','LINEORDER','PART','SUPPLIER','DWDATE');

-- 3. ONNX 모델 목록
SELECT model_name, algorithm, mining_function 
FROM all_mining_models 
WHERE owner = 'ADMIN';

-- 4. Vector Store에 데이터가 있는지
SELECT 'DOCUMENTS' AS tbl, COUNT(*) AS cnt FROM admin.documents
UNION ALL SELECT 'DOC_CHUNKS', COUNT(*) FROM admin.doc_chunks;

-- 5. Select AI 프로필 목록
SELECT profile_name, status 
FROM dba_cloud_ai_profiles 
WHERE owner = 'ADMIN';



--신규 테넌시의 Object Storage에 접근하기 위한 인증 정보
BEGIN
    DBMS_CLOUD.CREATE_CREDENTIAL(
        credential_name => 'MIGRATION_CRED',
        username        => '<OCI_ACCOUNT_EMAIL>',   -- 신규 테넌시 로그인 이메일
        password        => '<OCI_AUTH_TOKEN>'            -- Step 2에서 생성한 토큰
    );
END;
/


-- 버킷 접근 가능한지 확인
SELECT * FROM DBMS_CLOUD.LIST_OBJECTS(
    credential_name => 'MIGRATION_CRED',
    location_uri    => 'https://objectstorage.ap-chuncheon-1.oraclecloud.com/n/<OS_NAMESPACE>/b/investhub-migration/o/'
);
-- 빈 결과가 나오면 정상 (버킷은 비어있으니까)
-- 에러가 나오면 credential이나 URL이 잘못된 것

-- 선택적 테이블 Export
DECLARE
    l_dp_handle NUMBER;
BEGIN
    l_dp_handle := DBMS_DATAPUMP.OPEN(
        operation   => 'EXPORT',
        job_mode    => 'TABLE',
        remote_link => NULL,
        job_name    => 'DB26AI_EXPORT'
    );

    -- 덤프 파일
    DBMS_DATAPUMP.ADD_FILE(
        handle    => l_dp_handle,
        filename  => 'https://objectstorage.ap-chuncheon-1.oraclecloud.com/n/<OS_NAMESPACE>/b/investhub-migration/o/db26ai_export_%U.dmp',
        directory => 'MIGRATION_CRED',
        filetype  => DBMS_DATAPUMP.KU$_FILE_TYPE_URIDUMP_FILE
    );

    -- 로그 파일
    DBMS_DATAPUMP.ADD_FILE(
        handle    => l_dp_handle,
        filename  => 'db26ai_export.log',
        directory => 'DATA_PUMP_DIR',
        filetype  => DBMS_DATAPUMP.KU$_FILE_TYPE_LOG_FILE
    );

    -- SH 테이블 8개 + Vector Store 2개 = 10개 테이블만 지정
    DBMS_DATAPUMP.METADATA_FILTER(
        handle => l_dp_handle,
        name   => 'NAME_EXPR',
        value  => q'[IN ('CHANNELS','COSTS','COUNTRIES','CUSTOMERS','PRODUCTS','PROMOTIONS','SALES','TIMES','DOCUMENTS','DOC_CHUNKS')]',
        object_type => 'TABLE'
    );

    DBMS_DATAPUMP.METADATA_FILTER(
        handle => l_dp_handle,
        name   => 'SCHEMA_EXPR',
        value  => q'[IN ('ADMIN')]'
    );

    DBMS_DATAPUMP.SET_PARAMETER(
        handle => l_dp_handle,
        name   => 'COMPRESSION',
        value  => 'ALL'
    );

    DBMS_DATAPUMP.START_JOB(handle => l_dp_handle);
    DBMS_DATAPUMP.DETACH(handle => l_dp_handle);
END;
/


SELECT job_name, operation, job_mode, state
FROM DBA_DATAPUMP_JOBS;


-- 작업이 시작되면 DBA_DATAPUMP_JOBS 뷰에서 상태를 확인할 수 있습니다.
SELECT * FROM DBA_DATAPUMP_JOBS WHERE STATE = 'EXECUTING';


-- 작업 완료 후 소스 ADB에서 credential 삭제:
BEGIN
    DBMS_CLOUD.DROP_CREDENTIAL('MIGRATION_CRED');
END;
/
