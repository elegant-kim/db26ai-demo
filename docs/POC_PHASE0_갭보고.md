# 고객사 PoC 대응 — Phase 0 분석·갭 보고

> 요청서: `docs/_private/POC_UPGRADE_PROMPT.md (비공개 — 저장소가 공개라 고객명이 든 요청서는 추적하지 않는다)` · 작성 2026-09-29 (Fable 5.1) · **구현 없음, 사용자 승인 대기**
> 실측 시그니처는 `docs/verified-signatures.md`. 작업량은 S/M/L 만 적는다(시간 추정은 이 프로젝트에서 금지 — 과거 5~18배 과대).

## 1. 저장소 요약

| 항목 | 현재 |
|---|---|
| 백엔드 | FastAPI(`main.py`, :8247) + python-oracledb **비동기 풀 min 1 / max 5, call_timeout 120s**. 탭별 라우터 `app/routers/<tab>.py`, 서비스는 `app/<tab>.py` 평면 모듈. 세션·인증 없음(요청은 전부 무상태) |
| 프론트 | `web/` Vue 3 + TS + Vite + Tailwind 4 + Pinia. 탭마다 `pages/<tab>/` + `stores/<tab>.ts` + `lib/<tab>.ts`. 서브탭 `?sub=`, 자동 실행 `&run=1`, 장표 `&slide=`. 디자인 토큰 `styles/tokens.css`(컴포넌트에 hex 금지), UI 부품 `components/ui/`(Card·Button·Badge·Stat·차트) + `components/demo/`(SqlBlock·ResultTable·CompareView·ChatThread/ChatComposer·KvGrid·PipelineProgress·SlideViewer …) |
| DB 접속 | `.env` → `app/config.py` Settings(DSN·유저·지갑). **프로필은 세션에 고정하지 않는다** — 풀 커넥션이 요청마다 바뀌므로 `GENERATE(profile_name => …)` 로 매번 명시(`resolve_profile`). `SELECT AI …` 축약구문만 같은 커넥션에서 `SET_PROFILE` 후 실행 |
| 비밀값 | `.env`(gitignore) 만. 저장소는 GitHub **PUBLIC** → 커밋 전 `scripts/check-secrets.sh` 필수 |
| 빌드/실행 | `python main.py`(uvicorn reload) · `cd web && npm run build` · `scripts/deploy.sh`(pytest → ruff → build → kickstart → 스모크) |
| 테스트 | `tests/test_units.py` 11 · `tests/test_api_smoke.py` 43(서버·ADB 필요, 없으면 skip). 2026-09-29 현재 GEMINI 경유 3건이 타임아웃 |
| DB 스크립트 | `sql/setup/NN_*.sql`(번호순, 시크릿은 `_private/`). **`db/migrations/` 는 없다** → 질문 ① |
| 문서 | `CLAUDE.md`(구조) · `docs/개발노하우.md`(규율) · `docs/SESSION_HANDOFF.md`(현재 상태) · `docs/guides/`(매뉴얼 탭) · `docs/design/`(설계) |

## 2. NL2SQL 코드 지도

| 요청서 항목 | 실제 |
|---|---|
| `DBMS_CLOUD_AI.*` 호출 지점 | `app/select_ai.py` — `ask_select_ai()` → `GENERATE(prompt, profile_name, action)` **오버로드 2(params 없음, 단발)**; `set_profile()` → `SET_PROFILE`(속성 조회용); `execute_raw_sql()` → 같은 커서에서 `SET_PROFILE` 후 `SELECT AI …`; `submit_feedback()` → **DB 에 없는 시그니처, 어디서도 안 부름**(삭제 대상). `SET_ATTRIBUTE` 호출 없음 |
| 액션별 흐름 | `routers/nl2sql.py` `POST /api/ask` — `VALID_ACTIONS` 7종 검사 → explainsql 이면 한국어 지시 덧붙임 → `ask_select_ai` → runsql 이면 JSON 파싱 → `{result, elapsed_ms}`. **로그 기록 없음.** 프론트 `stores/nl2sql.ts` `send()`/`runAction()`(후속 버튼은 같은 프롬프트로 다른 액션을 다시 GENERATE, 결과 `cached`) |
| 프로필 → 세션 | 세션 고정 없음. 페이지 헤더 셀렉트(`s.profile`) 값을 요청마다 body 로 보낸다. `/api/set-profile` 은 속성을 읽어오는 용도 |
| 환경 탭 조회 뷰 | `ENV_QUERIES`(`app/select_ai.py`): ACL `dba_host_aces`(폴백 `user_network_acl_privileges`) · 크리덴셜 `user_credentials` · 프로필 `DBA_CLOUD_AI_PROFILE_ATTRIBUTES`(USER_ 폴백). 프론트가 `provider_endpoint` 의 호스트를 ACL 과 대조(`hostFromEndpoint`/`aclHostMatches`) — **openai 계열 전제** |
| Annotation | `ALL_ANNOTATIONS_USAGE` 조회, `ALTER TABLE … ANNOTATIONS (DROP Display) / (ADD Display '…')` DDL. 세트 정본 `web/src/lib/annotations.ts`(SH 59건), SQL 판은 `sql/setup/51` §5 |
| 예시 질문 소스 | **하드코딩** `web/src/lib/nl2sql.ts` `EXAMPLE_QUESTIONS`(SH 14 · SSB 10 · DEFAULT 3), 프로필명에 SH/SSB 포함 여부로 선택 |
| 새 화면 등록 절차 | ① 상단 메뉴: `web/src/lib/menu.ts` `MENUS` + `router/index.ts` ② 기능 지도·⌘K: `app/feature_registry.py`(`TAB_LABELS` + `_F` 튜플; 테스트가 **탭 6개**를 고정하므로 같이 고침) ③ `CLAUDE.md` 탭 표 · `docs/guides/01` ④ 새 서브탭은 레지스트리 한 줄. **"프레젠테이션 모드"는 이 앱에 없다** — 요청서가 본 헤더 아이콘은 테마 토글(시스템/라이트/다크)이다 → 질문 ⑤ |

## 3. 요구 기능 갭 표

판정: **있음 / 부분 / 없음**. 파일은 주로 건드릴 곳.

| # | 요구 | 판정 | 량 | 건드릴 파일 | 리스크·메모 |
|---|---|---|---|---|---|
| 1-A | 말풍선 대화 + 타임스탬프 | **부분** — `ChatThread` 말풍선·`HH:MM` 있음. 그리팅 없음 | S | `Nl2sqlAsk.vue`, `stores/nl2sql.ts` | 스레드 컴포넌트는 AWR·RAG 와 공용 — NL2SQL 슬롯만 고친다 |
| 1-A | 7 액션·예시·직접 실행 유지 | **있음** | — | — | 회귀 확인만 |
| 1-A | Enter 전송 / Shift+Enter 줄바꿈 | **부분** — `ChatComposer` 는 `<input>`(한 줄), Enter 전송·중복 방지·스피너 있음 | S | `ChatComposer.vue`(textarea 옵션) | 다른 탭(AWR·Vector)도 쓰는 부품 — prop 으로 분기 |
| 1-A | **멀티턴**(토글·새 대화·이어서·정상답변시 초기화) | **없음** | **M** | `select_ai.py`(conversation 서비스), `routers/nl2sql.py`, `stores/nl2sql.ts`, `Nl2sqlAsk.vue` | 실측: `CREATE_CONVERSATION` 동작, `GENERATE(params=>'{"conversation_id":…}')` 가 대화 활성(스펙 주석) — **LLM 경로가 오늘 죽어 있어 실제 기억 여부 미확인**. 세션이 없으므로 conversation_id 는 **브라우저(Pinia)가 들고 매 요청 전달**(질문 ②). 대화는 DB 객체라 남는다 — `retention_days`·정리 정책 필요 |
| 1-A | 답변 메타 줄 | **부분** — elapsed·프로필 배지 있음 | S | `Nl2sqlAnswer.vue` | conversation_id·multi turn 은 1-A 멀티턴에 종속 |
| 1-A | 생성 SQL / 프롬프트 접기 | **부분** — 후속 버튼 `showsql`/`showprompt` 로 추가 호출·캐시 | S | `Nl2sqlAnswer.vue` | runsql 답변에 SQL 을 자동으로 붙이려면 GENERATE 1회 추가(비용 2배) — "버튼 클릭 시"로 두는 게 시연에 맞는지 결정(질문 ⑥) |
| 1-B | 👍/👎 + 사유 + 저장, `DBMS_CLOUD_AI.FEEDBACK` | **없음**(옛 `submit_feedback` 은 틀린 시그니처) | **M** | `select_ai.py`(feedback 서비스+트랜잭션), `routers/nl2sql.py`, `Nl2sqlAnswer.vue`, 신규 `FeedbackBox.vue` | `sql_id` 는 `V$MAPPED_SQL`(ADMIN 권한 있음, 8행) vs `sql_text` 오버로드 — **실측 후 채택**. 피드백 벡터 인덱스의 **임베딩 모델**: 프로필에 `embedding_model` 없음 + Gemini 호환 엔드포인트 → 첫 FEEDBACK 이 임베딩 실패할 가능성. 실측 전엔 판단 불가 |
| 1-B | `AI_FEEDBACK_LOG` + 환경 배지·인덱스 표시 | **없음** | S | 마이그레이션, `Nl2sqlEnv.vue`, `stores/nl2sql.ts` | 인덱스 존재는 `USER_INDEXES LIKE '%FEEDBACK_VECINDEX'` |
| 1-C | 질의 이력 탭 + `AI_QUERY_LOG` + 필터·페이징·모달·요약 | **없음**(V$SQL 패널만) | **M** | 마이그레이션, `select_ai.py`(공통 로그), 신규 `routers/nl2sql.py` 3~4 엔드포인트, 신규 `Nl2sqlHistory.vue`, 레지스트리 | 모든 GENERATE 를 서비스 한 곳으로 모으는 리팩터가 선행(공통 원칙 5). `SELECT AI` 직접 실행 경로도 로그에 태워야 한다 |
| 1-D | DB 저장 프리셋 + CRUD | **부분**(하드코딩) | S | 마이그레이션(시드 = 현재 24문항), `routers/nl2sql.py`, `lib/nl2sql.ts`, `Nl2sqlAsk.vue` | 프로필별 프리셋 — SH/SSB 매핑을 `profile_name LIKE` 로 시드 |
| 2-A | Few-shot 파일 업로드·검증·일괄 FEEDBACK | **없음** | **M** | 신규 서브탭, `routers/nl2sql.py`(업로드·검증·진행률), `select_ai.py` | XLSX 는 `openpyxl` 추가 의존. 검증은 `EXPLAIN PLAN`(이미 `get_explain_plan` 있음). 1-B 서비스 재사용 |
| 2-B | 정확도 3단계 비교 | **부분**(Annotation 적용/제거 있음, `CompareView` 있음) | M | `stores/nl2sql.ts`, 신규 `AccuracyScenario.vue`, `select_ai.py`(SET_ATTRIBUTE) | **`SET_ATTRIBUTE(annotations=>false)` 방식 권장** — DDL 로 Annotation 을 뗐다 붙이는 것보다 안전하고 복원이 확실. 3단계 = GENERATE 3회 + 피드백 등록 |
| 2-C | showprompt 전/후 diff | **부분**(showprompt 있음) | S | 신규 `DiffBlock.vue`(줄 단위) | 피드백 주입 문구가 프롬프트 어디에 붙는지 실측 후 하이라이트 규칙 |
| 3-A | OCI 프로바이더 해석 + 프로필 생성 도우미 | **없음**(openai 전제) | **M** | `select_ai.py` ENV, `lib/nl2sql.ts`, `Nl2sqlEnv.vue`, 신규 `ProfileWizard.vue` | 이 DB 에 OCI 프로필·크리덴셜이 없어 **화면 검증 불가** — 모의 데이터로만. 리전 목록은 하드코딩(오사카 등) |
| 3-B | 고객사형 데이터셋·Annotation·프로필·프리셋 시드 | **없음** | **L** | `sql/seed/crown_like/*.sql`(또는 질문 ①의 위치) | 합성 데이터 수만 행 생성 SQL, 한국어 COMMENT/Annotation. 프로필 크리덴셜은 기존 GEMINI_CRED 재사용 |
| 3-C | 모델별 평균 elapsed · 모델 비교 실행 | **없음** | S~M | 이력 집계 API, `Nl2sqlAsk.vue` | GROQ 프로필이 ORA-20404(키)라 지금은 비교 대상이 1개 |
| 4 | Select AI Agent 탭 3종 | **없음** | **L** | 새 메뉴(`menu.ts`·router·레지스트리·CLAUDE.md), `app/agent.py`, `routers/agent.py`, `pages/agent/*` | 패키지·히스토리 뷰 **존재 확인**(46 프로시저, TEAM/TASK/TOOL_HISTORY). `RUN_TEAM` 시간이 길 수 있어 타임아웃·비동기 고려. 테스트의 "탭 6개" 고정 해제 |

## 4. 새 DB 객체 초안

```sql
-- AI_QUERY_LOG — 모든 Select AI 호출 (GENERATE · SELECT AI 직접 실행 · Phase 4 RUN_TEAM)
CREATE TABLE ai_query_log (
  id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  started_at      TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
  source          VARCHAR2(16)  DEFAULT 'GENERATE' NOT NULL,   -- GENERATE | RAWSQL | RUN_TEAM
  profile_name    VARCHAR2(128),
  action          VARCHAR2(16),
  question        CLOB,
  generated_sql   CLOB,
  response_text   CLOB,                                         -- narrate/chat 요약(앞 4000자)
  status          VARCHAR2(10)  NOT NULL,                       -- SUCCEEDED | FAILED
  error_msg       VARCHAR2(4000 CHAR),
  elapsed_ms      NUMBER,
  conversation_id VARCHAR2(36),
  row_count       NUMBER,
  model           VARCHAR2(128),
  sql_id          VARCHAR2(13),                                 -- V$MAPPED_SQL 에서 잡히면
  created_by      VARCHAR2(128) DEFAULT SYS_CONTEXT('USERENV','SESSION_USER')
);
CREATE INDEX ai_query_log_ix1 ON ai_query_log (started_at DESC);
CREATE INDEX ai_query_log_ix2 ON ai_query_log (profile_name, action, status);

-- AI_FEEDBACK_LOG — Oracle FEEDBACK 과 한 트랜잭션으로 기록 (수정 = delete 후 add)
CREATE TABLE ai_feedback_log (
  id               NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  log_id           NUMBER REFERENCES ai_query_log(id),
  profile_name     VARCHAR2(128) NOT NULL,
  conversation_id  VARCHAR2(36),
  question         CLOB,
  generated_sql    CLOB,
  sql_id           VARCHAR2(13),
  feedback_type    VARCHAR2(8)  NOT NULL CHECK (feedback_type IN ('positive','negative')),
  feedback_content VARCHAR2(4000 CHAR),
  corrected_sql    CLOB,
  source           VARCHAR2(16) DEFAULT 'INLINE',               -- INLINE | HISTORY | FEWSHOT
  created_at       TIMESTAMP DEFAULT SYSTIMESTAMP,
  updated_at       TIMESTAMP
);
CREATE INDEX ai_feedback_log_ix1 ON ai_feedback_log (log_id);

-- AI_PROMPT_PRESET — 예시 질문(하드코딩 24문항을 시드로)
CREATE TABLE ai_prompt_preset (
  id           NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  profile_name VARCHAR2(128),                                   -- NULL = 모든 프로필. 'SH%' 같은 LIKE 패턴 허용
  title        VARCHAR2(200 CHAR) NOT NULL,
  question     VARCHAR2(2000 CHAR) NOT NULL,
  action       VARCHAR2(16) DEFAULT 'runsql',
  sort_order   NUMBER DEFAULT 100,
  created_at   TIMESTAMP DEFAULT SYSTIMESTAMP
);
```

권한: ADMIN 에 `EXECUTE ON DBMS_CLOUD_AI` · `DBMS_CLOUD_AI_AGENT`, `SELECT ON V_$MAPPED_SQL` · `V_$SESSION` **이미 있음** — 추가 GRANT 없음(다른 스키마로 옮기면 그때 필요). 롤백 = `DROP TABLE` 3개(순서 feedback → query_log → preset).
한글 컬럼은 `CHAR` 단위(`개발노하우` 3.3), VECTOR 컬럼 없음.

## 5. 질문 (한꺼번에)

1. **마이그레이션 위치** — 요청서는 `db/migrations/NNN_*.sql`, 이 저장소 관례는 `sql/setup/NN_*.sql`(51~60 사용 중). 관례대로 `sql/setup/70_crown_*.sql` + `_rollback.sql` 로 가도 되는가, 아니면 요청서대로 새 폴더를 만드는가.
2. **conversation 상태의 보관 위치** — 앱에 사용자 세션이 없다. conversation_id·토글 상태를 **브라우저(Pinia) 가 들고 매 요청 body 로 보내는 방식**으로 가겠다(서버는 무상태, `GENERATE(params=>conversation_id)`). 요청서의 "사용자 세션에 보관"을 이렇게 해석해도 되는가. (서버 세션을 새로 만들면 로그인·쿠키가 따라온다)
3. **LLM 경로가 오늘 죽어 있다** — GEMINI 경유 `GENERATE` 가 서버 밖에서도 90초 타임아웃(핸드오프 열린 과제 9), GROQ 는 키 문제(과제 7). Phase 1 은 살아 있는 프로필 없이는 검증이 안 된다. 키·Gemini 측을 봐 주실 수 있는가, 아니면 제가 먼저 원인(ACL·크리덴셜·엔드포인트)을 진단할까.
4. **요청서 파일 커밋 여부** — `docs/_private/POC_UPGRADE_PROMPT.md (비공개 — 저장소가 공개라 고객명이 든 요청서는 추적하지 않는다)` 는 지금 untracked 다. 고객명이 들어 있고 저장소가 공개라 **커밋하지 않는 것**을 권한다(`docs/_private/` 로 옮기고 gitignore). 이 보고서와 `verified-signatures.md` 도 고객명을 지우고 커밋할지, 같이 비공개로 둘지.
5. **"프레젠테이션 모드"** 는 앱에 없다(테마 토글이었다). 등록 대상에서 제외하는 것으로 이해해도 되는가.
6. **runsql 답변의 SQL 자동 첨부** — 지금은 `showsql` 버튼을 눌러야 SQL 이 보인다(캐시). 자동 첨부는 GENERATE 를 매번 한 번 더 부른다(시간 2배). 시연에서는 버튼 방식이 오히려 "같은 질문을 다른 액션으로"를 보여주므로 **버튼 유지 + 접기**를 권한다.

승인·답변을 받으면 Phase 1 을 1-A 멀티턴(서비스 계층 통합 + 로그 테이블) → 1-B 피드백 → 1-C 이력 → 1-D 프리셋 순으로, 작은 커밋으로 진행한다.

## 6. 결정 (2026-09-29, 사용자)

| # | 결정 |
|---|---|
| ① | 마이그레이션은 `sql/` 아래 — `sql/setup/70_poc_*.sql` + `_rollback.sql` |
| ② | conversation_id·토글 상태는 **브라우저(Pinia)** 가 들고 매 요청에 보낸다. 서버는 무상태, `GENERATE(params => conversation_id)` |
| ③ | LLM 경로는 진단부터(비밀값 아닌 부분). 진단 결과는 아래 |
| ④ | 요청서는 `docs/_private/`(gitignore)로, 보고서는 고객명을 지워 커밋 |
| ⑤ | 프레젠테이션 모드는 앱에 없음 — 등록 대상에서 제외 |
| ⑥ | runsql 답변의 SQL 은 버튼(캐시) 유지 + 접기만 추가 |

**③ 진단 결과** — ACL(`generativelanguage.googleapis.com` · `api.groq.com` 에 CONNECT/HTTP/RESOLVE) 정상, 크리덴셜 둘 다 ENABLED. 같은 날 오후 `GENERATE(chat)` 이 **4.6초에 정상 응답** — 오전의 90초 무응답은 Gemini 또는 ADB 아웃바운드 쪽의 **일시 장애**였다. Mac 에서 Gemini 직접 호출도 정상(200). 앱 코드 원인 아님. GROQ 는 여전히 키 문제(열린 과제 7).
**같은 날 저녁 확정**: `AI_QUERY_LOG` 에 `ORA-20429 … HTTP 429` 가 500초 elapsed 로 남았다 — **Gemini 키 할당량 초과**가 진짜 원인(DBMS_CLOUD_AI 가 재시도하며 버틴다). 키·결제는 사용자 영역(핸드오프 과제 9).
