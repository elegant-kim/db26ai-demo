# SPA 이식 설계서

> **작성:** 2026-09-05 (Phase 4-1, Fable 5.1) · **상태:** 사용자 검토 대기
> **입력:** db26ai 프론트 8,338줄 전수 해부 · investhub `web/` 소스 · investhub 실제 화면 캡처 6장(`captures/`)
> **짝 문서:** `06_디자인_시스템.md`(시각 규칙) · `../ROADMAP.md`(작업 순서·모델)
>
> 이 문서는 **Phase 5의 7세션이 무엇을 어떤 순서로 만들지**를 확정한다.
> 여기서 정한 것은 이후 세션이 다시 묻지 않고 그대로 따른다. 바꿔야 하면 이 문서를 먼저 고친다.

---

## 0. 결정 요약

| # | 결정 | 한 줄 근거 |
|---|---|---|
| D1 | **좌측 사이드바를 없애고 investhub 구조(상단 메뉴 → 페이지 h1 → 서브탭 pill → 카드)로 간다** | "거의 유사하게"의 핵심이 바로 이 골격이다. 사이드바 항목은 3종류로 갈리며 각각 갈 곳이 있다(§3.2) |
| D2 | **백엔드 API 는 바꾸지 않는다.** 응답 키 불일치(D11)는 TS 어댑터 한 층에서 흡수한다 | 레거시 UI 와 공존하는 동안 API 를 건드리면 둘 다 깨진다 |
| D3 | **`/` = 새 SPA, `/legacy` = 기존 화면**. dist 가 없으면 `/` 도 레거시로 폴백 | 롤백이 "dist 삭제" 한 동작이 된다 |
| D4 | 상태는 **탭별 Pinia 스토어 + 페이지 KeepAlive** | 현재 `v-show` 가 주던 "탭을 오가도 대화가 남는" 경험을 그대로 보존 |
| D5 | 기능 레지스트리 정본은 **Python(`app/feature_registry.py`) 하나로 유지**하고 SPA 는 API 로 읽는다 | 계획서의 "TS 로 승격"은 정본을 둘로 만든다 — 철회 |
| D6 | 마크다운 렌더는 **`marked` + `dompurify`** 로 통일하고 `renderMarkdown`/`renderDoc` 둘 다 폐기 | 정규식 렌더러 2개는 3-8 때 이미 부채로 기록했다 |
| D7 | 이식 순서 **graph → productivity → duality → AWR → nl2sql → vector → manual** (계획서 유지) | 작은 것으로 파이프라인을 검증하고, 가장 얽힌 vector 를 마지막에 |
| D8 | 탭을 옮길 때 **그 탭의 백엔드 라우터를 `app/routers/` 로 함께 분리**한다 | 별도 리팩터링 세션 없이 `routes.py` 1,500줄이 자연히 해체된다 |
| D9 | investhub 의 **인증·RBAC·위젯(계산기·환율·메모·달력 알림)·IdleGuard 는 가져오지 않는다** | 개인 데모앱에 인증이 없다. 껍데기만 가져오면 죽은 코드가 된다 |
| D10 | SQL 블록은 **다크 "터미널" 스타일을 라이트·다크 모두에서 유지**한다 | 이 앱의 주인공은 SQL 이다. 06 문서 §5.6, **사용자 확인 포인트** |

---

## 1. 목표와 비목표

**목표**
1. 프론트를 `templates/index.html`·`static/js/app.js`·`static/css/style.css`(8,338줄, 빌드 없음)에서
   **Vue 3 + TypeScript + Vite + Tailwind 4 SPA(`web/`)** 로 옮긴다.
2. 시각·상호작용이 **investhub 와 거의 같아야 한다** — 토큰·타이포·간격·컴포넌트를 그대로 잇고
   팔레트만 Oracle 로 재매핑한다(06 문서).
3. 이식 중에도 **앱은 매일 쓸 수 있어야 한다** — 옮긴 탭은 새 화면, 안 옮긴 탭은 레거시.
4. 끝나면 `routes.py` 가 탭별 라우터로 나뉘어 있고, 테스트 46개가 그대로 통과한다.

**비목표** (하지 않는다)
- 기능 추가·제거. 6탭 + 매뉴얼의 기능 집합은 그대로다. (예외: D11 정규화, 아래 §4.2)
- 인증·다중 사용자. investhub 의 로그인/권한은 이식하지 않는다.
- 백엔드 성능·구조 개선(라우터 분리 제외). Phase 1 에서 끝났다.
- 모바일 최적화. investhub 의 반응형 골격(md 브레이크·드로어)은 따라오지만 모바일 전용 설계는 안 한다.

---

## 2. 현재 프론트 해부

### 2.1 규모

| 파일 | 줄수 | 구성 |
|---|---:|---|
| `templates/index.html` | 2,723 | Jinja2 + Vue `[[ ]]`. 탭 7개가 `v-show` 로 **전부 한 DOM 에** 존재 |
| `static/js/app.js` | 2,879 | `setup()` 하나에 **ref/computed 125개 · 함수 약 90개**. 탭 구분 없음 |
| `static/css/style.css` | 3,000 | 클래스 350개. 섹션 주석으로만 구분 |

탭별 마크업 크기 — 이식 공수의 1차 근거:

| 탭 | index.html 줄 | 비고 |
|---|---:|---|
| vector | **1,062** | 세션 탭·업로드 파이프라인·4모드 검색·청크 카드·ONNX 관리·임베딩 설정·시각화 |
| duality | 410 | 3구획 비교·문서 CRUD·ETag 시뮬 |
| nl2sql | 352 | 채팅 스레드·스키마 트리·Annotation·실행계획·차트 |
| extra(AWR) | 351 | 업로드·SSE 진행·다중 결과탭·점수 게이지·액션아이템·후속질문 |
| graph | 213 | 생성/삭제·좌우 비교·패턴·시각화 |
| productivity | 161 | 시뮬 2종 (단계 카드) |
| manual | 109 | 3-8 에서 신설. 이미 "새 구조"에 가깝다 |

### 2.2 화면 패턴 인벤토리 (350 클래스를 12개 패턴으로 압축)

투입 판단의 핵심: **db26ai 는 investhub 에 없는 패턴이 절반이다.** 카드·표·버튼은 가져오면 되지만
아래 ★ 는 새로 만들어야 한다.

| 패턴 | 현 클래스(대표) | 쓰는 탭 | investhub 대응 |
|---|---|---|---|
| 채팅 스레드(사용자 말풍선 → 결과 블록) ★ | `chat-area` `message-bubble` `bubble-user` | nl2sql · vector | 없음 (AssistantDrawer 가 유사하나 구조 다름) |
| **SQL 블록**(헤더+하이라이트 코드+복사) ★ | `sql-section` `sql-header` `sql-code`(33곳) | 전 탭 | 없음 |
| 결과 표(행수·소요·스크롤) | `result-table` `table-wrapper` `row-count`(21곳) | 전 탭 | 표 스타일만 |
| **좌우 비교** ★ | `duality-compare-grid`, graph compare 2열, vector compare | duality · graph · vector | 없음 — 이 앱의 서사 |
| 단계 카드(step-card + 헤더 + SQL + 결과) | `step-card`(37곳) `step-title` | productivity · duality · graph | Card 로 대체 가능 |
| **파이프라인 진행** ★ | `pipeline-*`(링·점·바) | vector 업로드(SSE) · AWR(타이머 연출) | 없음 |
| 세션/결과 탭 바 ★ | `awr-result-tabs` | vector · AWR | 없음 |
| 청크 카드(유사도 바·점수 3종) ★ | `vec-chunk-card` `vec-badge` | vector | 없음 |
| 상태 목록(사이드바 시스템 상태) | `status-row` `status-label` `status-value` | 전 탭 | MarketStatusBar(헤더 칩) |
| 점수 게이지·액션 아이템 ★ | `awr-score-*` `awr-action-*` | AWR | 없음 |
| 스키마 트리 + Annotation ★ | `schema-table-item` `schema-col-row` | nl2sql | 없음 |
| 마크다운 문서 뷰어 | `manual-doc` | manual · AWR | Settings `md-body` |

### 2.3 상태(125개)의 성격

| 성격 | 예 | 새 구조에서 |
|---|---|---|
| 탭 전역 설정 | 프로필·실행모드·검색모드·임베딩 소스 | 탭 스토어 |
| 대화/세션 누적 | messages, vectorSessions, awrTabs | 탭 스토어 (KeepAlive 가 아니라 **스토어**에 — 새로고침 전까지 유지) |
| 일회성 UI | 로딩 플래그, 드롭다운 열림, 토스트 | 컴포넌트 로컬 ref |
| 앱 전역 | health, LLM 제공자 목록, 토스트 | `useSystemStore` |

---

## 3. 목표 구조

### 3.1 디렉터리

```
web/
├── index.html
├── package.json                     investhub 와 동일 의존성 (버전 §8.1)
├── vite.config.ts                   port 5175, proxy /api → 8247
├── tsconfig*.json
├── scripts/check-undef-composables.mjs   investhub 에서 복사
└── src/
    ├── main.ts                      Pinia·router·stale-chunk 자동복구(investhub 이식)
    ├── App.vue                      AppShell + RouterView(KeepAlive) + CommandPalette
    ├── router/index.ts              7개 라우트 (§3.3)
    ├── styles/tokens.css            06 문서의 팔레트
    ├── styles/tailwind.css
    ├── lib/
    │   ├── api.ts                   axios 인스턴스 + GET 재시도 (investhub 이식, 401 처리 제거)
    │   ├── normalize.ts             ★ D11 어댑터 — 응답 키 통일
    │   ├── sse.ts                   ★ fetch+ReadableStream SSE 파서
    │   ├── format.ts                fmtNum·fmtMs·fmtBytes (investhub 부분 이식)
    │   ├── markdown.ts              marked+dompurify 래퍼
    │   ├── theme.ts                 investhub 그대로
    │   ├── menu.ts                  TOP_MENUS·라벨·아이콘 (permissions.ts 의 권한 없는 판)
    │   └── types/                   엔드포인트별 응답 타입
    ├── stores/
    │   ├── system.ts                health·providers·toast
    │   ├── nl2sql.ts · vector.ts · duality.ts · graph.ts · productivity.ts · awr.ts
    │   └── commandPalette.ts
    ├── composables/
    │   ├── useSse.ts                ★ 진행률 스트림 소비
    │   ├── useHealth.ts             폴링·상태칩
    │   └── useSubTab.ts             ?sub= 딥링크 ↔ 서브탭 동기화 (Invest.vue 패턴 일반화)
    ├── components/
    │   ├── layout/  AppShell · TopNav · MobileDrawer · StatusChips ★
    │   ├── ui/      Card Button Badge Stat LoadingBlock Skeleton InfoTip ConfirmModal
    │   │            Pagination SearchableSelect LineChart BarChart DonutChart  (investhub 이식)
    │   ├── demo/    ★ SqlBlock ResultTable CompareView ChatThread ChatComposer
    │   │            PipelineProgress SessionTabs ChunkCard ScoreGauge KvGrid
    │   │            SchemaTree ExplainPlan EmptyState DocViewer
    │   └── CommandPalette.vue       investhub 이식 (권한 필터 제거, 레지스트리는 API)
    └── pages/
        ├── Nl2sql.vue     서브탭: 질문 · 스키마·Annotation
        ├── Vector.vue     서브탭: 검색 · 문서·업로드 · Vector Store · 임베딩·ONNX
        ├── Duality.vue    서브탭: 뷰 관리 · 관계형 vs JSON · 문서 CRUD · ETag
        ├── Graph.vue      서브탭: 그래프 관리 · SQL vs PGQ · 패턴 탐색 · 시각화
        ├── Productivity.vue  서브탭: Lock-Free · Priority TX
        ├── Awr.vue        서브탭 없음 (결과 세션탭이 곧 탭)
        └── Manual.vue     서브탭: 기능 지도 · 사용 설명서 · 현재 상태·계획
```

### 3.2 IA 매핑 — 사이드바 항목은 어디로 가나 (D1 의 실체)

현 사이드바의 모든 항목을 세 갈래로 나눴다. **하나도 버리지 않는다.**

| 갈래 | 현재 | 새 위치 | 근거 |
|---|---|---|---|
| **① 화면 이동**(sub-menu-btn) | Vector Store 관리 / PDF 업로드 / 비정형 문서 검색 / 실행 쿼리 확인 · Duality 4개 · Graph 4개 · Productivity 2개 | **서브탭 pill 행** (페이지 h1 바로 아래) | investhub 의 `Invest.vue` TABS 패턴 그대로 |
| **② 실행 옵션**(질의마다 바뀜) | 실행 모드 7종 · 검색 모드 4종 · AI 프로필 · 예시 질문 · LLM 모델 | **컴포저 툴바** — 입력창 바로 위의 세그먼트/셀렉트 | 옵션은 입력과 붙어 있어야 "지금 무엇으로 묻는지"가 보인다 |
| **③ 설정·관리**(가끔 바꿈) | 임베딩 설정 · ONNX 모델 관리 · 참조 테이블·Annotation | **전용 서브탭** ("임베딩·ONNX", "스키마·Annotation") | 가끔 쓰는 것은 상시 노출하지 않는다 — investhub 가 설정을 드롭다운으로 내린 것과 같은 판단 |
| **④ 시스템 상태** | 사이드바 하단 status-list | **헤더 상태 칩**(DB● · 임베딩 모델 · LLM) + 매뉴얼>현재 상태 | investhub `MarketStatusBar` 의 KR/NY 칩과 같은 자리 |
| **⑤ 실행 쿼리 확인** | 각 탭 사이드바 | 각 페이지 우상단 **보조 버튼**(`AdminLink` 스타일) → 슬라이드 패널 | 어느 탭에나 있는 공통 기능이라 위치를 통일 |

> **사용자 확인 포인트 ①** — 이 매핑을 화면으로 보시고 판단하실 항목: "실행 모드 7종을 입력창 위
> 세그먼트로 두면 좁지 않은가". 대안은 셀렉트 하나로 접는 것. 5-5 에서 두 안을 다 만들어 보여드린다.

### 3.3 라우트

| 경로 | 페이지 | 서브탭 쿼리 | 비고 |
|---|---|---|---|
| `/` | → `/nl2sql` 리다이렉트 | | |
| `/nl2sql` | Nl2sql | `?sub=ask\|schema` | 기본 진입 |
| `/vector` | Vector | `?sub=search\|docs\|store\|embedding` | |
| `/duality` | Duality | `?sub=views\|compare\|crud\|etag` | |
| `/graph` | Graph | `?sub=manage\|compare\|pattern\|viz` | |
| `/productivity` | Productivity | `?sub=lockfree\|priority` | |
| `/awr` | Awr | | 세션탭은 스토어 |
| `/manual` | Manual | `?sub=features\|guide\|status&doc=user-guide` | 기능 레지스트리 `path` 가 여기로 승격 |
| `/legacy` | (FastAPI 가 Jinja 서빙) | `#tab` | 이식 기간 한정 |

기능 레지스트리(`app/feature_registry.py`)의 `path` 필드는 현재 `"vector:검색 모드"` 같은 위치 표기다.
탭을 이식할 때마다 그 탭 항목을 `"/vector?sub=search"` 형태의 **실제 딥링크**로 바꾼다(graph 는 5-1 에서 완료). 정본은 Python 그대로.

**`&run=1` 규약 (5-1 에서 확정):** 결과가 있는 서브탭은 `?sub=compare&run=1` 로 들어오면 mount 직후 기본 동작을 한 번 실행한다.
기능 지도의 [이동]이 결과까지 보여줄 수 있고, 헤드리스 캡처(`docs/design/captures/`)와 시연 딥링크가 이 규약에 기댄다. 이미 결과가 캐시돼 있으면 재실행하지 않는다.

---

## 4. 레이어 설계

### 4.1 API 클라이언트

investhub `lib/api.ts` 를 가져오되 **401 → /login 리다이렉트를 제거**한다(인증 없음).
GET 재시도(5xx·네트워크, 1.5초 백오프)는 유지 — ADB 절전 복귀 창을 흡수하는 목적이 같다.

엔드포인트별 함수는 `lib/types/` 의 타입과 함께 `lib/<tab>.ts` 로 둔다 (investhub `lib/research.ts` 패턴):

```ts
// lib/graph.ts
export interface CompareResult { label: string; sql_query: string; pgq_query: string;
  sql_columns: string[]; sql_data: Row[]; sql_elapsed: number; sql_error?: string; /* … */ }
export const compareSqlVsPgq = (i: number) => api.post<CompareResult>('/api/graph/compare', { query_index: i }).then(r => r.data)
```

### 4.2 D11 정규화 — `lib/normalize.ts`

응답 배열 키가 `data` / `chunks` / `sql_data`·`pgq_data` / `models` / `profiles` / `views` 로 제각각이다.
**백엔드는 두고** 클라이언트에서 한 층으로 흡수한다:

```ts
export interface Rows { columns: string[]; rows: Record<string, unknown>[]; elapsedMs?: number; sql?: string }
export const fromExecuteSql = (r: any): Rows => ({ columns: r.columns, rows: r.data, elapsedMs: r.elapsed_ms, sql: r.sql_executed })
export const fromGraphSide  = (r: any, side: 'sql'|'pgq'): Rows => ({ columns: r[`${side}_columns`], rows: r[`${side}_data`], elapsedMs: r[`${side}_elapsed`], sql: r[`${side}_query`] })
```

`ResultTable` 과 `CompareView` 는 **`Rows` 하나만 받는다.** 어댑터가 유일한 "키 이름을 아는 곳"이 되고,
Phase 6 에서 백엔드 키를 통일할지는 그때 선택한다(안 해도 된다).

### 4.3 스토어

탭 스토어는 "대화·세션·설정"만 담고 fetch 함수는 `lib/` 에 둔다. 한 예:

```ts
// stores/vector.ts
export const useVectorStore = defineStore('vector', () => {
  const mode = ref<'vector'|'keyword'|'hybrid'|'compare'>('vector')
  const sessions = ref<Session[]>([])            // 결과 세션탭
  const activeSession = ref(0)
  const embedding = ref<EmbeddingConfig | null>(null)
  async function search(q: string) { /* lib/vector.search → sessions 에 push */ }
  return { mode, sessions, activeSession, embedding, search }
})
```

페이지는 `<KeepAlive>` 안에서 렌더된다(App.vue — investhub 와 동일). 스토어 + KeepAlive 조합이면
탭을 오가도 대화·스크롤·입력이 남는다. 지금 `v-show` 가 주던 경험과 같다.

### 4.4 SSE — `composables/useSse.ts`

현 `app.js:1065~` 의 파서(fetch → `getReader()` → `event:`/`data:` 프레임)를 그대로 옮긴다.
investhub 에는 SSE 소비자가 없으므로 **이건 db26ai 고유 자산**이다.

```ts
export function useSse<TStep, TDone>() {
  const steps = ref<TStep[]>([]); const progress = ref<{current:number,total:number,percent:number}|null>(null)
  const done = ref<TDone|null>(null); const error = ref<string|null>(null); const running = ref(false)
  async function start(url: string, body: FormData | object) { /* 프레임 파싱 → steps/progress/done 갱신 */ }
  function reset() { /* … */ }
  return { steps, progress, done, error, running, start, reset }
}
```

소비처: PDF 업로드(`PipelineProgress`), AWR 분석(같은 컴포넌트, 라벨만 다름).
`done.warning`(임베딩 실패 건수 — Phase 1 에서 추가한 필드)을 **반드시 화면에 띄운다.**

### 4.5 서브탭 딥링크 — `composables/useSubTab.ts`

investhub `Invest.vue` 의 `?subtab=` 감시 + 레거시 id 리다이렉트 맵을 일반화한다.
모든 페이지가 `const sub = useSubTab(['search','docs','store','embedding'], 'search')` 한 줄로 쓴다.
CommandPalette·기능 지도의 [이동] 이 이 쿼리로 들어온다.

---

## 5. 공존·전환·롤백 (D3)

### 5.1 FastAPI 서빙

```python
# main.py — 변경 요지
DIST = Path("web/dist")
if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="spa-assets")
app.mount("/static", StaticFiles(directory="static"), name="static")      # 레거시 유지

@app.get("/legacy")
async def legacy(request: Request): return templates.TemplateResponse(request=request, name="index.html", ...)

@app.get("/{path:path}")          # /api 는 라우터가 먼저 잡으므로 여기 안 온다
async def spa(path: str, request: Request):
    if (DIST / "index.html").exists(): return FileResponse(DIST / "index.html")
    return await legacy(request)   # dist 가 없으면 레거시로 폴백 = 롤백
```

- 순서: `/api/*` 라우터 → `/static` → `/assets` → `/legacy` → catch-all. `/api/health` 가 catch-all 에
  먹히지 않는지 테스트로 고정한다(§8.3).
- **롤백** = `rm -rf web/dist` 후 재기동. 코드 되돌리기 없이 레거시가 `/` 로 복귀한다.

### 5.2 이식 기간의 탭 이동

새 SPA 의 상단 메뉴에는 7개가 다 있다. **아직 안 옮긴 탭은 `/legacy#<tab>` 으로 나간다.**
레거시 `app.js` 에 3줄을 더한다: 기동 시 `location.hash` 가 탭 id 면 `activeTab` 을 그걸로.
반대 방향(레거시 → SPA)은 레거시 헤더에 "새 화면으로" 링크 하나. 둘 다 Phase 6 에서 제거.

### 5.3 빌드·배포·캐시

| 항목 | 지금 | 이식 후 |
|---|---|---|
| 빌드 | 없음 | `cd web && npm run build` (`vue-tsc` + undef-check + `vite build`) |
| 배포 | `launchctl kickstart` | **빌드 → kickstart** (FastAPI 가 dist 를 정적 서빙) |
| 캐시버스팅 | `?v=N` 수동 | Vite 해시 파일명. `?v=N` 관례 **종료** — Phase 6 에서 CLAUDE.md·노하우 문서 갱신 |
| 배포 직후 회색화면 | (해당 없음) | investhub `main.ts` 의 **stale-chunk 자동 새로고침** 이식 (5-0) |
| 개발 | `python main.py` 자동리로드 | `npm run dev`(5175, `/api` 프록시) + 백엔드 그대로 |

`scripts/deploy.sh` 하나를 둔다: `pytest -q && ruff && (cd web && npm run build) && launchctl kickstart …`.
운영 가이드 3절을 이 스크립트로 갱신한다(5-0 완료 시).

---

## 6. 이식 순서와 탭별 분해 (D7·D8)

### 6.0 · 5-0 토대 (★ Fable)

| 만드는 것 | 출처 |
|---|---|
| `web/` 스캐폴딩, `vite.config.ts`, `tsconfig`, `package.json` | investhub 복사 후 포트·이름만 변경 |
| `styles/tokens.css` | **06 문서 §2 의 팔레트** (레거시 별칭 블록 없이) |
| `AppShell`·`TopNav`·`MobileDrawer` | investhub 이식. 로고·헤더색·활성표시 = 06 §4 |
| `StatusChips` ★ | `MarketStatusBar` 를 본떠 DB●·임베딩·LLM 칩 |
| `components/ui/*` 13종 | investhub 그대로 (Stat 의 이모지 아이콘 경로 제거) |
| `components/demo/*` 중 **SqlBlock·ResultTable·CompareView·EmptyState** | 신규 — 이 4개가 있어야 첫 탭(graph)이 선다 |
| `lib/api.ts`·`normalize.ts`·`format.ts`·`markdown.ts`·`theme.ts`·`menu.ts` | §4 |
| `stores/system.ts`·`composables/useHealth.ts`·`useSubTab.ts` | §4 |
| `main.py` 서빙 변경 + `/legacy` + hash shim | §5 |
| `scripts/deploy.sh`, `check-undef-composables.mjs` | |
| **빈 7페이지**(각각 "이 화면은 아직 레거시입니다 → /legacy#tab" 링크) | 5-1 부터 하나씩 채운다 |

**완료 판정:** `npm run build` 통과 · `/` 가 SPA · `/legacy` 가 기존 화면 · 헤더 상태칩이 `/api/health` 를 반영 · 다크모드 토글 동작 · 06 캡처와 헤더·카드·서브탭 스타일 대조.

### 6.1 · 5-1 Property Graph (★ Fable — 첫 탭, 조립 패턴의 기준) — ✅ 완료 2026-09-05

| 서브탭 | 컴포넌트 트리 | API |
|---|---|---|
| 그래프 관리 | `Card` › 설명 + `Button×2`(생성/삭제) › `SqlBlock`(DDL) | create · drop |
| SQL vs PGQ | `SearchableSelect`(쿼리 3) › `CompareView` › 좌·우 `SqlBlock`+`ResultTable`+소요 | compare |
| 패턴 탐색 | 셀렉트 › `SqlBlock` › `ResultTable` | pattern |
| 시각화 | ~~기존 canvas 로직~~ 레거시는 자리표시자였다 → **SVG 이분 그래프 신설** `GraphViz.vue`(고객 ⇢ 제품, 간선 굵기=매출, 색=카테고리, 라이브러리 없음) | (pattern 0 결과 재사용) |
| (공통) 실행 쿼리 확인 | 우상단 보조 버튼 › 슬라이드 패널 › `SqlBlock`+`ResultTable` = **`RecentQueriesPanel.vue`**(`endpoint` prop 만 바꿔 전 탭 재사용) | recent-queries |

백엔드: `app/routers/graph.py` 로 6개 엔드포인트 이동. **완료 판정:** SQL/PGQ 3종 완전일치 표시(회귀 테스트 통과) · 캡처 대조.
**여기서 세운 "카드 안에 SqlBlock + ResultTable" 조립 규칙이 5-2~5-5 의 기준이 된다.** 확정본은 `SESSION_HANDOFF.md` §4-5
(페이지 › SubTabs › KeepAlive · lib/<tab>.ts → stores/<tab>.ts → 페이지 · normalize 에서만 응답 키를 안다).

### 6.2 · 5-2 개발생산성 (~~Opus~~ Fable — 사용자 결정, 패턴 추종) — ✅ 완료 2026-09-05

시뮬 2종 = 서브탭 2개. 각각 `Card`(VersusBox 도입) › `Card`(실행 버튼 › `EmptyState` | **`StepList`**) — 결과는 한 번에 오지만 한 단계씩 드러낸다(스토어의 reveal 카운터, [바로 보기]로 건너뜀).
`StepList.vue`(성공/거부 라벨 props) 와 `VersusBox.vue`(기존 vs 26ai 두 칸) 가 여기서 생겼고 graph 관리 화면도 VersusBox 로 통일했다. 라우터 `productivity.py`.
Priority 시뮬은 ADB 에서 2~6단계가 설명이라는 사실을 화면에 적었다(레거시는 숨김).

### 6.3 · 5-3 Duality (~~Opus~~ Fable — 사용자 결정, 패턴 추종) — ✅ 완료 2026-09-05

| 서브탭 | 핵심 |
|---|---|
| 뷰 관리 | 생성/삭제/목록 — 5-1 의 관리 화면과 같은 조립 |
| 관계형 vs JSON | `CompareView` (좌 `ResultTable`, 우 JSON 프리티 — `SqlBlock` 의 json 모드 ↔ **앱 화면 카드** `Segmented` 토글). `equal` = PK/_id 배열 일치. 백엔드를 PK 정렬로 고쳐 같은 행이 마주 본다 |
| 문서 CRUD | 목록(`ResultTable` 클릭) › 편집 카드(JSON textarea + 저장) |
| ETag | 단계 카드(5-2 의 `StepList`, `Step.etag` 배지). 4단계 = DB 의 ORA-42699 거부(진짜 검사) |

라우터 `duality.py`.

### 6.4 · 5-4 AWR (★ Fable — 시각 밀도 최상위) — ✅ 완료 2026-09-05

> **정정(2026-09-05):** `/api/awr/analyze` 는 SSE 가 아니라 분석 후 JSON 1회다. `PipelineProgress` 는 타이머 연출로 돌고, SSE 수신은 5-6 업로드에서만 쓴다.
> 8섹션은 아코디언 대신 **기본 펼침 + 접기 버튼**(정보 누락 0 원칙). 원문은 iframe 모달. `?load=<json>` 로 저장된 응답을 열 수 있다(캡처·시연).

서브탭 없이 한 페이지: 상단 업로드 카드(드롭존 + LLM 셀렉트) › `PipelineProgress`(~~SSE~~ 타이머) › **`SessionTabs`** › 결과:
`ScoreGauge`(7 카테고리) › 요약 › 8섹션 아코디언(각 `KvGrid`/`ResultTable`/해석) › 액션아이템(우선순위 배지 + evidence) › 후속질문(`ChatThread` 축소판) › 원문 보기(모달).
`renderMarkdown` 은 `lib/markdown.ts`(marked+dompurify)로 대체. 라우터 `awr.py`.
**완료 판정:** 기존 분석 결과 JSON 을 그대로 넣어 렌더가 같은가(픽셀이 아니라 **정보 누락 0**).

### 6.5 · 5-5 NL2SQL (★ Fable — 첫 화면, 앱의 얼굴) — ✅ 완료 2026-09-05 (확인 포인트 ①·④ 제시 중)

| 서브탭 | 컴포넌트 |
|---|---|
| 질문 | `ChatThread`(사용자 말풍선·결과 블록: `SqlBlock`+`ResultTable`+차트+실행계획 버튼) + **`ChatComposer`**(프로필 셀렉트 · 실행모드 세그먼트 · 예시질문 셀렉트 · 입력 · SQL 직접실행 입력) |
| 스키마·Annotation | `SchemaTree`(테이블 › 컬럼, Annotation 배지) + `Button`(적용/제거) |

라우터 `nl2sql.py`(ask·profiles·set-profile·annotations·schema-info·explain-plan·execute-sql).
**사용자 확인 포인트 ①**(§3.2)을 여기서 두 안으로 시연.

### 6.6 · 5-6 Vector (★ Fable — 상태 의존 최상위)

| 서브탭 | 컴포넌트 |
|---|---|
| 검색 | `SessionTabs` › `ChatThread`(답변 + `ChunkCard` 목록 + 시각화) + `ChatComposer`(검색모드 세그먼트 4 · top_k · LLM) — compare 모드는 `CompareView` |
| 문서·업로드 | 드롭존 › `PipelineProgress`(SSE, **warning 표시**) › 문서 목록 `ResultTable`(삭제) |
| Vector Store | 정의/데이터/인덱스 3버튼 › `SqlBlock`+`ResultTable` |
| 임베딩·ONNX | 소스 토글 · 모델 셀렉트 · **차원 경고 배너**(HNSW 함정 — 트러블슈팅 4절) · ONNX 목록/테스트/업로드 |

라우터 `vector.py`(25개). `vector_search.py` 는 그대로.
**완료 판정:** 4모드 회귀 테스트 통과 · 자연어 질문에서 keyword 점수 > 0 · 세션탭 전환 시 대화 보존.

### 6.7 · 5-7 매뉴얼 + ⌘K (Opus)

`Manual.vue` 서브탭 3: 기능 지도(`/api/guide/features` — 카드형 목록, [이동] 버튼이 §3.3 딥링크로), 사용 설명서(`DocViewer`, `md-body` 스타일 이식), 현재 상태·계획.
`CommandPalette` 이식 — 데이터 소스를 `FEATURES` import 에서 **`/api/guide/features` fetch** 로 바꾼다(D5).
헤더 `?` 아이콘 = `/manual`. 레지스트리 `path` 를 실제 라우트로 갱신(Python 한 파일).

---

## 7. 백엔드 라우터 분리 (D8) — 규칙

- `app/routers/__init__.py` 없이 파일별 `router = APIRouter(prefix="/api/<tab>")`. 공통(`/health`·`/llm/providers`)은 `routers/system.py`.
- **경로·응답은 바꾸지 않는다.** `routes.py` 에서 함수를 **잘라 붙이기**만 한다. Pydantic 모델도 함께 이동.
- `main.py` 는 `for r in (system, nl2sql, vector, …): app.include_router(r.router)`.
- 탭 하나 옮길 때마다 `pytest -q` 46개가 그대로 통과해야 한다 — 경로가 안 바뀌었다는 증거.
- 마지막(5-7)에 `routes.py` 가 비면 삭제. 03_API_명세서 의 "구현" 열(`routes.py:NNN`)은 생성 스크립트가 파일명을 따라가도록 수정.

---

## 8. 품질 게이트

### 8.1 의존성 (investhub 와 동일 버전 — 이식 마찰 0)

`vue ^3.5 · vue-router ^4.6 · pinia ^2.3 · vite ^7 · typescript ~5.6 · tailwindcss ^4.2 · @tailwindcss/vite · @vitejs/plugin-vue ^6 · vue-tsc ^2.2 · lucide-vue-next · chart.js ^4.5 · marked ^18 · dompurify ^3 · axios ^1.7`
(node v22 확인됨)

### 8.2 프론트 게이트 (매 탭 커밋 전)

```
npm run typecheck    = check-undef-composables + vue-tsc --noEmit
npm run build
```
**빌드 통과는 동작 확인이 아니다**(노하우 §4). 매 탭마다 **브라우저에서 실제로 조작**하고, 06 캡처와 나란히 놓고 편차를 적는다.

### 8.3 백엔드·통합

- `pytest tests/ -q` 46개 그대로 + 신규 2개: `GET /` 가 SPA(`id="app"`)를 주는지, `GET /api/health` 가 catch-all 에 먹히지 않는지.
- `ruff check .`
- `scripts/check-secrets.sh`

### 8.4 시각 대조 프로토콜 (사용자용)

각 탭 완료 시 제가 (1) 새 화면 캡처 (2) `captures/investhub_*.png` 중 대응 화면 (3) 편차 목록 3~7줄을 드린다.
사용자는 **"이 편차를 받아들일 것인가"만** 판단하면 된다. 편차 종류는 06 §10 의 5가지로 분류한다.

---

## 9. 가져오지 않는 것 (D9) — 명시적 제외

| investhub 것 | 이유 |
|---|---|
| `stores/auth.ts`, `Login.vue`, `Forbidden.vue`, `permissions.ts` 권한 매트릭스, `IdleGuard`, `UserBadge` 드롭다운 | 인증 없음. 헤더 우측은 상태칩·테마·`?`·⌘K 만 |
| `MiniCalculator`·`FxConverter`·`MemoPad`·`CalendarTodayAlert`·`AssistantDrawer`·`QuickGuideReturnChip` | 도메인 위젯 |
| `tokens.css` 의 "레거시 별칭" 블록 | 처음부터 canonical 이름만 (그쪽 TODO 를 물려받지 않는다) |
| `api.ts` 의 401 리다이렉트, 로그인 재시도 규칙, 은퇴설계 PUT 재시도 | 해당 엔드포인트 없음 |
| 페이지별 `expert` 모드 토글, per-user localStorage 키 | 사용자 1명 |

---

## 10. 리스크·미결·사용자 확인 포인트

| # | 리스크 | 대응 |
|---|---|---|
| R1 | 채팅형 화면(nl2sql·vector)이 사이드바 없이 **너무 넓어져** 말풍선 가독성이 떨어질 수 있다 | 스레드 폭 `max-w-[960px]` 중앙 정렬 — investhub `md-body` 의 폭 감각과 맞춘다. 5-5 에서 확인 |
| R2 | vector 탭 1,062줄의 상태 얽힘(세션·모드·임베딩 설정이 서로 참조) | 스토어 먼저 설계하고 컴포넌트는 스토어만 본다. 5-6 이 Fable 인 이유 |
| R3 | ~~그래프 시각화~~·벡터 시각화의 canvas 코드가 Vue 생명주기와 충돌 | 그래프는 5-1 에서 **순수 SVG 템플릿**으로 만들어 생명주기 문제 자체가 없다(레거시에 canvas 코드도 없었다). 벡터는 `VectorViz.vue` 로 격리. investhub `LineChart.vue` 가 선례 |
| R4 | 이식 중 레거시와 SPA 의 **캐시버스팅 규칙이 이중** | 레거시는 `?v=N` 유지, SPA 는 해시. 노하우 문서에 기간 한정 규칙 명시 |
| R5 | `marked` 의 표 렌더가 3-8 정규식 렌더러와 달라 가이드 문서 모양이 바뀜 | 06 §5.13 `md-body` 스타일을 investhub 에서 그대로 가져와 오히려 좋아진다. 5-7 에서 4문서 전부 육안 확인 |

**사용자 확인 포인트 (화면을 보고 판단하실 것)**
1. §3.2 ① — 실행 모드 7종의 배치(세그먼트 vs 셀렉트) — 5-5 에서 두 안 시연 → **제시함** (`captures/db26ai_nl2sql_ask_light.png` = A 세그먼트 · `ask_select_light.png` = B 셀렉트, `?modeui=select`)
2. D10 — SQL 블록 다크 스타일 유지 여부 — 5-1 첫 화면에서 → **✅ 확정: 두 테마 모두 다크 유지** (사용자, 2026-09-05; 근거 캡처 `captures/db26ai_graph_compare_light.png` · `_dark.png`)
3. 헤더 색 — Oracle 다크 차콜(권고) vs investhub 블루 — 5-0 에서
4. 채팅 스레드 폭(R1) — 5-5 에서 → **제시함** (`max-w-[960px]` 중앙 정렬, 같은 캡처)
5. 매뉴얼 탭의 헤더 `?` 아이콘 진입 — 5-7 에서

각 지점에서 제가 멈추고 캡처 2장(새 화면·기준선)과 함께 묻는다. 그 외에는 이 문서대로 진행한다.
