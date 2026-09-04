# db26ai-demo — 세션 핸드오프

> **목적:** 새 대화창에서, 또는 몇 달 뒤에 다시 열었을 때 **끊김 없이 이어가기 위한 인수인계.**
> **최종 갱신:** 2026-09-04 · **정본 소스:** `~/Dev/db26ai-demo/db26ai-demo`
> **함께 읽기:** `CLAUDE.md`(자동 로드) · `docs/개발노하우.md`(자동 로드) · `docs/ROADMAP.md`(작업 계획)
>
> **이 파일이 존재하는 이유:** 2026-04에 멈춘 이 프로젝트를 2026-09에 다시 열었을 때,
> 개발자 본인이 `docs/41`·`42` SQL 이 무엇이었는지 기억하지 못했다. 코드도 커밋 메시지도
> 있었지만 **"지금 이 앱이 어떤 상태인가"에 답하는 문서가 없었다.** 결국 앱을 실행해 DB에
> 직접 질의해서야 이관이 끝났음을 확인했다. 그 상황을 다시 만들지 않기 위한 문서다.
> **작업을 끝낼 때마다 3·4·6절을 갱신한다.**

---

## 1. 한 줄 요약

Oracle AI Database 26ai 기능 데모 앱. **FastAPI(:8247) + Oracle ADB 26ai + Vue 3(CDN, 빌드 없음)**.
6개 탭(NL2SQL / Vector Search / JSON Duality / Property Graph / 개발생산성 / AWR 분석).
macOS launchd 로 상시 구동. **서버는 자동 리로드가 없어 코드 변경 후 수동 재기동 필요.**

## 2. 운영 빠른 참조

```bash
# 재기동 (코드 변경 후 필수)
launchctl kickstart -k gui/$(id -u)/com.db26ai.server
# 헬스 (DB·프로필·문서·ONNX·벡터인덱스 상태 한 번에)
curl -s http://localhost:8247/api/health | python3 -m json.tool
# 로그 (기동 메시지·워밍 결과·경고)
tail -f db26ai.log
# 구문 검사
./venv/bin/python -c "import ast; ast.parse(open('app/routes.py').read())"
# 일회성 DB 작업 (DDL·CTE 는 /api/execute-sql 로 안 된다)
./venv/bin/python <스크립트>     # 반드시 프로젝트 루트 cwd — .env 로딩
```

- **재기동 후 ~15초**간 커넥션 풀 워밍(ONNX 예열)이 백그라운드로 돈다.
  서버는 즉시 응답하지만 첫 벡터 질의는 워밍 완료 후가 정확하다. 로그에 `✓ 커넥션 풀 워밍 완료`.
- `/api/execute-sql` 은 **SELECT 로 시작하는 문장만** 받는다(`WITH` CTE 도 거부).

## 3. 현재 환경 실측 스냅샷 (2026-09-04)

| 항목 | 값 |
|---|---|
| **DB** | `db26aidemo_medium` · schema **ADMIN** · Oracle 26ai **23.26.3.2.0** |
| **테넌시** | 신규(춘천). 2026-04-14 08:50 Data Pump 이관 **완료** — 구 aidb 는 더 이상 안 씀 |
| **Wallet** | `~/Dev/Wallet_DB26AIDEMO` |
| **SH 샘플** | SALES 918,843 · CUSTOMERS 55,500 · COSTS 82,112 · TIMES 1,826 · PROMOTIONS 503 · PRODUCTS 72 · COUNTRIES 23 · CHANNELS 5 |
| **Select AI 프로필** | 2개 (GROQ_SH / GEMINI_SH) |
| **Vector Store** | 문서 1개(`SQL작성가이드.pdf`) · 청크 79 · **임베딩 79/79 (768차원)** |
| **ONNX 모델** | `MULTILINGUAL_E5_BASE`(768, 사용 중) · `MULTILINGUAL_E5_SMALL`(384) |
| **임베딩 설정** | `database` / `MULTILINGUAL_E5_BASE` |
| **인덱스** | `DOC_CHUNKS_HNSW_IDX`(VECTOR, 768차원 고정) · `DOC_CHUNKS_TEXT_IDX`(Oracle Text, WORLD_LEXER, SYNC ON COMMIT) |
| **LLM** | google / gemini-2.5-flash (RAG 답변·AWR 분석용) |
| **Property Graph** | `SALES_GRAPH` 생성됨 (customers·products 정점, sales 간선) |
| **keepalive** | 주 1회 월 09:00 ADB 핑 (OCI Always Free 회수 방지) |
| **저장소** | `elegant-kim/db26ai-demo` — **GitHub 공개(PUBLIC)** ⚠ |

**성능 실측 (2026-09-04, 79청크 기준, RAG 제외 SQL 시간):**
vector 95ms · keyword 49ms · hybrid 0.1초대 · compare 39~69ms.
검색 응답 전체는 3~4초이며 나머지는 RAG LLM 호출 시간이다.

## 4. 직전 세션에서 한 일 (2026-09-04, 커밋 `8a5582b` → `6c864fd`)

5개월 만에 재개. 계획서(`docs/ROADMAP.md`)를 세우고 Phase 0·1 을 완료했다.

1. **`019d2a1` 보안** — `docs/` 아래 SQL 5종에 OCI API 개인키·테넌시 OCID·Groq/Google 키가
   평문이었고 `.gitignore`가 그 경로를 막지 않았다(공개 저장소!). 자리표시자로 치환해
   `sql/setup/` 으로 옮기고 원본은 `sql/setup/_private/`(gitignore)로 격리. **git 이력에
   올라간 적은 없음을 전 브랜치·태그에서 확인.**
2. **`c3526d6`** — `/api/health` 가 5개월간 ONNX 모델을 `[]`로 거짓 보고. list 를 dict 로
   취급한 타입 오류 + `except: pass`. 계획서의 "ONNX 재로드 미완" 판단도 이 거짓 보고 탓이었다(정정).
3. **`c4aa907`** — 4월에 미커밋으로 멈춰 있던 Property Graph 작업 완결. PGQ 집계가
   `ORA-49011` 로 0행이었고, SQL/PGQ 가 서로 다른 10행을 보여주고 있었다(정렬 부재).
4. **`fbd06bd`** — `/health` bare except 5곳 전부 로깅 추가, 죽은 `awr_analyzer.py` 517줄 삭제.
5. **`31cf617` (가장 큰 건)** — 4개 검색 모드 중 **2개가 스펙과 다르게 동작**하고 있었다.
   Oracle Text 인덱스 부재로 키워드가 LIKE 폴백(9.9초), 하이브리드는 CONTAINS 를 아예 미사용.
   인덱스 생성 + `hybrid_search` 재작성. **또 업로드가 임베딩 실패를 "성공"으로 보고**하던
   문제(ORA-51932, 임베딩 전량 NULL)도 여기서 잡았다.
6. **`6c864fd`** — 커넥션 풀 워밍 신설 + `vector_search` 스칼라 서브쿼리(5.4초 → 95ms).

**관통하는 패턴**: 고친 버그 4개가 전부 **"실패를 삼키고 성공이라 보고"**하는 코드였다.
`docs/개발노하우.md` 3.1절에 표로 정리했다.

## 5. 절대 지켜야 할 규칙 (발췌 — 정본은 `docs/개발노하우.md`)

- **커밋 전 시크릿 게이트 필수.** 저장소가 GitHub 공개다. 한번 push 된 시크릿은
  force-push 해도 회수 불가 — 유일한 수습은 키 로테이션.
- **`except: pass` 금지.** 삼켜야 해도 `logger.warning` 은 남긴다. 성공 카운트는 실제 성공분만.
- **`VECTOR_EMBEDDING` 은 항상 `(SELECT ... FROM dual)` 스칼라 서브쿼리로 감싼다** (100배).
- **프론트 파일 수정 시 `?v=N` 증가.** 현재 v=74.
- **검증이 끝난 변경은 묻지 말고 커밋·푸시.** 작게 자주.
- 확인을 구하는 것: 시크릿 수정, `push --force`, `DROP TABLE`/조건 없는 `DELETE`.

## 6. 열린 과제

| # | 내용 | 근거 |
|---|---|---|
| 1 | **UI 런타임 임베딩 전환이 HNSW 차원 함정을 그대로 밟는다** — 사이드바에서 모델을 바꾸고 업로드하면 임베딩이 전부 NULL 이 된다(ORA-51932). 전환 시 인덱스 재생성이 필요하다는 안내나 자동 처리 없음 | `개발노하우.md` 3.2 |
| 2 | **테스트·린트가 없다** (D4). pytest 스모크 + ruff 도입이 계획서 X-1 | `docs/ROADMAP.md` |
| 3 | **API 응답 구조 불일치** (D11) — `data`/`chunks`/`sql_data`/`models`. SPA 이식 때 정규화 | `개발노하우.md` 3.4 |
| 4 | **프론트 8,338줄 단일파일** → Vue 3 + TS + Vite SPA 이식 (계획서 Phase 4·5, 7세션) | `docs/ROADMAP.md` |
| 5 | **인앱 매뉴얼 미구현** (계획서 Phase 3) — `docs/guides/` + 화이트리스트 API + 매뉴얼 탭 | `docs/ROADMAP.md` |
| 6 | *(선택)* OCI API 키 로테이션 — 유출 근거는 없으나 개인키가 5개월간 평문으로 있었다 | `019d2a1` |

## 7. 새 세션 첫 단계 권장

1. `CLAUDE.md` + `docs/개발노하우.md`(둘 다 자동 로드) + **이 파일** 훑기
2. `curl -s localhost:8247/api/health` 로 3절 스냅샷과 대조 — 다르면 그 차이가 첫 단서
3. `docs/ROADMAP.md` 의 Phase 진행 상황 확인 후 다음 작업 착수
4. `git log --oneline -10` 으로 직전 아크 확인
