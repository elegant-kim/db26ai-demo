"""기능 레지스트리 — 앱 전 기능의 단일 정본 카탈로그 (2026-09-04 신설, 계획서 3-3).

소비처: 「매뉴얼」 탭의 기능 지도 — "어디에 뭐가 있고 언제 쓰나".
투입 배경: 이 프로젝트를 5개월 만에 열었을 때 **개발자 본인이 무엇을 만들었는지
기억하지 못했다.** investhub 의 featureRegistry.ts 주석이 같은 문제를 이렇게 적고 있다 —
"기능이 많아 관리자조차 저사용 기능을 잊는 문제".

규칙: **새 탭·기능을 만들면 여기 한 줄 추가한다.** 탭 라벨을 바꾸면 `tab_label` 도
글자 그대로 맞춘다 — 화면과 다른 이름이 적혀 있으면 사람이 그 이름으로 화면을 못 찾는다.
정본이 두 곳이 되지 않도록, 이 파일이 기능 카탈로그의 정본이다.

path 형식: 실제 라우트(`/vector?sub=search`) — 기능 지도의 [이동]·⌘K 가 그대로 push 한다.

slides (선택, 7번째 자리): 이 기능을 설명하는 장표의 꼬리표 목록 — `["VS-12", "VS-13"]`.
장표 연동(2026-09-29, P5)의 앵커 정본이 여기다. 페이지 헤더 「장표」 버튼·⌘K·매뉴얼이 같은 값을 본다.
꼬리표는 docs/slides/README.md 규칙(`덱코드-번호`). 덱이 아직 없거나 꼬리표가 덱에 없으면 화면에서 조용히 빠진다
(매뉴얼 › 장표 에 「덱에 없는 꼬리표」로만 보인다) — 문서보다 코드가 먼저여도 앱은 그대로 돈다.
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

# (tab, name, desc, how, path, keyword[, slides])
_F = [
 # ── ① NL2SQL ──────────────────────────────────────────────
 ("nl2sql", "AI 프로필 선택", "Select AI 프로필(LLM 제공자·모델·참조 테이블 묶음) 전환",
  "페이지 우상단 셀렉트 — 세 서브탭이 같은 프로필을 본다. GROQ_SH / GEMINI_SH 두 개가 같은 SH 테이블을 다른 LLM 으로 본다.",
  "/nl2sql?sub=env", "profile 프로필 groq gemini select ai"),
 ("nl2sql", "실행 모드 7종", "runsql·showsql·narrate·explainsql·showprompt·summarize·chat",
  "SQL 만 보려면 showsql, 바로 실행하려면 runsql, 생성된 SQL 해설은 explainsql(한국어).",
  "/nl2sql?sub=ask", "action runsql showsql narrate explainsql showprompt summarize chat 모드"),
 ("nl2sql", "환경 — 프로필 · 크리덴셜 · ACL 사슬", "시연의 시작점. 프로필이 무엇을 보는지 → credential_name 의 크리덴셜 → provider_endpoint 호스트의 ACL 을 한 화면에",
  "Select AI 가 돌기 위한 세 조건을 먼저 보여준다. 상태 스트립이 ✓/✗ 로 요약하고, 카드마다 조회 SQL 을 펼쳐 볼 수 있다. ACL 이 없으면 ORA-24247, 키가 틀리면 ORA-20404.",
  "/nl2sql?sub=env", "env environment acl credential 크리덴셜 네트워크 권한 ORA-24247 ORA-20404 진단 환경"),
 ("nl2sql", "새 프로필 만들기 (OCI · OpenAI 호환 · Azure …)", "환경 탭 상태 줄의 버튼 — provider · 모델 · 크리덴셜 · object_list · 플래그를 폼으로 받아 DBMS_CLOUD_AI.CREATE_PROFILE PL/SQL 을 미리보고 실행. OCI Generative AI 는 region 필수(제공 리전만 선택지)",
  "운영 전환 때 Google 대신 OCI Generative AI 로 옮기거나, 다른 테이블 묶음의 프로필을 만들 때. 환경 탭이 OCI 프로필의 region·oci_apiformat·크리덴셜 유형(API Key/Resource Principal)도 읽는다. 2026-09-30 PoC 3-A.",
  "/nl2sql?sub=env", "profile create wizard oci generative ai region 프로필 생성 오사카 azure"),
 ("nl2sql", "실제 호출 테스트", "선택한 프로필로 chat 한 번을 보내 크리덴셜 · ACL · LLM 경로가 실제로 통하는지 확인",
  "세 카드가 전부 ✓ 여도 키가 만료됐으면 실패한다 — ENABLED='TRUE' 는 유효성이 아니다. 시연 전에 한 번 눌러 둔다. ?sub=env&run=1 로 바로 돌릴 수 있다.",
  "/nl2sql?sub=env&run=1", "test call 호출 테스트 검증 키 만료 ORA-20404"),
 ("nl2sql", "멀티턴 대화", "Multi Turn · 이어서 질문하기 · 정상답변시 대화초기화 · 새 대화 — DBMS_CLOUD_AI 대화(conversation_id)로 앞 질문을 이어받는다",
  "\"그중 1위 제품만 월별로\" 처럼 앞 답을 가리키는 질문을 할 때. 답변 아래 메타 줄에 conversation_id · elapsed · 모델 · log # 이 보인다. 2026-09-29 PoC 1-A.",
  "/nl2sql?sub=ask", "multi turn 멀티턴 대화 conversation 이어서 새 대화 conversation_id"),
 ("nl2sql", "유통 시연용 샘플 데이터셋 (RETAIL_DEMO_PROFILE)", "제과 유통 합성 데이터 4 테이블(POC_STORES·POC_PRODUCTS·POC_DISPLAYS·POC_SALES, 6만 행) + 한국어 Annotation + 프로필 + 예시 질문 10 — 진열위치 미입력 30% 로 데이터 품질 시연",
  "고객 업무와 닮은 데이터로 시연할 때. 프로필을 바꾸면 질문·Annotation·이력이 전부 따라온다. 적재·원복 sql/seed/retail_demo/. 2026-09-30 PoC 3-B.",
  "/nl2sql?sub=ask&profile=RETAIL_DEMO_PROFILE", "retail 유통 샘플 데이터셋 진열 매장 제품 매출 미입력 dataset"),
 ("nl2sql", "예시 질문 · 저장 프리셋", "DB 표 AI_PROMPT_PRESET 의 질문(제목 + 질문 + 실행 모드) — 화면에서 추가·수정·삭제, 프로필 이름 패턴(%SH%)으로 범위",
  "무엇을 물어야 할지 막힐 때, 시연에서 잘 먹힌 질문을 제목 붙여 저장해 둘 때. 2026-09-29 PoC 1-D — 옛 내장 예시 27건이 시드.",
  "/nl2sql?sub=ask", "sample 예시 질문 데모 preset 프리셋 저장 질문"),
 ("nl2sql", "참조 테이블 · Annotation", "프로필이 보는 테이블의 컬럼 정의와 Display Annotation 일괄 적용/제거",
  "LLM 이 컬럼 의미를 잘못 잡을 때 Annotation 을 붙여 정확도를 올린다. 23ai+ 기능.",
  "/nl2sql?sub=schema", "schema annotation 어노테이션 컬럼 코멘트"),
 ("nl2sql", "답변 피드백 👍/👎", "답변 아래 좋음/나쁨 + 사유 + (나쁨이면) 올바른 SQL → DBMS_CLOUD_AI.FEEDBACK 벡터 인덱스 + AI_FEEDBACK_LOG. 유사 질문의 프롬프트에 예시로 자동 주입",
  "LLM 이 틀린 SQL 을 만들었을 때 고쳐 가르칠 때, 잘 만든 SQL 을 정답 예시로 굳힐 때. 26ai 전용. 등록 후 showprompt 로 주입을 확인한다. 2026-09-30 PoC 1-B.",
  "/nl2sql?sub=ask", "feedback 피드백 좋음 나쁨 thumbs few-shot 예시 정확도 FEEDBACK_VECINDEX"),
 ("nl2sql", "정확도 개선 시나리오 ①②③", "같은 질문을 ① Annotation 없이 → ② Annotation 적용 → ③ 피드백 반영 으로 풀어 3열 비교 + ②/③ showprompt diff 로 피드백 예시가 주입된 자리를 하이라이트",
  "\"Annotation 과 피드백이 정확도를 어떻게 올리나\" 를 한 번에 보여줄 때. 프로필 속성 annotations/comments 를 SET_ATTRIBUTE 로 잠시 끄고 켜며 끝나면 복원(피드백은 기본 삭제). 1분 안팎. 2026-09-30 PoC 2-B·2-C.",
  "/nl2sql?sub=ask", "accuracy 정확도 시나리오 annotation 비교 showprompt diff 프롬프트 주입 few-shot"),
 ("nl2sql", "프로필(모델) 비교 실행", "같은 질문을 고른 프로필 2~3개로 순차 실행 — 프로필마다 모델 · 생성 SQL · 결과 앞 5행 · 생성/실행 소요를 한 열씩. 이력 탭 「프로필(모델)별 소요」 가 누적 평균",
  "\"모델을 바꾸면 SQL 이 어떻게 달라지나, 얼마나 빠른가\" 를 보여줄 때. 같은 테이블을 보는 프로필끼리 비교해야 뜻이 있다(다르면 경고). 2026-09-30 PoC 3-C.",
  "/nl2sql?sub=ask", "compare 비교 프로필 모델 elapsed 속도 벤치마크"),
 ("nl2sql", "Few-shot 일괄 등록", "시연자가 만든 (질문, 정답 SQL, 설명) CSV/JSON/XLSX 를 올려 미리보기 → EXPLAIN PLAN 검증 → positive 피드백으로 일괄 등록(진행률·실패만 재시도) + 등록된 피드백 목록·개별/전체 삭제",
  "인수인계 때 시연자가 검증한 정답 SQL 수십 건을 한 번에 가르칠 때. 행마다 SELECT AI 가 1회 돌아 수 초씩 걸린다. 2026-09-30 PoC 2-A.",
  "/nl2sql?sub=fewshot", "few-shot fewshot 일괄 등록 업로드 csv xlsx 피드백 목록 전체 삭제 정확도"),
 ("nl2sql", "질의 이력", "모든 Select AI 호출(질문·후속 버튼·SELECT AI 직접 실행)이 AI_QUERY_LOG 에 남는다 — 요약 카드 · 프로필(모델)별 소요 · 필터(질문·기간·프로필·액션·상태·피드백) · 행 클릭 상세",
  "\"아까 그 질문 SQL 이 뭐였지\", \"실패한 호출은 왜 실패했나\"(ORA 오류 전문이 남는다), \"모델별로 얼마나 걸리나\". 2026-09-29 PoC 1-C. ?sub=history&run=1 로 바로 조회.",
  "/nl2sql?sub=history&run=1", "history 이력 로그 log 질의 기록 elapsed 실패 원인 ai_query_log"),
 ("nl2sql", "SQL 직접 실행", "화면 하단 입력창에서 SELECT 문을 직접 실행",
  "AI 가 만든 SQL 을 손봐서 다시 돌려볼 때. SELECT 로 시작하는 문장만 허용(WITH 도 거부).",
  "/nl2sql?sub=ask", "execute sql select 직접 실행"),
 ("nl2sql", "실행계획", "생성된 SQL 의 EXPLAIN PLAN 조회",
  "AI 가 만든 SQL 이 인덱스를 타는지 확인할 때.",
  "/nl2sql?sub=ask", "explain plan 실행계획 dbms_xplan"),

 # ── ② AI Vector Search ────────────────────────────────────
 ("vector", "환경 — 이 DB 에 무엇이 준비돼 있나", "VECTOR 타입 테이블 · DB 안 ONNX 모델 · HNSW/Hybrid Vector Index 를 시연 시작 전에 한 화면에서",
  "시연의 시작점(기본 진입). 준비 상태 한눈에 → ① 벡터를 담는 테이블 → ② 텍스트를 벡터로 바꾸는 모델(「이 문장을 벡터로」 실제 호출) → ③ 인덱스 2종. 값마다 뜻이 붙어 있어 보는 사람이 그대로 이해한다. 바꾸는 것은 「내부」에서.",
  "/vector?sub=env", "env environment 환경 준비 상태 vector table onnx index"),
 ("vector", "내부 — 테이블·인덱스 조회", "DOCUMENTS/DOC_CHUNKS 테이블 생성·삭제·정의·데이터·인덱스 조회",
  "벡터 저장소가 실제로 어떤 테이블·인덱스로 되어 있는지 보여줄 때. DBA 가 반드시 묻는 것.",
  "/vector?sub=internals", "table 테이블 인덱스 정의 doc_chunks documents"),
 ("vector", "적재 — PDF 업로드 파이프라인", "PDF → 텍스트 추출(앱) → 청킹(UTL_TO_CHUNKS) → 임베딩(UPDATE … VECTOR_EMBEDDING) → 인덱싱(SYNC_INDEX), SSE 진행률",
  "새 문서를 넣을 때. 5단계가 실시간으로 보이고, 끝나면 단계 라벨을 눌러 실행된 SQL 과 결과 표본(청크 3개 · 벡터 앞 8차원 · 인덱스 조각 수)을 펼친다.",
  "/vector?sub=load", "upload pdf 업로드 청킹 임베딩 chunk"),
 ("vector", "비정형 문서 검색", "4가지 모드로 문서 검색 + RAG 답변 생성",
  "이 탭의 핵심. 같은 질문을 모드만 바꿔 물어보면 차이가 바로 드러난다.",
  "/vector?sub=search", "search rag 검색 질문 유사도"),
 ("vector", "검색 모드 — 벡터", "VECTOR_DISTANCE 코사인 유사도 (의미 검색)",
  "단어가 달라도 의미가 같으면 찾는다. 키워드 검색과 비교해 보여줄 때 기준선.",
  "/vector?sub=search", "vector 벡터 의미 semantic cosine"),
 ("vector", "검색 모드 — 키워드", "Oracle Text CONTAINS + SCORE (인덱스 없으면 LIKE 폴백)",
  "전통적 검색. 정확한 단어가 있어야 찾는다 — 벡터 검색의 대조군.",
  "/vector?sub=search", "keyword contains score oracle text 키워드"),
 ("vector", "검색 모드 — 수동 하이브리드", "단일 SQL 에서 CONTAINS + VECTOR_DISTANCE 를 직접 가중합",
  "hybrid = 0.7×벡터유사도 + 0.3×키워드점수 를 앱이 SQL 로 짠 것. 23ai 어디서나 되는 방식 — 26ai 의 Hybrid Vector Index 와 나란히 보여준다.",
  "/vector?sub=search&mode=hybrid", "hybrid 하이브리드 가중합 결합"),
 ("vector", "검색 모드 — Hybrid Vector Index (26ai)", "CREATE HYBRID VECTOR INDEX 하나 + DBMS_HYBRID_VECTOR.SEARCH 로 텍스트·벡터 융합",
  "26ai 의 대표 기능. 텍스트 컬럼 하나에 인덱스 하나를 만들면 DB 가 청킹·임베딩·인덱싱·융합을 다 한다. 융합 점수·벡터 점수·텍스트 점수가 청크마다 보인다.",
  "/vector?sub=search&mode=hvi", "hybrid vector index 하이브리드 인덱스 26ai DBMS_HYBRID_VECTOR fusion rsf"),
 ("vector", "Hybrid Vector Index 안 들여다보기", "내부 테이블 12개 · 자주 나온 단어 15 · 조각 표본 5 — 인덱스 하나가 실제로 무엇을 만들어 놓았나",
  "DBA 가 \"인덱스 안에 뭐가 있냐\"고 물을 때. 단어가 조사 붙은 채 저장되는 것($I)과 조각마다 벡터가 있는 것($VR)이 그대로 보인다.",
  "/vector?sub=internals", "hybrid index internals 내부 토큰 조각 $I $VR ivf"),
 ("vector", "Hybrid Vector Index 생성", "「환경」 탭에서 인덱스 상태 확인 · 생성(옛 Oracle Text 인덱스 대체)",
  "청크 수 × 0.2초. 업로드마다 CTX_DDL.SYNC_INDEX 로 새 청크가 반영된다. 실행되는 DDL 이 화면에 남는다.",
  "/vector?sub=env", "hybrid vector index create 생성 ctx_ddl sync"),
 ("vector", "실행계획 — 술어 하나가 인덱스를 죽인다", "같은 벡터 검색을 WHERE embedding IS NOT NULL 유무로 EXPLAIN 해 나란히",
  "2026-09-08 까지 앱의 검색 SQL 은 이 술어 때문에 HNSW 인덱스를 한 번도 안 탔다. 계획이 TABLE ACCESS FULL ↔ VECTOR INDEX HNSW SCAN 으로 갈리는 것을 보여준다.",
  "/vector?sub=internals", "explain plan 실행계획 hnsw approx 근사 술어"),
 ("vector", "검색 모드 — 비교", "키워드·벡터를 동시에 실행해 좌우로 나란히 표시",
  "차이를 한 화면에서 보여줄 때 가장 설득력 있다. RAG 답변은 생성하지 않아 빠르다(40~70ms).",
  "/vector?sub=search", "compare 비교 좌우"),
 ("vector", "임베딩 설정", "DB 내장(ONNX) ↔ 외부 API 런타임 전환, 모델 선택",
  "같은 질문을 다른 임베딩 모델로 돌려 결과 차이를 보여줄 때. ⚠ 차원이 다른 모델로 바꾸면 HNSW 인덱스 재생성이 필요하다.",
  "/vector?sub=internals", "embedding onnx 임베딩 모델 전환 e5"),
 ("vector", "ONNX 모델 관리", "DB 내 ONNX 모델 목록·상세·테스트 임베딩·업로드·OML Cloud 로드·삭제",
  "\"임베딩이 DB 안에서 돈다\"를 증명할 때. 테스트 임베딩이 차원과 소요시간을 보여준다.",
  "/vector?sub=internals", "onnx model 모델 적재 테스트 차원"),
 ("vector", "실행 쿼리 확인", "V$SQL 에서 방금 돈 벡터 쿼리 원문 조회",
  "화면 뒤에서 어떤 SQL 이 돌았는지 보여줄 때. 데모의 신뢰도를 크게 올린다.",
  "/vector?sub=internals", "v$sql recent query 실행 쿼리"),

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
    {"tab": row[0], "tab_label": TAB_LABELS.get(row[0], row[0]), "name": row[1], "desc": row[2],
     "how": row[3], "path": row[4], "keyword": row[5], "slides": list(row[6]) if len(row) > 6 else []}
    for row in _F
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
