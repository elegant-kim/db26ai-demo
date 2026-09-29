-- 72_poc_prompt_preset_seed.sql — 예시 질문 프리셋 시드 (2026-09-29, PoC 1-D). 표가 비어 있을 때만 넣는다(멱등).
-- 정본이 코드(web/src/lib/nl2sql.ts EXAMPLE_QUESTIONS)에서 이 표로 옮겨왔다. 화면에서 추가·수정·삭제한다.
-- profile_name: NULL = 모든 프로필, '%SH%' 같은 LIKE 패턴 = 이름이 맞는 프로필만

DECLARE
  n NUMBER;
BEGIN
  SELECT COUNT(*) INTO n FROM ai_prompt_preset;
  IF n > 0 THEN
    DBMS_OUTPUT.PUT_LINE('ai_prompt_preset 에 이미 ' || n || '건 — 시드 생략');
    RETURN;
  END IF;
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '매출 상위 5개 제품을 알려주세요', '매출 상위 5개 제품을 알려주세요', 'runsql', 10);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '월별 매출 추이를 알려주세요', '월별 매출 추이를 알려주세요', 'runsql', 20);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '국가별 고객 수를 알려주세요', '국가별 고객 수를 알려주세요', 'runsql', 30);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '연도별 총 매출액을 알려주세요', '연도별 총 매출액을 알려주세요', 'runsql', 40);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '채널별 주문 건수를 알려주세요', '채널별 주문 건수를 알려주세요', 'runsql', 50);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '2000년 인터넷 채널에서 가장 많이 판매된 제품 카테고리 상위 3개…', '2000년 인터넷 채널에서 가장 많이 판매된 제품 카테고리 상위 3개와 매출액을 알려줘', 'runsql', 60);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '미국 고객 중 연간 구매금액이 가장 높은 상위 10명의 이름과 총 구…', '미국 고객 중 연간 구매금액이 가장 높은 상위 10명의 이름과 총 구매금액은?', 'runsql', 70);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '프로모션 유형별 평균 할인율과 그에 따른 매출 변화를 분석해줘', '프로모션 유형별 평균 할인율과 그에 따른 매출 변화를 분석해줘', 'runsql', 80);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '분기별 매출 성장률을 전년 동기 대비로 보여줘', '분기별 매출 성장률을 전년 동기 대비로 보여줘', 'runsql', 90);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '고객 연령대별 선호 제품 카테고리와 평균 구매단가를 알려줘', '고객 연령대별 선호 제품 카테고리와 평균 구매단가를 알려줘', 'runsql', 100);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '유효한 고객 수를 알려줘', '유효한 고객 수를 알려줘', 'runsql', 110);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '유효하지 않은 고객 중 신용한도가 가장 높은 5명은?', '유효하지 않은 고객 중 신용한도가 가장 높은 5명은?', 'runsql', 120);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '소득구간별 고객 수와 평균 신용한도를 보여줘', '소득구간별 고객 수와 평균 신용한도를 보여줘', 'runsql', 130);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SH%', '인터넷 채널과 직접판매 채널의 매출 비교', '인터넷 채널과 직접판매 채널의 매출 비교', 'runsql', 140);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SSB%', '총 매출액이 가장 높은 공급업체 5곳을 알려줘', '총 매출액이 가장 높은 공급업체 5곳을 알려줘', 'runsql', 150);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SSB%', '연도별 총 주문금액 추이를 보여줘', '연도별 총 주문금액 추이를 보여줘', 'runsql', 160);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SSB%', '지역별 고객 수와 평균 주문금액을 알려줘', '지역별 고객 수와 평균 주문금액을 알려줘', 'runsql', 170);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SSB%', '제품 브랜드별 판매수량 순위를 알려줘', '제품 브랜드별 판매수량 순위를 알려줘', 'runsql', 180);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SSB%', '월별 주문건수와 평균 할인율을 보여줘', '월별 주문건수와 평균 할인율을 보여줘', 'runsql', 190);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SSB%', '1997년에 아시아 지역 고객이 주문한 제품 중 매출 상위 5개 브랜…', '1997년에 아시아 지역 고객이 주문한 제품 중 매출 상위 5개 브랜드는?', 'runsql', 200);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SSB%', '공급업체 국가별 평균 공급비용과 총 매출을 비교해줘', '공급업체 국가별 평균 공급비용과 총 매출을 비교해줘', 'runsql', 210);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SSB%', '할인율 20% 이상 적용된 주문의 연도별 매출 비중을 분석해줘', '할인율 20% 이상 적용된 주문의 연도별 매출 비중을 분석해줘', 'runsql', 220);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SSB%', '제품 카테고리별 수익성(매출-공급비용)이 가장 높은 상위 5개 제품은?', '제품 카테고리별 수익성(매출-공급비용)이 가장 높은 상위 5개 제품은?', 'runsql', 230);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%SSB%', '분기별 주문량 추이와 전분기 대비 증감률을 보여줘', '분기별 주문량 추이와 전분기 대비 증감률을 보여줘', 'runsql', 240);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES (NULL, '테이블 목록을 보여줘', '테이블 목록을 보여줘', 'runsql', 250);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES (NULL, '전체 레코드 수를 알려줘', '전체 레코드 수를 알려줘', 'runsql', 260);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES (NULL, '최근 데이터 10건을 보여줘', '최근 데이터 10건을 보여줘', 'runsql', 270);
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('ai_prompt_preset 시드 27건');
END;
/
