# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Oracle AI Database 26ai 데모 애플리케이션. 3개의 메인 탭으로 구성:
1. **NL2SQL (Select AI)** — 자연어 → SQL 생성/실행 (Oracle DBMS_CLOUD_AI)
2. **AI Vector Search** — PDF 업로드, 벡터/키워드/하이브리드 검색, RAG 답변 생성
3. **기타 부가 기능** — AWR HTML 리포트 업로드 → LLM 기반 성능 분석

대상: Oracle 26ai의 AI 기능(Select AI, Vector Search, ONNX 임베딩)을 처음 접하는 개발자/DBA.
Oracle Autonomous Database + python-oracledb thin client 기반.

## Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # DB 접속정보 및 API 키 설정

# Run (파일 변경 시 자동 리로드)
python main.py
# → http://localhost:8000
```

빌드 불필요 — Vue 3, Chart.js는 CDN에서 로드.

## Architecture

### Backend (Python FastAPI)

| 파일 | 역할 |
|------|------|
| `main.py` | FastAPI 엔트리, static 마운트, 라우터 등록, DB 풀 + 벡터 테이블 초기화 |
| `app/config.py` | `.env` → Settings 클래스 (DB, 임베딩, LLM 설정) |
| `app/database.py` | oracledb 비동기 커넥션 풀 (min=1, max=5, 120초 타임아웃) |
| `app/select_ai.py` | Select AI 핵심: `DBMS_CLOUD_AI.GENERATE`, 프로필 관리, raw SQL 실행, 스키마 정보, Annotation, EXPLAIN PLAN |
| `app/routes.py` | 모든 API 엔드포인트 (`/api` prefix) — NL2SQL, Vector Search, ONNX 모델 관리, AWR 분석 |
| `app/vector_search.py` | 벡터 검색 전체: PDF 업로드(SSE 스트리밍), 청킹, 임베딩(ONNX/외부API), 검색(vector/keyword/hybrid/compare), RAG, ONNX 모델 관리 |
| `app/awr_analyzer.py` | AWR HTML 파싱 (HTMLParser), 섹션 추출, LLM 분석 프롬프트 빌드, 후속 질문 |
| `app/llm_client.py` | 공통 LLM 클라이언트 — Groq (Llama 3.3 70B), Google Gemini (2.5 Flash) 지원. OpenAI 호환 API 사용 |

### Frontend (Single-page, no build)

| 파일 | 역할 |
|------|------|
| `templates/index.html` | Jinja2 템플릿, Vue 3 `[[ ]]` 구분자 (Jinja `{{ }}` 충돌 방지) |
| `static/js/app.js` | Vue 3 Composition API (`createApp` + `setup()`), 모든 반응형 상태 및 API 호출 |
| `static/css/style.css` | CSS 변수 기반 커스텀 스타일 (Oracle 테마: `--oracle-red: #C74634`) |

## API Endpoints 전체 목록

### NL2SQL
- `POST /api/ask` — Select AI 쿼리 실행 (action: runsql/showsql/narrate/explainsql/showprompt/summarize/chat)
- `GET /api/profiles` — AI 프로필 목록
- `POST /api/set-profile` — 프로필 설정 + 속성 조회
- `POST /api/apply-annotations` — Display Annotation 일괄 적용
- `POST /api/remove-annotations` — Annotation 일괄 제거
- `POST /api/schema-info` — 프로필의 참조 테이블 스키마 조회
- `POST /api/explain-plan` — SQL 실행계획
- `POST /api/execute-sql` — SELECT 문 직접 실행
- `GET /api/health` — DB 연결 상태 + 스키마명

### Vector Search
- `POST /api/vector/upload` — PDF 업로드 (SSE 스트리밍 진행률)
- `POST /api/vector/search` — 벡터/키워드/하이브리드/비교 검색
- `GET /api/vector/documents` — 업로드 문서 목록
- `DELETE /api/vector/documents/{doc_id}` — 문서 삭제
- `GET /api/vector/index-info` — 벡터 인덱스 메타데이터
- `POST /api/vector/embedding-info` — 임베딩 과정 정보
- `POST /api/vector/drop-tables` — Vector Store 테이블 삭제
- `POST /api/vector/create-tables` — Vector Store 테이블 생성/연결
- `POST /api/vector/table-definition` — 테이블 컬럼 정의
- `POST /api/vector/table-data` — 테이블 데이터 샘플
- `POST /api/vector/table-indexes` — 인덱스 조회
- `GET /api/vector/recent-queries` — V$SQL 최근 벡터 쿼리
- `POST /api/vector/explain-plan` — 벡터 검색 실행계획

### Embedding & ONNX 관리
- `GET /api/vector/embedding-config` — 현재 임베딩 설정 조회
- `POST /api/vector/embedding-config` — 임베딩 소스/모델 변경
- `GET /api/vector/onnx-models` — DB 내 ONNX 모델 목록
- `POST /api/vector/onnx-models/upload` — ONNX 파일 업로드
- `POST /api/vector/onnx-models/load-cloud` — OML Cloud에서 ONNX 모델 로드
- `DELETE /api/vector/onnx-models/{model_name}` — ONNX 모델 삭제
- `POST /api/vector/onnx-models/test` — ONNX 모델 테스트 임베딩
- `GET /api/vector/onnx-models/{model_name}/detail` — ONNX 모델 상세

### LLM
- `GET /api/llm/providers` — 사용 가능한 LLM 제공자 목록

### AWR 분석
- `POST /api/awr/analyze` — AWR HTML 업로드 + LLM 분석 (SSE 스트리밍)
- `POST /api/awr/followup` — 후속 질문
- `GET /api/awr/source/{session_id}` — AWR 원본 HTML 반환

## Vector Search 상세

### 검색 모드 4가지
1. **의미 검색 (vector)**: `VECTOR_DISTANCE(embedding, VECTOR_EMBEDDING(model USING query AS data), COSINE)` — 코사인 유사도
2. **키워드 검색 (keyword)**: `CONTAINS(chunk_text, query, 1)` + `SCORE(1)` (Oracle Text). 미설정 시 `LIKE` 폴백
3. **하이브리드 검색 (hybrid, 26ai 기능)**: 단일 SQL에서 CONTAINS + VECTOR_DISTANCE 결합. `hybrid_score = 0.7 × vector_similarity + 0.3 × keyword_score/100`. CONTAINS 실패 시 vector-only 폴백
4. **비교 모드 (compare)**: 키워드/벡터 검색 동시 실행, UI에서 좌우 비교

### 임베딩 듀얼 모드
- **DB 내장 (ONNX)**: `EMBEDDING_SOURCE=database` — `VECTOR_EMBEDDING(model USING text AS data)` SQL
- **외부 API**: `EMBEDDING_SOURCE=external` — Google AI Studio OpenAI-compatible embedding API
- 사이드바 "임베딩 설정"에서 런타임 전환 가능 (서버 재시작 불필요)
- 전환 시 confirm 대화 → 기존 검색 결과를 세션 탭으로 자동 보존 → vectorMessages 초기화

### 세션 탭 (검색 결과 보존)
- 임베딩 설정 전환 시 `saveCurrentVectorSession()` → `vectorSessions` 배열에 저장
- AWR 결과 탭과 동일한 스타일 (`awr-result-tabs` / `awr-result-tab` CSS)
- 탭 표시: `label(ONNX/모델명 또는 API/모델명) + provider(ONNX|API) + timestamp + × 닫기`
- `vectorActiveSession`: -1 = 현재 세션, 0+ = 저장된 이전 세션 인덱스
- `switchVectorSession(index)`, `removeVectorSession(index)` 함수

### PDF 업로드 파이프라인 (SSE 스트리밍)
1. 문서 레코드 생성 (DOCUMENTS 테이블)
2. pdfplumber로 PDF 텍스트 추출
3. 청킹: `DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS` 시도 → 실패 시 Python 청킹 (500자, 50 overlap)
4. 임베딩 생성 + DB 저장 (각 청크별 진행률 SSE 이벤트)
5. 문서 상태 업데이트 → 'indexed'

### DB 테이블 구조
```sql
-- 문서 메타데이터
CREATE TABLE documents (
    doc_id      NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    filename    VARCHAR2(500),
    upload_date TIMESTAMP DEFAULT SYSTIMESTAMP,
    status      VARCHAR2(20) DEFAULT 'processing',
    chunks_count NUMBER
);

-- 청크 + 임베딩 벡터
CREATE TABLE doc_chunks (
    chunk_id    NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id      NUMBER NOT NULL,
    chunk_text  CLOB,
    source_file VARCHAR2(500),
    page_num    NUMBER,
    embedding   VECTOR
);

-- HNSW 벡터 인덱스
CREATE VECTOR INDEX doc_chunks_hnsw_idx
ON doc_chunks(embedding)
ORGANIZATION INMEMORY NEIGHBOR GRAPH
DISTANCE COSINE
WITH TARGET ACCURACY 95;
```

## AWR 리포트 분석 (기타 부가 기능 탭)

- AWR HTML 파일 업로드 (최대 20MB) → `parse_awr_html()` → 30+ 섹션 추출
- LLM 분석 (Groq/Google Gemini 선택 가능) → JSON 구조화 결과
- 카테고리별 성능 점수, 발견사항, 권장사항 표시
- 후속 질문 지원
- 다중 결과 탭 관리 (`awrResults` 배열, `awrActiveTab` 인덱스)
- AWR 원본 HTML 보기 기능 (`/api/awr/source/{session_id}`)

## Environment Variables (.env)

```bash
# Database
ORACLE_DSN=<host>:<port>/<service> 또는 tns_alias
ORACLE_USER=<username>
ORACLE_PASSWORD=<password>
ORACLE_WALLET_DIR=/path/to/wallet    # ADB 사용 시
ORACLE_WALLET_PASSWORD=<password>

# AI Profile (빈 값이면 DB에서 동적 결정)
SELECT_AI_PROFILE=

# App
APP_HOST=0.0.0.0
APP_PORT=8000

# Vector Embedding
EMBEDDING_SOURCE=database              # "database" (ONNX) 또는 "external"
EMBEDDING_MODEL=MULTI_MINILM_L12_V2   # ONNX 모델명 또는 외부 API 모델명
EMBEDDING_API_URL=                     # 외부 API URL
EMBEDDING_API_KEY=                     # 외부 API 키
EMBEDDING_DIM=768                      # 벡터 차원

# LLM (AWR 분석, RAG 답변 생성용)
LLM_PROVIDER=google                    # "groq" 또는 "google"
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
GOOGLE_API_KEY=
GOOGLE_MODEL=gemini-2.5-flash
```

## Key Oracle DB Dependencies

- `DBMS_CLOUD_AI.GENERATE(prompt, profile_name, action)` — NL2SQL 핵심
- `DBMS_CLOUD_AI.SET_PROFILE(profile_name)` — AI 프로필 설정
- `DBA_CLOUD_AI_PROFILES` / `DBA_CLOUD_AI_PROFILE_ATTRIBUTES` — 프로필 메타데이터 (USER_ 뷰 폴백)
- `ALL_ANNOTATIONS_USAGE` — 테이블/컬럼 Annotation (Oracle 23ai+ 기능)
- `DBMS_XPLAN.DISPLAY()` — 실행계획
- `V$SQL` — 최근 SQL 조회
- `VECTOR_EMBEDDING(model USING expr AS data)` — DB 내 ONNX 모델 임베딩
- `VECTOR_DISTANCE(v1, v2, COSINE)` — 벡터 유사도 거리
- `CONTAINS(column, query, label)` / `SCORE(label)` — Oracle Text 키워드 검색
- `DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS()` — DB 기반 텍스트 청킹
- `DBMS_DATA_MINING.IMPORT_ONNX_MODEL()` — ONNX 모델 로드
- Sample schemas: SH (Sales History)

## Critical Implementation Notes

### VECTOR_EMBEDDING 모델명은 bind variable 불가
Oracle `VECTOR_EMBEDDING` 함수의 첫 번째 인자(모델명)는 SQL identifier(리터럴)이어야 하며, bind variable(`:model_name`)로 전달하면 silent failure 발생. 반드시 f-string으로 삽입:
```python
# 올바른 사용법
sql = f"SELECT VECTOR_EMBEDDING({safe_model} USING :text_data AS data) FROM dual"

# 잘못된 사용법 (silent failure!)
sql = "SELECT VECTOR_EMBEDDING(:model_name USING :text_data AS data) FROM dual"
```

### LOB 처리
Oracle LOB 값은 `await _lob_to_str(val)` 변환 필수. `hasattr(row[0], 'read')` 체크 후 변환.

### DDL과 bind variable
`ALTER TABLE ... ANNOTATIONS` 등 DDL은 bind variable 사용 불가. 문자열 포맷팅 + `replace("'", "''")`로 이스케이프.

### Cache Busting
`style.css?v=N`, `app.js?v=N` — 코드 변경 시 반드시 버전 증가. 현재 v=46.

### SSE 스트리밍
PDF 업로드와 AWR 분석은 `StreamingResponse` + `text/event-stream`으로 진행률 실시간 전달. 프론트엔드는 `EventSource` 또는 `fetch` + `ReadableStream`으로 수신.

### 검색 모드별 SQL 패턴
- **Vector (ONNX)**: `VECTOR_DISTANCE(embedding, VECTOR_EMBEDDING({model} USING :query AS data), COSINE)`
- **Vector (외부API)**: `VECTOR_DISTANCE(embedding, TO_VECTOR(:query_vector), COSINE)` — 벡터를 먼저 외부에서 생성 후 문자열로 바인드
- **Hybrid**: 위 vector SQL + `CONTAINS(chunk_text, :query_kw, 1)` + `SCORE(1)` 결합

## Important Conventions

- UI 텍스트는 전부 한국어 (데모 대상: 한국 개발자/DBA)
- `explainsql` action은 한국어 지시 자동 추가: `"(Please explain in Korean / 한국어로 설명해 주세요)"`
- `execute_raw_sql()` — SELECT 문만 허용 (보안)
- 프론트엔드 fetch 120초 타임아웃 = DB call 타임아웃과 일치
- 프로필 이름에 'SH' 포함 시 SH 스키마용 예시 질문/Annotation 세트 적용
- AWR 결과 탭과 벡터 검색 세션 탭은 동일한 CSS 클래스 (`awr-result-tabs`/`awr-result-tab`) 공유
