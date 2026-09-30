-- 02_data.sql — 합성 데이터 (PoC 3-B, 2026-09-30). 재현 가능(DBMS_RANDOM.SEED). 실행 1분 안쪽.
-- 매장 120 · 제품 60 · 진열 3,000(매장당 25제품, 진열위치 미입력 30%·전시상태 미입력 10%) · 매출 60,000(2025-10-01 ~ 2026-09-30)
-- 매출은 진열 행에서 뽑아 만들므로 항상 진열과 조인되고, 수량이 면수·전시상태에 약하게 비례한다(시연 질문이 "그럴듯한" 답을 내도록).
-- ADB 는 INSERT … SELECT 를 병렬로 돌리는데 CONNECT BY + DBMS_RANDOM 조합이 ORA-12860(병렬 서버 간 데드락)을 냈다(2026-09-30 실측) → 세션 병렬 끔
ALTER SESSION DISABLE PARALLEL DML;
ALTER SESSION DISABLE PARALLEL QUERY;

BEGIN
  DBMS_RANDOM.SEED(26);

  -- 매장 120
  INSERT INTO poc_stores (store_name, region, channel, open_date, store_size_sqm)
  SELECT r.region || ' ' || c.channel || ' ' || TO_CHAR(n, 'FM000') || '호점',
         r.region, c.channel,
         DATE '2015-01-01' + TRUNC(DBMS_RANDOM.VALUE(0, 3800)),
         CASE c.channel WHEN '대형마트' THEN ROUND(DBMS_RANDOM.VALUE(3000, 9000)) WHEN '편의점' THEN ROUND(DBMS_RANDOM.VALUE(40, 120))
                        WHEN '슈퍼마켓' THEN ROUND(DBMS_RANDOM.VALUE(300, 1500)) ELSE NULL END
  FROM (SELECT LEVEL n FROM dual CONNECT BY LEVEL <= 120) x
  JOIN (SELECT '서울' region, 1 k FROM dual UNION ALL SELECT '경기', 2 FROM dual UNION ALL SELECT '인천', 3 FROM dual UNION ALL SELECT '부산', 4 FROM dual
        UNION ALL SELECT '대구', 5 FROM dual UNION ALL SELECT '광주', 6 FROM dual UNION ALL SELECT '대전', 7 FROM dual UNION ALL SELECT '강원', 8 FROM dual
        UNION ALL SELECT '충청', 9 FROM dual UNION ALL SELECT '전라', 10 FROM dual UNION ALL SELECT '경상', 11 FROM dual UNION ALL SELECT '제주', 12 FROM dual) r
    ON r.k = MOD(x.n, 12) + 1
  JOIN (SELECT '대형마트' channel, 1 k FROM dual UNION ALL SELECT '편의점', 2 FROM dual UNION ALL SELECT '슈퍼마켓', 3 FROM dual UNION ALL SELECT '온라인', 4 FROM dual) c
    ON c.k = MOD(TRUNC(x.n / 12), 4) + 1;

  -- 제품 60 (카테고리 5 × 12) — 실제 브랜드명은 쓰지 않는다
  INSERT INTO poc_products (product_name, category, unit_price, launch_date, is_new)
  SELECT cat.category || ' ' || nm.name || ' ' || TO_CHAR(x.n, 'FM00'),
         cat.category,
         ROUND(DBMS_RANDOM.VALUE(800, 4500), -2),
         DATE '2018-01-01' + TRUNC(DBMS_RANDOM.VALUE(0, 3200)),
         'N'
  FROM (SELECT LEVEL n FROM dual CONNECT BY LEVEL <= 60) x
  JOIN (SELECT '비스킷' category, 1 k FROM dual UNION ALL SELECT '스낵', 2 FROM dual UNION ALL SELECT '캔디', 3 FROM dual
        UNION ALL SELECT '젤리', 4 FROM dual UNION ALL SELECT '초콜릿', 5 FROM dual) cat ON cat.k = MOD(x.n, 5) + 1
  JOIN (SELECT '오리지널' name, 1 k FROM dual UNION ALL SELECT '딸기', 2 FROM dual UNION ALL SELECT '초코', 3 FROM dual UNION ALL SELECT '바닐라', 4 FROM dual
        UNION ALL SELECT '치즈', 5 FROM dual UNION ALL SELECT '녹차', 6 FROM dual) nm ON nm.k = MOD(TRUNC(x.n / 5), 6) + 1;
  UPDATE poc_products SET is_new = 'Y' WHERE launch_date >= ADD_MONTHS(DATE '2026-09-30', -12);

  -- 진열 3,000: 매장마다 제품 25개 (product_id 를 매장별로 다르게 고른다)
  -- identity 값은 1부터라고 가정하지 않는다(실패한 적재로 시퀀스가 올라가 있을 수 있다, 2026-09-30 ORA-02291) → 행 번호로 고른다
  INSERT INTO poc_displays (store_id, product_id, display_location, face_count, display_state, display_position, survey_date)
  SELECT s.store_id,
         pr.product_id,
         CASE WHEN DBMS_RANDOM.VALUE < 0.30 THEN '미입력'
              ELSE CASE TRUNC(DBMS_RANDOM.VALUE(0, 5)) WHEN 0 THEN '매장입구' WHEN 1 THEN '중앙통로' WHEN 2 THEN '계산대앞' WHEN 3 THEN '음료코너' ELSE '시식코너' END END,
         TRUNC(DBMS_RANDOM.VALUE(1, 7)),
         CASE WHEN DBMS_RANDOM.VALUE < 0.10 THEN '미입력' WHEN DBMS_RANDOM.VALUE < 0.55 THEN '단독' ELSE '혼합' END,
         CASE TRUNC(DBMS_RANDOM.VALUE(0, 5)) WHEN 0 THEN '전면중앙' WHEN 1 THEN '전면좌측' WHEN 2 THEN '전면우측' WHEN 3 THEN '상단' ELSE '하단' END,
         DATE '2026-09-01' + TRUNC(DBMS_RANDOM.VALUE(0, 28))
  FROM (SELECT store_id, ROW_NUMBER() OVER (ORDER BY store_id) sn FROM poc_stores) s
  CROSS JOIN (SELECT LEVEL n FROM dual CONNECT BY LEVEL <= 25) k
  JOIN (SELECT product_id, ROW_NUMBER() OVER (ORDER BY product_id) rn FROM poc_products) pr ON pr.rn = MOD(s.sn * 7 + k.n * 11, 60) + 1;

  -- 매출 60,000: 진열 행 하나를 무작위로 골라 그 매장·제품으로. 수량은 면수·전시상태·전시위치에 비례(+잡음), 프로모션 20%
  INSERT INTO poc_sales (sale_date, store_id, product_id, quantity, amount, promo_flag)
  SELECT d.sale_date, dp.store_id, dp.product_id, q.qty,
         q.qty * p.unit_price * CASE d.promo WHEN 'Y' THEN 0.8 ELSE 1 END,
         d.promo
  FROM (SELECT DATE '2025-10-01' + TRUNC(DBMS_RANDOM.VALUE(0, 365)) sale_date,
               TRUNC(DBMS_RANDOM.VALUE(1, 3001)) display_id,
               CASE WHEN DBMS_RANDOM.VALUE < 0.2 THEN 'Y' ELSE 'N' END promo,
               DBMS_RANDOM.VALUE r
        FROM dual CONNECT BY LEVEL <= 60000) d
  JOIN (SELECT dp0.*, ROW_NUMBER() OVER (ORDER BY display_id) rn FROM poc_displays dp0) dp ON dp.rn = d.display_id
  JOIN poc_products p ON p.product_id = dp.product_id
  CROSS JOIN LATERAL (SELECT GREATEST(1, ROUND(d.r * (4 + dp.face_count * 1.5
                                                 + CASE dp.display_state WHEN '단독' THEN 3 WHEN '혼합' THEN 1 ELSE 0 END
                                                 + CASE dp.display_position WHEN '전면중앙' THEN 3 WHEN '전면좌측' THEN 1 WHEN '전면우측' THEN 1 ELSE 0 END
                                                 + CASE d.promo WHEN 'Y' THEN 4 ELSE 0 END))) qty FROM dual) q;
  COMMIT;
END;
/
-- 확인
SELECT 'poc_stores' t, COUNT(*) FROM poc_stores UNION ALL SELECT 'poc_products', COUNT(*) FROM poc_products
UNION ALL SELECT 'poc_displays', COUNT(*) FROM poc_displays UNION ALL SELECT 'poc_sales', COUNT(*) FROM poc_sales;
SELECT display_location, ROUND(COUNT(*) / SUM(COUNT(*)) OVER () * 100, 1) pct FROM poc_displays GROUP BY display_location ORDER BY 2 DESC;
