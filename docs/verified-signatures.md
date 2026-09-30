# 실측 검증한 Oracle 시그니처·뷰 (고객사 PoC 확장)

> `docs/_private/POC_UPGRADE_PROMPT.md (비공개 — 저장소가 공개라 고객명이 든 요청서는 추적하지 않는다)` 공통 원칙 4: **패키지 시그니처는 추측하지 않는다.** 대상 DB 에서 확인한 것만 쓴다.
> 대상: `db26aidemo` ADB — `Oracle AI Database 26ai EE 23.26.3.3.0` (2026-09-29 실측). 확인 SQL 은 각 절에 그대로 둔다.
> 패키지 스펙(`ALL_SOURCE`, owner `C##CLOUD$SERVICE`)이 **wrapped 가 아니라 읽힌다** — 파라미터 설명은 거기서 옮겼다.

## 1. 확인 SQL

```sql
-- 프로시저·오버로드·파라미터 (owner 는 C##CLOUD$SERVICE)
SELECT object_name, overload, argument_name, data_type, in_out, defaulted
FROM   all_arguments
WHERE  package_name = 'DBMS_CLOUD_AI' AND object_name IN ('GENERATE','FEEDBACK','CREATE_CONVERSATION','SET_CONVERSATION_ID','DROP_CONVERSATION')
ORDER  BY object_name, overload, position;

-- 스펙 주석 (파라미터 의미)
SELECT line, text FROM all_source WHERE owner='C##CLOUD$SERVICE' AND name='DBMS_CLOUD_AI' AND type='PACKAGE' ORDER BY line;

-- 뷰와 컬럼
SELECT table_name, LISTAGG(column_name, ', ') WITHIN GROUP (ORDER BY column_id)
FROM   all_tab_columns WHERE table_name IN ('USER_CLOUD_AI_CONVERSATIONS','USER_CLOUD_AI_CONVERSATION_PROMPTS','USER_AI_AGENT_TEAM_HISTORY','USER_AI_AGENT_TASK_HISTORY','USER_AI_AGENT_TOOL_HISTORY')
GROUP  BY table_name;

-- 권한
SELECT table_name, privilege FROM user_tab_privs WHERE table_name IN ('DBMS_CLOUD_AI','DBMS_CLOUD_AI_AGENT','V_$MAPPED_SQL','V_$SESSION');
```

## 2. `DBMS_CLOUD_AI` (2026-09-29)

| 대상 | 실측 | 비고 |
|---|---|---|
| `GENERATE` 오버로드 1 | `(prompt CLOB, profile_name VARCHAR2 DEFAULT NULL, action VARCHAR2 DEFAULT NULL, attributes CLOB DEFAULT NULL, params CLOB) RETURN CLOB` | **`params => '{"conversation_id": "…"}'` 가 대화를 켠다** (스펙 주석 520행: "Parameters such as 'conversation_id' which enables conversation feature if provided"). 상수 `PARAM_CONV_ID := 'conversation_id'` |
| `GENERATE` 오버로드 2 | 위에서 `params` 없음 | 앱이 지금 쓰는 것(단발) |
| `CREATE_CONVERSATION` | 함수 `(attributes CLOB DEFAULT NULL) RETURN VARCHAR2` + 프로시저 오버로드 | 속성 키: `title`·`description`·`retention_days`·`tags`. **실측 호출 성공** → `5C9B2B3E-…` (36자 GUID). 곧바로 `DROP_CONVERSATION(force=>TRUE)` 로 지웠다 |
| `SET_CONVERSATION_ID(conversation_id)` · `GET_CONVERSATION_ID` · `DROP_CONVERSATION(conversation_id, force BOOLEAN DEFAULT FALSE)` · `UPDATE_CONVERSATION(conversation_id, attributes)` · `ADD/REMOVE_CONVERSATION_TAG` · `DELETE_CONVERSATION_PROMPT` | 존재 | 세션 고정 방식(`SET_CONVERSATION_ID`)은 풀 커넥션에 안 맞는다 → **`params` 방식 채택** |
| `FEEDBACK` 오버로드 1 | `(profile_name, sql_id VARCHAR2, feedback_type DEFAULT NULL, response CLOB, feedback_content CLOB, operation DEFAULT 'add')` | `sql_id` = `V$MAPPED_SQL` 의 SQL 식별자 |
| `FEEDBACK` 오버로드 2 | `(profile_name, sql_text CLOB, …같음)` | `sql_text` = 자연어 `select ai …` 원문. 상수 `OPT_ADD='add'`·`OPT_DELETE='delete'` |
| 오류 상수 | `-20046` 프로필 없음 · `-20047` 속성 · `-20050` **대화 없음** | 화면 오류 힌트에 쓴다 |
| 없는 것 | `ENABLE/DISABLE_CONVERSATION`, `USER_CLOUD_AI_VECTOR_INDEXES` | 요청서·기억 속 이름을 그대로 쓰면 ORA-00942/06550 |
| 앱의 옛 `submit_feedback()` | `FEEDBACK(profile_name, prompt, feedback)` 로 호출 | **DB 에 없는 시그니처** — 미사용 코드. Phase 1 에서 삭제 |

프로필 속성 실측(`USER_CLOUD_AI_PROFILE_ATTRIBUTES`): `GEMINI_SH_PROFILE`·`GROQ_SH_PROFILE` 모두 `provider=openai`, `conversation=true`, `annotations=true`, `comments=true`. `embedding_model` 속성은 **없다**(피드백 벡터 인덱스가 어떤 임베딩 모델을 쓰는지 Phase 1 첫 호출에서 확인 — 아래 열린 항목).

## 3. 뷰 (컬럼 실측)

| 뷰 | 컬럼 |
|---|---|
| `USER_CLOUD_AI_CONVERSATIONS` | CONVERSATION_ID, CONVERSATION_TITLE, DESCRIPTION, CREATED, MODIFIED, RETENTION_DAYS, CONVERSATION_LENGTH, TAGS |
| `USER_CLOUD_AI_CONVERSATION_PROMPTS` | CONVERSATION_PROMPT_ID, CONVERSATION_ID, CONVERSATION_TITLE, PROFILE_NAME, PROMPT_ACTION, PROMPT, PROMPT_RESPONSE, CREATED, MODIFIED, CLIENT_IDENTIFIER, CLIENT_IP, SID, SERIAL# |
| `USER_AI_AGENT_TEAM_HISTORY` | TEAM_EXEC_ID, TEAM_NAME, STATE, START_DATE, END_DATE, CONVERSATION_ID, PARAMS |
| `USER_AI_AGENT_TASK_HISTORY` | TEAM_EXEC_ID, TEAM_NAME, TASK_ORDER, AGENT_NAME, TASK_NAME, CONVERSATION_PARAMS, INPUT, RESULT, STATE, START_DATE, END_DATE |
| `USER_AI_AGENT_TOOL_HISTORY` | INVOCATION_ID, TEAM_EXEC_ID, TASK_ORDER, TOOL_NAME, AGENT_NAME, TASK_NAME, START_DATE, END_DATE, INPUT, OUTPUT, TOOL_OUTPUT |
| `V$MAPPED_SQL` | SQL_TEXT, SQL_FULLTEXT, SQL_ID, HASH_VALUE, MAPPED_SQL_TEXT, MAPPED_SQL_FULLTEXT, MAPPED_SQL_ID, … USE_COUNT — ADMIN 에 `SELECT` 권한 있음(8행) |

그 밖에 존재: `USER_AI_AGENTS/_TASKS/_TEAMS/_TOOLS(+_ATTRIBUTES)`, `USER_AI_AGENT_TASK_STATES`, `DBA_*` 동형, `SESSION_CLOUD_AI_CONVERSATION_PROMPTS`.

## 4. `DBMS_CLOUD_AI_AGENT` (Phase 4 용, 존재만 확인)

`CREATE_TOOL/CREATE_TASK/CREATE_AGENT/CREATE_TEAM(name, attributes CLOB, status, description)` · `RUN_TEAM(team_name, user_prompt CLOB, params CLOB) RETURN CLOB` (오버로드 2 는 `team_exec_id OUT`) · `SQL_TOOL(tool_name, query CLOB, action) RETURN CLOB` · `GET_TEAM_STATE(team_name, params)` · `RAG_TOOL`·`HUMAN_TOOL`·`WEB_SEARCH_TOOL`·`SEND_EMAIL_TOOL`·`SLACK_TOOL`·`EXPORT/IMPORT_TEAM`·`SHOW_AGENT_PROMPT` 등 46개. ADMIN 에 `EXECUTE` 있음. 팀·툴 0개(빈 상태).

## 5. 멀티턴 실측 (2026-09-29 오후, GEMINI_SH_PROFILE)

`CREATE_CONVERSATION` → `GENERATE(prompt, profile, action, attributes => NULL, params => '{"conversation_id": "<id>"}')` 로 두 번:

| 턴 | 질문 | 결과 |
|---|---|---|
| 1 (커넥션 A) | 2000년 매출 상위 3개 제품 이름과 매출액 | 정상 SQL (7.1초) |
| 2 (**다른 풀 커넥션 B**) | 그중 1위 제품만 월별 매출로 보여줘 | `WHERE CALENDAR_YEAR = 2000 AND PROD_NAME = …` — 앞 턴의 연도·제품을 이어받음 (8.3초) |
| 2' (대화 없이) | 같은 질문 | 제품을 서브쿼리로 추측 — 연도 조건 없음 (10.5초) |
| 3 (chat) | 방금 내가 처음 물어본 게 뭐였지? | **자기 질문을 되읊음**(56.8초) — SQL 액션의 문맥은 이어지지만 chat 의 회상은 이 실측에서 틀렸다. 화면 안내에 과장하지 말 것 |

`USER_CLOUD_AI_CONVERSATION_PROMPTS` 에 세 턴이 전부 남았다(SID 가 턴마다 달라도 무관). 결론: **세션 고정 없이 params 방식으로 충분** — 앱은 `run_select_ai()` 가 이 방식을 쓴다.

## 6. FEEDBACK 실측 (2026-09-30, GEMINI_SH_PROFILE) — 1-B 의 전제 셋 다 확인

| 확인 | 결과 |
|---|---|
| 프로필에 `embedding_model` 없이 FEEDBACK | **`ORA-20048: Embedding Model must be specified for vector embeddings with OPENAI Compatible Provider`** |
| `SET_ATTRIBUTE(profile, 'embedding_model', 'gemini-embedding-001')` 후 | 첫 FEEDBACK 이 `GEMINI_SH_PROFILE_FEEDBACK_VECINDEX`(`USER_CLOUD_VECTOR_INDEXES` ENABLED) + `…$VECTAB(CONTENT CLOB, ATTRIBUTES JSON, EMBEDDING VECTOR)` + IVF 테이블 2개를 만든다(2.8초). `text-embedding-004` 도 됨 |
| GENERATE 로만 물은 질문에 `sql_text` FEEDBACK | **`ORA-20000: No matching SQL statement found for the SQL_ID or SQL text`** — GENERATE 는 SQL 번역이 아니라 `V$MAPPED_SQL` 에 안 남는다 |
| `SET_PROFILE` → `SELECT AI showsql <질문>` 실행 후 | `V$MAPPED_SQL` 에 `sql_id bhvnagg0rfz3s` 한 행. **`sql_id` 오버로드 OK(4.2초) · `sql_text` 오버로드 OK(1.9초) · 다른 풀 커넥션에서 `sql_text` OK(1.4초)** |
| 저장 단위 | `$VECTAB` 은 **질문 텍스트당 1행**(CONTENT = 질문, ATTRIBUTES.response = SQL) — 같은 질문에 3번 add 해도 1행. 수정 = delete 후 add 가 맞다 |
| 프롬프트 주입 | showprompt 끝에 `Use the examples below in two ways: … Here are examples of previous successful queries for similar questions … [{"user_prompt": …, "sql_query": …}]` 뒤에 `Question: …`. 유사 질문("2000년 매출 상위 3개 제품")에도 주입됐다 |
| 삭제 | `FEEDBACK(profile, sql_text => 문장, operation => 'delete')` → `$VECTAB` 0행 |

**앱 설계 귀결**(`app/feedback.py`): 피드백 저장 시 같은 커넥션에서 `SET_PROFILE` → 문장이 매핑돼 있지 않으면 `SELECT AI showsql <질문>` 1회 실행(LLM) → `sql_text` 오버로드 FEEDBACK → `AI_FEEDBACK_LOG` INSERT, 실패 시 rollback. 채택 근거는 이 표.

**모델 id (2026-09-30, 이 키·무료 등급)**: `gemini-2.5-pro` → 404 "no longer available to new users" · `gemini-pro-latest`/`gemini-3.1-pro-preview` → 429(무료 등급 할당량 0) · `gemini-2.5-flash`/`gemini-flash-latest`/**`gemini-3.8-flash`**(채택, 프로필·기본값) → 200. Pro 계열은 결제 연결 뒤에만 의미가 있다. 목록에는 3-flash-preview · 3.1-flash-lite · 3.5/3.6/3.7/3.8-flash · 3.1-pro-preview 도 있다.

## 8. DBMS_CLOUD_AI_AGENT 실측 (2026-09-30)

| 확인 | 결과 |
|---|---|
| 속성 키(패키지 상수) | 에이전트 `role` · `enable_human_tool`(+ `profile_name`) / 태스크 `instruction` · `tools` · `input` / 툴 `tool_type` · `tool_params` · `instruction` · `function` · `tool_inputs` / 팀 `agents` · `process` · `supervisor_agent` |
| 생성 | `CREATE_TOOL('DEMO_SQL_TOOL', '{"tool_type":"SQL","tool_params":{"profile_name":…,"action":"runsql"},"instruction":…}')` · `CREATE_AGENT(…, '{"profile_name":…,"role":…,"enable_human_tool":"false"}')` · `CREATE_TASK(…, '{"instruction":…,"tools":["DEMO_SQL_TOOL"]}')` · `CREATE_TEAM(…, '{"agents":[{"name":…,"task":…}],"process":"sequential"}')` 전부 OK |
| 태스크 `"input": "{query}"` | **ORA-20051 Invalid task - {query}** — 자리표시자 없이 두면 사용자 프롬프트가 첫 태스크 입력으로 들어간다 |
| `RUN_TEAM` 없이 conversation | **ORA-20053 Conversation_id is not set in the session** → `params => '{"conversation_id": …}'`(CREATE_CONVERSATION 으로 발급) |
| OpenAI 호환(Gemini) 프로필로 RUN_TEAM | 툴은 성공(CHANNEL_COUNT 5)했지만 마지막 LLM 호출이 **HTTP 400 "Requests ending with a model turn are not supported"** — 호환 엔드포인트가 Agent 의 메시지 순서를 거부 |
| provider=google 네이티브 프로필(GEMINI_SH_NATIVE, 같은 키) | `GENERATE(chat)` 5.7초 OK · **RUN_TEAM 15.8초 정답**("판매 채널은 총 5개") · 2턴 "그중 이름이 가장 긴 채널은?" 20.1초 **Direct Sales** — 멀티턴 OK |
| 히스토리 뷰 | `USER_AI_AGENT_TEAM_HISTORY`(TEAM_EXEC_ID·STATE·START/END_DATE·CONVERSATION_ID) · `_TASK_HISTORY`(TASK_ORDER·INPUT·RESULT) · `_TOOL_HISTORY`(INVOCATION_ID·INPUT `{"TOOL_NAME","QUERY","ACTION"}`·OUTPUT `{"status","result"}`) — 툴이 SHOWSQL 과 RUNSQL 두 번 불린다 |
| `RUN_TEAM` 오버로드 2 | `team_exec_id OUT` 으로 실행 ID 를 바로 받는다(앱이 쓰는 형태). `DESCRIBE_TEAM` 은 A2A 카드형 JSON |

## 7. 열린 항목 (실측 못 한 것)

- ~~FEEDBACK 임베딩 모델 · sql_id vs sql_text~~ → §6 에서 해소.
