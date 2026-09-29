-- 71_poc_ai_tables_rollback.sql — 70 번의 원복. 순서: 자식(feedback) → 부모(query_log) → 독립(preset)
DROP TABLE ai_feedback_log PURGE;
DROP TABLE ai_query_log PURGE;
DROP TABLE ai_prompt_preset PURGE;
