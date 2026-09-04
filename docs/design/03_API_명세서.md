# API 명세서

> **정본은 `app/routes.py` 의 라우트 정의와 docstring 이다.** 이 문서는 그것을 추출해 옮긴
> 것이며, 엔드포인트를 추가·변경하면 **같은 커밋에서 이 문서와 `CLAUDE.md` API 목록을 함께
> 고친다.** 설명은 라우트 함수의 docstring 첫 줄에서 온다 — 코드에 쓰면 문서에 반영된다.
> 최종 갱신: 2026-09-04 · 전체 **53개** 엔드포인트 · 공통 prefix `/api`

## 공통 규약

| 항목 | 내용 |
|---|---|
| Prefix | 모든 경로에 `/api` 가 붙는다 (`router = APIRouter(prefix="/api")`) |
| 성공 응답 | 대부분 `{"success": true, ...}`. 일부는 `success` 없이 데이터만 반환 |
| 실패 응답 | `JSONResponse(status_code=4xx/5xx, content={"success": false, "error": "..."})` |
| DB 미연결 | `503` + `"데이터베이스에 연결되지 않았습니다."` |
| 타임아웃 | DB call 120초 = 프론트엔드 fetch 타임아웃 |
| SSE | `POST /api/vector/upload`, `POST /api/awr/analyze` 만 `text/event-stream` |
| 업로드 한도 | `MAX_UPLOAD_SIZE = 10MB` (AWR 은 별도 20MB) |

### ⚠ 결과 배열 키가 엔드포인트마다 다르다 (알려진 부채 D11)

| 엔드포인트 | 결과 배열 키 |
|---|---|
| `/execute-sql`, `/duality/*`, `/graph/recent-queries` | `data` |
| `/vector/search` | `chunks` (compare 모드는 `keyword_results.chunks` / `vector_results.chunks`) |
| `/graph/compare` | `sql_data` · `pgq_data` (평면 구조) |
| `/vector/onnx-models` → `models` · `/profiles` → `profiles` · `/duality/views` → `views` | |

**응답을 파싱하기 전에 키를 먼저 확인할 것.** 2026-09-04 세션에서 Claude 가 3번 틀렸다.
SPA 이식(Phase 5) 때 정규화 대상.

---

## 공통

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `GET` | `/api/health` | — | DB 연결·스키마·버전·프로필 수·문서/청크/임베딩 수·ONNX 모델·벡터 인덱스 상태를 한 번에 반환한다. | `routes.py:282` |
| `GET` | `/api/llm/providers` | — | 사용 가능한 LLM 제공자 목록 반환 (기본 제공자 포함) | `routes.py:1030` |

## ① NL2SQL (Select AI)

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `POST` | `/api/apply-annotations` | raw JSON | annotation 세트를 DB에 일괄 적용한다. | `routes.py:186` |
| `POST` | `/api/ask` | AskRequest | Select AI 로 자연어 질문을 처리한다 (action 7종: runsql/showsql/narrate/explainsql/showprompt/summarize/chat). | `routes.py:91` |
| `POST` | `/api/execute-sql` | ExecuteSqlRequest | 사용자가 입력한 SQL을 직접 실행 | `routes.py:257` |
| `POST` | `/api/explain-plan` | ExecuteSqlRequest | SQL에 대한 실행계획을 조회한다. | `routes.py:236` |
| `GET` | `/api/profiles` | — | 등록된 AI 프로필 목록을 조회한다. | `routes.py:142` |
| `POST` | `/api/remove-annotations` | raw JSON | annotation을 일괄 제거한다. | `routes.py:201` |
| `POST` | `/api/schema-info` | SetProfileRequest | 프로필에 등록된 테이블의 컬럼 정보를 조회한다. | `routes.py:217` |
| `POST` | `/api/set-profile` | SetProfileRequest | DBMS_CLOUD_AI.SET_PROFILE 실행 | `routes.py:162` |

## ② AI Vector Search — 검색·문서

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `GET` | `/api/vector/documents` | — | 업로드된 문서 목록 조회 | `routes.py:508` |
| `DELETE` | `/api/vector/documents/{doc_id}` | — | 특정 문서 및 관련 청크 삭제 | `routes.py:528` |
| `POST` | `/api/vector/embedding-info` | EmbeddingInfoRequest | 질문 텍스트의 임베딩 과정 정보 반환 | `routes.py:568` |
| `POST` | `/api/vector/explain-plan` | — | 벡터 검색 SQL의 실행 계획 조회 | `routes.py:715` |
| `GET` | `/api/vector/index-info` | — | 벡터 인덱스 메타데이터 조회 | `routes.py:548` |
| `GET` | `/api/vector/recent-queries` | — | V$SQL에서 최근 벡터 관련 쿼리 조회 | `routes.py:695` |
| `POST` | `/api/vector/search` | VectorSearchRequest | 벡터 유사도 검색 / 키워드 검색 / 비교 검색 | `routes.py:446` |
| `POST` | `/api/vector/upload` | multipart 파일 | PDF 파일 업로드 -> SSE 스트리밍으로 실시간 진행 상황 전달 | `routes.py:380` |
| `POST` | `/api/vector/visualize` | VectorVisRequest | 청크 임베딩을 2D PCA로 축소하여 시각화 데이터 반환 | `routes.py:740` |

## ② AI Vector Search — 테이블 관리

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `POST` | `/api/vector/create-tables` | — | Vector Store 테이블 생성/연결 | `routes.py:610` |
| `POST` | `/api/vector/drop-tables` | — | Vector Store 테이블 삭제 | `routes.py:590` |
| `POST` | `/api/vector/table-data` | TableQueryRequest | 테이블 데이터 조회 | `routes.py:655` |
| `POST` | `/api/vector/table-definition` | TableQueryRequest | 테이블 컬럼 정의 조회 | `routes.py:635` |
| `POST` | `/api/vector/table-indexes` | TableQueryRequest | 테이블 인덱스 조회 | `routes.py:675` |

## ② 임베딩 · ONNX 모델

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `GET` | `/api/vector/embedding-config` | — | 현재 임베딩 설정 반환 | `routes.py:1045` |
| `POST` | `/api/vector/embedding-config` | EmbeddingConfigRequest | 임베딩 설정 런타임 변경 (서버 재시작 시 .env 값으로 복원) | `routes.py:1058` |
| `GET` | `/api/vector/onnx-models` | — | DB에 로드된 ONNX 임베딩 모델 목록 조회 | `routes.py:1093` |
| `POST` | `/api/vector/onnx-models/load-cloud` | raw JSON | OCI Object Storage에서 ONNX 모델을 가져와 DB에 적재 | `routes.py:1169` |
| `POST` | `/api/vector/onnx-models/test` | raw JSON | ONNX 모델 테스트 (샘플 임베딩 생성) | `routes.py:1228` |
| `POST` | `/api/vector/onnx-models/upload` | multipart 파일 | ONNX 파일 업로드 → DB 모델 적재 | `routes.py:1116` |
| `DELETE` | `/api/vector/onnx-models/{model_name}` | — | DB에서 ONNX 모델 삭제 | `routes.py:1208` |
| `GET` | `/api/vector/onnx-models/{model_name}/detail` | — | ONNX 모델 상세 정보 조회 | `routes.py:1258` |

## ③ JSON Relational Duality

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `POST` | `/api/duality/compare` | DualityCompareRequest | 같은 데이터를 관계형 SQL JOIN 과 Duality View JSON 으로 각각 조회해 비교한다. | `routes.py:819` |
| `POST` | `/api/duality/create-views` | — | SH 스키마 기반 JSON Relational Duality View 들을 생성한다. | `routes.py:780` |
| `POST` | `/api/duality/doc` | DualityCrudRequest | Duality View 의 단일 JSON 문서를 조회한다 (ETag 포함). | `routes.py:845` |
| `POST` | `/api/duality/doc/update` | DualityCrudRequest | Duality View 의 JSON 문서를 수정한다 — 관계형 테이블에 그대로 반영된다. | `routes.py:858` |
| `POST` | `/api/duality/docs` | DualityCrudRequest | Duality View 문서 목록 (ID + 요약) 조회 | `routes.py:832` |
| `POST` | `/api/duality/drop-views` | — | Duality View 들을 삭제한다. | `routes.py:793` |
| `POST` | `/api/duality/etag-simulation` | — | ETag 낙관적 동시성 제어를 시뮬레이션한다 (동시 수정 충돌 재현). | `routes.py:871` |
| `GET` | `/api/duality/recent-queries` | — | V$SQL 에서 Duality View 관련 최근 실행 쿼리를 조회한다. | `routes.py:884` |
| `GET` | `/api/duality/views` | — | 현재 존재하는 Duality View 목록을 조회한다. | `routes.py:806` |

## ④ Property Graph

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `POST` | `/api/graph/compare` | GraphQueryRequest | 같은 질문을 기존 SQL JOIN 과 SQL/PGQ 로 각각 실행해 결과·소요시간을 비교한다. | `routes.py:945` |
| `POST` | `/api/graph/create` | — | SH 스키마(CUSTOMERS·PRODUCTS·SALES) 기반 SQL Property Graph 를 생성한다. | `routes.py:913` |
| `POST` | `/api/graph/drop` | — | Property Graph 를 삭제한다. | `routes.py:926` |
| `POST` | `/api/graph/pattern` | GraphQueryRequest | SQL/PGQ MATCH 패턴 질의를 실행한다 (관계 탐색). | `routes.py:958` |
| `GET` | `/api/graph/queries` | — | 비교 쿼리·패턴 쿼리 목록을 반환한다 (정본은 graph.py 의 COMPARE_QUERIES/PATTERN_QUERIES). | `routes.py:939` |
| `GET` | `/api/graph/recent-queries` | — | V$SQL 에서 GRAPH_TABLE 관련 최근 실행 쿼리를 조회한다. | `routes.py:971` |

## ⑤ 개발생산성 향상

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `POST` | `/api/productivity/lockfree` | — | 26ai Lock-Free Reservations 를 시뮬레이션한다 (동시 예약 시 잠금 경합 없이 처리). | `routes.py:986` |
| `POST` | `/api/productivity/priority-tx` | — | 26ai Priority Transactions 를 시뮬레이션한다 (우선순위 트랜잭션이 낮은 순위를 선점). | `routes.py:999` |
| `GET` | `/api/productivity/recent-queries` | — | V$SQL 에서 개발생산성 시뮬레이션 관련 최근 실행 쿼리를 조회한다. | `routes.py:1012` |

## ⑥ 기타 부가 기능 (AWR)

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `POST` | `/api/awr/analyze` | multipart 파일 | AWR HTML 파일 업로드 → 파싱 (23개 섹션) → LLM 분석 (8개 섹션 보고서) | `routes.py:1290` |
| `POST` | `/api/awr/followup` | AWRFollowupRequest | AWR 분석 결과에 대한 후속 질문 | `routes.py:1376` |
| `GET` | `/api/awr/source/{session_id}` | — | AWR HTML 원문 보기 | `routes.py:1411` |

---

## 요청 모델 (Pydantic)

`app/routes.py` 상단에 정의된다. 기본값이 있는 필드는 생략 가능하다.

### `AWRFollowupRequest`

```python
    question: str (필수)
    session_id: str = 'default'
    provider: str = ''
```

### `AskRequest`

```python
    prompt: str (필수)
    action: str = 'runsql'
    profile_name: str = ''
```

### `DualityCompareRequest`

```python
    view_name: str = 'CUSTOMERS_DV'
    limit: int = 5
```

### `DualityCrudRequest`

```python
    view_name: str (필수)
    doc_id: str = ''
    doc_json: dict = {}
```

### `EmbeddingConfigRequest`

```python
    source: str = ''
    model: str = ''
    reset_model: bool = False
```

### `EmbeddingInfoRequest`

```python
    text: str (필수)
```

### `ExecuteSqlRequest`

```python
    sql: str (필수)
```

### `GraphQueryRequest`

```python
    query_index: int = 0
```

### `SetProfileRequest`

```python
    profile_name: str (필수)
```

### `TableQueryRequest`

```python
    table_name: str = 'DOC_CHUNKS'
    limit: int = 50
```

### `VectorSearchRequest`

```python
    query: str (필수)
    mode: str = 'vector'
    top_k: int = 5
    profile_name: str = ''
    provider: str = ''
```

### `VectorVisRequest`

```python
    query: str (필수)
    matched_chunk_ids: list = []
```

