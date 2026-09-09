# db26ai-demo — 세션 핸드오프

> **목적:** 새 대화창에서, 또는 몇 달 뒤에 다시 열었을 때 **끊김 없이 이어가기 위한 인수인계.**
> **최종 갱신:** 2026-09-05 (**Phase 6 완료 = 계획서 전체 완료.** 새 화면 단일 서빙, 레거시 없음) · **정본 소스:** `~/Dev/db26ai-demo/db26ai-demo`
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

## 3. 현재 환경 실측 스냅샷 (2026-09-05 갱신)

| 항목 | 값 |
|---|---|
| **DB** | `db26aidemo_medium` · schema **ADMIN** · Oracle 26ai **23.26.3.3.0** |
| **테넌시** | 신규(춘천). 2026-04-14 08:50 Data Pump 이관 **완료** — 구 aidb 는 더 이상 안 씀 |
| **Wallet** | `~/Dev/Wallet_DB26AIDEMO` |
| **SH 샘플** | SALES 918,843 · CUSTOMERS 55,500 · COSTS 82,112 · TIMES 1,826 · PROMOTIONS 503 · PRODUCTS 72 · COUNTRIES 23 · CHANNELS 5 |
| **Select AI 프로필** | 2개 (GROQ_SH / GEMINI_SH) — **GROQ 는 2026-09-05 현재 ORA-20404 로 실패**(열린 과제 7), 화면 기본은 GEMINI |
| **Vector Store** | 문서 2개(`SQL작성가이드.pdf` 79청크 · `현대Card개인회원약관.pdf` 101청크) · 청크 180 · **임베딩 180/180 (768차원)** |
| **ONNX 모델** | `MULTILINGUAL_E5_BASE`(768, 사용 중) · `MULTILINGUAL_E5_SMALL`(384) |
| **임베딩 설정** | `database` / `MULTILINGUAL_E5_BASE` |
| **인덱스** | `DOC_CHUNKS_HNSW_IDX`(VECTOR, 768차원 고정) · `DOC_CHUNKS_TEXT_IDX`(Oracle Text, WORLD_LEXER, SYNC ON COMMIT) |
| **LLM** | google / gemini-2.5-flash (RAG 답변·AWR 분석용) |
| **Property Graph** | `SALES_GRAPH` 생성됨 (customers·products 정점, sales 간선) |
| **keepalive** | 주 1회 월 09:00 ADB 핑 (OCI Always Free 회수 방지) |
| **저장소** | `elegant-kim/db26ai-demo` — **GitHub 공개(PUBLIC)** ⚠ |
| **프론트** | `web/` Vue 3 SPA 단일 서빙(2026-09-05). 레거시 templates/static 없음. `/` → `/nl2sql` |

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
| 페이지 + 서브탭 2(`?sub=ask\|schema`). 스레드·컴포저는 ~~폭 960 중앙 정렬~~ → **전체 폭**(확인 포인트 ④, 2026-09-05 사용자 지시로 변경: "첫 탭만 좁아 보인다") | `web/src/pages/Nl2sql.vue` · `pages/nl2sql/{Nl2sqlAsk,Nl2sqlAnswer,Nl2sqlSchema}.vue` |
| 스토어 — 프로필(기본 GROQ_SH_PROFILE)·실행 모드·스레드·스키마·Annotation. 레거시 sendQuestion/executeAction/processResult 를 그대로 옮기고 결과는 `Rows` 로 | `web/src/stores/nl2sql.ts` · `lib/nl2sql.ts`(ACTIONS·ACTION_BUTTONS·예시 질문) · `lib/annotations.ts`(SH 세트 — app.js 에서 이전) |
| 어시스턴트 메시지 = 카드 없는 블록: 프로필 속성 표 · 생성 SQL(`SqlBlock`) · 결과 표(`ResultTable`) · **차트(Bar/Line/Donut, 세그먼트 전환)** · 서술(md-body) · 프롬프트(text) · 실행계획 · 후속 버튼 행(캐시된 것은 primary) | `Nl2sqlAnswer.vue` |
| `ChatThread` 에 `user`/`assistant` 스코프 슬롯 + `minHeight` — 결과 블록을 꽂는 자리. 5-6 도 같은 방식 | `components/demo/ChatThread.vue` |
| 컴포저 위 슬롯: 프로필 셀렉트 · **실행 모드 세그먼트 7종** · 예시 질문 셀렉트. 아래 줄: SELECT 직접 실행 + 대화 비우기 | `Nl2sqlAsk.vue` |
| 딥링크 `?profile=…&action=runsql&q=…&run=1` (캡처·시연) | |
| **기본 프로필을 GEMINI 우선으로** — 2026-09-05 GROQ_SH_PROFILE 이 DB 자격증명 문제(`ORA-20404 Object not found - bearer://api.groq.com/...`)로 모든 질문에 실패한다. Groq 를 고치면 `stores/nl2sql.ts` 의 `PREFER` 순서만 되돌리면 된다 | `stores/nl2sql.ts` |
| 라우터 분리 5호 `app/routers/nl2sql.py`(8 라우트 + 모델 3 + VALID_ACTIONS). routes.py 에는 health·llm/providers·vector·guide 27개만 남았다 | |
| 캡처 3장 `captures/db26ai_nl2sql_{ask_light,ask_dark,schema_light}.png` | 확인 포인트 ①·④ 근거 |

**사용자 확인 포인트 ①·④ 확정 (2026-09-05)** — ① 세그먼트 한 줄("계속 진행" = 기본안). ④ 는 처음 960 중앙 정렬로 갔다가 **사용자 지시로 전체 폭으로 변경** — 서브탭마다 폭이 다르면 첫 탭만 좁아 보인다. NL2SQL 질문·Vector 검색 모두 다른 화면과 같은 1400 컨테이너를 채운다. B 셀렉트 분기와 캡처는 삭제(git 125bfdd 에 남음).

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


## 4-13. ✅ Phase 6-3 · 6-5 · 6-6 완료 (2026-09-05, Fable 5.1) — 계획서 끝

**6-3 UI 검수** — 7페이지 × 라이트/다크 14장(`captures/final_<tab>_{light,dark}.png`)을 06 §10 다섯 분류로 점검:

| 분류 | 결과 |
|---|---|
| A 의도된 편차 | 헤더 차콜 · SQL 다크 블록(두 테마) · 레드 액센트 — 전 페이지 일관. 사용자 확정 ②③ + 기본안 ①④⑤ |
| B 도메인 편차 | CompareView·StepList·VersusBox·ChunkCard·PipelineProgress·ScatterChart·GraphViz·SessionTabs·RecentQueriesPanel — investhub 에 없는 db26ai 부품, 토큰만 사용 |
| C 밀도 | 카드 패딩 24 · 서브탭 pill · 표 8px/14 — 기준선과 동일. 비교 화면의 좌우 SQL 블록 높이 차는 06 §5 의 `items-start` 규칙대로 둠 |
| D 색 | 컴포넌트에 hex 없음(차트 팔레트·GraphViz 카테고리색만 상수). 다크에서 배지·막대·코드 블록 대비 확인 |
| E 상태 | 로딩(LoadingBlock/PipelineProgress)·빈 상태(EmptyState)·오류(배너, 삼키지 않음)·경고(warm 배너) 전 탭 존재 |

교정 1건: 기능 지도의 `how` 문구에 마크다운 강조·백틱이 평문으로 찍혀 레지스트리 문자열을 평문으로 정리.

**6-6 회귀** — pytest 53개 통과. 7탭 실제 조작(브라우저 패널): NL2SQL runsql→차트→SQL 보기, Vector 하이브리드→시각화→업로드 SSE(101청크), Duality 비교→앱 화면 토글→CRUD 저장→ETag 시뮬, Graph 3쿼리 동일 배너·시각화, 생산성 2시뮬 연출, AWR 픽스처 렌더→후속질문→원문 모달, 매뉴얼 기능 지도·문서·⌘K.

**이 뒤에 열린 과제만 남는다** — §6 표. 특히 7번(GROQ 프로필 ORA-20404)은 사용자 판단.

## 4-14. Select AI 독립 실행 SQL 3종 세트 (2026-09-07, Opus 5)

**계기** — 사용자가 "앱 화면이 아니라 SQL 만으로 세팅·시연하던 옛 파일 2개를 검토해 달라"고 요청.
검토 결과 두 파일은 **다른 환경에서 쓰던 작업 로그**였고 이 ADB 에서는 첫 줄부터 깨졌다.

| 발견 | 내용 |
|---|---|
| 프로필명 불일치 | `set_profile('GROQ_PROFILE')` — 실제는 `GROQ_SH_PROFILE`. 두 파일 모두 시연 첫 줄에서 ORA-20000 |
| 실행 순서 역전 | 프로필의 `object_list` 가 `ADMIN.*` 인데 ADMIN 복제(CTAS)는 180줄 뒤에 있었다 |
| 스키마 불일치 | 대본은 `SH` 를 조회하는데 프로필은 `ADMIN` 을 본다 |
| DROP 블록 | `DROP_PROFILE` 4개가 한 BEGIN/END — 첫 실패가 나머지를 막는다 |
| 죽은 설정 | `OCI_CRED` 생성 — 참조하는 프로필 없음, 현재 DB 에도 없음. SSB 프로필 2개도 대상 테이블이 주석 처리돼 있었다 |
| 시크릿 | `create user mhmc identified by Welcome12345` 가 **두 파일에 각각** + 무관한 고객사 테이블명 |

**기존 2개는 보존**(다른 환경용, 사용자 지시). 새로 3개를 추가했다:

| 파일 | 내용 |
|---|---|
| `sql/setup/51_selectai_adb_setup.sql` | §0 사전확인 → §1 SH→ADMIN 복제 → §2 ACL → §3 크리덴셜 → §4 프로필 2개 → §5 Annotation 59건 → §6 검증 6종 |
| `sql/setup/52_selectai_adb_demo.sql` | §0 프로필·워밍업 → §2 액션 6종 → §3 한국어 질문 → **§4 Annotation 효과 비교(핵심)** → §5 멀티턴 → §6 함수 호출 → §7 실행계획·프로필 전환 |
| `sql/setup/53_selectai_adb_teardown.sql` | 프로필 → 크리덴셜 → Annotation → ACL 순 원복. **테이블 삭제(§5)는 주석 처리**(다른 탭의 기반이라) |

**실측으로 확인한 것** (추측으로 쓰지 않기 위해 전부 이 ADB 에서 돌렸다):

- `select AI` 축약구문에서 액션 6종(`runsql`·`showsql`·`narrate`·`explainsql`·`showprompt`·`summarize`) 전부 동작
- `explainsql` 은 한국어 지시를 질문에 직접 붙여야 한국어로 답한다(앱은 자동으로 붙인다)
- `summarize` 는 질의 **결과**가 아니라 **프롬프트 텍스트**를 요약한다 — 짧은 질문에는 쓸모가 없다
- **`ANNOTATIONS (ADD Display ...)` 는 덮어쓰지 않고 중복 행을 만든다** → `개발노하우.md` 3.3 에 추가
- §5 블록 왕복 검증: 59건 적용 → 0건 제거 → 59건 복원, 중복 0
- 검증 쿼리 12개 전부 오류 없이 실행

**Annotation 목록은 손으로 옮기지 않았다** — 정본 `web/src/lib/annotations.ts` 에서 생성했다(59건 일치).
내용을 바꿀 때는 TS 를 먼저 고치고 51번 §5 를 다시 생성한다.

## 4-15. NL2SQL 액션 라벨 `영문(한글)` + 「환경 확인」 3종 (2026-09-07, Opus 5)

> **② 는 4-16 에서 폐기됐다** — 사용자가 "직관적이지 않고 일관성이 떨어진다"고 기각. ① 라벨은 유지.

**요청** — ① Select AI 옵션 라벨이 전부 한글이라 실제 action 이름을 알 수 없다 → `runsql(실행)` 형태로.
② 프로필 속성만 보여주지 말고 네트워크 ACL·크리덴셜도 같은 버튼 방식으로 확인하게.

**① 라벨** — `web/src/lib/nl2sql.ts` 의 `ACTIONS` 7종을 `showsql(SQL 보기)`처럼 바꿨다.
영문이 곧 `DBMS_CLOUD_AI.GENERATE` 의 action 값이자 `SELECT AI <영문> <질문>` 의 이름이라 화면이 그걸 가르쳐야 한다.
답변 아래 후속 버튼(`ACTION_BUTTONS`)도 영문으로 통일하되 **`차트`·`실행계획`만 한글로 남겼다** —
그 둘은 Select AI 액션이 아니라 앱이 붙인 기능이라, 표기 차이가 그대로 구분 힌트가 된다.
1400px 컨테이너에서 7개 버튼 + 프로필 셀렉트 + 예시 셀렉트가 한 줄에 들어가는 것을 캡처로 확인했다.

**② 환경 확인** — 질문 입력창 아래에 세그먼트 버튼 3개(`profile` · `acl` · `credential`).
누르면 조회 SQL + 결과 표가 대화 스레드에 남는다(무엇을 어떻게 확인했는지가 화면에 남아야 시연에서 설명이 된다).

| 계층 | 추가한 것 |
|---|---|
| `app/select_ai.py` | `ENV_QUERIES`(조회 SQL 정본) · `_run_display_query()`(DBA_ 뷰 막히면 USER_ 뷰 폴백) · `get_env_info()` |
| `app/routers/nl2sql.py` | `POST /api/env-info` (`kind`: profile/acl/credential, 그 외 400) · `VALID_ENV_KINDS` |
| `web/src/lib/nl2sql.ts` | `ENV_CHECKS` · `getEnvInfo()` |
| `web/src/stores/nl2sql.ts` | `checkEnv()` · `envRows()` · 메시지 타입에 `envResult` |
| `Nl2sqlAsk.vue` · `Nl2sqlAnswer.vue` | 세그먼트 행 + 결과 렌더(크리덴셜·ACL 은 주의 문구 동반) |

**설계 판단 2개**
- ACL 조회는 `host='*'` 인 DB 내부 계정 ACE 를 뒤로 밀었다(`ORDER BY CASE WHEN host='*' THEN 2 ELSE 1 END, …`).
  안 그러면 정작 봐야 할 LLM 엔드포인트가 아래로 밀린다.
- 크리덴셜 표 아래에 **"ENABLED='TRUE' 는 키가 유효하다는 뜻이 아니다"** 를 명시했다.
  실제로 GROQ_CRED 가 TRUE 인데 호출은 ORA-20404 다(열린 과제 7). 이 화면이 그 오해를 만들면 안 된다.
  API 키 값은 어떤 뷰에도 나오지 않으므로 노출 위험은 없다.

**검증** — pytest 53개 · ruff · `npm run build`(vue-tsc) 통과. `/api/env-info` 3종 + 잘못된 kind(400) 스모크.
화면에서 버튼 3개를 실제로 눌러 결과가 스레드에 쌓이는 것 확인(브라우저 패널이 숨겨져 있으면 물리 클릭이
안 되므로 `javascript_tool` 로 눌렀다 — 노하우 3.4 의 그 함정). 캡처 `captures/nl2sql_envcheck_{light,dark}.png`.

## 4-16. NL2SQL 메인 화면 재설계 — 환경 서브탭 + 페이지 공통 프로필 (2026-09-07, Fable 5.1)

**계기** — 4-15 ② 를 사용자가 기각했다: "화면이 직관적이지 않고 일관성이 떨어진다. Select AI 기능 시연 *이전에* 세팅된 환경을
보여주는 부분이 필요하다. 버튼은 아래인데 결과는 위 창에 나온다. 요청을 무작정 시행하지 말고 편의성·일관성·직관성으로 대폭 수정하라."
먼저 이해를 말로 정리해 확인받은 뒤(이견 없음) 진행했다.

**무엇이 잘못됐었나 (4-15 ②)** — ① 시연 흐름(환경 → 시연)을 무시하고 요청받은 자리에 붙였다. ② 누른 곳(하단)과 결과(상단 스레드)가 달랐다.
③ 모드 선택기(`Segmented`)와 같은 생김새로 한 번 조회하는 버튼을 만들어 동작이 달랐다. ④ 정적인 환경 정보를 동적인 대화 스레드에 섞었다.

**새 구조** — 이 앱의 다른 탭과 같은 문법("단계 = 서브탭")으로.

```
NL2SQL(Select AI)                          [AI 프로필 ▾]   ← 페이지 헤더 공통, 세 서브탭이 같이 본다
 환경 (기본) │ 질문 │ 스키마 · Annotation
```

| 서브탭 | 내용 |
|---|---|
| **환경** `Nl2sqlEnv.vue` (신규) | 소개 카드(질문 탭에서 이동) › 상태 스트립(프로필·모델·크리덴셜 ✓/✗·ACL ✓/✗·참조 테이블·Annotation) › 3열 카드 ① 프로필 `KvGrid cols=1` + object_list 칩 · ② 크리덴셜 ← `credential_name` · ③ ACL ← `provider_endpoint` 호스트(권한 배지, 해당 호스트 ACE 표, 전체 11건 토글) — 카드마다 접힌 조회 SQL › **실제 호출 테스트**(chat 1회 → 응답·소요시간 또는 ORA 코드 + 원인 힌트) |
| **질문** `Nl2sqlAsk.vue` | 대화만. 소개 카드·프로필 셀렉트·환경 버튼 제거 → 입력창 행은 `[실행 모드 7종] [예시 질문]`. 프로필을 바꿔도 스레드에 속성 표가 끼지 않는다 |
| **스키마 · Annotation** | 그대로, 위치만 셋째 |

**설계 판단**
- **사슬로 보여준다**: 11건 ACL 을 덤프하지 않고 프로필의 endpoint 호스트에 해당하는 것만(`aclHostMatches` — 정확·`*`·`*.suffix`), 크리덴셜도 프로필이 가리키는 한 건만. "왜 동작하는가"가 한 줄로 읽힌다.
- **✓ 판정은 앱 계정(ADMIN) 기준**: 다른 principal 의 ACE 는 이 앱에 도움이 안 되므로 `system.health.schema` 와 대조한다. USER_ 뷰 폴백엔 PRINCIPAL 열이 없어 그때는 거르지 않는다.
- **`DBMS_CLOUD_AI.SET_PROFILE` 호출 제거**: 세션 단위라 풀 커넥션에선 무의미(ORA-20046 교훈)하고 `/api/ask` 가 매번 프로필명을 명시한다. 옛 화면이 이걸 부른 이유는 속성 표를 얻기 위해서였는데 그건 `/api/env-info` 가 대신한다. `/api/set-profile` 엔드포인트는 남아 있으나 SPA 는 안 부른다.
- **`?profile=` 딥링크는 스토어 `init(preferred)` 가 받는다**: 페이지·서브탭이 같은 인자로 부르므로 첫 호출이 이기고, 로드 뒤에 다른 값이 오면 그때 바꾼다. `?sub=env&run=1` 은 실제 호출 테스트를 바로 돌린다(캡처용).
- `KvGrid` 에 `cols` prop 추가(기본 2) — 1/3 폭 카드에서 2열이면 라벨이 잘린다.

**실측** — 헤드리스 캡처 `captures/nl2sql_env_{light,dark}.png` · `nl2sql_env_run_light.png`(GEMINI 호출 "네, 준비됐습니다." 4.05초) · `nl2sql_ask_light.png`.
브라우저 패널에서 조회 SQL 토글 · 전체 11건 토글 · 헤더 셀렉트로 GROQ 전환(스트립이 GROQ_CRED · api.groq.com 으로 바뀜) → 호출 시 ORA-20404 · GEMINI 복귀 · 질문 탭 showsql 왕복 확인.

## 4-17. 「SQL 직접 실행」이 `SELECT AI …` 를 받는다 (2026-09-07, Fable 5.1)

**계기** — 사용자가 직접 실행창에 `select ai 매출 상위 5개 제품을 알려주세요` 를 쳤더니 `ORA-00923: FROM keyword not found`.
"SQL 직접 실행이면 select AI 도 되어야 하는 것 아닌가?" — 맞다. `execute_raw_sql` 의 주석은 이미 "SELECT 또는 SELECT AI만 허용"이었는데
세션 프로필을 아무도 안 잡았다.

**원인** — `SELECT AI` 는 DB 가 번역하지만 **그 세션에 프로필이 있어야** 번역이 걸린다. 풀 커넥션에는 없으니 일반 SELECT 로 파싱된다.
ORA-20046(4-9)과 같은 뿌리, 다른 증상. 오전에 SQL Developer 가 낸 `Unknown Command` 는 이것과 별개 — 클라이언트가 보내기 전에 거른 것.

**수정** — `execute_raw_sql(pool, sql, profile_name)`: 문장이 `^SELECT\s+AI\b` 이면 **같은 커넥션에서 `SET_PROFILE` 후 실행**, 응답에
`select_ai: true, profile_name` 을 싣는다. 프로필 없이 오면 "페이지 우상단에서 프로필을 고르세요" 오류. 화면은 `SqlBlock` 에 `SELECT AI · 프로필` 배지.
덤으로 같은 오류가 상단 배너 + 표 오류행에 **두 번** 찍히던 것을 표 자리 한 번으로 정리했다(사용자 캡처에 그대로 보였다).

**검증** — 테스트 3개 추가(`TestSelectAiShorthand`: 프로필 동반 → RESPONSE 열에 CUSTOMERS SQL · 프로필 없음 → 명확한 오류 · 일반 SELECT 는 인자 무시), 56개 통과.
브라우저에서 `select ai showsql 고객이 모두 몇 명인가요` → 배지 + RESPONSE, `select foo from nowhere` → ORA-00942 한 번.
`개발노하우.md` 3.4 · 가이드 01 「직접 SQL 실행」 · CLAUDE.md API 목록 갱신.

## 4-18. 직접 실행한 `SELECT AI` 도 자연어 답변과 같은 블록으로 + 입력줄 두 개 통일 (2026-09-07, Fable 5.1)

**계기** — 사용자 캡처: `select ai showsql 월별 매출 추이` 를 직접 실행하니 생성 SQL 이 `RESPONSE` 한 칸에 **한 줄로 주욱** 나왔다.
"자연어 질문 결과처럼 들여쓰기된 SQL 로 나올 수 없나? 그리고 자연어 줄과 SQL 직접 실행 줄의 글자 크기가 다르다 — 일관되게, 대신 SQL 을 직접
넣는 줄이라는 특징은 살려서."

**① 결과 블록** — `SELECT AI [액션] 질문` 은 자연어 질문과 같은 것이므로 **같은 길로 보낸다.**
- 서버 `execute_raw_sql` 이 액션과 질문을 분리해 `select_ai_action` · `select_ai_prompt` 로 돌려준다(액션 생략 = runsql).
  액션 7종 목록은 `select_ai.py` 의 `SELECT_AI_ACTIONS` 하나로 모았고 라우터 `VALID_ACTIONS` 는 그것을 쓴다.
- 스토어 `runSql` 이 `select_ai` 응답이면 `msg.action = 액션`, `msg.prompt = 질문`, `msg.cached[액션] = 응답` 을 채우고
  **`processResult()` 를 그대로 태운다** → showsql 은 「생성된 SQL」 줄번호 블록, narrate/explainsql 은 마크다운 서술, runsql 은 표 + 차트.
  친 문장은 위 「직접 실행한 SQL」 블록(배지 `SELECT AI · 프로필`)에 남고, `RESPONSE` 한 칸짜리 표는 `aiDirect` 로 숨긴다.
- 그래서 **후속 버튼(runsql · narrate · 실행계획 · showprompt …)이 자연어 답변과 똑같이 달린다** — `runAction` 이 `msg.prompt`/`msg.profileName` 으로 `/api/ask` 를 부르므로 추가 코드 없이 동작.

**② 입력줄 통일** — 두 줄이 **같은 부품(`ChatComposer`)** 을 쓰게 했다. 높이 38px · 글자 14px · 버튼 크기가 같아진다(실측).
성격을 말하는 것만 다르다: 앞 아이콘(말풍선 vs `>_`), SQL 줄은 mono 글꼴, 버튼은 primary 「질문」 vs secondary 「실행」(▶).
`ChatComposer` 에 `icon` · `sendIcon` · `mono` · `sendVariant` 를 추가했고 기본값은 기존 동작 그대로(Vector 탭 영향 없음).
덤: `Button` secondary 가 `border` 로 테두리를 그려 옆의 primary 보다 **2px 컸다**(39.7 vs 37.7). inset `box-shadow` 로 바꿔 앱 전체에서
primary 옆에 놓인 secondary 가 같은 높이가 된다 — 이 화면만이 아니라 모든 탭에 적용되는 변경이다(모양은 동일).

**검증** — 테스트 +1(`select ai 질문` 기본 액션이 진짜 결과 집합을 돌려준다), 57개 통과. 브라우저에서 showsql → 줄번호 SQL 블록 + 후속 4개,
기본형 → 고객수 55,500 표 + 후속 7개(차트 포함), `RESPONSE` 표 없음. 두 입력줄 computed: 38px/14px, `-apple-system` vs `SF Mono`.

## 4-19. Vector 탭 보완 ①②③ — HNSW 실제 사용 · Hybrid Vector Index · DB 안 배치 임베딩 (2026-09-08, Fable 5.1)

**계기** — 사용자 요청 "Vector Search 가 26ai 최신 기능을 충분히 보여주는지 판단해 보완하라". 소스 검토에서 5개를 제안했고 ①②③ 진행(④ Select AI RAG · ⑤ VECTOR_DIMS 는 대화 후 결정).
셋 다 **만들기 전에 이 ADB 에서 실측**했고, 그 실측이 설계를 바꿨다.

### ① HNSW 인덱스를 5개월간 한 번도 안 탔다
- 검색 SQL 4종이 전부 `WHERE embedding IS NOT NULL … FETCH FIRST`. 실측: **술어가 붙으면 `FETCH APPROX FIRST` 여도 `TABLE ACCESS FULL`**, 술어를 빼면
  `VECTOR INDEX HNSW SCAN` — 그리고 이 ADB(23.26) 에선 정확 `FETCH FIRST` 도 인덱스를 탔다. 즉 범인은 정확/근사가 아니라 **술어 하나**.
- Vector Store 탭 실행계획 카드는 제목이 "APPROX 가 HNSW 를 타는지 본다" 인데 대상 SQL 은 정확 검색 — **제목과 반대되는 계획을 보여주고 있었다**.
- 수정: `vector_search()` 술어 제거 + `FETCH APPROX FIRST`(의도를 SQL 에 적는다). 실행계획 카드 = `CompareView` **전(술어 있음) vs 후(없음)** — `query_explain_plan` 이 둘 다 EXPLAIN 해 `before/after` + `access`·`uses_index` 를 준다. 수동 하이브리드는 가중합 ORDER BY 라 인덱스를 못 쓴다(원래 그렇다) — 화면 SQL 주석에 명시.

### ② Hybrid Vector Index (26ai) — "하이브리드 (26ai)" 라벨이 가리키던 것이 사실은 23ai 수동 가중합이었다
- 실측 순서: 임시 테이블에서 문법·SEARCH 확인(OK) → 실제 `doc_chunks` 에 생성 → **ORA-29880** (같은 컬럼에 CONTEXT 인덱스) → 텍스트 쪽 0건 → 원인은 토큰(공백 단위, `보험금`≠`보험금을`)이지 인덱스가 아님 → 앱의 `to_contains_query()` ACCUM 변환을 그대로 쓰면 됨 → 동기화는 `CTX_DDL.SYNC_INDEX`(0.3초).
- 결정: **CONTEXT 인덱스를 대체**한다(하이브리드 인덱스가 CONTAINS/SCORE 도 서빙 — 키워드 모드 코드 무변경). 이 DB 에서 실행: `DROP INDEX doc_chunks_text_idx` → `CREATE HYBRID VECTOR INDEX doc_chunks_hvi … PARAMETERS('MODEL MULTILINGUAL_E5_BASE LEXER HVI_WORLD_LEXER')` **56.8초, 180청크 → 인덱스 내부 452조각**.
- 추가: 검색 모드 `hvi`(라벨 "Hybrid Vector Index (26ai)", 옛 hybrid 는 "수동 하이브리드"로 개명) → `DBMS_HYBRID_VECTOR.SEARCH(JSON)` 융합 검색, 청크마다 score/vector_score/text_score(`ChunkCard` hybrid 모드 재사용).
  `GET /api/vector/hybrid-index` · `POST /api/vector/hybrid-index/create` · Vector Store 탭 카드(상태·생성·실행 DDL). 업로드 5단계가 `SYNC_INDEX` 를 부르고 시간을 단계로 드러낸다(실측 420ms/1청크).
  빈 테이블이면 기동 시 자동 생성, 청크가 있으면 버튼(청크 × ~0.3초). `sql/setup/60_hybrid_vector_index.sql` 신설, 50번은 "대체됨" 주석.

### ③ "DB 안에서 임베딩" 을 참으로
- 실측(180청크, 워밍 후): `UPDATE … VECTOR_EMBEDDING` **200ms/행** · `UTL_TO_EMBEDDINGS` 197 · 파이썬 청크별 루프 340. E5_BASE 는 어느 길이든 행당 200ms 가 바닥 → DB 안 UPDATE 가 가장 빠르고 가장 단순.
- 수정: 4단계 = 본문 일괄 INSERT → **20청크씩 `UPDATE doc_chunks SET embedding = VECTOR_EMBEDDING(model USING DBMS_LOB.SUBSTR(chunk_text,4000,1))`**(진행률 SSE 유지) → 성공 카운트는 `COUNT(embedding IS NOT NULL)` 실측. 외부 API 소스는 옛 루프.
- 추출은 앱(pdfplumber)에 남겼다 — **쪽 번호를 청크에 남기기 위해**(`UTL_TO_TEXT` 는 문서 전체 한 덩어리). 라벨·헤더 문구를 그에 맞게 정직하게: "추출만 앱에서, 청킹·임베딩·인덱싱은 DB 안에서".

**검증** — 테스트 4개 추가(`TestVectorIndexPaths`: 계획 before FULL/after HNSW · 의미 검색 SQL 이 APPROX·술어 없음 · hvi 융합 점수 3종 · 키워드가 CONTAINS). 실제 PDF 업로드 2회(인덱스 전/후) → 5단계 SYNC 확인 → hvi 로 새 문서 검색(text_score 54) → 테스트 문서 삭제, 데모 문서 2개 그대로.
`개발노하우.md` 3.2 에 함정 3개 추가(술어가 인덱스를 죽인다 · ORA-29880 · 배치 임베딩 실측). CLAUDE.md 검색 모드 5종·파이프라인·인덱스 구조·Critical Notes 갱신.

## 4-20. Vector 탭 재편 P1+P2 — 서브탭 = 시연 순서, 적재 단계마다 SQL·표본 (2026-09-09, Fable 5.1)

**계기** — 사용자: "헤더 문장은 올리면→청킹→임베딩→인덱싱→검색인데 첫 탭이 검색이다. 결과만이 아니라 어떤 Oracle 함수·메커니즘이 돌아
이게 되는지를 보여줘야 한다." 진단에서 하나 더 잡았다: **서버는 단계별 SQL 을 `done` 이벤트에 실어 보내는데 화면이 버리고 있었다.**
종합 플랜 P1~P7 + 장표(PPT/PDF) 연동 방식 확정(A: PDF→쪽 이미지 사전 변환 + 꼬리표 `VS-12` 앵커, B: PDF iframe 임시 경로,
`docs/slides/` gitignore) — 이견 없음. 4탭 구성·기본 모드 의미 검색 유지 확정.

**P1 골격** — `Vector.vue` 서브탭 **환경 → 적재 → 검색·RAG → 내부**, 기본 진입 환경. 옛 `?sub=docs/store/embedding` 은 `LEGACY` 맵으로 자동 이동.
`VectorDocs.vue → VectorLoad.vue`, `VectorStore.vue → VectorInternals.vue`(소개·HVI 카드를 떼고 `<VectorEmbedding/>` 을 관리 카드로 붙임),
`VectorEnv.vue` 신설(P1 판: 소개 카드 + 「지금 설정」 칩 + HVI 카드 — **P3 에서 상태 스트립 + 사슬로 재구성**).
검색 모드 순서를 학습 순서로: 키워드 → 의미 → 비교 → 수동 하이브리드 → HVI(기본 선택은 의미 유지). 헤더 문구를 ①→③ 순서로.

**P2 적재 메커니즘** — `upload_document` 가 단계 `done` 이벤트에 `sql` + `sample` 을 싣는다:
3단계 `UTL_TO_CHUNKS` 파라미터·DB/파이썬 청킹 쪽 수·앞 3청크 / 4단계 청크 하나의 `VECTOR_DIMS` + 벡터 앞 8개 / 5단계 하이브리드 인덱스 조각 전→후 + SYNC 시간.
화면(`VectorLoad`)은 파이프라인 아래 「단계별 실행 내역」 — 라벨을 누르면 실행된 SQL 과 표본이 펼쳐진다.

**함정 1개 추가** — uvicorn 자동 리로드가 `Waiting for background tasks to complete` 에서 멈춰 8247 이 죽는다(브라우저·캡처·테스트가 한꺼번에 타임아웃).
`launchctl kickstart -k` 로 복구. `개발노하우.md` 3.4.

**검증** — 테스트 +1(기능 지도의 vector 딥링크가 새 id 만 쓴다). 브라우저: 옛 `?sub=store` → 내부 자동 이동 · 환경/내부 카드 분배 ·
모드 순서 · 적재 화면에서 실제 PDF 업로드 후 단계 펼침(SQL·청크 표본·768차원 미리보기·인덱스 조각) · 테스트 문서 삭제.
남은 것: P3 환경 탭(상태 스트립·사슬·테스트 임베딩·`VECTOR_DIMS`) → P4 내부 표본 → P5 장표 기반 → P7. ④ Select AI RAG 는 P1–P4 뒤 논의.

## 4-21. Vector 「환경」 탭 P3 — 보는 사람 기준으로 다시 짓다 + `VECTOR_DIMS` 실측 (2026-09-09, Fable 5.1)

**계기** — P1 화면에 대한 사용자 피드백: 소개 카드 밑의 "정본은 CLAUDE.md …" 줄은 관객에게 불필요 · 「지금 설정」 카드의 목적이 안 보인다 ·
칩 문구들이 나열만 되어 **보는 사람이 무엇을 얻어가는지** 없다. → 이것을 P3 의 설계 원칙으로 삼아 한 번에 지었다(P1 카드를 손본 뒤 다시 뜯지 않음).

**원칙** — 값을 나열하지 않는다. **값마다 뜻**, **카드마다 "이게 있어서: …" 한 줄**(이게 있어서 무엇이 되는가), 가능한 곳엔 **그 자리에서 실제 호출**.
개발자용 문구(정본 위치·카탈로그 원문)는 「내부」로 보낸다.

**구조** (`VectorEnv.vue` 전면 교체)
1. 개요 `VersusBox` — 관객 문장으로("뜻이 비슷하면 찾는다 · 벡터가 테이블 컬럼에 있어 한 SQL"). 정본 안내 줄 삭제.
2. **「검색 준비 완료」 요약** — 3열: 검색 대상(문서·청크·전부 벡터화됨 → "의미 검색이 볼 수 있는 조각의 수") · 텍스트→벡터(모델 · **숫자 768개 (저장된 벡터에서 실측)**) · 빨리 찾는 구조(HNSW ✓ · HVI ✓ → "수백만 개에서도 ms").
3. **사슬 3카드** — ① 벡터를 담는 테이블(컬럼 4개 + 뜻, "이게 있어서: 조인·트랜잭션이 그대로") · ② 텍스트를 벡터로 바꾸는 모델(DB 안, "이게 있어서: 원문이 밖으로 안 나간다") + **「이 문장을 벡터로」** 입력·실행(`onnx-models/test` 재사용 → 숫자 768개·ms·앞부분·SQL) · ③ 인덱스 2종(HNSW = 의미 검색이 타는 길 · Hybrid Vector Index **26ai** = 키워드·HVI 모드가 타는 길, 각각 「만든 문장」 DDL 펼침, 생성/재생성 버튼, "이게 있어서: 문서가 늘어도 검색 시간이 안 는다").
옛 「지금 설정」·「Hybrid Vector Index」 카드는 각각 요약 행과 ③ 으로 흡수.

**⑤ 해소** — `get_index_info` 의 `vector_dimensions: 768` 이 **하드코딩**이었다. 저장된 벡터에서 `VECTOR_DIMS` 로 재고 `dimensions_measured` 를 같이 준다(없으면 설정값 폴백). `hnsw_ddl` 도 응답에(화면의 「만든 문장」). 그 자리의 `except: pass` 를 `logger.warning` 으로.
테스트 +1(`dimensions_measured is True`, `hnsw_ddl` 포함).

**함정** — `lib/vector.ts` 인터페이스를 문자열 슬라이스로 바꾸다 안쪽 `}` 에서 잘라 빌드가 깨졌다(`index?: {…} | null` 의 중괄호). 다음 `export ` 선언 직전까지를 범위로 잡아 복구. 여러 줄 타입은 정규식으로 자르지 말고 파일을 읽고 고칠 것.

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
| ~~4~~ | ~~프론트 SPA 이식~~ **해소** — Phase 4·5·6 완료(2026-09-05). 레거시 삭제, 7페이지 새 화면 | `docs/design/05_SPA_이식_설계서.md` |
| ~~5~~ | ~~인앱 매뉴얼 미구현~~ **해소** — Phase 3 완료 (위 4-2) | — |
| 6 | *(선택)* OCI API 키 로테이션 — 유출 근거는 없으나 개인키가 5개월간 평문으로 있었다 | `019d2a1` |
| 7 | **GROQ_SH_PROFILE 이 ORA-20404 로 실패** (`Object not found - bearer://api.groq.com/openai/v1/chat/completions`). **2026-09-07 범위 축소: 네트워크 ACL 은 정상**(`dba_host_aces` 에 CONNECT·RESOLVE·HTTP 가 GEMINI 와 동일하게 부여돼 있음) → 남은 원인은 `GROQ_CRED` 의 API 키다. 수습은 키 재발급 후 `DROP_CREDENTIAL` → `CREATE_CREDENTIAL`(51번 §3). 시크릿 영역이라 **사용자 판단**. 그동안 화면 기본 프로필은 GEMINI | 4-9 · 4-14 |
| 8 | AWR 후속 질문이 Gemini 에서 가끔 120초 타임아웃(httpx) 또는 비정상 장문(918k자) — 상한 40k 로 방어했고 타임아웃은 그대로 오류로 보인다 | `routers/awr.py` |

## 7. 새 세션 첫 단계 권장

1. `CLAUDE.md` + `docs/개발노하우.md`(둘 다 자동 로드) + **이 파일** 훑기
2. `curl -s localhost:8247/api/health` 로 3절 스냅샷과 대조 — 다르면 그 차이가 첫 단서
3. `docs/ROADMAP.md` 의 Phase 진행 상황 확인 후 다음 작업 착수
4. `git log --oneline -10` 으로 직전 아크 확인
