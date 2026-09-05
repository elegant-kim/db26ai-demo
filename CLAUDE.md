# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **작업 규율·검증 사이클·반복 함정은 `docs/개발노하우.md`가 정본이다** (아래 `@import`로 자동 로드).
> 이 파일은 **무엇을 만드는가(도메인·구조·API·Oracle 사용법)**의 정본이다.
> **지금 상태가 어떤가**는 `docs/SESSION_HANDOFF.md`를 먼저 읽는다.

## Project Overview

Oracle AI Database 26ai 데모 애플리케이션. **6개 탭**으로 구성:

| # | 탭 라벨 (화면 그대로) | 내용 | 모듈 |
|---|---|---|---|
| 1 | **NL2SQL(Select AI)** | 자연어 → SQL 생성/실행 (`DBMS_CLOUD_AI`) | `select_ai.py` |
| 2 | **AI Vector Search** | PDF 업로드, 벡터/키워드/하이브리드 검색, RAG | `vector_search.py` |
| 3 | **JSON Relational Duality** | Duality View 생성, 관계형↔JSON 비교, CRUD, ETag 동시성 | `duality.py` |
| 4 | **Property Graph** | SQL/PGQ 그래프, SQL vs PGQ 비교, 패턴 질의 | `graph.py` |
| 5 | **개발생산성 향상** | Lock-Free Reservations, Priority Transactions 시뮬레이션 | `productivity.py` |
| 6 | **기타 부가 기능** | AWR HTML 리포트 업로드 → LLM 성능 분석 | `awr_analyzer_v2.py` |

대상: Oracle 26ai의 AI·컨버지드 기능을 처음 접하는 개발자/DBA.
Oracle Autonomous Database + python-oracledb thin client 기반.

## Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # DB 접속정보 및 API 키 설정

# Run (개발 중 — 파일 변경 시 자동 리로드)
python main.py
# → http://localhost:8247

# 운영 반영 — launchd 가 `python main.py` 를 돌리므로 uvicorn reload=True 가 켜져 있다:
#   .py 를 저장하면 서버가 스스로 재기동된다 (진행 중인 SSE 업로드·LLM 요청은 끊긴다 — 2026-09-05 실측).
#   .env·web/dist 변경은 리로드 대상이 아니므로 그때만 수동 재기동:
launchctl kickstart -k gui/$(id -u)/com.db26ai.server
# 재기동 후 헬스체크
curl -s http://localhost:8247/api/health
```

```bash
# 검증 (X-1, 2026-09-04 도입)
pip install -r requirements-dev.txt
./venv/bin/python -m pytest tests/ -q     # 단위 + 통합(서버 없으면 자동 skip)
./venv/bin/ruff check .                   # 린트
scripts/check-secrets.sh                  # 커밋 전 시크릿 게이트
```

```bash
# 프론트 SPA (web/ — 2026-09-05 부터, 이식 중)
cd web && npm install                     # 최초 1회
npm run dev                               # 개발 HMR (http://localhost:5175, /api·/legacy 는 8247 로 프록시)
npm run build                             # undef-check + vue-tsc + vite → web/dist (FastAPI 가 서빙)

# 배포 한 방 = pytest + ruff + npm build + 재기동 + 스모크
scripts/deploy.sh
```

**서빙 규칙**: `/` 와 모든 비-API 경로 = `web/dist/index.html`(history 라우팅), `/assets` = 빌드 산출물, 미정의 `/api/*` = JSON 404.
`web/dist` 가 없으면 503 JSON — `cd web && npm run build`. 레거시(templates·static)는 Phase 6-1(2026-09-05)에 삭제됐다.
로그는 `db26ai.log` (gitignore 대상).

## Architecture

### Backend (Python FastAPI)

| 파일 | 줄수 | 역할 |
|------|-----|------|
| `main.py` | ~85 | FastAPI 엔트리, static 마운트, 라우터 등록, DB 풀 + 벡터 테이블 초기화 + **커넥션 풀 워밍** + keepalive 스케줄러 |
| `app/config.py` | 40 | `.env` → Settings 클래스 (DB, 임베딩, LLM 설정) |
| `app/database.py` | 56 | oracledb 비동기 커넥션 풀 (min=1, max=5, 120초 타임아웃) |
| `app/select_ai.py` | 463 | Select AI 핵심: `DBMS_CLOUD_AI.GENERATE`, 프로필 관리, raw SQL 실행, 스키마 정보, Annotation, EXPLAIN PLAN |
| `app/routes.py` | ~190 | 공통 5개 — health · llm/providers · guide 3. 6탭 API 는 전부 `app/routers/<tab>.py` (D8 완료) |
| `app/routers/graph.py` | 99 | ④ Property Graph 6개 엔드포인트 (5-1 에서 분리, 경로·응답 불변). 이식된 탭의 라우터는 여기 모인다 |
| `app/routers/productivity.py` | 56 | ⑤ 개발생산성 3개 엔드포인트 (5-2 에서 분리) |
| `app/routers/duality.py` | ~135 | ③ Duality 9개 엔드포인트 (5-3 에서 분리) |
| `app/routers/awr.py` | ~200 | ⑥ AWR 3개 엔드포인트 + 세션 캐시 (5-4 에서 분리). **분석은 SSE 가 아니라 JSON 1회** |
| `app/routers/nl2sql.py` | ~230 | ① NL2SQL 8개 엔드포인트 + 요청 모델 + `VALID_ACTIONS` (5-5 에서 분리) |
| `app/routers/vector.py` | ~640 | ② Vector 22개 엔드포인트 — 업로드(SSE)·검색·문서·테이블·임베딩 설정·ONNX (5-6 에서 분리) |
| `app/vector_search.py` | ~1,530 | 벡터 검색 전체: PDF 업로드(SSE), 청킹, 임베딩(ONNX/외부API), 검색 4종, RAG, ONNX 모델 관리, 풀 워밍 |
| `app/duality.py` | ~540 | JSON Relational Duality View 생성/삭제/조회, 관계형↔JSON 비교(**양쪽 PK 정렬 — 같은 행이 마주 봐야 비교다**), 문서 CRUD, ETag 시뮬레이션(**4단계 = DB 의 ORA-42699 거부, 원복은 `_metadata` 없이**) |
| `app/graph.py` | 315 | SQL/PGQ Property Graph 생성/삭제, SQL vs PGQ 비교 쿼리 3종, 패턴 질의 3종 |
| `app/productivity.py` | 270 | 26ai 개발생산성 기능 시뮬레이션 — Lock-Free Reservations, Priority Transactions |
| `app/awr_analyzer_v2.py` | 634 | AWR HTML 파싱(23개 섹션), 8개 섹션 분석 보고서, categoryScores/actionItems, 후속 질문 |
| `app/llm_client.py` | 212 | 공통 LLM 클라이언트 — Groq (Llama 3.3 70B), Google Gemini (2.5 Flash). OpenAI 호환 API |
| `app/scheduler.py` | 83 | APScheduler — ADB Keepalive 주간 핑 (OCI Always Free 회수 방지) |

> `app/awr_analyzer.py`(구버전)는 2026-09-04 삭제됨. V2가 유일한 정본.

### Frontend — `web/` (Vue 3 + TypeScript + Vite + Tailwind 4 + Pinia, 2026-09-05 이식 완료)

구조는 `docs/design/05`, 시각 규칙은 `06` 이 정본. 탭마다 `pages/<tab>/` + `stores/<tab>.ts` + `lib/<tab>.ts` 셋으로 조립한다(`docs/SESSION_HANDOFF.md` §4-5)

| 경로 | 역할 |
|---|---|
| `web/src/lib/menu.ts` | 상단 메뉴 정본 — 순서·짧은 라벨·페이지 제목·아이콘·경로 |
| `web/src/styles/tokens.css` | 팔레트·간격·타이포 토큰. **컴포넌트에 hex 금지** |
| `web/src/lib/normalize.ts` | D11 어댑터 — 응답 배열 키 불일치를 흡수. 키 이름을 아는 유일한 곳 |
| `web/src/lib/sqlHighlight.ts` | Oracle SQL 토크나이저 (레거시 `highlightOracleSQL` 이식) |
| `web/src/components/ui/` | investhub 이식 13종 (Card·Button·Badge·Stat·LoadingBlock·차트 …) |
| `web/src/components/demo/` | db26ai 고유 ★ SqlBlock·ResultTable·CompareView·EmptyState·SubTabs·Segmented·PageHeader·StepList·VersusBox·**PipelineProgress·KvGrid·SessionTabs·ChatThread/ChatComposer**(5-4) |
| `web/src/components/layout/` | AppShell·TopNav·StatusChips(헤더 상태칩 = 옛 사이드바 시스템 상태)·ThemeToggle·Toast |
| `web/src/stores/system.ts` · `composables/useHealth.ts` | `/api/health` 30초 폴링 · 토스트 |
| `web/src/pages/<tab>/` · `stores/<tab>.ts` · `lib/<tab>.ts` | 이식된 탭마다 이 셋 (graph 5-1 · productivity 5-2). 조립 규칙은 `docs/SESSION_HANDOFF.md` §4-5 — 새 탭은 graph 를 복제해 시작한다 |
| `web/src/components/demo/RecentQueriesPanel.vue` | 「실행 쿼리 확인」 슬라이드 패널 — 전 탭 공통, `endpoint` prop 만 다르다 |
| `web/src/pages/*.vue` | 7 페이지 전부 이식 완료(각 `pages/<tab>/` + `stores/<tab>.ts` + `lib/<tab>.ts`). `/` 는 `/nl2sql` 로 리다이렉트 |
| `web/src/components/layout/CommandPalette.vue` · `stores/guide.ts` · `lib/guide.ts` | ⌘K 빠른 이동 + 매뉴얼 탭 데이터(`/api/guide/*`). 기능 카탈로그 정본은 `app/feature_registry.py` (D5) |
| `web/src/composables/useSse.ts` | SSE 수신(fetch + ReadableStream) — PDF 업로드 전용 |
| `web/src/lib/annotations.ts` | SH Display Annotation 세트 정본 (app.js 에서 이전, 5-5) |
| `/styleguide` | 디자인 토대 검증 화면(메뉴에 없음) — 06 캡처와 대조하는 곳 |


### 운영 파일

| 경로 | 역할 |
|---|---|
| `scripts/deploy.sh` | **배포 한 방**: pytest → ruff → `npm run build` → kickstart → 스모크 |
| `deploy/com.db26ai.server.plist` | macOS launchd 상시 구동 정의 |
| `deploy/install-launchd.sh` / `uninstall-launchd.sh` | launchd 등록/해제 |
| `sql/setup/*.sql` | 일회성 셋업·마이그레이션 SQL (**시크릿은 자리표시자**, 원본은 `_private/`에 gitignore) |
| `docs/` | 사람이 읽는 문서 — 아래 "문서 체계" 참조 |

## 문서 체계 (4층)

| 층 | 파일 | 독자 | 로드 | 답하는 질문 |
|---|---|---|---|---|
| L1 | **`CLAUDE.md`** (이 파일) | Claude+사람 | 매 세션 자동 | 이 앱은 무엇이고 어떤 규칙으로 만드나 |
| L2 | **`docs/개발노하우.md`** | Claude | `@import` 자동 | 어떻게 일하나 — 작업 규율·검증·함정 |
| L3 | **`docs/SESSION_HANDOFF.md`** | Claude+사람 | 세션 시작 시 | **지금 상태 / 마지막에 뭘 했나 / 뭐가 미완인가** |
| L4 | `docs/guides/*.md` | 사람 | **앱 「매뉴얼」 탭(`/manual`)** | 어떤 기능이 어디 있고 언제 쓰나 |

부속: `docs/README.md`(인덱스) · `docs/design/`(설계 명세) · `docs/ROADMAP.md`(업데이트 계획서)

## API Endpoints 전체 목록

### 공통
- `GET /api/health` — DB 연결 상태, 스키마, DB 버전, 프로필 수, 문서/청크/임베딩 수, ONNX 모델, 벡터 인덱스 상태
- `GET /api/llm/providers` — 사용 가능한 LLM 제공자 목록

### ① NL2SQL (Select AI) (`app/routers/nl2sql.py`)
- `POST /api/ask` — Select AI 쿼리 실행 (action: runsql/showsql/narrate/explainsql/showprompt/summarize/chat)
- `GET /api/profiles` — AI 프로필 목록
- `POST /api/set-profile` — 프로필 설정 + 속성 조회
- `POST /api/apply-annotations` / `POST /api/remove-annotations` — Display Annotation 일괄 적용/제거
- `POST /api/schema-info` — 프로필의 참조 테이블 스키마 조회
- `POST /api/explain-plan` — SQL 실행계획
- `POST /api/execute-sql` — SELECT 문 직접 실행 (**SELECT로 시작하는 문장만 허용 — `WITH` CTE도 거부됨**)

### ② AI Vector Search (`app/routers/vector.py`)
- `POST /api/vector/upload` — PDF 업로드 (SSE 스트리밍 진행률)
- `POST /api/vector/search` — 벡터/키워드/하이브리드/비교 검색
- `GET /api/vector/documents` · `DELETE /api/vector/documents/{doc_id}` — 문서 목록/삭제
- `GET /api/vector/index-info` — 벡터 인덱스 메타데이터
- `POST /api/vector/embedding-info` — 임베딩 과정 정보
- `POST /api/vector/drop-tables` · `POST /api/vector/create-tables` — Vector Store 테이블 삭제/생성
- `POST /api/vector/table-definition` · `table-data` · `table-indexes` — 테이블 정의/데이터/인덱스 조회
- `GET /api/vector/recent-queries` — V$SQL 최근 벡터 쿼리
- `POST /api/vector/explain-plan` — 벡터 검색 실행계획
- `POST /api/vector/visualize` — 벡터 시각화 데이터

### 임베딩 & ONNX 관리 (`app/routers/vector.py`)
- `GET /api/vector/embedding-config` · `POST /api/vector/embedding-config` — 임베딩 소스/모델 조회·변경
- `GET /api/vector/onnx-models` — DB 내 ONNX 모델 목록
- `POST /api/vector/onnx-models/upload` · `load-cloud` — ONNX 파일 업로드 / OML Cloud 로드
- `DELETE /api/vector/onnx-models/{model_name}` — 삭제
- `POST /api/vector/onnx-models/test` — 테스트 임베딩 (차원·소요시간 반환)
- `GET /api/vector/onnx-models/{model_name}/detail` — 상세

### ③ JSON Relational Duality (`app/routers/duality.py`)
- `POST /api/duality/create-views` · `POST /api/duality/drop-views` — Duality View 생성/삭제
- `GET /api/duality/views` — View 목록
- `POST /api/duality/compare` — 관계형 SQL JOIN vs Duality JSON 비교
- `POST /api/duality/docs` · `POST /api/duality/doc` · `POST /api/duality/doc/update` — 문서 목록/조회/수정
- `POST /api/duality/etag-simulation` — ETag 낙관적 동시성 제어 시뮬레이션
- `GET /api/duality/recent-queries` — V$SQL 최근 쿼리

### ④ Property Graph (`app/routers/graph.py`)
- `POST /api/graph/create` · `POST /api/graph/drop` — Property Graph 생성/삭제
- `GET /api/graph/queries` — 비교 쿼리 3종 + 패턴 쿼리 3종 목록
- `POST /api/graph/compare` — 같은 질문을 SQL과 SQL/PGQ로 각각 실행해 결과·시간 비교
- `POST /api/graph/pattern` — MATCH 패턴 질의 실행
- `GET /api/graph/recent-queries` — V$SQL 최근 쿼리

### ⑤ 개발생산성 향상 (`app/routers/productivity.py`)
- `POST /api/productivity/lockfree` — Lock-Free Reservations 시뮬레이션
- `POST /api/productivity/priority-tx` — Priority Transactions 시뮬레이션
- `GET /api/productivity/recent-queries` — V$SQL 최근 쿼리

### ⑥ 기타 부가 기능 (AWR) (`app/routers/awr.py`)
- `POST /api/awr/analyze` — AWR HTML 업로드 + LLM 분석 (**JSON 1회 응답, 30~120초** — SSE 아님. 2026-09-05 정정)
- `POST /api/awr/followup` — 후속 질문
- `GET /api/awr/source/{session_id}` — AWR 원본 HTML 반환

## Vector Search 상세

### 검색 모드 4가지
1. **의미 검색 (vector)**: `VECTOR_DISTANCE(embedding, (SELECT VECTOR_EMBEDDING(model USING :q AS data) FROM dual), COSINE)` — 코사인 유사도
2. **키워드 검색 (keyword)**: `CONTAINS(chunk_text, :q, 1)` + `SCORE(1)` (Oracle Text). 인덱스 없거나 실패 시 `LIKE` 폴백
3. **하이브리드 (hybrid, 26ai 기능)**: 단일 SQL에서 CONTAINS + VECTOR_DISTANCE 결합.
   `hybrid_score = 0.7 × vector_similarity + 0.3 × keyword_score/100`.
   SCORE는 WHERE에 CONTAINS가 있어야 쓸 수 있는데 WHERE에 두면 키워드 미매칭 청크가 걸러지므로,
   **CONTAINS를 LEFT JOIN 서브쿼리로 분리하고 `NVL(k.kw_score, 0)`으로 0을 채운다.**
4. **비교 모드 (compare)**: 키워드/벡터 검색 동시 실행, UI에서 좌우 비교 (RAG 미생성)

### 임베딩 듀얼 모드
- **DB 내장 (ONNX)**: `EMBEDDING_SOURCE=database` — `VECTOR_EMBEDDING(model USING text AS data)`
- **외부 API**: `EMBEDDING_SOURCE=external` — Google AI Studio OpenAI-compatible embedding API
- 「임베딩 · ONNX」 서브탭에서 런타임 전환 가능 (인덱스 모델과 다르면 화면이 경고한다)
- ⚠ **모델을 바꾸면 벡터 차원이 바뀌고 HNSW 인덱스가 깨진다** — 아래 Critical Notes 참조

### PDF 업로드 파이프라인 (SSE 스트리밍)
1. 문서 레코드 생성 (DOCUMENTS)
2. pdfplumber로 PDF 텍스트 추출
3. 청킹: `DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS` 시도 → 실패 시 Python 청킹 (500자, 50 overlap)
4. 임베딩 생성 + DB 저장 (청크별 진행률 SSE). **임베딩 실패 건수와 첫 오류를 응답에 실어 보낸다**
5. 문서 상태 → 'indexed'

### DB 테이블·인덱스 구조
```sql
CREATE TABLE documents (
    doc_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    filename VARCHAR2(500), upload_date TIMESTAMP DEFAULT SYSTIMESTAMP,
    status VARCHAR2(20) DEFAULT 'processing', chunks_count NUMBER
);

CREATE TABLE doc_chunks (
    chunk_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id NUMBER NOT NULL, chunk_text CLOB,
    source_file VARCHAR2(500), page_num NUMBER,
    embedding VECTOR                      -- 차원 무제약. 차원을 고정하는 것은 인덱스다
);

-- 벡터 인덱스 (main.py 기동 시 자동 생성)
CREATE VECTOR INDEX doc_chunks_hnsw_idx ON doc_chunks(embedding)
ORGANIZATION INMEMORY NEIGHBOR GRAPH DISTANCE COSINE WITH TARGET ACCURACY 95;

-- 전문검색 인덱스 (sql/setup/50_oracle_text_index.sql)
CREATE INDEX doc_chunks_text_idx ON doc_chunks(chunk_text)
INDEXTYPE IS CTXSYS.CONTEXT
PARAMETERS ('LEXER CTXSYS.WORLD_LEXER SYNC (ON COMMIT)');
```

## Environment Variables (.env)

```bash
# Database
ORACLE_DSN=db26aidemo_medium          # 신규 테넌시 ADB (2026-04-14 이관 완료)
ORACLE_USER=admin
ORACLE_PASSWORD=<password>
ORACLE_WALLET_DIR=/path/to/Wallet_DB26AIDEMO
ORACLE_WALLET_PASSWORD=<password>

SELECT_AI_PROFILE=                     # 빈 값이면 DB에서 동적 결정

APP_HOST=0.0.0.0
APP_PORT=8247

# Vector Embedding
EMBEDDING_SOURCE=database              # "database"(ONNX) 또는 "external"
EMBEDDING_MODEL=MULTILINGUAL_E5_BASE   # ONNX 모델명 또는 외부 API 모델명
EMBEDDING_DIM=768                      # 표시용 — 실제 차원은 모델이 결정한다
EMBEDDING_API_URL=                     # 외부 API 사용 시
EMBEDDING_API_KEY=

# LLM (AWR 분석, RAG 답변 생성용)
LLM_PROVIDER=google                    # "groq" 또는 "google"
GROQ_API_KEY= / GROQ_MODEL=llama-3.3-70b-versatile
GOOGLE_API_KEY= / GOOGLE_MODEL=gemini-2.5-flash
```

## Key Oracle DB Dependencies

- `DBMS_CLOUD_AI.GENERATE(prompt, profile_name, action)` / `SET_PROFILE` — NL2SQL 핵심
- `DBA_CLOUD_AI_PROFILES` / `DBA_CLOUD_AI_PROFILE_ATTRIBUTES` — 프로필 메타데이터 (USER_ 뷰 폴백)
- `ALL_ANNOTATIONS_USAGE` — 테이블/컬럼 Annotation (23ai+)
- `DBMS_XPLAN.DISPLAY()` — 실행계획 · `V$SQL` — 최근 SQL 조회
- `VECTOR_EMBEDDING(model USING expr AS data)` — DB 내 ONNX 임베딩
- `VECTOR_DISTANCE(v1, v2, COSINE)` — 벡터 유사도
- `CONTAINS(column, query, label)` / `SCORE(label)` — Oracle Text 키워드 검색
- `DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS()` — DB 기반 텍스트 청킹
- `DBMS_DATA_MINING.IMPORT_ONNX_MODEL()` / `DBMS_VECTOR.LOAD_ONNX_MODEL()` — ONNX 모델 로드
- `CREATE PROPERTY GRAPH` / `GRAPH_TABLE(... MATCH ... COLUMNS ...)` — SQL/PGQ (SQL:2023)
- `CREATE OR REPLACE JSON RELATIONAL DUALITY VIEW` — Duality View
- Sample schema: **SH** (Sales History) — ADMIN 스키마에 적재됨

## Critical Implementation Notes

### ⚡ VECTOR_EMBEDDING은 반드시 스칼라 서브쿼리로 감쌀 것 (100배 차이)
쿼리 안에 `VECTOR_EMBEDDING(...)`을 인라인으로 두면 **행마다 재평가**된다.
79청크 기준 hybrid 11.3초 / vector 5.4초 → 감싸면 0.1초 / 0.095초 (2026-09-04 실측).
```sql
-- 올바른 사용법
VECTOR_DISTANCE(embedding, (SELECT VECTOR_EMBEDDING(MODEL USING :q AS data) FROM dual), COSINE)
-- 잘못된 사용법 (행마다 재평가!)
VECTOR_DISTANCE(embedding, VECTOR_EMBEDDING(MODEL USING :q AS data), COSINE)
```

### VECTOR_EMBEDDING 모델명은 bind variable 불가
모델명은 SQL identifier(리터럴)여야 한다. `:model_name`으로 넘기면 silent failure.
반드시 f-string 삽입 + 이스케이프(`replace("'", "")` 등).

### ONNX 모델은 커넥션마다 최초 1회 로드된다 (콜드스타트)
E5_BASE 5.2초 / E5_SMALL 1.1초, 2회차부터 20~40ms. 풀이 max=5라 데모 중 산발적 멈춤이 생긴다.
→ `warm_embedding_pool()`이 기동 시 커넥션 5개를 **동시에** 잡아 예열한다.
순차 acquire/release 하면 같은 커넥션이 재사용되어 하나만 달궈지니 주의.

### 임베딩 모델을 바꾸면 HNSW 인덱스를 재생성해야 한다
`embedding VECTOR` 컬럼은 차원 무제약이지만 **HNSW 인덱스가 첫 데이터의 차원으로 고정**된다.
차원이 다른 벡터를 넣으면 `ORA-51932: Mismatched dimension count`.
→ 순서: 기존 청크 삭제 → `DROP INDEX doc_chunks_hnsw_idx` → 새 모델로 재적재 → 인덱스 재생성.

### SQL/PGQ: GRAPH_TABLE() 안에서 집계함수 불가
`COLUMNS` 절에 `COUNT`/`SUM`을 쓰면 `ORA-49011`. 원시 행을 투영하고 **바깥에서 집계**한다.

### Duality View 문서에 `_metadata.etag` 가 실려 있으면 UPDATE 때 DB 가 ETag 를 검사한다
문서를 읽은 그대로(`_metadata` 포함) 고쳐서 UPDATE 하면 현재 ETag 와 다를 때 `ORA-42699` 로 거부된다 — 이것이 낙관적 잠금이다.
**원복·무조건 쓰기는 `_metadata` 를 뺀 문서로 보낸다**(검사 생략). 2026-09-05 까지 ETag 시뮬의 원복이 옛 ETag 를 실은 채 UPDATE 해
조용히 실패했고, 그 결과 고객 5명의 신용한도가 +1 씩 오염돼 있었다(되돌림). `SAMPLE(n)` 절은 테이블 별칭 **앞**에 온다.

### VECTOR 컬럼에는 집계함수를 직접 못 쓴다
`COUNT(embedding)` → `ORA-22849`. `COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END)`로 우회.

### LOB 처리
Oracle LOB 값은 `await _lob_to_str(val)` 변환 필수. `hasattr(row[0], 'read')` 체크 후 변환.

### DDL과 bind variable
`ALTER TABLE ... ANNOTATIONS` 등 DDL은 bind variable 사용 불가.
문자열 포맷팅 + `replace("'", "''")` 이스케이프.

### `except: pass` 금지
이 저장소에서 이 패턴이 만든 버그가 2026-09-04 하루에 **4건** 확인됐다
(ONNX 거짓보고 5개월, 임베딩 전량 NULL을 "성공"으로 보고 등).
예외를 삼켜야 하는 자리라도 **`logger.warning`은 반드시 남긴다.**

### 프론트 배포 = 빌드 + 재기동
SPA(`web/`)는 Vite 해시 파일명이라 캐시버스팅 버전이 없다. `npm run build` 뒤 `scripts/deploy.sh` 또는 kickstart.
배포 직후 옛 chunk 404 는 `main.ts` 의 stale-chunk 자동 새로고침이 흡수한다.

### SSE 스트리밍
**PDF 업로드만** `StreamingResponse` + `text/event-stream` 이다(프론트는 `fetch` + `ReadableStream`).
AWR 분석은 SSE 가 아니라 분석 후 JSON 1회 — 화면의 진행 표시는 타이머 연출이다(2026-09-05 정정. 그 전까지 이 문단이 코드와 달랐다).

### API 응답 구조가 엔드포인트마다 다르다 (알려진 부채 D11)
결과 배열 키가 `data`(execute-sql) / `chunks`(vector/search) / `sql_data`·`pgq_data`(graph/compare) /
`models`(onnx)로 통일돼 있지 않다. **SPA 이식 시 정규화 대상.**

## Important Conventions

- UI 텍스트는 전부 한국어 (데모 대상: 한국 개발자/DBA)
- `explainsql` action은 한국어 지시 자동 추가: `"(Please explain in Korean / 한국어로 설명해 주세요)"`
- `execute_raw_sql()` — SELECT 문만 허용 (보안). `WITH` CTE도 거부되니 주의
- 프론트엔드 fetch 120초 타임아웃 = DB call 타임아웃과 일치
- 프로필 이름에 'SH' 포함 시 SH 스키마용 예시 질문/Annotation 세트 적용 (`web/src/lib/annotations.ts` · `lib/nl2sql.ts`)
- 새 화면의 기본 프로필 우선순위는 `stores/nl2sql.ts` 의 `PREFER` (2026-09-05 현재 GEMINI → GROQ; GROQ 프로필이 ORA-20404 로 실패 중)
- AWR 결과 탭과 벡터 검색 세션 탭은 같은 `SessionTabs` 컴포넌트를 쓴다
- 저장소는 **GitHub 공개(PUBLIC)** — 커밋 전 시크릿 검사 필수 (`docs/개발노하우.md` 참조)

@docs/개발노하우.md
