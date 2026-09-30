# API 명세서

> **정본은 라우트 정의와 docstring 이다** (`app/routes.py` + `app/routers/*.py`). 이 문서는
> `scripts/gen_api_doc.py` 가 생성한다 — **손으로 고치지 말고 코드를 고친 뒤 다시 생성할 것.**
> 엔드포인트를 추가·변경하면 같은 커밋에서 이 문서와 `CLAUDE.md` API 목록을 함께 갱신한다.
> 전체 **84개** 엔드포인트 · 공통 prefix `/api`

## 공통 규약

| 항목 | 내용 |
|---|---|
| Prefix | 모든 경로에 `/api` 가 붙는다 |
| 성공 응답 | 대부분 `{"success": true, ...}`. 일부는 `success` 없이 데이터만 반환 |
| 실패 응답 | `JSONResponse(status_code=4xx/5xx, content={"success": false, "error": "..."})` |
| DB 미연결 | `503` + `"데이터베이스에 연결되지 않았습니다."` |
| 미정의 `/api/*` | `404` JSON (SPA 셸을 주지 않는다 — `main.py` catch-all) |
| 타임아웃 | DB call 120초 = 프론트엔드 fetch 타임아웃 |
| SSE | `POST /api/vector/upload`, `POST /api/awr/analyze` 만 `text/event-stream` |

### ⚠ 결과 배열 키가 엔드포인트마다 다르다 (부채 D11)

`data`(execute-sql·duality·recent-queries) / `chunks`(vector/search) / `sql_data`·`pgq_data`(graph/compare) /
`models`·`profiles`·`views`. **새 화면은 `web/src/lib/normalize.ts` 한 층이 흡수한다** — 키 이름을 아는 유일한 곳.

---

## 공통

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `GET` | `/api/health` | — | DB 연결·스키마·버전·프로필 수·문서/청크/임베딩 수·ONNX 모델·벡터 인덱스 상태를 한 번에 반환한다. | `app/routes.py:23` |
| `GET` | `/api/llm/providers` | — | 사용 가능한 LLM 제공자 목록 반환 (기본 제공자 포함) | `app/routes.py:123` |

## ① NL2SQL (Select AI)

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `POST` | `/api/apply-annotations` | raw JSON | annotation 세트를 DB에 일괄 적용한다. | `app/routers/nl2sql.py:236` |
| `POST` | `/api/ask` | AskRequest | Select AI 로 자연어 질문을 처리한다 (action 7종: runsql/showsql/narrate/explainsql/showprompt/summarize/chat). | `app/routers/nl2sql.py:130` |
| `POST` | `/api/conversations` | ConversationRequest | 멀티턴 대화 발급 — DBMS_CLOUD_AI.CREATE_CONVERSATION. 돌려준 conversation_id 를 /api/ask 에 실어 보내면 앞 질문을 이어받는다. | `app/routers/nl2sql.py:166` |
| `DELETE` | `/api/conversations/{conversation_id}` | — | 대화 삭제 — DBMS_CLOUD_AI.DROP_CONVERSATION(force). 「새 대화」는 이걸 부르지 않는다(이력 뷰에 남기려고); 정리용. | `app/routers/nl2sql.py:179` |
| `POST` | `/api/execute-sql` | ExecuteSqlRequest | 사용자가 입력한 SQL을 직접 실행. `SELECT AI …` 도 받는다 (profile_name 필요). | `app/routers/nl2sql.py:307` |
| `POST` | `/api/explain-plan` | ExecuteSqlRequest | SQL에 대한 실행계획을 조회한다. | `app/routers/nl2sql.py:286` |
| `POST` | `/api/nl2sql/accuracy-scenario` | ScenarioRequest | 같은 질문을 ① annotations/comments 끔 → ② 켬 → ③ ②의 SQL 을 피드백으로 등록 후 다시 — SSE(event: start | step | done | error). | `app/routers/nl2sql.py:604` |
| `POST` | `/api/nl2sql/compare-profiles` | CompareRequest | 같은 질문을 2~3개 프로필로 순차 실행(showsql + 생성 SQL 실행) — SSE(event: start | step | done | error). 이력에 source=COMPARE. | `app/routers/nl2sql.py:645` |
| `GET` | `/api/nl2sql/feedback` | — | 등록된 피드백 목록(앱 기록 기준). | `app/routers/nl2sql.py:459` |
| `POST` | `/api/nl2sql/feedback` | FeedbackRequest | 👍/👎 저장 — DBMS_CLOUD_AI.FEEDBACK(sql_text 오버로드) + AI_FEEDBACK_LOG 를 한 트랜잭션으로. 같은 이력에 다시 저장하면 delete 후 add. | `app/routers/nl2sql.py:471` |
| `POST` | `/api/nl2sql/feedback/purge` | PurgeRequest | 프로필의 피드백 전체 삭제 — 벡터 인덱스의 질문마다 FEEDBACK(delete) + AI_FEEDBACK_LOG. 되돌릴 수 없다(화면은 확인 모달). | `app/routers/nl2sql.py:590` |
| `GET` | `/api/nl2sql/feedback/status` | — | 피드백 준비 상태 — 프로필 embedding_model 유무 · `<PROFILE>_FEEDBACK_VECINDEX` 존재 · 인덱스 안 행 수 · 앱 기록 수. 환경 탭 배지. | `app/routers/nl2sql.py:447` |
| `DELETE` | `/api/nl2sql/feedback/{feedback_id}` | — | 피드백 삭제 — Oracle FEEDBACK(delete) + 앱 행. | `app/routers/nl2sql.py:496` |
| `POST` | `/api/nl2sql/fewshot/parse` | multipart 파일 | CSV/JSON/XLSX 파싱 → 미리보기 행(question·sql·note, 비어 있으면 error). 등록은 하지 않는다. | `app/routers/nl2sql.py:523` |
| `POST` | `/api/nl2sql/fewshot/register` | FewshotRows | 일괄 등록 — SSE(event: row | done | error). 행마다 SELECT AI showsql 1회(LLM) + FEEDBACK positive + AI_FEEDBACK_LOG(FEWSHOT). | `app/routers/nl2sql.py:551` |
| `GET` | `/api/nl2sql/fewshot/template` | — | 템플릿 CSV 다운로드 — 헤더 question,sql,note (한글 헤더 질문/SQL/설명 도 받는다). | `app/routers/nl2sql.py:516` |
| `POST` | `/api/nl2sql/fewshot/validate` | FewshotRows | 각 SQL 을 EXPLAIN PLAN 으로 문법·객체 검증(실행 안 함) → valid/error. | `app/routers/nl2sql.py:538` |
| `GET` | `/api/nl2sql/history` | — | Select AI 호출 이력(AI_QUERY_LOG) 한 쪽 — 최신순, 필터: 질문 LIKE(대소문자 무시)·기간·프로필·액션·상태·피드백(any/none/positive/negative). 최근 피드백 한 건을 조인. | `app/routers/nl2sql.py:334` |
| `GET` | `/api/nl2sql/history/summary` | — | 이력 요약 — 총 질의·성공률·평균/최대 elapsed·피드백 비율 + 프로필(모델)별·액션별 평균 elapsed. | `app/routers/nl2sql.py:351` |
| `GET` | `/api/nl2sql/history/{log_id}` | — | 이력 한 건 상세 — 질문·생성 SQL·답변 앞부분·오류 전문 + 그 건의 피드백 목록. | `app/routers/nl2sql.py:363` |
| `GET` | `/api/nl2sql/presets` | — | 예시 질문 프리셋 — profile 을 주면 NULL(전체) + LIKE 패턴이 맞는 것만. 화면의 「예시 질문 고르기」 소스. | `app/routers/nl2sql.py:384` |
| `POST` | `/api/nl2sql/presets` | PresetRequest | 프리셋 추가 (제목·질문·action·profile_name 패턴). | `app/routers/nl2sql.py:396` |
| `DELETE` | `/api/nl2sql/presets/{preset_id}` | — | 프리셋 삭제. | `app/routers/nl2sql.py:430` |
| `PUT` | `/api/nl2sql/presets/{preset_id}` | PresetRequest | 프리셋 수정. | `app/routers/nl2sql.py:412` |
| `GET` | `/api/nl2sql/profile-wizard/meta` | — | 「새 프로필 만들기」 폼의 선택지 — 프로바이더·OCI GenAI 리전·엔드포인트 프리셋·크리덴셜(유형 추정)·현재 스키마 테이블. | `app/routers/nl2sql.py:686` |
| `GET` | `/api/profiles` | — | 등록된 AI 프로필 목록을 조회한다. | `app/routers/nl2sql.py:192` |
| `POST` | `/api/profiles/create` | ProfileCreateRequest | DBMS_CLOUD_AI.CREATE_PROFILE — 폼을 attributes JSON 으로 만들어 PL/SQL 미리보기(preview_only) 또는 실행. | `app/routers/nl2sql.py:698` |
| `DELETE` | `/api/profiles/{profile_name}` | — | DBMS_CLOUD_AI.DROP_PROFILE(force) — 화면은 확인 모달. | `app/routers/nl2sql.py:721` |
| `POST` | `/api/remove-annotations` | raw JSON | annotation을 일괄 제거한다. | `app/routers/nl2sql.py:251` |
| `POST` | `/api/schema-info` | SetProfileRequest | 프로필에 등록된 테이블의 컬럼 정보를 조회한다. | `app/routers/nl2sql.py:267` |
| `POST` | `/api/set-profile` | SetProfileRequest | DBMS_CLOUD_AI.SET_PROFILE 실행 | `app/routers/nl2sql.py:212` |

## ② AI Vector Search — 검색·문서

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `GET` | `/api/vector/documents` | — | 업로드된 문서 목록 조회 | `app/routers/vector.py:246` |
| `DELETE` | `/api/vector/documents/{doc_id}` | — | 특정 문서 및 관련 청크 삭제 | `app/routers/vector.py:266` |
| `POST` | `/api/vector/embedding-info` | EmbeddingInfoRequest | 질문 텍스트의 임베딩 과정 정보 반환 | `app/routers/vector.py:306` |
| `POST` | `/api/vector/explain-plan` | — | 벡터 검색 SQL의 실행 계획 조회 | `app/routers/vector.py:453` |
| `GET` | `/api/vector/index-info` | — | 벡터 인덱스 메타데이터 조회 | `app/routers/vector.py:286` |
| `GET` | `/api/vector/recent-queries` | — | V$SQL에서 최근 벡터 관련 쿼리 조회 | `app/routers/vector.py:433` |
| `POST` | `/api/vector/search` | VectorSearchRequest | 벡터 유사도 검색 / 키워드 검색 / 비교 검색 | `app/routers/vector.py:136` |
| `POST` | `/api/vector/upload` | multipart 파일 | PDF 파일 업로드 -> SSE 스트리밍으로 실시간 진행 상황 전달 | `app/routers/vector.py:70` |
| `POST` | `/api/vector/visualize` | VectorVisRequest | 청크 임베딩을 2D PCA로 축소하여 시각화 데이터 반환 | `app/routers/vector.py:478` |

## ② AI Vector Search — 테이블 관리

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `POST` | `/api/vector/create-tables` | — | Vector Store 테이블 생성/연결 | `app/routers/vector.py:348` |
| `POST` | `/api/vector/drop-tables` | — | Vector Store 테이블 삭제 | `app/routers/vector.py:328` |
| `POST` | `/api/vector/table-data` | TableQueryRequest | 테이블 데이터 조회 | `app/routers/vector.py:393` |
| `POST` | `/api/vector/table-definition` | TableQueryRequest | 테이블 컬럼 정의 조회 | `app/routers/vector.py:373` |
| `POST` | `/api/vector/table-indexes` | TableQueryRequest | 테이블 인덱스 조회 | `app/routers/vector.py:413` |

## ② 임베딩 · ONNX 모델

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `GET` | `/api/vector/embedding-config` | — | 현재 임베딩 설정 반환 | `app/routers/vector.py:506` |
| `POST` | `/api/vector/embedding-config` | EmbeddingConfigRequest | 임베딩 설정 런타임 변경 (서버 재시작 시 .env 값으로 복원) | `app/routers/vector.py:519` |
| `GET` | `/api/vector/onnx-models` | — | DB에 로드된 ONNX 임베딩 모델 목록 조회 | `app/routers/vector.py:554` |
| `POST` | `/api/vector/onnx-models/load-cloud` | raw JSON | OCI Object Storage에서 ONNX 모델을 가져와 DB에 적재 | `app/routers/vector.py:630` |
| `POST` | `/api/vector/onnx-models/test` | raw JSON | ONNX 모델 테스트 (샘플 임베딩 생성) | `app/routers/vector.py:689` |
| `POST` | `/api/vector/onnx-models/upload` | multipart 파일 | ONNX 파일 업로드 → DB 모델 적재 | `app/routers/vector.py:577` |
| `DELETE` | `/api/vector/onnx-models/{model_name}` | — | DB에서 ONNX 모델 삭제 | `app/routers/vector.py:669` |
| `GET` | `/api/vector/onnx-models/{model_name}/detail` | — | ONNX 모델 상세 정보 조회 | `app/routers/vector.py:719` |

## ③ JSON Relational Duality

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `POST` | `/api/duality/compare` | DualityCompareRequest | 같은 데이터를 관계형 SQL JOIN 과 Duality View JSON 으로 각각 조회해 비교한다. | `app/routers/duality.py:77` |
| `POST` | `/api/duality/create-views` | — | SH 스키마 기반 JSON Relational Duality View 들을 생성한다. | `app/routers/duality.py:38` |
| `POST` | `/api/duality/doc` | DualityCrudRequest | Duality View 의 단일 JSON 문서를 조회한다 (ETag 포함). | `app/routers/duality.py:103` |
| `POST` | `/api/duality/doc/update` | DualityCrudRequest | Duality View 의 JSON 문서를 수정한다 — 관계형 테이블에 그대로 반영된다. | `app/routers/duality.py:116` |
| `POST` | `/api/duality/docs` | DualityCrudRequest | Duality View 문서 목록 (ID + 요약) 조회 | `app/routers/duality.py:90` |
| `POST` | `/api/duality/drop-views` | — | Duality View 들을 삭제한다. | `app/routers/duality.py:51` |
| `POST` | `/api/duality/etag-simulation` | — | ETag 낙관적 동시성 제어를 시뮬레이션한다 (동시 수정 충돌 재현). | `app/routers/duality.py:129` |
| `GET` | `/api/duality/recent-queries` | — | V$SQL 에서 Duality View 관련 최근 실행 쿼리를 조회한다. | `app/routers/duality.py:142` |
| `GET` | `/api/duality/views` | — | 현재 존재하는 Duality View 목록을 조회한다. | `app/routers/duality.py:64` |

## ④ Property Graph

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `POST` | `/api/graph/compare` | GraphQueryRequest | 같은 질문을 기존 SQL JOIN 과 SQL/PGQ 로 각각 실행해 결과·소요시간을 비교한다. | `app/routers/graph.py:61` |
| `POST` | `/api/graph/create` | — | SH 스키마(CUSTOMERS·PRODUCTS·SALES) 기반 SQL Property Graph 를 생성한다. | `app/routers/graph.py:29` |
| `POST` | `/api/graph/drop` | — | Property Graph 를 삭제한다. | `app/routers/graph.py:42` |
| `POST` | `/api/graph/pattern` | GraphQueryRequest | SQL/PGQ MATCH 패턴 질의를 실행한다 (관계 탐색). | `app/routers/graph.py:74` |
| `GET` | `/api/graph/queries` | — | 비교 쿼리·패턴 쿼리 목록을 반환한다 (정본은 graph.py 의 COMPARE_QUERIES/PATTERN_QUERIES). | `app/routers/graph.py:55` |
| `GET` | `/api/graph/recent-queries` | — | V$SQL 에서 GRAPH_TABLE 관련 최근 실행 쿼리를 조회한다. | `app/routers/graph.py:87` |

## ⑤ 개발생산성 향상

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `POST` | `/api/productivity/lockfree` | — | 26ai Lock-Free Reservations 를 시뮬레이션한다 (동시 예약 시 잠금 경합 없이 처리). | `app/routers/productivity.py:20` |
| `POST` | `/api/productivity/priority-tx` | — | 26ai Priority Transactions 를 시뮬레이션한다 (우선순위 트랜잭션이 낮은 순위를 선점). | `app/routers/productivity.py:33` |
| `GET` | `/api/productivity/recent-queries` | — | V$SQL 에서 개발생산성 시뮬레이션 관련 최근 실행 쿼리를 조회한다. | `app/routers/productivity.py:46` |

## ⑥ 기타 부가 기능 (AWR)

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `POST` | `/api/awr/analyze` | multipart 파일 | AWR HTML 파일 업로드 → 파싱 (23개 섹션) → LLM 분석 (8개 섹션 보고서) | `app/routers/awr.py:36` |
| `POST` | `/api/awr/followup` | AWRFollowupRequest | AWR 분석 결과에 대한 후속 질문 | `app/routers/awr.py:122` |
| `GET` | `/api/awr/source/{session_id}` | — | AWR HTML 원문 보기 | `app/routers/awr.py:160` |

## 매뉴얼

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `GET` | `/api/guide/docs` | — | 앱에서 열람 가능한 문서 목록을 반환한다 (가이드 + 현황 문서). | `app/routes.py:154` |
| `GET` | `/api/guide/docs/{key}` | — | 단일 문서의 마크다운 원문을 반환한다 (화이트리스트 key 만). | `app/routes.py:164` |
| `GET` | `/api/guide/features` | — | 기능 지도 — 6탭 전 기능 카탈로그 (정본: app/feature_registry.py). | `app/routes.py:178` |
| `GET` | `/api/guide/slides` | — | 장표 카탈로그 — 덱 목록(이미지/PDF 모드 · 꼬리표→쪽) + 기능 레지스트리 `slides` 앵커를 (deck, page) 로 푼 것. 정본: docs/slides/ · app/slides.py. | `app/routes.py:189` |

## 기타

| Method | 경로 | 요청 | 설명 | 구현 |
|---|---|---|---|---|
| `POST` | `/api/env-info` | EnvInfoRequest | Select AI 환경 3종을 조회한다 — profile(프로필 속성) · acl(네트워크 ACL) · credential(크리덴셜). | `app/routers/nl2sql.py:113` |
| `GET` | `/api/vector/hybrid-index` | — | Hybrid Vector Index(26ai) 상태 — 있는가, 내부에 몇 청크가 임베딩돼 있는가, 옛 CONTEXT 인덱스가 남았는가. | `app/routers/vector.py:204` |
| `GET` | `/api/vector/hybrid-index/internals` | — | Hybrid Vector Index 안 들여다보기 — 내부 테이블 목록·행 수, 상위 토큰 15($I), 조각 표본 5($VR). 없으면 exists=false. | `app/routers/vector.py:220` |
| `POST` | `/api/vector/hybrid-index/create` | HybridIndexRequest | Hybrid Vector Index 생성(옛 Oracle Text 인덱스 대체). 청크 수 × ~200ms — 180청크 약 50초. | `app/routers/vector.py:233` |

---

## 요청 모델 (Pydantic)

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
    conversation_id: str = ''
```

### `CompareRequest`

```python
    question: str (필수)
    profiles: list[str] (필수)
```

### `ConversationRequest`

```python
    title: str = ''
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

### `EnvInfoRequest`

```python
    kind: str = 'profile'
    profile_name: str = ''
```

### `ExecuteSqlRequest`

```python
    sql: str (필수)
    profile_name: str = ''
```

### `FeedbackRequest`

```python
    log_id: int (필수)
    feedback_type: str (필수)
    feedback_content: str = ''
    corrected_sql: str = ''
    source: str = 'INLINE'
```

### `FewshotRows`

```python
    rows: list[dict] (필수)
    profile_name: str = ''
```

### `GraphQueryRequest`

```python
    query_index: int = 0
```

### `HybridIndexRequest`

```python
    force: bool = False
```

### `PresetRequest`

```python
    title: str (필수)
    question: str (필수)
    action: str = 'runsql'
    profile_name: str | None = None
```

### `ProfileCreateRequest`

```python
    profile_name: str (필수)
    form: dict (필수)
    description: str = ''
    preview_only: bool = False
```

### `PurgeRequest`

```python
    profile_name: str (필수)
```

### `ScenarioRequest`

```python
    question: str (필수)
    profile_name: str (필수)
    corrected_sql: str = ''
    keep_feedback: bool = False
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
