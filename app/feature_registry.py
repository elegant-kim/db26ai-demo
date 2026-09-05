"""기능 레지스트리 — 앱 전 기능의 단일 정본 카탈로그 (2026-09-04 신설, 계획서 3-3).

소비처: 「매뉴얼」 탭의 기능 지도 — "어디에 뭐가 있고 언제 쓰나".
투입 배경: 이 프로젝트를 5개월 만에 열었을 때 **개발자 본인이 무엇을 만들었는지
기억하지 못했다.** investhub 의 featureRegistry.ts 주석이 같은 문제를 이렇게 적고 있다 —
"기능이 많아 관리자조차 저사용 기능을 잊는 문제".

규칙: **새 탭·기능을 만들면 여기 한 줄 추가한다.** 탭 라벨을 바꾸면 `tab_label` 도
글자 그대로 맞춘다 — 화면과 다른 이름이 적혀 있으면 사람이 그 이름으로 화면을 못 찾는다.
정본이 두 곳이 되지 않도록, 이 파일이 기능 카탈로그의 정본이다.

path 형식: "탭id:사이드바항목" — 현재 레거시 UI 는 딥링크가 없어 위치 표기로만 쓴다.
Phase 5 SPA 이식 때 실제 라우트(`/vector?sub=search`)로 승격한다.
"""
from __future__ import annotations

TAB_LABELS = {
    "nl2sql": "NL2SQL(Select AI)",
    "vector": "AI Vector Search",
    "duality": "JSON Relational Duality",
    "graph": "Property Graph",
    "productivity": "개발생산성 향상",
    "extra": "기타 부가 기능",
}

# (tab, name, desc, how, path, keyword)
_F = [
 # ── ① NL2SQL ──────────────────────────────────────────────
 ("nl2sql", "AI 프로필 선택", "Select AI 프로필(LLM 제공자·모델·참조 테이블 묶음) 전환",
  "질문 전에 먼저 고른다. GROQ_SH / GEMINI_SH 두 개가 같은 SH 테이블을 다른 LLM 으로 본다.",
  "/nl2sql?sub=ask", "profile 프로필 groq gemini select ai"),
 ("nl2sql", "실행 모드 7종", "runsql·showsql·narrate·explainsql·showprompt·summarize·chat",
  "SQL 만 보려면 showsql, 바로 실행하려면 runsql, 생성된 SQL 해설은 explainsql(한국어).",
  "/nl2sql?sub=ask", "action runsql showsql narrate explainsql showprompt summarize chat 모드"),
 ("nl2sql", "예시 질문", "SH 스키마용 데모 질문 14종",
  "무엇을 물어야 할지 막힐 때. 난이도 순으로 배치돼 있다.",
  "/nl2sql?sub=ask", "sample 예시 질문 데모"),
 ("nl2sql", "참조 테이블 · Annotation", "프로필이 보는 테이블의 컬럼 정의와 Display Annotation 일괄 적용/제거",
  "LLM 이 컬럼 의미를 잘못 잡을 때 Annotation 을 붙여 정확도를 올린다. 23ai+ 기능.",
  "/nl2sql?sub=schema", "schema annotation 어노테이션 컬럼 코멘트"),
 ("nl2sql", "SQL 직접 실행", "화면 하단 입력창에서 SELECT 문을 직접 실행",
  "AI 가 만든 SQL 을 손봐서 다시 돌려볼 때. SELECT 로 시작하는 문장만 허용(WITH 도 거부).",
  "/nl2sql?sub=ask", "execute sql select 직접 실행"),
 ("nl2sql", "실행계획", "생성된 SQL 의 EXPLAIN PLAN 조회",
  "AI 가 만든 SQL 이 인덱스를 타는지 확인할 때.",
  "/nl2sql?sub=ask", "explain plan 실행계획 dbms_xplan"),

 # ── ② AI Vector Search ────────────────────────────────────
 ("vector", "Vector Store 관리", "DOCUMENTS/DOC_CHUNKS 테이블 생성·삭제·정의·데이터·인덱스 조회",
  "벡터 저장소가 실제로 어떤 테이블·인덱스로 되어 있는지 보여줄 때. 데모의 도입부로 좋다.",
  "/vector?sub=store", "table 테이블 인덱스 정의 doc_chunks documents"),
 ("vector", "PDF 업로드", "PDF → 텍스트 추출 → 청킹 → 임베딩 → 저장 (SSE 진행률)",
  "새 문서를 넣을 때. 5단계 파이프라인이 실시간으로 보인다. 27쪽 PDF 가 79청크·30초.",
  "/vector?sub=docs", "upload pdf 업로드 청킹 임베딩 chunk"),
 ("vector", "비정형 문서 검색", "4가지 모드로 문서 검색 + RAG 답변 생성",
  "이 탭의 핵심. 같은 질문을 모드만 바꿔 물어보면 차이가 바로 드러난다.",
  "/vector?sub=search", "search rag 검색 질문 유사도"),
 ("vector", "검색 모드 — 벡터", "VECTOR_DISTANCE 코사인 유사도 (의미 검색)",
  "단어가 달라도 의미가 같으면 찾는다. 키워드 검색과 비교해 보여줄 때 기준선.",
  "/vector?sub=search", "vector 벡터 의미 semantic cosine"),
 ("vector", "검색 모드 — 키워드", "Oracle Text CONTAINS + SCORE (인덱스 없으면 LIKE 폴백)",
  "전통적 검색. 정확한 단어가 있어야 찾는다 — 벡터 검색의 대조군.",
  "/vector?sub=search", "keyword contains score oracle text 키워드"),
 ("vector", "검색 모드 — 하이브리드", "단일 SQL 에서 CONTAINS + VECTOR_DISTANCE 결합 (26ai)",
  "26ai 의 대표 기능. hybrid = 0.7×벡터유사도 + 0.3×키워드점수. 두 방식의 장점을 합친다.",
  "/vector?sub=search", "hybrid 하이브리드 26ai 결합"),
 ("vector", "검색 모드 — 비교", "키워드·벡터를 동시에 실행해 좌우로 나란히 표시",
  "차이를 한 화면에서 보여줄 때 가장 설득력 있다. RAG 답변은 생성하지 않아 빠르다(40~70ms).",
  "/vector?sub=search", "compare 비교 좌우"),
 ("vector", "임베딩 설정", "DB 내장(ONNX) ↔ 외부 API 런타임 전환, 모델 선택",
  "같은 질문을 다른 임베딩 모델로 돌려 결과 차이를 보여줄 때. ⚠ 차원이 다른 모델로 바꾸면 HNSW 인덱스 재생성이 필요하다.",
  "/vector?sub=embedding", "embedding onnx 임베딩 모델 전환 e5"),
 ("vector", "ONNX 모델 관리", "DB 내 ONNX 모델 목록·상세·테스트 임베딩·업로드·OML Cloud 로드·삭제",
  "\"임베딩이 DB 안에서 돈다\"를 증명할 때. 테스트 임베딩이 차원과 소요시간을 보여준다.",
  "/vector?sub=embedding", "onnx model 모델 적재 테스트 차원"),
 ("vector", "실행 쿼리 확인", "V$SQL 에서 방금 돈 벡터 쿼리 원문 조회",
  "화면 뒤에서 어떤 SQL 이 돌았는지 보여줄 때. 데모의 신뢰도를 크게 올린다.",
  "/vector?sub=store", "v$sql recent query 실행 쿼리"),

 # ── ③ JSON Relational Duality ─────────────────────────────
 ("duality", "Duality View 생성/삭제", "관계형 테이블 위에 JSON 문서 뷰를 만든다",
  "시작점. CUSTOMERS_DV·PRODUCTS_DV 두 개가 생긴다. 데이터 복제가 없다는 점이 핵심.",
  "/duality?sub=views", "duality view 생성 json 이중성"),
 ("duality", "관계형 vs JSON 비교", "같은 데이터를 SQL JOIN 과 JSON 문서로 나란히 조회",
  "\"하나의 데이터, 두 개의 얼굴\"을 보여주는 화면.",
  "/duality?sub=compare", "compare 관계형 json 비교 join"),
 ("duality", "JSON 문서 CRUD", "JSON 문서를 조회·수정하면 관계형 테이블에 그대로 반영",
  "JSON 을 고쳤는데 테이블이 바뀌는 것을 보여줄 때. Duality 의 진짜 가치.",
  "/duality?sub=crud", "crud 수정 update 문서 json"),
 ("duality", "ETag 동시성 제어", "낙관적 동시성 — 두 사용자가 같은 문서를 고칠 때 충돌 재현",
  "실제 서비스에서 왜 안전한지 설명할 때. ETag 불일치로 뒤늦은 수정이 거부된다.",
  "/duality?sub=etag", "etag 동시성 낙관적 충돌 concurrency"),
 ("duality", "실행 쿼리 확인", "V$SQL 에서 Duality 관련 최근 쿼리 조회",
  "JSON 조회가 실제로 어떤 SQL 로 도는지 보여줄 때.",
  "/duality?sub=views", "v$sql 실행 쿼리"),

 # ── ④ Property Graph ──────────────────────────────────────
 ("graph", "그래프 생성/삭제", "SH 테이블(CUSTOMERS·PRODUCTS·SALES) 위에 SQL Property Graph 정의",
  "시작점. 정점 2종·간선 1종. 기존 테이블 위의 뷰라 데이터 복제가 없다 — Neo4j 등과의 결정적 차이.",
  "/graph?sub=manage", "graph 그래프 생성 property sql/pgq"),
 ("graph", "SQL vs SQL/PGQ 비교", "같은 질문을 기존 JOIN 과 그래프 질의로 각각 실행",
  "이 탭의 핵심. 3가지 질문(구매 목록 / 제품별 매출 Top-10 / 추천 시스템 기초)이 양쪽 완전 동일한 결과를 낸다.",
  "/graph?sub=compare", "compare join pgq 비교 graph_table"),
 ("graph", "관계 탐색 (패턴 매칭)", "MATCH 패턴으로 관계를 따라가는 질의 3종",
  "JOIN 으로는 쓰기 힘든 질의를 보여줄 때. 2-hop(고객→제품←고객) 이 대표적.",
  "/graph?sub=pattern", "match 패턴 관계 탐색 2-hop"),
 ("graph", "그래프 시각화", "패턴 질의 결과(고객 → 구매 제품)를 SVG 이분 그래프로 그린다 — 간선 굵기 = 매출",
  "표만으로 감이 안 올 때. 2026-09-05 신설(레거시는 자리표시자였다).",
  "/graph?sub=viz", "visualize 시각화 그래프"),
 ("graph", "실행 쿼리 확인", "V$SQL 에서 GRAPH_TABLE 관련 최근 쿼리 조회 — 페이지 우상단 버튼",
  "그래프 질의가 실제로 어떤 SQL 인지 보여줄 때.",
  "/graph?sub=manage", "v$sql 실행 쿼리 graph_table"),

 # ── ⑤ 개발생산성 향상 ──────────────────────────────────────
 ("productivity", "Lock-Free Reservations", "동시 차감 시뮬레이션 — 잠금 경합 없이 잔액을 예약",
  "여러 세션이 같은 잔액을 동시에 차감할 때, 기존 방식은 잠금 대기가 생기지만 26ai 는 예약으로 처리한다. CHECK 제약 위반도 재현된다.",
  "/productivity?sub=lockfree", "lock free reservation 동시 차감 잠금 예약"),
 ("productivity", "Priority Transactions", "우선순위 충돌 시뮬레이션 — 높은 우선순위가 낮은 쪽을 선점",
  "긴급 트랜잭션이 일반 트랜잭션에 막히지 않아야 할 때.",
  "/productivity?sub=priority", "priority transaction 우선순위 선점"),
 ("productivity", "실행 쿼리 확인", "V$SQL 에서 시뮬레이션 관련 최근 쿼리 조회",
  "시뮬레이션이 실제로 어떤 SQL 을 돌렸는지 확인할 때.",
  "/productivity?sub=lockfree", "v$sql 실행 쿼리"),

 # ── ⑥ 기타 부가 기능 ──────────────────────────────────────
 ("extra", "AWR 리포트 분석", "AWR HTML 업로드 → 23개 섹션 파싱 → LLM 이 8개 섹션 보고서 생성",
  "실제 DB 성능 리포트를 AI 가 읽고 진단하게 할 때. 최대 20MB.",
  "/awr", "awr 성능 분석 리포트 튜닝"),
 ("extra", "카테고리 점수 · 액션 아이템", "7개 카테고리 0-100점 + 우선순위별 조치 목록",
  "\"어디가 문제인가\"를 한눈에 볼 때. 각 액션에 근거(evidence)가 붙는다.",
  "/awr", "score 점수 action item 액션 우선순위"),
 ("extra", "후속 질문", "분석 결과에 대해 이어서 질문",
  "보고서만으로 부족할 때. 원본 AWR 을 컨텍스트로 답한다.",
  "/awr", "followup 후속 질문"),
 ("extra", "AWR 원본 보기", "업로드한 AWR HTML 원문을 그대로 열람",
  "AI 분석의 근거를 원문에서 확인할 때.",
  "/awr", "source 원본 html"),

 # ── 공통 ──────────────────────────────────────────────────
 ("nl2sql", "시스템 상태", "DB 연결·임베딩 모델·LLM 모델 — 헤더 상태칩(전 화면 공통), 호버하면 상세",
  "무언가 이상할 때 여기부터 본다. /api/health 와 같은 값이다.",
  "/nl2sql", "health 상태 연결 버전 시스템 상태칩"),
]

FEATURES = [
    {"tab": t, "tab_label": TAB_LABELS.get(t, t), "name": n, "desc": d,
     "how": h, "path": p, "keyword": k}
    for t, n, d, h, p, k in _F
]


def list_features(tab: str | None = None) -> list[dict]:
    """기능 목록. tab 을 주면 해당 탭만."""
    return [f for f in FEATURES if tab is None or f["tab"] == tab]


def grouped() -> list[dict]:
    """탭 순서대로 묶은 기능 지도 — 「매뉴얼」 탭이 그대로 그린다."""
    return [
        {"tab": t, "tab_label": label, "items": [f for f in FEATURES if f["tab"] == t]}
        for t, label in TAB_LABELS.items()
    ]
