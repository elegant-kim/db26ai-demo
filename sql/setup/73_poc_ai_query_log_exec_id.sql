-- 73_poc_ai_query_log_exec_id.sql — AI_QUERY_LOG 에 exec_id (Phase 4 Agent RUN_TEAM 의 team_exec_id 36자, 2026-09-30)
-- USER_AI_AGENT_TEAM_HISTORY.TEAM_EXEC_ID 와 조인해 Agent History 탭이 질문·피드백을 붙인다. 롤백: ALTER TABLE ai_query_log DROP COLUMN exec_id;
ALTER TABLE ai_query_log ADD (exec_id VARCHAR2(36));
CREATE INDEX ai_query_log_ix3 ON ai_query_log (exec_id);
COMMENT ON COLUMN ai_query_log.exec_id IS 'Agent RUN_TEAM 의 team_exec_id (source=RUN_TEAM 일 때)';
