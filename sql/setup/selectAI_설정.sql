-- ⚠️ 이 파일은 시크릿이 제거된 공개 버전입니다 (2026-09-04 정제).
-- <...> 자리표시자의 실제 값은 저장소에 없습니다:
--   <GROQ_API_KEY> / <GOOGLE_API_KEY>  → .env 의 GROQ_API_KEY / GOOGLE_API_KEY
--   <OCI_*> / <TENANCY_OCID> / <USER_OCID> / <FINGERPRINT> / <OS_NAMESPACE>
--                                      → OCI 콘솔에서 확인·재발급
-- 원본(시크릿 포함)은 sql/setup/_private/ 에 있으며 .gitignore 로 제외됩니다.
--
--=============================================================
-- 시연
-- DB User에게 권한부여 , ADMIN유저는 이미권한이 있음
-- GRANT EXECUTE ON DBMS_CLOUD_AI TO SH;
-- 1. Configure DBMS_CLOUD_AI Package (사전 작업)
-- 1-1 DB User에게 Network ACL권한부여
-- SYS AS SYSDBA 또는 ADMIN 유저로 실행
BEGIN
    DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE (
        HOST => 'api.groq.com',
        ACE  => xs$ace_type(PRIVILEGE_LIST => xs$name_list('http'),
            principal_name => 'admin',
            principal_type => xs_acl.ptype_db));
END;
/

BEGIN
    DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE(
        host => 'generativelanguage.googleapis.com',
        ace  => xs$ace_type(
            privilege_list => xs$name_list('connect','resolve'),
            principal_name => 'ADMIN',  -- 실제 DB 접속 유저명
            principal_type => xs_acl.ptype_db
        )
    );
END;
/

-- 현재 ACL 설정 확인
SELECT host, lower_port, upper_port, principal, privilege
FROM   dba_host_aces
WHERE  host LIKE '%g%'
;

-- 1-2. credential 조회
select owner, credential_name, username 
  from DBA_CREDENTIALS
;

-- (필요시) credential 삭제
BEGIN
    DBMS_CLOUD.DROP_CREDENTIAL (
        credential_name  => 'GROQ_CRED'
    );
END;
/

BEGIN
    DBMS_CLOUD.DROP_CREDENTIAL (
        credential_name  => 'GEMINI_CRED'
    );
END;
/

-- 1-3 credential 생성 (LLM (openai) 정보 세팅)
BEGIN
    DBMS_CLOUD.CREATE_CREDENTIAL (
        credential_name  => 'GROQ_CRED',
        username => 'GROQ',
        password => '<GROQ_API_KEY>'
    );
END;
/

BEGIN
    DBMS_CLOUD.CREATE_CREDENTIAL (
        credential_name  => 'GEMINI_CRED',
        username => 'GEMINI',
        password => '<GOOGLE_API_KEY>'
    );
END;
/

BEGIN
    DBMS_CLOUD.CREATE_CREDENTIAL(
        credential_name => 'OCI_CRED',
        user_ocid       => '<USER_OCID>',
        tenancy_ocid    => '<TENANCY_OCID>',
        fingerprint     => '<FINGERPRINT>',
        private_key     => '<OCI_API_PRIVATE_KEY>'
    );
END;
/

SELECT c.cust_id, c.cust_first_name, c.cust_last_name,
       c.cust_city, c.cust_income_level, c.cust_credit_limit
FROM admin.customers c
WHERE ROWNUM <= 50
ORDER BY c.cust_city
;

-- 2. AI Profile 생성 (위에서 생성한 Credential정보를 이용하여 AI Profile를 생성)
-- 2-1 AI Profile 조회
select profile_name, owner, status 
  from DBA_CLOUD_AI_PROFILES
;

-- (필요시) 기존 AI Profile 삭제
BEGIN
    DBMS_CLOUD_AI.DROP_PROFILE(profile_name => 'GROQ_SH_PROFILE');
    DBMS_CLOUD_AI.DROP_PROFILE(profile_name => 'GROQ_SSB_PROFILE');
    DBMS_CLOUD_AI.DROP_PROFILE(profile_name => 'GEMINI_SH_PROFILE');
    DBMS_CLOUD_AI.DROP_PROFILE(profile_name => 'GEMINI_SSB_PROFILE');
END;
/

-- 2-2 AI Profile 생성 
BEGIN
    DBMS_CLOUD_AI.CREATE_PROFILE(
        profile_name => 'GROQ_SH_PROFILE',
        attributes => '{
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
        }'
    );
END;
/

BEGIN
    DBMS_CLOUD_AI.CREATE_PROFILE(
        profile_name => 'GROQ_SSB_PROFILE',
        attributes => '{
            "provider": "openai",
            "credential_name": "GROQ_CRED",
            "model": "llama-3.3-70b-versatile",
            "provider_endpoint": "https://api.groq.com/openai/v1",
            "object_list": [
              {"owner": "SSB","name":"CUSTOMER"},
              {"owner": "SSB","name":"DWDATE"},
              {"owner": "SSB","name":"LINEORDER"},
              {"owner": "SSB","name":"PART"},
              {"owner": "SSB","name":"SUPPLIER"}
            ],
            "annotations": true,
            "comments": true,
            "constraints": true,
            "conversation": true
        }'
    );
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
        }'
    );
END;
/

BEGIN
    DBMS_CLOUD_AI.CREATE_PROFILE(
        profile_name => 'GEMINI_SSB_PROFILE',
        attributes => '{
            "provider": "openai",
            "credential_name": "GEMINI_CRED",
            "model": "gemini-2.5-flash",
            "provider_endpoint": "https://generativelanguage.googleapis.com/v1beta/openai/v1",
            "object_list": [
              {"owner": "SSB","name":"CUSTOMER"},
              {"owner": "SSB","name":"DWDATE"},
              {"owner": "SSB","name":"LINEORDER"},
              {"owner": "SSB","name":"PART"},
              {"owner": "SSB","name":"SUPPLIER"}
            ],
            "annotations": true,
            "comments": true,
            "constraints": true,
            "conversation": true
        }'
    );
END;
/

select * from dictionary where table_name like '%ANN%';

grant alter any table to admin;
grant alter any table on schema sh to admin;
ALTER TABLE MHMC.TB_MH_PC_CM_MKT ADD (test varchar2(10));

-- 어노테이션 적용여부 확인
SELECT object_name, column_name, annotation_name, annotation_value 
FROM all_annotations_usage 
ORDER BY object_name, column_name NULLS FIRST
;


-- 1) 등록된 ONNX 모델 목록 확인
SELECT model_name, mining_function, algorithm, creation_date
FROM USER_MINING_MODELS
-- WHERE algorithm = 'ONNX'
ORDER BY creation_date DESC;

SELECT model_name, algorithm, mining_function from user_mining_models  WHERE model_name='MULTILINGUAL_E5_SMALL';

-- 2) 특정 모델이 실제 임베딩을 생성하는지 테스트
SELECT VECTOR_EMBEDDING(MULTILINGUAL_E5_SMALL USING '테스트 문장입니다' AS data) FROM dual;

SELECT VECTOR_EMBEDDING(MULTI_MINILM_L12_V2 USING '테스트 문장입니다' AS data) FROM dual;
SELECT VECTOR_EMBEDDING(ALL_MINILM_L12_V2 USING '테스트 문장입니다' AS data) FROM dual;
--



-- 쿼리 테스트
-- 2-3 세션에 AI Profile 설정
exec dbms_cloud_ai.set_profile('GROQ_PROFILE');
-- exec dbms_cloud_ai.set_profile('openai_gpt35');

-- 2-4 AI Profile 목록 및 Attribute 목록 조회
select profile_name, owner, status 
  from DBA_CLOUD_AI_PROFILES;

select profile_name, owner, attribute_name, attribute_value 
  from DBA_CLOUD_AI_PROFILE_ATTRIBUTES
where profile_name like '%PROFILE%';

-- SELECT host, acl FROM DBA_NETWORK_ACLS WHERE host = 'api.groq.com';
--------------------------------------

-- 기타 참고
select a.table_name, a.column_name, a.data_type, b.comments 
from dba_tab_cols a, dba_col_comments b 
where a.owner = 'SH' 
and a.table_name = 'SALES' 
and a.owner = b.owner 
and a.table_name = b.table_name 
and a.column_name = b.column_name 
order by a.COLUMN_ID
;

create user mhmc identified by Welcome12345 default tablespace users temporary tablespace temp;

grant create session to mhmc;
grant execute on DBMS_CLOUD_AI to mhmc;



-- ============================================
-- SH 테이블을 ADMIN 스키마로 복제 (CTAS)
-- ============================================

-- 1. 기존 테이블이 있으면 삭제 (최초 실행 시 에러 무시)
BEGIN
  FOR t IN (SELECT table_name FROM user_tables 
            WHERE table_name IN ('CHANNELS','COSTS','COUNTRIES','CUSTOMERS','PRODUCTS','PROMOTIONS','SALES','TIMES')) LOOP
    EXECUTE IMMEDIATE 'DROP TABLE ' || t.table_name || ' CASCADE CONSTRAINTS PURGE';
  END LOOP;
END;
/

-- 2. 테이블 복사 (데이터 포함)
CREATE TABLE CHANNELS    AS SELECT * FROM SH.CHANNELS;
CREATE TABLE COUNTRIES   AS SELECT * FROM SH.COUNTRIES;
CREATE TABLE CUSTOMERS   AS SELECT * FROM SH.CUSTOMERS;
CREATE TABLE PRODUCTS    AS SELECT * FROM SH.PRODUCTS;
CREATE TABLE PROMOTIONS  AS SELECT * FROM SH.PROMOTIONS;
CREATE TABLE TIMES       AS SELECT * FROM SH.TIMES;
CREATE TABLE COSTS       AS SELECT * FROM SH.COSTS;
CREATE TABLE SALES       AS SELECT * FROM SH.SALES;

-- 3. PK 제약조건 추가
ALTER TABLE CHANNELS   ADD CONSTRAINT PK_CHANNELS   PRIMARY KEY (CHANNEL_ID);
ALTER TABLE COUNTRIES  ADD CONSTRAINT PK_COUNTRIES  PRIMARY KEY (COUNTRY_ID);
ALTER TABLE CUSTOMERS  ADD CONSTRAINT PK_CUSTOMERS  PRIMARY KEY (CUST_ID);
ALTER TABLE PRODUCTS   ADD CONSTRAINT PK_PRODUCTS   PRIMARY KEY (PROD_ID);
ALTER TABLE PROMOTIONS ADD CONSTRAINT PK_PROMOTIONS PRIMARY KEY (PROMO_ID);
ALTER TABLE TIMES      ADD CONSTRAINT PK_TIMES      PRIMARY KEY (TIME_ID);

-- 4. FK 제약조건 추가
ALTER TABLE SALES ADD CONSTRAINT FK_SALES_CUST    FOREIGN KEY (CUST_ID)    REFERENCES CUSTOMERS(CUST_ID);
ALTER TABLE SALES ADD CONSTRAINT FK_SALES_PROD    FOREIGN KEY (PROD_ID)    REFERENCES PRODUCTS(PROD_ID);
ALTER TABLE SALES ADD CONSTRAINT FK_SALES_TIME    FOREIGN KEY (TIME_ID)    REFERENCES TIMES(TIME_ID);
ALTER TABLE SALES ADD CONSTRAINT FK_SALES_CHAN    FOREIGN KEY (CHANNEL_ID) REFERENCES CHANNELS(CHANNEL_ID);
ALTER TABLE SALES ADD CONSTRAINT FK_SALES_PROMO   FOREIGN KEY (PROMO_ID)   REFERENCES PROMOTIONS(PROMO_ID);
ALTER TABLE COSTS ADD CONSTRAINT FK_COSTS_PROD    FOREIGN KEY (PROD_ID)    REFERENCES PRODUCTS(PROD_ID);
ALTER TABLE COSTS ADD CONSTRAINT FK_COSTS_TIME    FOREIGN KEY (TIME_ID)    REFERENCES TIMES(TIME_ID);


-- 5. 통계 수집 (옵티마이저가 최신 통계를 기반으로 실행 계획을 수립할 수 있도록)
BEGIN
  DBMS_STATS.GATHER_TABLE_STATS(USER, 'CHANNELS');
  DBMS_STATS.GATHER_TABLE_STATS(USER, 'COUNTRIES');
  DBMS_STATS.GATHER_TABLE_STATS(USER, 'CUSTOMERS');
  DBMS_STATS.GATHER_TABLE_STATS(USER, 'PRODUCTS');
  DBMS_STATS.GATHER_TABLE_STATS(USER, 'PROMOTIONS');
  DBMS_STATS.GATHER_TABLE_STATS(USER, 'TIMES');
  DBMS_STATS.GATHER_TABLE_STATS(USER, 'COSTS');
  DBMS_STATS.GATHER_TABLE_STATS(USER, 'SALES');
END;
/

-- 테이블 확인
SELECT table_name, num_rows FROM user_tables 
WHERE table_name IN ('CHANNELS','COSTS','COUNTRIES','CUSTOMERS','PRODUCTS','PROMOTIONS','SALES','TIMES')
ORDER BY table_name;

-- 프로필 확인
SELECT profile_name, attribute_name, attribute_value 
FROM user_cloud_ai_profile_attributes 
WHERE profile_name = 'GROQ_SH_PROFILE';


-- ============================================
-- SSB 테이블을 ADMIN 스키마로 복제 (CTAS)
-- ============================================
-- ============================================
-- SSB 테이블 ADMIN 복제 (튜닝 버전)
-- ============================================

-- -- 기존 테이블 정리 (이미 있으면)
-- BEGIN FOR t IN (SELECT table_name FROM user_tables WHERE table_name IN ('CUSTOMER','LINEORDER','PART','SUPPLIER','DWDATE')) LOOP EXECUTE IMMEDIATE 'DROP TABLE ADMIN.' || t.table_name || ' CASCADE CONSTRAINTS PURGE'; END LOOP; END;
-- /

-- -- 세션 병렬 처리 활성화
-- ALTER SESSION ENABLE PARALLEL DDL;
-- ALTER SESSION ENABLE PARALLEL DML;
-- ALTER SESSION FORCE PARALLEL QUERY PARALLEL 8;

-- -- 1. 작은 테이블 먼저
-- CREATE TABLE ADMIN.DWDATE NOLOGGING PARALLEL 8 AS SELECT /*+ PARALLEL(8) */ * FROM SSB.DWDATE;
-- CREATE TABLE ADMIN.CUSTOMER NOLOGGING PARALLEL 8 AS SELECT /*+ PARALLEL(8) */ * FROM SSB.CUSTOMER;
-- CREATE TABLE ADMIN.PART NOLOGGING PARALLEL 8 AS SELECT /*+ PARALLEL(8) */ * FROM SSB.PART;
-- CREATE TABLE ADMIN.SUPPLIER NOLOGGING PARALLEL 8 AS SELECT /*+ PARALLEL(8) */ * FROM SSB.SUPPLIER;

-- -- 2. 대형 팩트 테이블
-- CREATE TABLE ADMIN.LINEORDER NOLOGGING PARALLEL 8 AS SELECT /*+ PARALLEL(8) */ * FROM SSB.LINEORDER;

-- -- 3. 병렬도 원복
-- ALTER TABLE ADMIN.DWDATE NOPARALLEL;
-- ALTER TABLE ADMIN.CUSTOMER NOPARALLEL;
-- ALTER TABLE ADMIN.PART NOPARALLEL;
-- ALTER TABLE ADMIN.SUPPLIER NOPARALLEL;
-- ALTER TABLE ADMIN.LINEORDER NOPARALLEL;

-- -- 4. PK 생성 (NOLOGGING + PARALLEL)
-- ALTER TABLE ADMIN.CUSTOMER ADD CONSTRAINT PK_SSB_CUSTOMER PRIMARY KEY (C_CUSTKEY) USING INDEX NOLOGGING PARALLEL 8;
-- ALTER TABLE ADMIN.PART ADD CONSTRAINT PK_SSB_PART PRIMARY KEY (P_PARTKEY) USING INDEX NOLOGGING PARALLEL 8;
-- ALTER TABLE ADMIN.SUPPLIER ADD CONSTRAINT PK_SSB_SUPPLIER PRIMARY KEY (S_SUPPKEY) USING INDEX NOLOGGING PARALLEL 8;
-- ALTER TABLE ADMIN.DWDATE ADD CONSTRAINT PK_SSB_DWDATE PRIMARY KEY (D_DATEKEY) USING INDEX NOLOGGING PARALLEL 8;
-- ALTER TABLE ADMIN.LINEORDER ADD CONSTRAINT PK_SSB_LINEORDER PRIMARY KEY (LO_ORDERKEY, LO_LINENUMBER) USING INDEX NOLOGGING PARALLEL 8;

-- -- 5. 인덱스 병렬도 원복
-- ALTER INDEX PK_SSB_CUSTOMER NOPARALLEL;
-- ALTER INDEX PK_SSB_PART NOPARALLEL;
-- ALTER INDEX PK_SSB_SUPPLIER NOPARALLEL;
-- ALTER INDEX PK_SSB_DWDATE NOPARALLEL;
-- ALTER INDEX PK_SSB_LINEORDER NOPARALLEL;

-- -- 6. FK (NOVALIDATE)
-- ALTER TABLE ADMIN.LINEORDER ADD CONSTRAINT FK_LO_CUSTKEY FOREIGN KEY (LO_CUSTKEY) REFERENCES ADMIN.CUSTOMER(C_CUSTKEY) ENABLE NOVALIDATE;
-- ALTER TABLE ADMIN.LINEORDER ADD CONSTRAINT FK_LO_PARTKEY FOREIGN KEY (LO_PARTKEY) REFERENCES ADMIN.PART(P_PARTKEY) ENABLE NOVALIDATE;
-- ALTER TABLE ADMIN.LINEORDER ADD CONSTRAINT FK_LO_SUPPKEY FOREIGN KEY (LO_SUPPKEY) REFERENCES ADMIN.SUPPLIER(S_SUPPKEY) ENABLE NOVALIDATE;
-- ALTER TABLE ADMIN.LINEORDER ADD CONSTRAINT FK_LO_ORDERDATE FOREIGN KEY (LO_ORDERDATE) REFERENCES ADMIN.DWDATE(D_DATEKEY) ENABLE NOVALIDATE;

-- -- 7. 통계 수집 (병렬)
-- BEGIN
--     DBMS_STATS.GATHER_TABLE_STATS('ADMIN','DWDATE', degree=>8);
--     DBMS_STATS.GATHER_TABLE_STATS('ADMIN','CUSTOMER', degree=>8);
--     DBMS_STATS.GATHER_TABLE_STATS('ADMIN','PART', degree=>8);
--     DBMS_STATS.GATHER_TABLE_STATS('ADMIN','SUPPLIER', degree=>8);
--     DBMS_STATS.GATHER_TABLE_STATS('ADMIN','LINEORDER', degree=>8);
-- END;
-- /

-- -- 8. 확인
-- SELECT table_name, num_rows FROM user_tables 
-- WHERE table_name IN ('CUSTOMER','LINEORDER','PART','SUPPLIER','DWDATE') ORDER BY table_name;

