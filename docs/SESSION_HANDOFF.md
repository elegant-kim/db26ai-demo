# db26ai-demo — 세션 핸드오프

> **목적:** 새 대화창에서, 또는 몇 달 뒤에 다시 열었을 때 **끊김 없이 이어가기 위한 인수인계.**
> **최종 갱신:** 2026-09-05 (Phase 6-1·6-2·6-4 완료 — 레거시 삭제, SPA 단일 서빙, 문서 동기화. 남은 것: 6-3 UI 검수 · 6-5 · 6-6) · **정본 소스:** `~/Dev/db26ai-demo/db26ai-demo`
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
# 배포 한 방 (pytest → ruff → npm build → 재기동 → 스모크)
scripts/deploy.sh
# 재기동만
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

## 4-1. 이어서 한 일 (Phase 2 · X-1 · Phase 3 일부)

| 커밋 | 내용 |
|---|---|
| `f2ec83d` `28ff138` | 문서 체계 L1·L2·L3 구축 + 시크릿 게이트를 **실제로 막도록** 수정 |
| `292e7a5` | `docs/README.md` 인덱스 · 폴더 체계 · changelog |
| `a7f742a` | `design/` 4종 (개요·아키텍처·**API 명세 53개**·DB 설계) + 라우트 docstring 20개 |
| `4fee5ae` | **pytest·ruff 도입** + Select AI 프로필 세션 의존 버그 수정 |
| `4c33db3` | 인앱 매뉴얼 API (화이트리스트 리졸버) |
| `a40bbc4` | 기능 레지스트리 34개 + 기능 지도 API |

**pytest 가 곧바로 진짜 버그를 둘 잡았다.** 특히 로그에 남아 있던 간헐적 500 의 정체가
`ORA-20046` 이었다 — `profile_name` 을 비워 `GENERATE` 를 부르면 Oracle 이 **세션 프로필**로
폴백하는데 `SET_PROFILE` 은 세션 단위이고 커넥션 풀은 요청마다 다른 세션을 준다.
**커넥션 풀 워밍으로 커넥션이 5개가 되면서 발생 확률이 오히려 올라갔다.**
`resolve_profile()` 로 항상 이름을 명시해 해결.

### 검증 명령 (이제 존재한다)

```bash
./venv/bin/python -m pytest tests/ -q   # 45 passed (서버 없으면 통합 자동 skip)
./venv/bin/ruff check .                 # All checks passed
scripts/check-secrets.sh                # 커밋 전 필수
```

## 4-2. ✅ Phase 3 완료 — 인앱 매뉴얼

**앱에 7번째 탭 「매뉴얼」이 생겼다.** 이제 소스 폴더를 뒤지지 않고 화면에서 문서를 읽는다.

| ID | 산출물 |
|---|---|
| 3-1·3-2 | `app/guide_docs.py` 화이트리스트 리졸버 + `/api/guide/docs[/{key}]` |
| 3-3 | `app/feature_registry.py` 6탭 **34개 기능 카탈로그** + `/api/guide/features` |
| 3-4~3-7 | `docs/guides/` 4종 (사용자 296줄 · 운영 230 · 트러블슈팅 254 · 데모시연 147) |
| 3-8 | 레거시 UI 「매뉴얼」 탭 — 기능 지도 + 문서 뷰어 (`?v=75`) |

**새 가이드를 추가하려면**: `docs/guides/` 에 `NN_제목.md` 로 넣고
`routes.py: _GUIDE_WHITELIST` 에 한 줄 추가. 번호 prefix glob 이라 코드 변경은 그 한 줄뿐이다.
**새 기능을 만들면** `app/feature_registry.py` 에 한 줄 추가한다.

> `renderDoc()`(app.js)은 `renderMarkdown()`과 별개다 — 가이드에 `<스크립트>` 같은
> 자리표시자가 많아 **HTML 이스케이프가 필요**한데, AWR 렌더링에 영향을 주지 않으려고
> 분리했다. **Phase 5 SPA 이식 때 통합 대상.**

## 4-3. ✅ Phase 4 완료 (2026-09-05, Fable 5.1) — 다음은 5-0

| 산출물 | 내용 |
|---|---|
| `docs/design/05_SPA_이식_설계서.md` | 결정 10건 · 사이드바 항목의 새 위치(IA 매핑) · 디렉터리 · 레이어(api/normalize/sse/stores) · `/legacy` 공존과 롤백 · 탭별 컴포넌트 트리 · 품질 게이트 |
| `docs/design/06_디자인_시스템.md` | 토큰(Oracle 재매핑) · 타이포 측정값 · 레이아웃 골격 · 컴포넌트 15종 스펙 · 상태 표현 · 편차 분류 |
| `docs/design/captures/` | investhub 실제 화면 5장 + db26ai 현재 1장 (헤드리스 Chrome, 1440px) |

**꼭 알아둘 결정**: 좌측 사이드바를 없애고 investhub 골격(상단 메뉴 → h1 → 서브탭 pill → 카드)으로 간다(D1).
백엔드 API 는 손대지 않고 응답 키 불일치는 `lib/normalize.ts` 한 층이 흡수한다(D2).
`/` 는 SPA, `/legacy` 는 기존 화면이며 `web/dist` 를 지우면 `/` 가 레거시로 돌아간다(D3 = 롤백).

**다음 작업 = 5-0 디자인 토대 (★ Fable)**. 설계서 05 §6.0 의 표가 곧 작업 목록이다.
착수 전 사용자가 05 §0 결정 요약과 06 §10 확인 포인트를 훑고 이의가 없으면 그대로 간다.

## 4-4. ✅ Phase 5-0 완료 (2026-09-05, Fable 5.1)

**`web/` 62개 파일 신설, `/` 에서 새 화면이 서빙 중.** 이식 전 7탭은 `LegacyStub` 이고 메뉴에서 `/legacy#탭` 으로 나간다.

| 만든 것 | 위치 |
|---|---|
| 토큰(Oracle Red 재매핑)·타이포·베이스 | `web/src/styles/tokens.css` |
| 헤더(56px `#312D2A`)·상단 메뉴·상태칩·테마 토글·토스트 | `web/src/components/layout/` |
| investhub ui 13종 이식 | `web/src/components/ui/` |
| db26ai 고유 ★ SqlBlock·ResultTable·CompareView·EmptyState·SubTabs·Segmented·PageHeader | `web/src/components/demo/` |
| api(GET 재시도)·normalize(D11)·sqlHighlight·format·markdown·theme·menu | `web/src/lib/` |
| system 스토어(health 30초 폴링·토스트)·useHealth·useSubTab | `web/src/stores/` `composables/` |
| FastAPI 공존 서빙(`/`·`/legacy`·`/assets`·catch-all·`/api/*` JSON 404) | `main.py` |
| 레거시 해시 shim(`/legacy#tab`)·헤더 "새 화면" 링크·v=76 | `static/js/app.js` `templates/index.html` |
| `scripts/deploy.sh` · 서빙 테스트 4개(총 50) | |
| 검증 화면 `/styleguide` + 캡처 `captures/db26ai_after_*` | |

**5-1 을 시작할 때**: `lib/menu.ts` 의 graph `migrated: true`, `pages/Graph.vue` 를 LegacyStub 에서 실제 화면으로,
`app/routers/graph.py` 분리(설계서 05 §6.1). 조립 규칙 = "Card 안에 SqlBlock + ResultTable", 비교는 CompareView.

**미결(5-7 에서 정리)**: 헤더 라벨은 짧게(`NL2SQL`·`Vector Search`…) 두었고 기능 레지스트리 `tab_label` 은
레거시 풀네임 그대로다. 페이지 h1 은 풀네임을 쓰므로 "화면 라벨 = 레지스트리" 규칙은 h1 기준으로 지켜진다.

## 4-5. ✅ Phase 5-1 완료 (2026-09-05, Fable 5.1)

**Property Graph 가 첫 이식 탭이다.** 메뉴 `migrated: true` → `/graph` 가 SPA 로 열리고 나머지 5탭은 아직 `/legacy#탭`.

| 만든 것 | 위치 |
|---|---|
| 페이지 + 서브탭 4개(`?sub=manage\|compare\|pattern\|viz`) | `web/src/pages/Graph.vue` · `pages/graph/Graph{Manage,Compare,Pattern,Viz}.vue` |
| 스토어(질의 목록 1회 로드·결과 캐시·busy 상태) · 타입드 API | `web/src/stores/graph.ts` · `lib/graph.ts` |
| **「실행 쿼리 확인」 슬라이드 패널 — 전 탭 공통 부품** (`endpoint` 만 바꿔 재사용) | `web/src/components/demo/RecentQueriesPanel.vue` |
| **그래프 시각화 신설** — 레거시는 자리표시자("향후 구현 예정")였다. 패턴 질의 0 결과를 SVG 이분 그래프로(간선 굵기=매출, 색=카테고리). 라이브러리 없음 | `pages/graph/GraphViz.vue` |
| `?run=1` 자동 실행 규약 — 딥링크·시연·헤드리스 캡처용 | compare/pattern/viz 의 `onMounted` |
| 백엔드 라우터 분리 1호 `app/routers/graph.py` (경로·응답 불변, 테스트 50 그대로) + API 명세 생성기 `scripts/gen_api_doc.py` | |
| 기능 레지스트리 graph 5항목 `path` → 실제 딥링크(`/graph?sub=…`) | `app/feature_registry.py` |
| 캡처 4장 `captures/db26ai_graph_{compare_light,compare_dark,manage_light,viz_light}.png` | 사용자 확인 포인트 ② 제시용 |

**여기서 확정된 조립 규칙(5-2~5-6 이 상속)**: 페이지 = `PageHeader`(우상단 `RecentQueriesPanel`) › `SubTabs` › `KeepAlive` 로 서브탭 컴포넌트 전환.
서브탭 = `Card` 하나 안에 [입력 행(`SearchableSelect`+`Button`)] › [`LoadingBlock` | `EmptyState` | 결과]. 결과 = `SqlBlock` + `ResultTable`,
비교는 `CompareView`(좌·우 슬롯에 같은 조합, `equal=rowsEqual(...)`). 응답 → `Rows` 변환은 `lib/normalize.ts` 에서만.
페이지가 API 를 직접 부르지 않는다 — `lib/<tab>.ts`(타입드 호출) → `stores/<tab>.ts`(상태) → 페이지.

**5-2 를 시작할 때**: `lib/menu.ts` productivity `migrated: true`, `pages/Productivity.vue` 를 위 규칙대로, `app/routers/productivity.py` 분리
(`routes.py` 의 `# === 개발생산성` 블록을 `routers/graph.py` 와 같은 모양으로), 레지스트리 `path` 갱신, `scripts/gen_api_doc.py` 재실행.
~~모델은 Opus 5~~ → 사용자 결정(2026-09-05): **5-2·5-3 도 Fable 로 진행.** 5-1 실측 시간은 측정되지 않았다.

## 4-6. ✅ Phase 5-2 완료 (2026-09-05, Fable 5.1)

**사용자 확인 포인트 ② 확정: SQL 블록은 두 테마 모두 다크 유지** (D10 그대로). 5-1 의 조립 규칙을 그대로 따라 두 번째 탭을 옮겼다.

| 만든 것 | 위치 |
|---|---|
| 페이지 + 서브탭 2개(`?sub=lockfree\|priority`) | `web/src/pages/Productivity.vue` · `pages/productivity/{LockFree,PriorityTx}.vue` |
| 스토어 — 결과는 한 번에 오지만 **한 단계씩 드러내는 연출**(첫 0.3초, 이후 1.2초; 레거시 계승) + [바로 보기] | `web/src/stores/productivity.ts` · `lib/productivity.ts` |
| **`StepList.vue`** — 단계 카드 목록(성공/거부 토큰 색, 단계별 SqlBlock, 진행 중 표시). 5-3 ETag 시뮬·5-6 업로드 파이프라인이 재사용 | `web/src/components/demo/StepList.vue` |
| **`VersusBox.vue`** — "기존 방식 vs 26ai" 두 칸 비교 상자. graph 관리 화면도 이걸로 바꿨다 | `web/src/components/demo/VersusBox.vue` |
| Priority 화면에 **정직한 안내** 추가 — ADB 는 `PRIORITY_TXNS_MODE` 를 못 바꿔 1단계만 실제 실행, 2~6단계는 설명 (레거시는 이 사실을 숨겼다) | `PriorityTx.vue` |
| 라우터 분리 2호 `app/routers/productivity.py` (경로·응답 불변) | |
| 회귀 테스트 `TestProductivity` 2개 — 동시 차감 성공·CHECK 거부·최종 잔액 400 을 고정 (총 52) | `tests/test_api_smoke.py` |
| 레지스트리 productivity 3항목 딥링크 · 캡처 3장 `captures/db26ai_productivity_*` | |

**5-3 을 시작할 때**: duality 도 같은 순서 — `lib/menu.ts` migrated, `pages/Duality.vue` + `pages/duality/` 4서브탭(views·compare·crud·etag),
`app/routers/duality.py`(routes.py 의 `# === JSON Duality` 블록), 레지스트리 path, `gen_api_doc.py`. 관계형 vs JSON 은 `CompareView`
(우측은 `SqlBlock lang="json"`), ETag 는 `StepList`, 문서 CRUD 는 `ResultTable` 클릭 → 편집 카드. 설계서 05 §6.3.

## 4-7. ✅ Phase 5-3 완료 (2026-09-05, Fable 5.1)

**이식하면서 백엔드 버그 2건을 찾았다 — 둘 다 HTTP 200 뒤에 숨어 있었다** (`개발노하우.md` 3.1 표에 5·6번째 행으로 추가):

| 증상 | 원인 | 고침 |
|---|---|---|
| 관계형 vs JSON 비교의 관계형 쪽이 5개월간 `ORA-03049` | `FROM admin.customers c SAMPLE(5)` — SAMPLE 은 별칭 **앞**에 와야 한다. 게다가 양쪽이 `SAMPLE` 무작위라 비교 자체가 불가능했다 | 양쪽 다 PK 오름차순 + `FETCH FIRST n` → 같은 엔티티가 마주 본다. 테스트가 id 배열 일치를 고정 |
| ETag 시뮬이 4단계에서 끊기고 `error` 동반, **고객 5명의 신용한도가 +1 씩 오염** | 4단계는 WHERE 로 흉내 냈고, 5단계 원복이 옛 ETag 를 실은 문서로 UPDATE → 진짜 ETag 검사(ORA-42699)가 거기서 터짐 → `except: pass` | 4단계가 **DB 의 ORA-42699 거부**를 그대로 보여준다(진짜 낙관적 잠금). 원복은 `_metadata` 를 뺀 문서로(검사 생략). 오염 5건은 SH 표준값으로 되돌렸다(`UPDATE … -1 WHERE IN (1501,5001,7001,11001)`) |

| 만든 것 | 위치 |
|---|---|
| 페이지 + 서브탭 4개(`?sub=views\|compare\|crud\|etag`) | `web/src/pages/Duality.vue` · `pages/duality/Duality{Views,Compare,Crud,Etag}.vue` |
| 스토어(뷰 목록 1회 로드·비교/문서/ETag 결과 캐시) · 타입드 API · `normalize.fromDualityRelational` | `web/src/stores/duality.ts` · `lib/duality.ts` |
| 비교 = `CompareView`(좌 `ResultTable`, 우 `SqlBlock lang="json"` ↔ **앱 화면 카드** `Segmented` 토글). `equal` 은 PK/_id 배열 일치, 배너 문구는 `equalText` prop | `DualityCompare.vue` |
| 문서 CRUD = 목록(클릭 행) → 편집 카드(textarea + ETag 배지 + 저장). 저장 성공 시 새 ETag 를 textarea 의 `_metadata` 에 되써서 연속 저장이 된다 | `DualityCrud.vue` |
| ETag 시뮬 = `StepList`(ETag 배지 지원 — `Step.etag`, 공용 타입 `lib/types/steps.ts`) | `DualityEtag.vue` · `StepList.vue` |
| 라우터 분리 3호 `app/routers/duality.py` · 테스트 `TestDuality` 2개 강화(총 52) · 레지스트리 5항목 딥링크 · 캡처 `captures/db26ai_duality_*` | |

**5-4 를 시작할 때 (AWR, ★ Fable)**: 서브탭 없이 한 페이지. SSE(`POST /api/awr/analyze`) 수신용 `composables/useSse.ts` 를 먼저 만들고,
`PipelineProgress`(SSE 단계) · `SessionTabs` · `ScoreGauge`(7 카테고리) · `KvGrid` · 액션아이템 · 후속질문 · 원문 모달 순으로. 설계서 05 §6.4.
**완료 판정은 픽셀이 아니라 정보 누락 0** — 기존 분석 JSON 을 그대로 넣어 렌더가 같은가. `app/routers/awr.py` 분리.

## 4-8. ✅ Phase 5-4 완료 (2026-09-05, Fable 5.1)

**문서와 코드가 갈라져 있던 것 하나 정정**: CLAUDE.md·설계서는 AWR 분석을 SSE 라고 적었지만 **`POST /api/awr/analyze` 는 분석이 끝난 뒤 JSON 을 한 번 돌려준다**(30~120초).
레거시 화면의 진행 표시는 타이머 연출이었고, 새 화면도 같은 연출을 유지한다(`stores/awr.ts`). SSE 는 PDF 업로드뿐이다 → `useSse` 는 5-6 에서 만든다.

| 만든 것 | 위치 |
|---|---|
| 페이지(서브탭 없음): 업로드 카드(드롭존 + LLM 셀렉트) › 진행 카드 › `SessionTabs` › 보고서 | `web/src/pages/Awr.vue` · `pages/awr/{AwrUpload,AwrReport,AwrSection}.vue` |
| 보고서 = 분석 정보 배지 행(옛 사이드바) › 점수 카드 7(막대, 80/60/40 톤) › 8섹션 카드(접기; data→`KvGrid` · table(s)→`ResultTable` · interpretation) › 액션아이템(우선순위 배지·근거·기대효과) › 후속질문(`ChatThread`+`ChatComposer`) › 원문 iframe 모달 | `AwrReport.vue` |
| **공용 부품 4종 신설** — `PipelineProgress`(링 % + 단계, 5-6 업로드 재사용) · `KvGrid` · `SessionTabs` · `ChatThread`/`ChatComposer`(5-5·5-6 의 대화 화면 기초) + `lib/types/chat.ts` | `web/src/components/demo/` |
| `.md-body` 마크다운 스타일(06 §5.13) — 후속질문 답의 표·목록. 5-7 가이드 문서 렌더가 같은 클래스를 쓴다 | `web/src/styles/tokens.css` 끝 |
| `?load=<json url>` — 저장해 둔 분석 응답을 세션으로 연다(시연·캡처용). 픽스처는 **커밋하지 않는다**(고객 DB 이름이 든 실제 AWR) — `web/dist/awr_sample.json` 에 세션 한정으로 둔다 | `stores/awr.ts` `loadFromUrl` |
| 라우터 분리 4호 `app/routers/awr.py` (routes.py 에 남아 있던 잔존 헤더·상수도 정리) · 레지스트리 extra 4항목 → `/awr` | |
| 캡처 `captures/db26ai_awr_report_{light,dark}.png` (샘플 = `~/Dev/db26ai-demo/awr분석/awrrpt_1_199355_199359.html`, RAC+Exadata, Gemini 73초) | |

**5-5 를 시작할 때 (NL2SQL, ★ Fable — 앱의 첫 화면)**: 사용자 확인 포인트 ①(실행 모드 7종 배치: 세그먼트 vs 셀렉트, 두 안 시연)과 ④(스레드 폭 `max-w-[960px]`) 가 여기 있다.
`ChatThread`/`ChatComposer` 를 확장(결과 블록 = `SqlBlock`+`ResultTable`+차트+실행계획 버튼, 컴포저 위 슬롯에 프로필 셀렉트·모드 세그먼트·예시 질문). 서브탭 `ask|schema`(스키마 트리 + Annotation 적용/제거).
`app/routers/nl2sql.py`(ask·profiles·set-profile·annotations·schema-info·explain-plan·execute-sql). 5-5 가 끝나면 `homePath()` 가 `/nl2sql` 로 바뀐다(menu.ts 의 첫 migrated). 설계서 05 §6.5.

## 4-9. ✅ Phase 5-5 완료 (2026-09-05, Fable 5.1) — 확인 포인트 ①·④ 확정

**`/` 가 이제 `/nl2sql` 로 열린다** (`menu.ts` 의 `homePath()` — nl2sql 이 migrated 면 첫 화면). 앱의 얼굴이 새 화면이 됐다.

| 만든 것 | 위치 |
|---|---|
| 페이지 + 서브탭 2(`?sub=ask\|schema`). 스레드·컴포저는 **폭 960 중앙 정렬**(확인 포인트 ④) | `web/src/pages/Nl2sql.vue` · `pages/nl2sql/{Nl2sqlAsk,Nl2sqlAnswer,Nl2sqlSchema}.vue` |
| 스토어 — 프로필(기본 GROQ_SH_PROFILE)·실행 모드·스레드·스키마·Annotation. 레거시 sendQuestion/executeAction/processResult 를 그대로 옮기고 결과는 `Rows` 로 | `web/src/stores/nl2sql.ts` · `lib/nl2sql.ts`(ACTIONS·ACTION_BUTTONS·예시 질문) · `lib/annotations.ts`(SH 세트 — app.js 에서 이전) |
| 어시스턴트 메시지 = 카드 없는 블록: 프로필 속성 표 · 생성 SQL(`SqlBlock`) · 결과 표(`ResultTable`) · **차트(Bar/Line/Donut, 세그먼트 전환)** · 서술(md-body) · 프롬프트(text) · 실행계획 · 후속 버튼 행(캐시된 것은 primary) | `Nl2sqlAnswer.vue` |
| `ChatThread` 에 `user`/`assistant` 스코프 슬롯 + `minHeight` — 결과 블록을 꽂는 자리. 5-6 도 같은 방식 | `components/demo/ChatThread.vue` |
| 컴포저 위 슬롯: 프로필 셀렉트 · **실행 모드 세그먼트 7종** · 예시 질문 셀렉트. 아래 줄: SELECT 직접 실행 + 대화 비우기 | `Nl2sqlAsk.vue` |
| 딥링크 `?profile=…&action=runsql&q=…&run=1` (캡처·시연) | |
| **기본 프로필을 GEMINI 우선으로** — 2026-09-05 GROQ_SH_PROFILE 이 DB 자격증명 문제(`ORA-20404 Object not found - bearer://api.groq.com/...`)로 모든 질문에 실패한다. Groq 를 고치면 `stores/nl2sql.ts` 의 `PREFER` 순서만 되돌리면 된다 | `stores/nl2sql.ts` |
| 라우터 분리 5호 `app/routers/nl2sql.py`(8 라우트 + 모델 3 + VALID_ACTIONS). routes.py 에는 health·llm/providers·vector·guide 27개만 남았다 | |
| 캡처 3장 `captures/db26ai_nl2sql_{ask_light,ask_dark,schema_light}.png` | 확인 포인트 ①·④ 근거 |

**사용자 확인 포인트 ①·④ 확정 (2026-09-05, 사용자 "계속 진행" = 기본안)** — ① 세그먼트 한 줄, ④ 폭 960. B 셀렉트 분기와 캡처는 삭제(git 125bfdd 에 남음).

**5-6 을 시작할 때 (Vector, ★ Fable — 상태 의존 최상위)**: 스토어를 먼저 설계한다(세션·모드·임베딩 설정이 서로 참조 — R2). `composables/useSse.ts`(fetch+ReadableStream) 는 여기서 만든다 —
업로드만 SSE 다. 서브탭 `search|docs|store|embedding`. 검색은 `SessionTabs` › `ChatThread`(답변 + `ChunkCard` 목록 + 시각화) + 컴포저 슬롯에 검색모드 `Segmented` 4 · top_k · LLM. compare 모드는 `CompareView`.
업로드는 드롭존 › `PipelineProgress`(SSE, **warning 표시**) › 문서 목록. 임베딩·ONNX 탭에 **차원 경고 배너**(HNSW 함정). `app/routers/vector.py`(25개). 설계서 05 §6.6. 완료 판정: 4모드 회귀 · 자연어 질문 keyword>0 · 세션탭 전환 시 대화 보존.

## 4-10. ✅ Phase 5-6 완료 (2026-09-05, Fable 5.1)

**6개 데모 탭이 전부 새 화면이다.** 레거시(`/legacy`)로 남은 것은 「매뉴얼」 탭 하나. 상태가 가장 얽힌 vector 는 스토어를 먼저 설계했다(R2):
임베딩 설정 → 문서/업로드(SSE) → 검색(세션) → Store 점검 네 덩어리, 화면은 스토어만 본다.

| 만든 것 | 위치 |
|---|---|
| 페이지 + 서브탭 4(`?sub=search\|docs\|store\|embedding`). 레거시의 5메뉴(store·upload·search·query·onnx) 중 query 는 헤더 「실행 쿼리 확인」 + Store 탭의 EXPLAIN PLAN 으로 흡수 | `web/src/pages/Vector.vue` · `pages/vector/Vector{Search,Answer,Docs,Store,Embedding}.vue` |
| **`composables/useSse.ts`** — fetch + ReadableStream 파서(event/data). 이 앱의 유일한 SSE 소비자 = PDF 업로드 | |
| 스토어 — 임베딩 소스/모델/ONNX/인덱스 · 문서 · 업로드 파이프라인(5단계 + 임베딩 진행률 + `warning`) · 검색(모드 4 · top_k · LLM · 세션 탭) · Store 점검 · ONNX 적재 | `web/src/stores/vector.ts` · `lib/vector.ts` |
| 검색 답변 = md-body 답 · **`ChunkCard`**(출처·점수 배지·유사도 막대·4줄 접기) · SQL · 후속(임베딩 과정/키워드 비교/인덱스 정보/**2D 시각화 `ScatterChart`**). compare 모드는 `CompareView` 좌 키워드/우 의미 | `VectorAnswer.vue` · `components/demo/ChunkCard.vue` · `components/ui/ScatterChart.vue` |
| 세션 탭: 「현재」 + 보관 세션(임베딩 소스를 바꾸면 자동 보관, 수동 「세션으로 보관」도 있음). 보관 세션은 읽기 전용 | `SessionTabs` 에 탭별 `closable` 추가 |
| 업로드: 드롭존 › `PipelineProgress`(SSE step/progress/done/error, 단계별 ms, 임베딩 n/N) › 결과 요약 + **warning 배너**(임베딩 없이 저장된 청크 수) › 문서 목록(삭제 ConfirmModal) | `VectorDocs.vue` · `PipelineProgress` 에 `time`·`barLabel` 추가 |
| 임베딩·ONNX: 소스 세그먼트(변경 → 확인 2단계: 변경 → 초기화?) · 모델 셀렉트 · **차원 경고 배너**(인덱스 모델 ≠ 현재 모델이면 ORA-51932 예고 — 열린 과제 1의 화면 대응) · 모델 목록(선택/테스트/삭제) · 로컬/Object Storage 적재 · PL/SQL 참고 | `VectorEmbedding.vue` |
| Store: VersusBox 도입 · 테이블 생성/초기화 · 조회 3종(`ResultTable`) · EXPLAIN PLAN | `VectorStore.vue` |
| 라우터 분리 6호 `app/routers/vector.py`(22 라우트). **routes.py 에는 health · llm/providers · guide 3개 = 5개만 남았다** | |
| **백엔드 결함 수정**: PDF 텍스트 추출(pdfplumber, 동기)이 이벤트 루프를 막아 195쪽 PDF 에서 84초간 SSE 가 1단계에 멈춰 보이고 서버 전체가 응답하지 않았다 → `asyncio.to_thread`. 실측(자동차보험약관.pdf 3.6MB): 추출 84초 · 800청크 · 임베딩 약 50초 | `app/vector_search.py` |
| 딥링크 `?sub=search&mode=hybrid&q=…&run=1` · 레지스트리 vector 10항목 딥링크 · 캡처 `captures/db26ai_vector_*` | |

**5-7 을 시작할 때 (매뉴얼 + ⌘K, 계획서상 Opus — 사용자가 Fable 로 이어가는 것도 허용)**: `Manual.vue` 서브탭 3(기능 지도 `/api/guide/features` · 사용 설명서 `DocViewer`(md-body) · 현재 상태·계획),
`CommandPalette`(⌘K, 데이터는 `/api/guide/features`), 헤더 `?` = `/manual`(확인 포인트 ⑤). 레지스트리 `tab_label` 과 헤더 짧은 라벨 정리(§4-4 미결). 그 뒤 Phase 6(레거시 삭제·문서 동기화·UI 검수).

## 4-11. ✅ Phase 5-7 완료 (2026-09-05, Fable 5.1) — Phase 5 끝

**7페이지가 전부 새 화면이다. `/legacy` 는 이제 아무 메뉴에서도 열리지 않는다** (Phase 6-1 에서 파일째 삭제).

| 만든 것 | 위치 |
|---|---|
| `/manual` 서브탭 3: 기능 지도(`/api/guide/features`, 탭별 카드 + 검색 + [이동] 딥링크) · 사용 설명서 · 현재 상태·계획(`DocViewer`, `?doc=key`) | `web/src/pages/Manual.vue` · `pages/manual/{FeatureMap,ManualDocs}.vue` · `components/demo/DocViewer.vue` |
| **⌘K 빠른 이동** — investhub CommandPalette 이식. 메뉴 7 + 기능 34, 최근 5(localStorage). 헤더에 🔍 ⌘K 버튼 | `components/layout/CommandPalette.vue` · `stores/guide.ts` |
| 헤더 `?` → `/manual` (확인 포인트 ⑤ — 기본안대로 진입) | `AppShell.vue` |
| 레지스트리: 「시스템 상태」 항목을 헤더 상태칩 기준으로 정정. 6탭 34항목 전부 실제 딥링크 | `app/feature_registry.py` |
| 문서 렌더는 `.md-body`(marked + DOMPurify) 하나 — 레거시의 정규식 렌더러 2개(renderMarkdown/renderDoc)는 사라진다(D6) | |
| 캡처 `captures/db26ai_manual_{features_light,features_dark,guide_light}.png` | |

**Phase 6 착수 순서**: 6-1 레거시 3파일(`templates/index.html`·`static/js/app.js`·`static/css/style.css`) + `/legacy` 라우트 + `main.py` 의 dist 폴백 + `LegacyStub`·`legacyUrl`·`migrated` 플래그 삭제 →
6-2 (routes.py 분리는 이미 끝) → 6-3 UI 검수(★ Fable: 6탭 캡처를 06 §10 다섯 분류로 재점검, 다크 캡처 갱신) → 6-4 문서 동기화(CLAUDE.md 프론트 절·개발노하우 §4·가이드 01·README) → 배포 스크립트 점검.

## 4-12. ✅ Phase 6-1 · 6-2 · 6-4 완료 (2026-09-05, Fable 5.1) — 레거시 삭제, SPA 단일 서빙

| 한 것 | 내용 |
|---|---|
| 6-1 레거시 삭제 | `templates/index.html`(2,724줄) · `static/js/app.js`(2,890) · `static/css/style.css`(3,000) 삭제. `main.py` 에서 `/legacy`·`/static`·Jinja2·dist 폴백 제거 → 비-API 경로는 전부 `web/dist/index.html`, dist 없으면 503 JSON. `requirements.txt` 에서 jinja2 제거 |
| 프론트 정리 | `menu.ts` 의 `migrated`·`legacyTab`·`legacyUrl` 삭제, `LegacyStub.vue` 삭제, TopNav·MobileDrawer·AppShell·StatusChips 는 항상 라우터. `homePath()` = `/nl2sql` |
| 테스트 | `TestServing` 을 SPA 단일 서빙 기준 4개로 교체(`/`·딥링크·`/legacy`(SPA 셸)·미정의 API 404). 전체 통과 |
| 6-2 | 이미 5-1~5-6 에서 탭별 분리 완료 — `routes.py` 는 공통 5개 |
| 6-4 문서 동기화 | CLAUDE.md 프론트 절(공존 서술·캐시버스팅 규칙 삭제) · 개발노하우 §2 표·§4 도입부 · 가이드 01 §0 「화면 구성」을 새 화면 기준으로 다시 그림 · 02 레거시 절 삭제 · 03/04 「사이드바」 표현 정정 |

**남은 것**: 6-3 UI 검수(★ Fable — `captures/final_<tab>_{light,dark}.png` 14장을 06 §10 다섯 분류로 점검) · 6-5 이 문서 최종 스냅샷 · 6-6 7탭 회귀 스모크.

## 5. 절대 지켜야 할 규칙 (발췌 — 정본은 `docs/개발노하우.md`)

- **커밋 전 시크릿 게이트 필수.** 저장소가 GitHub 공개다. 한번 push 된 시크릿은
  force-push 해도 회수 불가 — 유일한 수습은 키 로테이션.
- **`except: pass` 금지.** 삼켜야 해도 `logger.warning` 은 남긴다. 성공 카운트는 실제 성공분만.
- **`VECTOR_EMBEDDING` 은 항상 `(SELECT ... FROM dual)` 스칼라 서브쿼리로 감싼다** (100배).
- **프론트를 고치면 `npm run build` + 재기동.** (Vite 해시 파일명이라 캐시버스팅 버전은 없다)
- **검증이 끝난 변경은 묻지 말고 커밋·푸시.** 작게 자주.
- 확인을 구하는 것: 시크릿 수정, `push --force`, `DROP TABLE`/조건 없는 `DELETE`.

## 6. 열린 과제

| # | 내용 | 근거 |
|---|---|---|
| 1 | **런타임 임베딩 전환의 HNSW 차원 함정** — 새 화면(5-6)은 인덱스 모델 ≠ 현재 모델이면 **경고 배너**를 띄우고 소스 전환 때 초기화를 묻는다. 자동 인덱스 재생성은 아직 없다(백엔드) | `개발노하우.md` 3.2 · `stores/vector.ts` `dimensionWarning` |
| ~~2~~ | ~~테스트·린트 없음~~ **해소** — pytest 45개 + ruff (`4fee5ae`) | — |
| 3 | **API 응답 구조 불일치** (D11) — `data`/`chunks`/`sql_data`/`models`. SPA 이식 때 정규화 | `개발노하우.md` 3.4 |
| 4 | **프론트 SPA 이식** — Phase 5 완료 + 6-1/6-2/6-4 완료(레거시 삭제). 6-3 UI 검수·6-5·6-6 남음 | `docs/design/05_SPA_이식_설계서.md` |
| ~~5~~ | ~~인앱 매뉴얼 미구현~~ **해소** — Phase 3 완료 (위 4-2) | — |
| 6 | *(선택)* OCI API 키 로테이션 — 유출 근거는 없으나 개인키가 5개월간 평문으로 있었다 | `019d2a1` |
| 7 | **GROQ_SH_PROFILE 이 ORA-20404 로 실패** (2026-09-05 실측: `Object not found - bearer://api.groq.com/openai/v1/chat/completions`). DB 의 `GROQ_CRED` 자격증명 또는 네트워크 ACL 문제로 보인다 — 시크릿 영역이라 **사용자 판단**. 그동안 화면 기본 프로필은 GEMINI | 4-9 |
| 8 | AWR 후속 질문이 Gemini 에서 가끔 120초 타임아웃(httpx) 또는 비정상 장문(918k자) — 상한 40k 로 방어했고 타임아웃은 그대로 오류로 보인다 | `routers/awr.py` |

## 7. 새 세션 첫 단계 권장

1. `CLAUDE.md` + `docs/개발노하우.md`(둘 다 자동 로드) + **이 파일** 훑기
2. `curl -s localhost:8247/api/health` 로 3절 스냅샷과 대조 — 다르면 그 차이가 첫 단서
3. `docs/ROADMAP.md` 의 Phase 진행 상황 확인 후 다음 작업 착수
4. `git log --oneline -10` 으로 직전 아크 확인
