--=============================================================
-- 시연
-- AI Profile 목록 및 Attribute 목록 조회
select profile_name, owner, status 
  from DBA_CLOUD_AI_PROFILES;

select profile_name, owner, attribute_name, attribute_value 
  from DBA_CLOUD_AI_PROFILE_ATTRIBUTES
where profile_name like '%PROFILE%';

select profile_name, owner, status 
  from DBA_CLOUD_AI_PROFILES
;

-- select * from dictionary where table_name like '%ANN%';

-- grant alter any table to admin;
-- grant alter any table on schema sh to admin;
-- ALTER TABLE MHMC.TB_MH_PC_CM_MKT ADD (test varchar2(10));

-- -- 어노테이션 적용여부 확인
-- SELECT object_name, column_name, annotation_name, annotation_value 
-- FROM all_annotations_usage 
-- ORDER BY object_name, column_name NULLS FIRST
-- ;

-- 세션에 AI Profile 설정
exec dbms_cloud_ai.set_profile('GROQ_PROFILE');

-- 3. 데모 시연 : 자연어 프롬프트 실행
-- 3-0 Warm up
SET SERVEROUTPUT ON;

DECLARE
    v_result CLOB;
BEGIN
    v_result := DBMS_CLOUD_AI.GENERATE(
        prompt       => '안녕하세요',
        profile_name => 'GROQ_PROFILE',
        action       => 'chat'
    );
    DBMS_OUTPUT.PUT_LINE(v_result);
END;
/

DECLARE
    v_result CLOB;
BEGIN
    v_result := DBMS_CLOUD_AI.GENERATE(
        prompt       => 'show me top 5 countries by total sales amount',
        profile_name => 'GROQ_PROFILE',
        action       => 'runsql'
    );
    DBMS_OUTPUT.PUT_LINE(v_result);
END;
/


select AI CHAT 안녕하세요;
select AI CHAT What is Oracle Database''s market share(한국어로 대답해줘);

-- 3-1 SH 스키마 설명
select owner, table_name, status 
  from all_tables 
  where owner='SH';

-- 3-2 select AI 테스트 (SH 스키마 이용)
-- select AI 사용 옵션(RUNSQL, SHOWSQL, NARRATE) 테스트
select AI how many customers;
select AI RUNSQL how many products;
select AI SHOWSQL how many customers;
select AI NARRATE how many products;

-- select AI 사용 옵션(RUNSQL, SHOWSQL, NARRATE) 테스트 - 한글테스트
select AI 얼마나 많은 고객이 있나요;
select AI RUNSQL 얼마나 많은 상품이 있나요;
select AI SHOWSQL 얼마나 많은 상품이 있나요;
select AI SHOWSQL 상품이 얼마나 많이 있나요;
select AI NARRATE 얼마나 많은 국가가 있나요;

SELECT COUNT(*) AS "상품_수"
FROM "SH"."PRODUCTS" "P"
;
SELECT COUNT(*) AS "Total_Products"
FROM "SH"."PRODUCTS" "p";

-- 3-3 SH 스키마를 이용한 판매 정보 추출
select AI SHOWSQL 2000년도의 총 판매량은 얼마인가요;
select AI 2000년도의 총 판매량은 얼마인가요;

select AI SHOWSQL 2000년 동안 판매된 각 제품의 총 판매 수량을 알고 싶어요;
select AI 2000년 동안 판매된 각 제품의 총 판매 수량을 알고 싶어요;

select AI Mouse Pad의 월별 판매량은 얼마인가요;
select AI SHOWSQL Mouse Pad의 월별 판매량은 얼마인가요;

select AI SHOWSQL 2001년도의 분기별 판매량을 알려주세요;
select AI 2001년도의 분기별 판매량을 알려주세요;

select AI SHOWSQL 가장 많이 팔린 상위 5개 제품의 이름과 판매량은 무엇인가요;
select AI 가장 많이 팔린 상위 5개 제품의 이름과 판매량은 무엇인가요;

select AI 상품 카테고리별 판매량은 얼마인가요;
select AI SHOWSQL 상품 카테고리별 판매량은 얼마인가요;

select AI 가장 많이 판매된 제품의 이름과 총 판매 수량을 알고 싶어요;
select AI SHOWSQL 가장 많이 판매된 제품의 이름과 총 판매 수량을 알고 싶어요;

select AI 각 판매 채널별 총 판매 금액이 얼마인지 알고 싶어요;
select AI SHOWSQL 각 판매 채널별 총 판매 금액이 얼마인지 알고 싶어요;

select AI  각 도시별로 평균 판매 금액이 얼마인지 알고 싶어요;
select AI SHOWSQL 각 도시별로 평균 판매 금액이 얼마인지 알고 싶어요;

select AI 직업별로 평균 판매 금액이 얼마인지 알고 싶어요;
select AI SHOWSQL 직업별로 평균 판매 금액이 얼마인지 알고 싶어요;

select AI 총 구매 금액이 100000을 초과한 고객의 이름과 구매 금액을 알고 싶어요;
select AI SHOWSQL 총 구매 금액이 100000을 초과한 고객의 이름과 구매 금액을 알고 싶어요;

select AI Nason Mann 이 구매한 상품들의 총액은 얼마인가요;
select AI SHOWSQL Nason Mann 이 구매한 상품들의 총액은 얼마인가요;

-- 3-4 SH 스키마를 이용한 분석 정보 추출 (분석함수 사용 쿼리)
select AI NARRATE 각 상품별 총 매출과 매출 순위는 무엇인가요;
select AI 각 상품별 총 매출과 매출 순위는 무엇인가요;

select AI SHOWSQL 각 상품별 누적 매출과 전체 매출 대비 해당 상품의 누적 매출 비율은 무엇인가요;
select AI 각 상품별 누적 매출과 전체 매출 대비 해당 상품의 누적 매출 비율은 무엇인가요;

select AI SHOWSQL 누적 매출 기여도가 80% 이하인 상품은 무엇인가요;
select AI 누적 매출 기여도가 80% 이하인 상품은 무엇인가요;

-- 아래 질의는 오래걸리는 쿼리임
-- select AI 상품 카테고리별 총 매출과 평균 판매 가격은 얼마인가요;
-- select AI SHOWSQL 상품 카테고리별 총 매출과 평균 판매 가격은 얼마인가요;

-- 3-5 SH 스키마를 이용한 기타 여러 정보 추출
select AI 각 프로모션의 이름과 해당 프로모션이 사용된 횟수를 알고 싶어요;
select AI 아시아에 있는 모든 국가의 이름을 알 수 있을까요;
select AI 각 나라에 고객이 몇 명 있는지 알고 싶어요;
select AI 결혼 상태별로 고객 수가 어떻게 되는지 알고 싶어요;

-- 4. 함수 사용 예
SELECT DBMS_CLOUD_AI.GENERATE(prompt => 'Mouse Pad의 월별 판매량은 얼마인가요',
                              profile_name => 'openai_gpt4o',
                              action => 'showsql')
FROM dual;

-- 5. 기타 참고
select a.table_name, a.column_name, a.data_type, b.comments 
from dba_tab_cols a, dba_col_comments b 
where a.owner = 'SH' 
and a.table_name = 'SALES' 
and a.owner = b.owner 
and a.table_name = b.table_name 
and a.column_name = b.column_name 
order by a.COLUMN_ID
;

create user mhmc identified by Welcome12345 default tablespace users temporary tablespace temp;

grant create session to mhmc;
grant execute on DBMS_CLOUD_AI to mhmc;