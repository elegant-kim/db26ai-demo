-- 04_profile.sql — Select AI 프로필 RETAIL_DEMO_PROFILE (PoC 3-B, 2026-09-30)
-- 크리덴셜은 기존 GEMINI_CRED 를 재사용한다(51번 §3 에서 만든 것). 모델·임베딩 모델은 GEMINI_SH_PROFILE 과 같다.
-- 프로필 이름에 RETAIL 이 들어가면 앱이 RETAIL Annotation 세트·'%RETAIL%' 프리셋을 고른다(web/src/lib/annotations.ts · nl2sql.ts).
BEGIN
  BEGIN DBMS_CLOUD_AI.DROP_PROFILE(profile_name => 'RETAIL_DEMO_PROFILE'); EXCEPTION WHEN OTHERS THEN NULL; END;
  DBMS_CLOUD_AI.CREATE_PROFILE(
    profile_name => 'RETAIL_DEMO_PROFILE',
    attributes   => '{
      "provider": "openai",
      "provider_endpoint": "https://generativelanguage.googleapis.com/v1beta/openai",
      "credential_name": "GEMINI_CRED",
      "model": "gemini-3.8-flash",
      "embedding_model": "gemini-embedding-001",
      "object_list": [
        {"owner": "ADMIN", "name": "POC_STORES"},
        {"owner": "ADMIN", "name": "POC_PRODUCTS"},
        {"owner": "ADMIN", "name": "POC_DISPLAYS"},
        {"owner": "ADMIN", "name": "POC_SALES"}
      ],
      "annotations": true,
      "comments": true,
      "constraints": true,
      "conversation": true
    }',
    description => '유통 시연용 샘플(제과 유통: 매장·제품·진열·매출) — PoC 3-B');
END;
/
SELECT profile_name, status FROM user_cloud_ai_profiles WHERE profile_name = 'RETAIL_DEMO_PROFILE';
