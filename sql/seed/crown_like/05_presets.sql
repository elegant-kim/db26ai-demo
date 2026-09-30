-- 05_presets.sql — 예시 질문 프리셋 (PoC 3-B, 2026-09-30). profile_name '%CROWN%' → CROWN_LIKE_PROFILE 에서만 보인다. 멱등.
DECLARE
  n NUMBER;
BEGIN
  SELECT COUNT(*) INTO n FROM ai_prompt_preset WHERE profile_name = '%CROWN%';
  IF n > 0 THEN DBMS_OUTPUT.PUT_LINE('CROWN 프리셋 ' || n || '건 있음 — 생략'); RETURN; END IF;
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%CROWN%', '면수별 전시상태별 매출', '면수별 전시상태별 매출 금액은?', 'runsql', 10);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%CROWN%', '전시위치별 매출 상위 10', '전시위치별 매출 상위 10개를 보여줘', 'runsql', 20);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%CROWN%', '진열위치별 매출 (미입력 제외)', '진열위치별 매출 금액을 보여줘. 진열위치가 미입력인 것은 제외해줘', 'runsql', 30);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%CROWN%', '미입력 비율', '진열 현황에서 진열위치가 미입력인 행의 비율은?', 'runsql', 40);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%CROWN%', '채널별 월별 매출', '유통 채널별 월별 매출 추이를 보여줘', 'runsql', 50);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%CROWN%', '카테고리별 프로모션 효과', '카테고리별로 프로모션 판매와 정가 판매의 평균 수량을 비교해줘', 'runsql', 60);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%CROWN%', '단독 진열 상위 매장', '단독 진열 면수가 가장 많은 매장 상위 5개는?', 'runsql', 70);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%CROWN%', '지역별 신제품 매출', '지역별 신제품 매출 금액과 비중을 알려줘', 'runsql', 80);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%CROWN%', '면수와 매출의 관계', '진열 면수가 많을수록 매출이 높은가? 면수별 평균 매출로 보여줘', 'runsql', 90);
  INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order) VALUES ('%CROWN%', '전시상태별 매출 (미입력 제외)', '전시상태가 미입력이 아닌 진열의 전시상태별 매출 합계는?', 'runsql', 100);
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('CROWN 프리셋 10건');
END;
/
