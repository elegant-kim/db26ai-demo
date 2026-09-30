-- 09_teardown.sql — 01~05 의 원복. 프로필 → 프리셋 → 피드백 인덱스(있으면) → 테이블(자식부터)
BEGIN DBMS_CLOUD_AI.DROP_PROFILE(profile_name => 'CROWN_LIKE_PROFILE'); EXCEPTION WHEN OTHERS THEN NULL; END;
/
DELETE FROM ai_prompt_preset WHERE profile_name = '%CROWN%';
DELETE FROM ai_feedback_log WHERE profile_name = 'CROWN_LIKE_PROFILE';
COMMIT;
DROP TABLE poc_sales PURGE;
DROP TABLE poc_displays PURGE;
DROP TABLE poc_products PURGE;
DROP TABLE poc_stores PURGE;
