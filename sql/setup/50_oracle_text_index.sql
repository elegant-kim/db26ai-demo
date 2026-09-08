-- ============================================================================
-- Oracle Text 전문검색 인덱스 — doc_chunks(chunk_text)
-- 2026-09-04 신설 (계획서 D10)
--
-- ⚠ 2026-09-08: 60_hybrid_vector_index.sql 의 Hybrid Vector Index 로 **대체됨**. 같은 컬럼에 도메인
--   인덱스는 하나라(ORA-29880) 둘 다 둘 수 없다. 하이브리드 인덱스가 CONTAINS 도 서빙한다.
--   이 파일은 하이브리드 인덱스를 쓰지 않는 환경(23ai 구버전 등)을 위해 남긴다.
--
-- 배경: 이 인덱스가 없으면 keyword_search 가 CONTAINS 대신 LIKE '%…%' 로 폴백해
--       CLOB 전체 스캔이 된다(실측 9.9초, 구(句) 질의는 0건). 이 앱의 핵심 데모
--       서사가 "키워드 검색 vs 의미 검색 비교"인데 비교 자체가 공정하지 않았다.
--
-- 렉서: WORLD_LEXER — 문서 내 언어를 자동 분절한다. 데모 문서가 한글 본문에
--       영문 기술용어(SQL·index 등)가 섞인 형태라 BASIC_LEXER(공백 분리)로는
--       "인덱스를" 이 "인덱스" 로 매칭되지 않는다.
--
-- 동기화: SYNC (ON COMMIT) — 새 PDF 를 올리면 커밋 시점에 즉시 검색 가능.
--         데모 특성상 적재 빈도가 낮아 커밋 오버헤드는 무시할 수준이다.
--
-- 재생성이 필요하면 아래 DROP 후 CREATE 를 다시 실행한다.
-- ============================================================================

-- DROP INDEX doc_chunks_text_idx;

CREATE INDEX doc_chunks_text_idx ON doc_chunks(chunk_text)
INDEXTYPE IS CTXSYS.CONTEXT
PARAMETERS ('LEXER CTXSYS.WORLD_LEXER SYNC (ON COMMIT)');

-- 확인
-- SELECT idx_name, idx_status FROM ctx_user_indexes;
-- SELECT COUNT(*) FROM doc_chunks WHERE CONTAINS(chunk_text, '인덱스', 1) > 0;
