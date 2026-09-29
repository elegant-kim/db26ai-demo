# 크라운제과 PoC 대응 기능 확장 — Phase 0 분석·갭 보고

> `docs/CROWN_POC_UPGRADE_PROMPT.md` 의 Phase 0 산출물. **구현은 하지 않았다.** 이 보고서 승인 후 Phase 1 로 간다.
> 작성: 2026-09-29, 클라우드 세션(GitHub `main` 3730351 기준). **DB 실측은 못 했다** — 이 컨테이너에는 `.env`·Wallet 이 없어
> ADB 에 접속할 수 없다. Oracle 패키지 시그니처는 §6 의 SQL 을 로컬에서 돌려 확인해야 한다(공통 원칙 4).

---

## 1. 저장소 구조 요약

| 항목 | 현재 |
|---|---|
| 백엔드 | Python FastAPI (`main.py` 엔트리, uvicorn `reload=True`). 탭별 라우터 `app/routers/<tab>.py`, 본체 `app/<tab>.py`. NL2SQL 은 `app/routers/nl2sql.py`(8 엔드포인트) + `app/select_ai.py`(624줄) |
| DB 접속 | `python-oracledb` thin **비동기 풀** `app/database.py` — min 1 / max 5, `call_timeout` 120초, Wallet(mTLS). **커넥션 고정(affinity) 없음** — 요청마다 다른 세션이 올 수 있다. 이것이 Select AI 설계의 핵심 제약(§2-2) |
| 설정·비밀값 | `.env` → `app/config.py` `Settings` (dotenv). 코드에 키 없음. 저장소 **GitHub 공개** → 커밋 전 `scripts/check-secrets.sh` 게이트 필수 |
| 프론트 | `web/` Vue 3 + TypeScript + Vite 7 + Tailwind 4 + Pinia 2 + vue-router 4. 탭마다 `pages/<tab>/` + `stores/<tab>.ts` + `lib/<tab>.ts` 셋. 빌드 산출물 `web/dist` 를 FastAPI 가 서빙 |
| 라우팅 | `web/src/router/index.ts` — 7 페이지 lazy chunk, `meta.menu`. 서브탭은 `composables/useSubTab.ts` 가 `?sub=` 와 동기화. 딥링크 3층: `?sub=` · `&run=1` · `&slide=` |
| 상태관리 | Pinia setup-store. NL2SQL 은 `stores/nl2sql.ts`(326줄) 하나가 프로필·대화·환경·스키마를 전부 가진다 |
| 스타일 | `styles/tokens.css` 토큰(컴포넌트에 hex 금지). UI 13종 `components/ui/`, 데모 전용 `components/demo/`(SqlBlock·ResultTable·ChatThread·ChatComposer·SessionTabs·KvGrid…). 규칙 정본 `docs/design/06` |
| 빌드·실행 | `python main.py`(:8247) · `cd web && npm run build`(undef-check + vue-tsc + vite) · 배포 `scripts/deploy.sh` · 운영은 macOS launchd |
| 테스트 | `tests/test_units.py`(순수 함수) + `tests/test_api_smoke.py`(통합 45개, 서버 없으면 자동 skip) + `ruff`. NL2SQL 통합 테스트 5개 |
| 문서 | `CLAUDE.md`(L1) · `docs/개발노하우.md`(L2) · `docs/SESSION_HANDOFF.md`(L3) · `docs/guides/`(L4, 앱 매뉴얼 탭) · `docs/design/03_API_명세서.md` 는 `scripts/gen_api_doc.py` 가 라우터 docstring 에서 **생성** |

---

## 2. NL2SQL 페이지 관련 코드 목록

### 2-1. `DBMS_CLOUD_AI.*` 호출 지점

| 호출 | 위치 | 비고 |
|---|---|---|
| `GENERATE(prompt, profile_name, action)` | `select_ai.py:57 ask_select_ai()` | 유일한 실행 경로. **프로필명을 매 호출 명시**(`resolve_profile` 이 빈 값을 채움). 액션 7종은 `SELECT_AI_ACTIONS` 튜플이 정본 |
| `SET_PROFILE(:p)` | `select_ai.py:127 set_profile()` → `/api/set-profile` | **프론트가 더 이상 부르지 않는다**(`stores/nl2sql.ts selectProfile` 주석: 세션 단위라 풀에선 무의미, ORA-20046 교훈). 라우터에만 남은 잔존 API |
| `SET_PROFILE` → 곧바로 `SELECT AI …` | `select_ai.py:330 execute_raw_sql()` | 「SQL 직접 실행」의 `SELECT AI <액션> <질문>` 축약구문. **같은 커넥션**에서 SET_PROFILE 후 실행하는 유일한 세션 의존 코드 |
| `FEEDBACK(profile_name, prompt, feedback)` | `select_ai.py:82 submit_feedback()` | **죽은 코드**: 어느 라우터도 import 하지 않는다. 파라미터명(`prompt`,`feedback`)이 26ai 문서 시그니처(`sql_id/sql_text`, `feedback_type`, `response`, `feedback_content`, `operation`)와 **다르다** — 추측으로 쓰인 흔적. Phase 1-B 에서 교체 대상 |
| `SET_ATTRIBUTE` · `CREATE_PROFILE` · `CREATE_CONVERSATION` · `DBMS_CLOUD_AI_AGENT.*` | 없음 | 프로필 생성은 `sql/setup/51_selectai_adb_setup.sql` §4 (SQLcl 수동). 앱은 읽기만 한다 |

액션별 흐름: `/api/ask` → `explainsql` 이면 한국어 지시 접미 → `ask_select_ai` → `runsql` 이면 `json.loads` 시도 → `{success, action, result, elapsed_ms}`.
`elapsed_ms` 는 **이미 서버에서 측정**한다(라우터 `time.time()`). 프론트 `processResult()` 가 runsql → 표, showsql → SQL, 나머지 → 마크다운으로 그린다.
후속 버튼(`ACTION_BUTTONS`)은 같은 프롬프트를 다른 액션으로 재호출해 `msg.cached[action]` 에 쌓는다 — 답변 하나에 showsql·narrate·showprompt 를 붙이는 구조가 **이미 있다**.

### 2-2. 프로필 선택이 세션에 반영되는 방식

- **세션 고정 없음.** 프로필은 Pinia `profile` ref 에만 있고, 모든 요청이 `profile_name` 을 body 로 보낸다. DB 세션 상태에 의존하는 것은 `SELECT AI` 축약구문 하나뿐이며 그것도 한 커넥션 안에서 끝낸다.
- 기본 프로필 우선순위 `PREFER = [?profile 딥링크, GEMINI_SH_PROFILE, GROQ_SH_PROFILE]`.
- **Phase 1 멀티턴에의 함의**: 풀이 커넥션을 섞어 주므로 "세션에 conversation 을 켜 두면 알아서 이어진다" 식 구현은 **불가**. `conversation_id` 를 매 GENERATE 호출에 명시적으로 넘겨야 하고(`params`/`attributes` JSON 로 넘기는 방식 — §6 에서 시그니처 검증 필요), conversation_id 의 생성·재사용·리셋은 서버 서비스 계층 + 프론트 스토어가 들고 다녀야 한다. 프로필 속성 `conversation=true` 는 두 프로필 모두 켜져 있다(51번 §4).

### 2-3. 환경 탭 진단 카드가 참조하는 뷰

| 카드 | 1차 뷰 | 폴백 | 코드 |
|---|---|---|---|
| 프로필 | `DBA_CLOUD_AI_PROFILE_ATTRIBUTES` | `USER_CLOUD_AI_PROFILE_ATTRIBUTES` | `get_profile_attributes()` |
| 프로필 목록 | `DBA_CLOUD_AI_PROFILES` | `USER_CLOUD_AI_PROFILES` | `list_profiles()` |
| 네트워크 ACL | `DBA_HOST_ACES` | `USER_NETWORK_ACL_PRIVILEGES` | `ENV_QUERIES["acl"]` |
| LLM 크리덴셜 | `USER_CREDENTIALS` | — | `ENV_QUERIES["credential"]` |

프론트는 `provider_endpoint` URL 에서 호스트를 뽑아(`hostFromEndpoint`) ACL 행을 거르고, `credential_name` 으로 크리덴셜 행을 고른다. **provider=`oci` 는 `provider_endpoint` 가 없고 `region`·`oci_compartment_id` 로 호스트가 정해지므로 지금 로직은 ACL 카드가 빈 채로 뜬다**(Phase 3-A 대상). 판정 키 `credOk`·`aclOk`·`annotationCount` 는 스토어 computed.

### 2-4. Annotation 탭이 쓰는 DDL/뷰

- 적용: `ALTER TABLE {fqn} ANNOTATIONS (DROP Display)` → `(ADD Display '…')`, 컬럼은 `MODIFY ({col} ANNOTATIONS (DROP/ADD Display …))`. **DROP-then-ADD 가 이유 있는 순서**(ADD 만 하면 중복 행이 쌓인다 — `개발노하우.md` 3.3).
- 조회: `ALL_ANNOTATIONS_USAGE` (`annotation_name='DISPLAY'`, `column_name IS NULL` 이 테이블 레벨). `get_schema_info()` 가 `ALL_TAB_COLUMNS`·`ALL_TABLES(num_rows)` 와 합친다.
- Annotation 세트 정본은 **프론트** `web/src/lib/annotations.ts`(SH 59건) — 프로필명에 `SH` 가 들어가면 적용된다. 51번 SQL §5 는 여기서 생성한 사본.
- 회귀 주의: `apply_annotations()`·`remove_annotations()` 안에 `except Exception: pass` 가 4곳 남아 있다(DROP 실패 무시). 요청 범위가 아니라 Phase 0 에선 건드리지 않았고, Phase 2-B 가 이 함수를 재사용할 때 `logger.warning` 을 붙이는 것을 제안한다.

### 2-5. 예시 질문 드롭다운의 데이터 소스

**하드코딩.** `web/src/lib/nl2sql.ts` `EXAMPLE_QUESTIONS = {SH: 14개, SSB: 10개, DEFAULT: 3개}`, `exampleQuestionsFor(profile)` 이 프로필명의 `SSB`/`SH` 포함 여부로 고른다. DB·API 없음. Phase 1-D 의 시드 원본이 된다.

### 2-6. 새 화면 추가 시 등록 절차 (⌘K · "프레젠테이션 모드")

요청서의 「프레젠테이션 모드」에 해당하는 기능은 **이 저장소에 없다.** 헤더에 있는 것은 ⌘K(`CommandPalette`)와 **장표 뷰어**(`SlideViewer`, `PageHeader` 가 자동으로 「장표 n」 버튼을 넣음)다. 장표 뷰어를 뜻한 것으로 해석했다 — 다르면 §7 Q5 에 답해 달라.

새 **서브탭**(이력·피드백) 추가 시:
1. `pages/Nl2sql.vue` `TABS` 배열 + `useSubTab` id 목록에 추가, `pages/nl2sql/Nl2sqlHistory.vue` 신설
2. `app/feature_registry.py` `_F` 에 한 줄(`path="/nl2sql?sub=history"`) → ⌘K·매뉴얼 기능 지도·장표 앵커가 자동 반영
3. (선택) `slides` 꼬리표를 같은 행 7번째 자리에

새 **상단 메뉴**(Phase 4 `Select AI Agent`) 추가 시: 위에 더해 `lib/menu.ts` `MENUS`(id 타입 `MenuId` 확장) · `router/index.ts` 라우트 · `feature_registry.py` `TAB_LABELS` · `CLAUDE.md` 탭 표 · `docs/guides/01` · 테스트 `test_6탭_전부_기능이_있다` 의 기대 수. 모바일 드로어(`MobileDrawer.vue`)는 `MENUS` 를 읽으므로 자동.

### 2-7. 그 밖에 Phase 1 에 직접 닿는 현재 상태

- **「질문」 탭은 이미 말풍선 대화 UI 다** (`ChatThread` + `ChatComposer` + `Nl2sqlAnswer`). 사용자/AI 말풍선, 타임스탬프(`HH:MM`), 로딩 스피너+경과초, 중복 전송 방지(`sending`), 대화 비우기 — 요청서 1-A 의 절반은 존재한다. 없는 것: 그리팅, Shift+Enter(입력이 `<input>` 단일행), 멀티턴 토글 3종, 답변 메타 한 줄, 접기(현재는 버튼으로 블록 교체).
- `ChatComposer` 는 `<input>` 이라 Shift+Enter 줄바꿈이 불가 — `<textarea>` 로 바꾸면 AWR 탭의 `ChatComposer` 사용처도 함께 영향(공통 컴포넌트). prop 으로 분기해야 한다.
- `/api/health` 가 `profile_count` 를 이미 준다. 피드백 건수 배지는 여기 또는 `/api/env-info` 확장.
- **열린 과제 9(SESSION_HANDOFF §6)**: 2026-09-29 현재 GEMINI 경유 `SELECT AI` 가 DPY-4024(타임아웃)로 응답이 없다. GROQ 는 ORA-20404. **즉 지금 두 프로필 모두 GENERATE 가 실패 중**이다. Phase 1 의 실제 호출 검증은 이 경로가 살아난 뒤에만 가능하다(§7 Q1).

---

## 3. 요구 기능 갭 표

판정: **있음 / 부분 / 없음**. 작업량 S(반나절 이하)·M(1~2일)·L(3일+). 파일은 신설 `+`, 수정 `~`.

### Phase 1

| # | 항목 | 판정 | 량 | 건드릴 파일 | 리스크 |
|---|---|---|---|---|---|
| 1-A | 대화 말풍선 리스트·타임스탬프 | **있음** | — | — | — |
| 1-A | 그리팅 메시지 | 없음 | S | `~stores/nl2sql.ts` `~Nl2sqlAsk.vue` | — |
| 1-A | 7 액션·예시·직접 실행 유지 | 있음 | — | — | 회귀 확인만 |
| 1-A | Enter 전송 / Shift+Enter 줄바꿈 | 부분 | S | `~components/demo/ChatComposer.vue`(textarea 옵션) | AWR 탭 공용 — prop 분기 |
| 1-A | 스피너·중복 방지 | 있음 | — | — | — |
| 1-A | **멀티턴** (Multi Turn·새 대화·이어서·정상답변시 초기화) | **없음** | **L** | `~select_ai.py`(conversation 서비스) `~routers/nl2sql.py`(`AskRequest` 확장·`/api/conversation/*`) `~stores/nl2sql.ts` `~Nl2sqlAsk.vue` `~lib/nl2sql.ts` | ① 풀 커넥션 → conversation_id 명시 필수 ② `CREATE_CONVERSATION`/`GENERATE params` 시그니처 **미검증**(§6) ③ 두 프로필 모두 현재 GENERATE 실패(과제 7·9) |
| 1-A | 답변 메타 한 줄(conv_id·elapsed·액션·프로필·multi turn) | 부분(elapsed·프로필 있음) | S | `~Nl2sqlAnswer.vue` | — |
| 1-A | 생성 SQL / 프롬프트 접기 | 부분(후속 버튼으로 교체 표시) | S | `~Nl2sqlAnswer.vue`(`<details>` 식 접기) | GENERATE 는 액션당 1호출 — runsql 답변에 SQL 을 자동으로 붙이려면 **showsql 추가 호출 = LLM 2회**(시간·비용 2배). 기본은 버튼 클릭 시 호출 유지 제안 |
| 1-B | 👍/👎 + 사유 + 저장 + 수정/삭제 | **없음** | **M** | `~select_ai.py`(`submit_feedback` 전면 교체) `+app/feedback.py`(서비스) `~routers/nl2sql.py`(`/api/feedback` CRUD) `~Nl2sqlAnswer.vue` `~stores/nl2sql.ts` | `FEEDBACK` 시그니처·`sql_id` vs `sql_text` 오버로드 **DB 실측 필요**. `V$MAPPED_SQL` READ 권한(ADMIN 은 있을 것). 26ai 23.26 에 FEEDBACK 이 있는지 자체를 먼저 확인 |
| 1-B | 👎 시 올바른 SQL 제시 → `response` | 없음 | S | 위와 동일 | — |
| 1-B | `AI_FEEDBACK_LOG` 테이블 + Oracle 호출과 한 트랜잭션 | 없음 | M | `+sql/setup/70_ai_query_log.sql`(§4) `+app/feedback.py` | FEEDBACK 은 내부적으로 autonomous 커밋일 가능성 — "Oracle 호출 실패 시 자체 기록 롤백"은 되지만 **반대(자체 INSERT 실패 시 Oracle 피드백 되돌리기)는 delete 보상 호출**로만 가능 |
| 1-B | 환경 탭 `피드백 N건` 배지 · `_FEEDBACK_VECINDEX` 표시 | 없음 | S | `~select_ai.py ENV_QUERIES` `~Nl2sqlEnv.vue` | 인덱스 이름 규칙(`<프로필>_FEEDBACK_VECINDEX`)·소유 뷰(`USER_INDEXES`? `USER_VECTOR_INDEXES`?) 실측 |
| 1-C | 「이력」 서브탭 + `AI_QUERY_LOG` 공통 기록 | **없음** | **M** | `+app/query_log.py` `~select_ai.py ask_select_ai`(기록 훅) `~execute_raw_sql`(SELECT AI 도 기록) `+routers` `/api/query-log` `+pages/nl2sql/Nl2sqlHistory.vue` `~Nl2sql.vue TABS` `~feature_registry.py` | 기록 INSERT 는 GENERATE 와 **다른 커넥션**에서(풀 중첩 acquire 금지 규칙). LLM 응답 원문(CLOB) 저장 여부 결정 필요 |
| 1-C | 필터·페이징·행 모달·요약 카드 | 없음 | M | 위 + `components/demo/ResultTable` 재사용, 모달은 `SlideViewer` 슬라이드오버 패턴 재사용 | 모달 컴포넌트가 아직 없다(슬라이드오버만) |
| 1-D | DB 저장 프리셋 CRUD + 시드 | 없음 | S~M | `+sql/setup/70_*.sql`(`AI_PROMPT_PRESET` + 시드 27건) `+/api/presets` `~lib/nl2sql.ts EXAMPLE_QUESTIONS`(시드 SQL 생성 원본으로 강등) `~Nl2sqlAsk.vue` | 정본 두 곳 금지 규칙 → 하드코딩 배열은 삭제하고 DB 만 정본. 오프라인 폴백 필요한지 결정 |

### Phase 2

| # | 항목 | 판정 | 량 | 건드릴 파일 | 리스크 |
|---|---|---|---|---|---|
| 2-A | Few-shot 파일 업로드(CSV/JSON/XLSX) → 검증 → 일괄 FEEDBACK | 없음 | **M~L** | `+app/fewshot.py` `+routers` `+pages/nl2sql/Nl2sqlFeedback.vue` | XLSX 는 `openpyxl` 의존성 추가. SQL 문법 검증은 `EXPLAIN PLAN`(기존 `get_explain_plan` 재사용) — `DBMS_SQL.PARSE` 는 DML 도 파싱해 주므로 EXPLAIN 이 안전. 진행률은 SSE 가 아니라 배치 20건 폴링 제안 |
| 2-A | 등록 피드백 목록·개별/전체 삭제 | 없음 | S | `AI_FEEDBACK_LOG` 기반 | Oracle 쪽 목록 뷰가 있는지(`USER_CLOUD_AI_FEEDBACK`?) 실측 — 없으면 자체 테이블이 유일한 목록 |
| 2-B | 정확도 개선 3단계 비교 | 없음 | M | `+app/scenario.py` `~Nl2sqlAsk.vue`(3열 카드 = `CompareView` 재사용) | Annotation DROP/ADD 는 **DDL** — 커밋을 강제하고 3단계 중 실패 시 복원이 늦어진다. **`SET_ATTRIBUTE(annotations=false)` 토글 방식 권장**(프로필 속성만 바뀜, 스키마 무손상). 단 이것은 프로필을 **전역**으로 바꾸므로 동시 사용자 있으면 간섭 |
| 2-C | showprompt 전/후 diff | 없음 | S | `~Nl2sqlAnswer.vue` + 간단 라인 diff 유틸 | diff 라이브러리 추가(`diff` npm) 또는 자체 LCS 30줄 |

### Phase 3

| # | 항목 | 판정 | 량 | 건드릴 파일 | 리스크 |
|---|---|---|---|---|---|
| 3-A | provider=oci 진단 해석 | 없음 | M | `~stores/nl2sql.ts`(endpointHost 분기) `~Nl2sqlEnv.vue` | OCI GenAI 는 한국 리전 없음 → `ap-osaka-1` 등 크로스리전. 크리덴셜은 OCI API 키(`user_ocid`… 4필드) 또는 Resource Principal(`OCI$RESOURCE_PRINCIPAL`) — 후자는 `USER_CREDENTIALS` 에 행이 없을 수 있음 |
| 3-A | 프로필 생성 도우미(`CREATE_PROFILE` 미리보기·실행) | 없음 | M | `+/api/profiles/create` `+ProfileCreateModal` | 크리덴셜 생성은 **시크릿 입력**을 화면이 받게 됨 — 공개 저장소·로그 노출 위험. 크리덴셜은 SQL 로 사전 생성, 화면은 기존 크리덴셜 선택만 하도록 범위 축소 제안 |
| 3-B | 크라운제과형 샘플 데이터셋·프로필·프리셋 | 없음 | **M** | `+sql/seed/crown_like/01_tables.sql … 05_profile.sql` | 수만 행 합성은 PL/SQL `INSERT … SELECT … CONNECT BY LEVEL` 로. Annotation 세트는 `annotations.ts` 에도 추가해야 화면 「적용」 버튼이 먹는다(정본 위치 결정) |
| 3-B | 프로필 전환 시 3탭 연동 | **있음** | — | — | 확인만 — `selectProfile` 이 env·schema 를 다시 읽고 이력은 `profile_name` 필터로 |
| 3-C | 프로필별 평균 elapsed 표 | 없음(1-C 후 S) | S | `AI_QUERY_LOG` 집계 | — |
| 3-C | 모델 비교 실행(2~3 프로필 순차) | 없음 | M | `~stores/nl2sql.ts` `~Nl2sqlAsk.vue` | 현재 GEMINI·GROQ 둘 다 죽어 있어 검증 불가(과제 7·9) |

### Phase 4

| # | 항목 | 판정 | 량 | 리스크 |
|---|---|---|---|---|
| 4 | `DBMS_CLOUD_AI_AGENT` 정의/실행/히스토리 3탭 + 상단 메뉴 | **없음** | **L** | 패키지 존재 여부부터 실측(23.26 에 있는지). 시그니처·히스토리 뷰 이름 전부 미검증. `RUN_TEAM` 은 수십 초 — 120초 타임아웃 안에 들지 확인. 메뉴 추가 절차 §2-6 |

---

## 4. 새 DB 객체 초안

스키마 ADMIN. 파일 위치는 §7 Q3 에 따라 `sql/setup/70_*.sql`(저장소 관례) 또는 `db/migrations/`(요청서).

```sql
-- 70_ai_query_log.sql
CREATE TABLE ai_query_log (
    id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at      TIMESTAMP        DEFAULT SYSTIMESTAMP NOT NULL,
    source          VARCHAR2(20)     DEFAULT 'GENERATE' NOT NULL,   -- GENERATE | RUN_TEAM (Phase 4)
    profile_name    VARCHAR2(128)    NOT NULL,
    action          VARCHAR2(20)     NOT NULL,                      -- runsql … chat
    question        VARCHAR2(4000 CHAR) NOT NULL,
    generated_sql   CLOB,
    response_text   CLOB,                                           -- 답변 요약용(모달) — 상한 40k 자
    status          VARCHAR2(10)     NOT NULL CHECK (status IN ('SUCCEEDED','FAILED')),
    error_msg       VARCHAR2(4000 CHAR),
    elapsed_ms      NUMBER,
    conversation_id VARCHAR2(128),
    row_count       NUMBER,
    model           VARCHAR2(128),
    created_by      VARCHAR2(128)    DEFAULT SYS_CONTEXT('USERENV','SESSION_USER')
);
CREATE INDEX ai_query_log_ix1 ON ai_query_log (started_at DESC);
CREATE INDEX ai_query_log_ix2 ON ai_query_log (profile_name, started_at DESC);
CREATE INDEX ai_query_log_ix3 ON ai_query_log (conversation_id);

CREATE TABLE ai_feedback_log (
    id               NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    log_id           NUMBER REFERENCES ai_query_log(id) ON DELETE SET NULL,
    profile_name     VARCHAR2(128)   NOT NULL,
    conversation_id  VARCHAR2(128),
    question         VARCHAR2(4000 CHAR) NOT NULL,
    generated_sql    CLOB,
    sql_id           VARCHAR2(13),                                  -- V$MAPPED_SQL.SQL_ID (있을 때만)
    feedback_type    VARCHAR2(10)    NOT NULL CHECK (feedback_type IN ('positive','negative')),
    feedback_content VARCHAR2(4000 CHAR),
    corrected_sql    CLOB,
    origin           VARCHAR2(20)    DEFAULT 'inline',              -- inline | history | fewshot (Phase 2-A)
    created_at       TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    updated_at       TIMESTAMP
);
CREATE INDEX ai_feedback_log_ix1 ON ai_feedback_log (profile_name, created_at DESC);

CREATE TABLE ai_prompt_preset (
    id           NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    profile_name VARCHAR2(128),                                     -- NULL = 모든 프로필 공통
    title        VARCHAR2(200 CHAR) NOT NULL,
    question     VARCHAR2(4000 CHAR) NOT NULL,
    action       VARCHAR2(20) DEFAULT 'runsql',
    sort_order   NUMBER DEFAULT 100,
    created_at   TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL
);
-- 시드: web/src/lib/nl2sql.ts EXAMPLE_QUESTIONS 27건 → profile_name 을 'GEMINI_SH_PROFILE'/'GROQ_SH_PROFILE' 이 아니라
--       패턴 매칭이 필요하면 profile_pattern 컬럼('%SH%') 으로 — Q4 참조

-- 권한 (ADMIN 은 이미 가진 것이 대부분 — 실측 후 확정)
-- GRANT READ ON SYS.V_$MAPPED_SQL TO admin;  GRANT READ ON SYS.V_$SESSION TO admin;
-- GRANT EXECUTE ON DBMS_CLOUD_AI TO admin;   (ADB ADMIN 은 기본 보유)
-- 71_ai_query_log_rollback.sql : DROP TABLE ai_feedback_log; DROP TABLE ai_prompt_preset; DROP TABLE ai_query_log;
```

한글 컬럼은 전부 `CHAR` 의미론(`개발노하우.md` 3.3 VARCHAR2 BYTE 함정). Duality/Graph 처럼 앱 기동 시 자동 생성하지 않고 **셋업 SQL 로만** 만든다(요청서 원칙 3).

---

## 5. 문제 제기 (요청서와 저장소 관례의 충돌 — 결정 필요)

| 요청서 | 저장소 관례 | 제안 |
|---|---|---|
| `db/migrations/NNN_*.sql` + 롤백, `db/seed/crown_like/` | `sql/setup/NN_*.sql`(50·51·60 번대, 롤백은 `53_teardown` 식 별파일) | `sql/setup/70_*.sql` + `sql/seed/crown_like/` 로 관례 유지 |
| `docs/verified-signatures.md` | 함정·실측은 `docs/개발노하우.md` 3절 | 요청대로 **별 파일 신설**(내용이 길고 SQL 이라 3절엔 링크만) |
| `docs/screens/` 캡처 | `docs/design/captures/` | 기존 폴더에 `crown_*.png` 접두로 |
| README 에 GRANT·적용 순서 | `docs/guides/02_운영_가이드.md` | 운영 가이드에 §추가 + README 는 한 줄 링크 |
| "서비스 계층 한 곳" | `app/select_ai.py` 가 이미 그 역할(624줄) | 로그·피드백·대화는 `app/select_ai_log.py`·`app/feedback.py` 로 **분리 신설**, `ask_select_ai` 는 그대로 진입점 |
| 커밋 트레일러 `Claude Opus 5` | 이 세션은 Fable 5.1 | 세션 안내대로 `Claude Fable 5.1` 트레일러 사용 |

---

## 6. DB 실측이 필요한 시그니처 — 로컬에서 돌릴 SQL

이 컨테이너는 ADB 에 닿지 않는다. 아래를 **로컬**(`./venv/bin/python` 스크립트 또는 SQLcl)에서 실행해 결과를 `docs/verified-signatures.md` 에 붙이면 Phase 1 착수 조건이 된다. 초안 파일을 같은 커밋에 넣어 두었다(결과란은 비어 있음).

```sql
-- (1) DBMS_CLOUD_AI 에 conversation·feedback 관련 프로시저가 있는가
SELECT object_name, overload, COUNT(*) args
FROM   all_arguments
WHERE  owner = 'C##CLOUD$SERVICE' AND package_name = 'DBMS_CLOUD_AI'
AND    object_name IN ('GENERATE','FEEDBACK','CREATE_CONVERSATION','DROP_CONVERSATION',
                       'SET_CONVERSATION_ID','CLEAR_CONVERSATION_ID','UPDATE_CONVERSATION','SET_ATTRIBUTE')
GROUP  BY object_name, overload ORDER BY 1, 2;

-- (2) 정확한 파라미터 (이름·타입·기본값 유무)
SELECT object_name, overload, position, argument_name, data_type, defaulted
FROM   all_arguments
WHERE  owner = 'C##CLOUD$SERVICE' AND package_name = 'DBMS_CLOUD_AI'
AND    object_name IN ('GENERATE','FEEDBACK','CREATE_CONVERSATION')
ORDER  BY object_name, overload, position;

-- (3) 대화·피드백 관련 뷰
SELECT view_name FROM all_views
WHERE  view_name LIKE '%CLOUD_AI%' ORDER BY 1;

-- (4) V$MAPPED_SQL 접근 가능 여부
SELECT COUNT(*) FROM v$mapped_sql WHERE ROWNUM <= 1;

-- (5) Agent 패키지 존재 여부 (Phase 4)
SELECT object_name, object_type, status FROM all_objects
WHERE  object_name IN ('DBMS_CLOUD_AI_AGENT') ;
SELECT DISTINCT object_name FROM all_arguments
WHERE  package_name = 'DBMS_CLOUD_AI_AGENT' ORDER BY 1;
SELECT view_name FROM all_views WHERE view_name LIKE '%AI_AGENT%' OR view_name LIKE '%AGENT%TEAM%' ORDER BY 1;

-- (6) 피드백 벡터 인덱스 명명 확인 (피드백 1건 add 후)
SELECT index_name, index_type FROM user_indexes WHERE index_name LIKE '%FEEDBACK%';
```

`owner` 가 `C##CLOUD$SERVICE` 가 아니면 `WHERE package_name = 'DBMS_CLOUD_AI'` 만으로 다시 조회.

---

## 7. 질문 (한 번에 — 승인과 함께 답해 주세요)

1. **선행 조건**: 과제 7·9 로 GEMINI·GROQ 두 프로필 모두 GENERATE 가 실패 중이다. Phase 1 의 화면 검증은 이 경로가 살아야 한다. (a) 사용자가 먼저 복구하는가, (b) 복구 진단(ACL·키·Gemini 측 상태 조회 SQL)을 Phase 1 의 첫 커밋으로 내가 맡는가?
2. **§6 시그니처 검증 SQL 을 로컬에서 돌려 결과를 주실 수 있나?** 이것이 없으면 conversation·FEEDBACK 코드는 추측이 된다(원칙 4). 대안: 결과 파일을 `docs/verified-signatures.md` 에 붙여 푸시해 주면 내가 이어서 쓴다.
3. **파일 위치 관례**: §5 의 제안(저장소 관례 유지)대로 갈지, 요청서 경로(`db/migrations` 등)를 그대로 쓸지.
4. **프리셋 정본**: 하드코딩 `EXAMPLE_QUESTIONS` 를 **삭제**하고 DB 만 정본으로 하는가(정본 한 곳 규칙), 아니면 DB 미연결 시 폴백으로 남기는가.
5. **"프레젠테이션 모드"** = 장표 뷰어(`?slide=`)로 해석했다. 다른 것을 뜻했다면 무엇인지.
6. **runsql 답변에 SQL 자동 첨부**: LLM 호출이 2배가 된다. (a) 항상 showsql 추가 호출, (b) 지금처럼 버튼 클릭 시만, (c) `narrate` 결과에서 SQL 블록 정규식 추출 시도 후 실패 시 (b). 권장 (b).
7. **Phase 2-B 방식**: Annotation DDL 토글 대신 `SET_ATTRIBUTE(annotations=false/true)` 프로필 속성 토글로 가도 되는가(스키마 무손상, 단 프로필 전역).
8. **작업 브랜치**: 지금은 `claude/peaceful-brahmagupta-hzn11i` 에 푸시하고 있다. 로컬에서 바로 보려면 아래 한 줄로 동기화된다. Phase 단위로 `main` 에 fast-forward 머지해도 되는지(머지 권한 요청).

```bash
cd ~/Dev/db26ai-demo/db26ai-demo && git fetch origin && git checkout claude/peaceful-brahmagupta-hzn11i && git pull --ff-only
```

---

## 8. 제안 우선순위 (승인 시 착수 순서)

1. §6 실측 → `docs/verified-signatures.md` 확정 (사용자 or 로컬 세션)
2. 1-C 로그 테이블 + 공통 기록 훅 (다른 모든 기능의 기반, GENERATE 가 죽어 있어도 FAILED 행으로 검증 가능)
3. 1-B 피드백 (FEEDBACK 시그니처 확정 후)
4. 1-A 멀티턴 (CREATE_CONVERSATION 확정 후) → 1-A 화면 마감(그리팅·메타·접기·Shift+Enter)
5. 1-D 프리셋
