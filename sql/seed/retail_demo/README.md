# 유통 시연용 샘플 데이터셋 (PoC 3-B, 2026-09-30)

제과 유통의 **매장(POC_STORES) · 제품(POC_PRODUCTS) · 진열현황(POC_DISPLAYS) · 매출(POC_SALES)** 4개 테이블과 Select AI 프로필 `RETAIL_DEMO_PROFILE`.
영문 이름 + 한국어 COMMENT/Annotation. 실제 고객 데이터·브랜드명은 없다(합성).

| 순서 | 파일 | 내용 |
|---|---|---|
| 01 | `01_tables.sql` | 테이블 4 + 인덱스 + COMMENT |
| 02 | `02_data.sql` | 합성 데이터 — 매장 120 · 제품 60 · 진열 3,000(진열위치 **미입력 30%**) · 매출 60,000(1년). `DBMS_RANDOM.SEED(26)` 로 재현 |
| 03 | `03_annotations.sql` | Display Annotation(DROP 후 ADD). **정본은 `web/src/lib/annotations.ts` 의 RETAIL 세트** — 앱 「스키마·Annotation」 탭과 같은 내용 |
| 04 | `04_profile.sql` | `RETAIL_DEMO_PROFILE` (GEMINI_CRED 재사용, 4 테이블, annotations/comments/conversation, embedding_model) |
| 05 | `05_presets.sql` | 예시 질문 10건(`%RETAIL%` 패턴 — 이 프로필에서만 보인다). "미입력 제외" 변형 포함 |
| 09 | `09_teardown.sql` | 전부 원복 |

실행: SQLcl/SQL Developer 에서 ADMIN 으로 01 → 05 순서, 또는 앱 저장소 루트에서
`./venv/bin/python scripts/seed_retail_demo.py` (같은 파일을 순서대로 돌리고 건수를 찍는다).

앱에서: 페이지 우상단 프로필을 `RETAIL_DEMO_PROFILE` 로 바꾸면 질문 탭 프리셋·스키마 탭 Annotation 세트·이력 필터가 이 프로필 기준으로 바뀐다.
데이터 품질 시연: "진열위치별 매출" 을 그냥 물으면 `미입력` 이 한 행으로 섞여 나오고, "미입력 제외" 를 붙이면 빠진다.
