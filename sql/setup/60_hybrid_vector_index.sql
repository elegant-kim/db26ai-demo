-- ============================================================================
-- Hybrid Vector Index (Oracle 26ai) — doc_chunks(chunk_text)
-- 2026-09-08 신설. 50_oracle_text_index.sql 의 CONTEXT 인덱스를 **대체**한다.
--
-- 무엇인가: 텍스트 컬럼 하나에 인덱스 하나를 만들면 DB 가 청킹 → 임베딩(ONNX 모델) →
--   텍스트 인덱스($I) → 벡터 인덱스($VR, IVF) 를 스스로 만들고, DBMS_HYBRID_VECTOR.SEARCH 가
--   텍스트·벡터 점수를 융합(rsf 등)해 돌려준다. 앱의 embedding 컬럼·HNSW 인덱스와는 별개다.
--
-- 왜 대체인가: 같은 컬럼에 도메인 인덱스는 하나 — CONTEXT 가 있으면 ORA-29880.
--   하이브리드 인덱스는 CONTEXT_V2 라 CONTAINS/SCORE 도 그대로 서빙한다(실측). 키워드 모드는 손대지 않는다.
--
-- 실측(이 ADB 23.26, 180청크): CREATE ~50초(청크당 ~200ms, 모델로 재임베딩) · SEARCH 0.6초 · SYNC_INDEX 0.3초.
-- 토큰은 공백 단위(기존과 동일) — 텍스트 조건은 앱의 to_contains_query() ACCUM/우측절단을 그대로 쓴다.
-- 새 청크 반영: 앱 업로드 5단계에서 CTX_DDL.SYNC_INDEX 를 부른다(수동 SYNC). SYNC (ON COMMIT) 도 받지만
--   커밋이 느려지는 것을 단계로 드러내는 편이 시연에 낫다.
--
-- 앱은 Vector Store 탭의 「Hybrid Vector Index 생성」 버튼(POST /api/vector/hybrid-index/create)이
-- 아래와 같은 절차를 밟는다. 빈 테이블이면 기동 시 자동 생성된다.
-- ============================================================================

-- 0. 옛 CONTEXT 인덱스가 있으면 먼저 지운다 (같은 컬럼에 하나만)
-- DROP INDEX doc_chunks_text_idx;

-- 1. 렉서 프리퍼런스 (한글·영문 혼재 — 기존 인덱스와 동일). 이미 있으면 ORA-20000 → 무시
BEGIN
    BEGIN CTX_DDL.CREATE_PREFERENCE('HVI_WORLD_LEXER', 'WORLD_LEXER');
    EXCEPTION WHEN OTHERS THEN IF SQLCODE <> -20000 THEN RAISE; END IF; END;
END;
/

-- 2. 인덱스 — MODEL 은 DB 에 적재된 ONNX 모델명 (앱은 EMBEDDING_MODEL 설정값)
CREATE HYBRID VECTOR INDEX doc_chunks_hvi ON doc_chunks(chunk_text)
PARAMETERS ('MODEL MULTILINGUAL_E5_BASE LEXER HVI_WORLD_LEXER');

-- 3. 확인
SELECT index_name, index_type, ityp_name, status FROM user_indexes WHERE table_name = 'DOC_CHUNKS';
SELECT COUNT(*) AS indexed_chunks FROM DR$DOC_CHUNKS_HVI$VR;          -- 인덱스 안에서 임베딩된 청크
SELECT COUNT(*) FROM doc_chunks WHERE CONTAINS(chunk_text, '보험%', 1) > 0;  -- CONTAINS 도 이 인덱스로

-- 4. 융합 검색 — JSON 한 덩어리. return.values 에 rowid 를 받아 원본 행과 조인한다
SELECT DBMS_HYBRID_VECTOR.SEARCH(JSON('{
  "hybrid_index_name": "doc_chunks_hvi",
  "search_scorer": "rsf", "search_fusion": "UNION",
  "vector": {"search_text": "자동차 사고 시 보험금 청구 절차", "search_mode": "DOCUMENT", "aggregator": "MAX", "score_weight": 1},
  "text":   {"contains": "보험%, 청구%", "score_weight": 1},
  "return": {"values": ["rowid", "score", "vector_score", "text_score"], "topN": 5}
}')) FROM dual;

-- 5. 새 청크 반영 (업로드 후)
-- BEGIN CTX_DDL.SYNC_INDEX('DOC_CHUNKS_HVI'); END;
-- /
