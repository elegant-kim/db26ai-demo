# Oracle AI Database 26ai Demo - 기능 설명서

## 개요

Oracle Autonomous Database 26ai의 AI 기능을 체험할 수 있는 데모 웹 애플리케이션입니다.
자연어 SQL 생성, 벡터 검색, JSON Duality View, Property Graph, 개발생산성 향상 기능 등
Oracle 26ai의 핵심 기능을 하나의 화면에서 직접 실행하고 결과를 확인할 수 있습니다.

- **대상**: Oracle 26ai AI 기능을 처음 접하는 개발자 / DBA
- **기술 스택**: Python FastAPI, Vue 3 (CDN), python-oracledb (thin client)
- **UI 언어**: 한국어

---

## 1. NL2SQL (Select AI)

Oracle `DBMS_CLOUD_AI.GENERATE`를 활용하여 자연어 질문을 SQL로 변환하고 실행하는 기능입니다.

### 1.1 AI 프로필 관리

| 기능 | 설명 |
|------|------|
| 프로필 선택 | `DBA_CLOUD_AI_PROFILES`에서 등록된 AI 프로필 목록 조회 및 전환 |
| 프로필 속성 조회 | 선택된 프로필의 provider, model, 참조 테이블 등 상세 속성 표시 |

### 1.2 실행 모드 (7가지 Action)

| 모드 | Action | 설명 |
|------|--------|------|
| SQL 실행 | `runsql` | 자연어 → SQL 생성 → 자동 실행 → 결과 테이블 표시 |
| SQL 보기 | `showsql` | 생성된 SQL만 표시 (실행하지 않음) |
| 설명 | `narrate` | 질문에 대한 자연어 설명 생성 |
| SQL 해설 | `explainsql` | 생성된 SQL에 대한 한국어 해설 |
| 프롬프트 | `showprompt` | LLM에 전달되는 내부 프롬프트 확인 |
| 요약 | `summarize` | 조회 결과 요약 |
| 대화 | `chat` | 자유형 대화 모드 |

### 1.3 스키마 뷰어

- 프로필에 연결된 참조 테이블의 컬럼 정의, 데이터 타입, 코멘트 조회
- SH(Sales History) 스키마 기반

### 1.4 Annotation 관리

- **Display Annotation 일괄 적용**: 테이블/컬럼에 한국어 설명 Annotation을 추가하여 Select AI의 SQL 생성 정확도 향상
- **Annotation 일괄 제거**: 적용된 Annotation 제거
- Oracle 23ai+ `ALL_ANNOTATIONS_USAGE` 뷰 기반

### 1.5 실행계획 (Explain Plan)

- 생성된 SQL의 `EXPLAIN PLAN` 조회
- `DBMS_XPLAN.DISPLAY()` 결과 표시

### 1.6 직접 SQL 실행

- 사용자가 직접 입력한 SELECT 문 실행 (보안상 SELECT만 허용)

---

## 2. AI Vector Search

PDF 문서를 업로드하고, 벡터 임베딩 기반 유사도 검색 및 RAG(Retrieval-Augmented Generation) 답변을 생성하는 기능입니다.

### 2.1 Vector Store 관리

| 기능 | 설명 |
|------|------|
| 테이블 생성 | `DOCUMENTS`, `DOC_CHUNKS` 테이블 + HNSW 벡터 인덱스 생성 |
| 테이블 삭제 | Vector Store 테이블 전체 삭제 |
| 테이블 정의 조회 | 컬럼 정의, 데이터 타입 확인 |
| 테이블 데이터 조회 | 저장된 데이터 샘플 확인 |
| 인덱스 조회 | 벡터 인덱스 메타데이터 확인 |

### 2.2 PDF 업로드

- PDF 파일 업로드 → 텍스트 추출 (pdfplumber) → 청킹 → 임베딩 생성 → DB 저장
- **청킹**: `DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS` 시도 → 실패 시 Python 청킹 (500자, 50 overlap) 폴백
- SSE(Server-Sent Events) 스트리밍으로 실시간 진행률 표시
- 업로드된 문서 목록 관리 및 개별 삭제

### 2.3 검색 모드 (4가지)

| 모드 | SQL 핵심 | 설명 |
|------|----------|------|
| 의미 검색 (Semantic) | `VECTOR_DISTANCE(COSINE)` | 벡터 임베딩 기반 코사인 유사도 검색 |
| 키워드 검색 (Keyword) | `CONTAINS()` / `LIKE` | Oracle Text 전문 검색 (미설정 시 LIKE 폴백) |
| 하이브리드 검색 (Hybrid) | `CONTAINS` + `VECTOR_DISTANCE` | 26ai 기능 - 단일 SQL에서 키워드 + 벡터 결합 (가중치: 벡터 0.7, 키워드 0.3) |
| 비교 모드 (Compare) | 키워드 + 벡터 병렬 | 두 검색 방식 결과를 좌우로 나란히 비교 |

### 2.4 RAG 답변 생성

- 검색된 청크를 컨텍스트로 LLM에 전달하여 자연어 답변 생성
- LLM 제공자 선택 가능 (사이드바에서 전환)

### 2.5 임베딩 설정

| 모드 | 설명 |
|------|------|
| DB 내장 (ONNX) | `VECTOR_EMBEDDING(모델명 USING text AS data)` — DB 안에서 임베딩 생성 |
| 외부 API | Google AI Studio 등 외부 임베딩 API 호출 |

- 사이드바에서 런타임 전환 가능 (서버 재시작 불필요)
- 전환 시 기존 검색 결과를 세션 탭으로 자동 보존

### 2.6 ONNX 임베딩 모델 관리

| 기능 | 설명 |
|------|------|
| 모델 목록 조회 | `USER_MINING_MODELS` 뷰에서 ONNX 모델 목록 표시 |
| 로컬 파일 업로드 | `.onnx` 파일 드래그앤드롭 → `DBMS_VECTOR.LOAD_ONNX_MODEL()` 적재 (최대 3GB) |
| OCI Object Storage 적재 | PAR URL 입력 → `DBMS_CLOUD.GET_OBJECT()` → `DBMS_VECTOR.LOAD_ONNX_MODEL()` |
| 모델 테스트 | 샘플 텍스트로 임베딩 생성 → 차원 수, 처리 시간, 벡터 미리보기 |
| 모델 삭제 | `DBMS_DATA_MINING.DROP_MODEL()` |
| 모델 전환 | 사용할 ONNX 모델 선택 |

### 2.7 실행 쿼리 확인

- `V$SQL`에서 최근 벡터 관련 쿼리 조회
- 벡터 검색 SQL의 실행계획(Explain Plan) 확인

---

## 3. JSON Relational Duality

하나의 테이블 데이터를 관계형(SQL)과 JSON 문서 양쪽으로 동시에 접근할 수 있는 Oracle 23ai Duality View 기능 데모입니다.

### 3.1 Duality View 관리

| 기능 | 설명 |
|------|------|
| Duality View 생성 | `CUSTOMERS_DV`, `PRODUCTS_DV` 두 개의 Duality View를 GraphQL DDL로 생성 |
| Duality View 삭제 | 생성된 Duality View 제거 |
| View 목록 조회 | 현재 등록된 Duality View 확인 |

**생성되는 Duality View:**

- `CUSTOMERS_DV`: 고객 정보 (이름, 성별, 출생연도, 도시, 소득수준, 신용한도, 이메일)
- `PRODUCTS_DV`: 제품 정보 (제품명, 설명, 카테고리, 정가, 최저가)

### 3.2 관계형 vs JSON 비교

- 동일한 데이터를 관계형 SQL JOIN과 JSON Duality View로 각각 조회
- 좌우 비교 화면으로 두 접근 방식의 차이를 시각적으로 확인

### 3.3 JSON 문서 CRUD

| 기능 | 설명 |
|------|------|
| 문서 목록 조회 | Duality View를 통한 JSON 문서 목록 |
| 문서 상세 조회 | 개별 JSON 문서 조회 (ETag 포함) |
| 문서 수정 | JSON 문서 업데이트 (ETag 기반 낙관적 동시성 제어) |

### 3.4 ETag 동시성 제어 시뮬레이션

Lost Update 문제를 방지하는 ETag 기반 동시성 제어를 5단계로 시연합니다:

1. 사용자 A가 문서를 읽음 (ETag 획득)
2. 사용자 B가 같은 문서를 읽음 (같은 ETag 획득)
3. 사용자 A가 수정 → 성공 (새 ETag 발급)
4. 사용자 B가 이전 ETag로 수정 시도 → 충돌 감지, 실패
5. 데이터 원복

### 3.5 실행 쿼리 확인

- `V$SQL`에서 최근 Duality 관련 쿼리 조회

---

## 4. Property Graph

Oracle SQL/PGQ(Property Graph Query) 표준을 활용한 그래프 데이터 분석 기능입니다.

### 4.1 그래프 관리

| 기능 | 설명 |
|------|------|
| 그래프 생성 | SH 스키마 기반 `sales_graph` Property Graph 생성 (Customers, Products, Sales) |
| 그래프 삭제 | 생성된 Property Graph 제거 |

### 4.2 SQL vs SQL/PGQ 비교

동일한 질문에 대해 전통적인 SQL JOIN과 SQL/PGQ GRAPH_TABLE을 좌우 비교합니다.

**비교 쿼리 3종:**

| # | 쿼리 | 설명 |
|---|------|------|
| 1 | 고객 524 구매 제품 목록 | 특정 고객의 구매 이력 조회 |
| 2 | 제품별 구매 고객 수 및 총 매출 Top-10 | 집계 분석 |
| 3 | 같은 제품을 산 고객 쌍 | 추천 시스템 기초 데이터 |

### 4.3 관계 탐색 (패턴 매칭)

SQL/PGQ의 `MATCH` 절을 활용한 그래프 패턴 매칭 쿼리를 실행합니다.

**패턴 매칭 쿼리 3종:**

| # | 쿼리 | 설명 |
|---|------|------|
| 1 | 고객 → 제품 구매 관계 | MATCH 패턴으로 구매 관계 탐색 |
| 2 | 고가 제품(>$1,000) 구매 고객과 도시 | 조건부 패턴 매칭 |
| 3 | 제품 13을 매개로 연결된 고객 쌍 | 공통 구매 기반 관계 탐색 |

### 4.4 그래프 시각화 (2026-09-05 신설)

패턴 질의 1번(고객 → 제품 구매 관계) 결과를 SVG 이분 그래프로 그립니다 — 간선 굵기 = 매출, 제품 색 = 카테고리.

### 4.5 실행 쿼리 확인

- `V$SQL`에서 최근 그래프 관련 쿼리 조회 — 페이지 우상단 버튼 → 슬라이드 패널

---

## 5. 개발생산성 향상

Oracle 26ai의 개발 생산성 향상 기능을 시뮬레이션으로 체험합니다.

### 5.1 Lock-Free Reservations

행 잠금(Row Lock) 없이 동시 차감을 처리하는 `RESERVABLE` 컬럼 기능 데모입니다.

| 단계 | 내용 |
|------|------|
| 1 | `balance RESERVABLE` 컬럼이 포함된 테이블 생성 (잔액 1,000) |
| 2 | 세션 A: 200 차감 (커밋하지 않음) |
| 3 | 세션 B: 100 차감 — Lock 없이 즉시 성공 |
| 4 | 세션 C: 300 차감 시도 — `CHECK(balance >= 0)` 제약 조건에 따라 결과 결정 |
| 5 | 세션 A 롤백 및 정리 |

### 5.2 Priority Transactions

트랜잭션 우선순위에 따라 DB가 자동으로 낮은 우선순위 트랜잭션을 롤백하는 기능 데모입니다.

| 단계 | 내용 |
|------|------|
| 1 | 테이블 생성 |
| 2 | LOW 우선순위 세션이 행을 잠금 |
| 3 | HIGH 우선순위 세션이 같은 행 요청 |
| 4 | DB가 LOW 세션을 자동 롤백, HIGH 세션 진행 |
| 5 | 정리 |

### 5.3 실행 쿼리 확인

- `V$SQL`에서 Lock-Free / Priority 관련 쿼리 조회

---

## 6. 기타 부가 기능 - AWR 리포트 AI 분석

Oracle AWR(Automatic Workload Repository) HTML 리포트를 업로드하면, AI가 성능 분석 보고서를 생성합니다.

### 6.1 AWR HTML 파싱

- 23개 핵심 섹션을 **섹션 타이틀 검색 방식**으로 추출
- TOC(목차) 링크를 자동으로 스킵하여 실제 데이터 테이블만 추출

**추출 대상 섹션 (23개):**

| # | 섹션 | # | 섹션 |
|---|------|---|------|
| 1 | Report Header | 13 | SGA Summary |
| 2 | ADDM | 14 | Buffer Pool Advisory |
| 3 | Load Profile | 15 | SGA Target Advisory |
| 4 | Instance Efficiency | 16 | PGA Memory Advisory |
| 5 | Top 10 Foreground Events | 17 | Tablespace IO Stats |
| 6 | SQL Elapsed Time | 18 | Snapshot Info |
| 7 | SQL CPU Time | 19 | Host CPU |
| 8 | SQL Gets | 20 | Interconnect Stats (RAC) |
| 9 | SQL Reads | 21 | Interconnect Client Stats (RAC) |
| 10 | SQL Executions | 22 | Global CR Served Stats (RAC) |
| 11 | Segments Logical Reads | 23 | Global Cache Transfer Stats (RAC) |
| 12 | Segments Physical Reads | | |

### 6.2 LLM 분석 보고서 (8개 섹션)

| # | 섹션 | 주요 분석 항목 |
|---|------|---------------|
| 1 | 시스템 개요 | DB Time, Elapsed Time, 평균 Active Sessions, CPU/Wait 비율 |
| 2 | 병목 진단 (Wait Events) | Top 대기 이벤트, 대기 시간 비율, 원인 분석 |
| 3 | Top SQL 분석 | 고부하 SQL 식별, Elapsed Time/CPU/Gets/Reads 기준 |
| 4 | I/O 분석 | 테이블스페이스별 I/O, 물리적 읽기/쓰기 분석 |
| 5 | Hot Segments | 논리적/물리적 읽기 상위 세그먼트 |
| 6 | 메모리 분석 | SGA/PGA 현황, Buffer Pool/SGA Target/PGA Advisory 분석 |
| 7 | Host CPU | CPU 사용률, User/System/Idle 비율 |
| 8 | 종합 권고사항 | 전체 분석 요약 및 우선순위별 개선 제안 |

### 6.3 카테고리별 성능 점수 (categoryScores)

7개 카테고리에 대해 LLM이 0~100점으로 평가합니다:

| 카테고리 | 평가 기준 |
|----------|----------|
| systemLoad | DB Time 대비 Elapsed Time, 평균 Active Sessions |
| waitEvents | 대기 이벤트 심각도 및 비율 |
| topSql | 고부하 SQL 존재 여부 및 영향도 |
| ioPerformance | I/O 처리량 및 지연 |
| hotSegments | 특정 세그먼트 집중도 |
| memory | SGA/PGA 적정성, Buffer Hit Ratio |
| hostCpu | CPU 사용률 및 여유 |

### 6.4 액션 아이템 (actionItems)

우선순위별로 구체적인 조치 사항을 제시합니다:

| 우선순위 | 의미 |
|----------|------|
| [긴급] | 즉시 조치 필요 |
| [높음] | 빠른 시일 내 조치 권장 |
| [중간] | 계획적 개선 대상 |

각 아이템에는 `action` (조치 내용)과 `evidence` (근거 데이터)가 포함됩니다.

### 6.5 결과 렌더링 (하이브리드 방식)

| 데이터 유형 | 렌더링 | 용도 |
|-------------|--------|------|
| `data` | 2열 Key-Value 그리드 | DB Time, SGA 크기 등 수치 지표 |
| `table` / `tables` | HTML 테이블 | Top SQL, Wait Events 등 목록 |
| `interpretation` | 텍스트 | AI의 해석 및 의견 |

### 6.6 후속 질문

- 분석 결과에 대해 추가 질문 가능
- Markdown 렌더링 지원 (코드 블록, 테이블, 리스트 등)
- 다중 분석 결과 탭 관리

---

## 7. 공통 기능

### 7.1 LLM 제공자 (5개)

AWR 분석, RAG 답변 생성 등에서 사용할 LLM 제공자를 선택할 수 있습니다.

| 제공자 | 모델 | 최대 입력 |
|--------|------|----------|
| Groq | Llama 3.3 70B | 12,000자 |
| Google | Gemini 2.5 Flash | 80,000자 |
| OpenAI | GPT-4o | 50,000자 |
| Anthropic | Claude Sonnet 4 | 80,000자 |
| xAI | Grok-3 | 50,000자 |

### 7.2 시스템 상태 표시

- DB 연결 상태 및 Oracle 버전
- 현재 사용 중인 LLM 모델

---

## 8. 기술 구성

### 8.1 Backend

| 항목 | 기술 |
|------|------|
| 웹 프레임워크 | FastAPI (비동기) |
| DB 드라이버 | python-oracledb (thin client, 비동기 커넥션 풀) |
| PDF 처리 | pdfplumber |
| LLM 호출 | OpenAI 호환 API (httpx) |

### 8.2 Frontend

| 항목 | 기술 |
|------|------|
| UI 프레임워크 | Vue 3 Composition API (CDN) |
| 차트 | Chart.js (CDN) |
| 스타일 | CSS 변수 기반 커스텀 테마 |
| 빌드 | 불필요 (CDN 로드) |

### 8.3 Oracle DB 핵심 패키지

| 패키지 / 함수 | 용도 |
|---------------|------|
| `DBMS_CLOUD_AI.GENERATE` | Select AI 자연어 → SQL |
| `VECTOR_EMBEDDING()` | DB 내 ONNX 모델 임베딩 생성 |
| `VECTOR_DISTANCE()` | 벡터 유사도 거리 계산 |
| `DBMS_VECTOR.LOAD_ONNX_MODEL` | ONNX 모델 DB 적재 |
| `DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS` | DB 기반 텍스트 청킹 |
| `CONTAINS()` / `SCORE()` | Oracle Text 전문 검색 |
| `GRAPH_TABLE` / `MATCH` | SQL/PGQ 그래프 쿼리 |
| `DBMS_XPLAN.DISPLAY` | SQL 실행계획 |
| `DBMS_DATA_MINING.DROP_MODEL` | ONNX 모델 삭제 |

---

## 9. 실행 방법

```bash
# 환경 설정
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # DB 접속정보 및 API 키 편집

# 실행
python main.py
# → http://localhost:8000
```

`.env` 파일에 Oracle Autonomous Database 접속 정보와 LLM API 키를 설정해야 합니다.
상세한 환경 변수 목록은 `.env.example`을 참고하세요.
