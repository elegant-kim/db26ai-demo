-- 01_tables.sql — 유통 시연용 샘플 데이터셋: 테이블 4개 + 한국어 COMMENT (PoC 3-B, 2026-09-30)
-- 영문 이름 + 한국어 설명(COMMENT 는 여기, Display Annotation 은 03번). 이름은 POC_ 접두어 — ADMIN 에 SH 의 PRODUCTS·SALES 가 있어 겹친다. 실행 순서: 01 → 02 → 03 → 04 → 05. 원복 09.
-- 시연 목적: 제과 유통의 매장·제품·진열·매출로 "면수별 전시상태별 매출", "전시위치별 상위 10", "미입력 제외" 같은 질문을 Select AI 에.

CREATE TABLE poc_stores (
  store_id        NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  store_name      VARCHAR2(100 CHAR) NOT NULL,
  region          VARCHAR2(20 CHAR)  NOT NULL,
  channel         VARCHAR2(20 CHAR)  NOT NULL,
  open_date       DATE,
  store_size_sqm  NUMBER(8,1)
);
COMMENT ON TABLE  poc_stores IS '매장 마스터 - 제과 유통 매장';
COMMENT ON COLUMN poc_stores.store_id IS '매장 ID (PK)';
COMMENT ON COLUMN poc_stores.store_name IS '매장명';
COMMENT ON COLUMN poc_stores.region IS '지역 (서울·경기·인천·부산·대구·광주·대전·강원·충청·전라·경상·제주)';
COMMENT ON COLUMN poc_stores.channel IS '유통 채널 (대형마트·편의점·슈퍼마켓·온라인)';
COMMENT ON COLUMN poc_stores.open_date IS '개점일';
COMMENT ON COLUMN poc_stores.store_size_sqm IS '매장 면적(㎡)';

CREATE TABLE poc_products (
  product_id    NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_name  VARCHAR2(100 CHAR) NOT NULL,
  category      VARCHAR2(20 CHAR)  NOT NULL,
  unit_price    NUMBER(10)         NOT NULL,
  launch_date   DATE,
  is_new        CHAR(1) DEFAULT 'N' CHECK (is_new IN ('Y','N'))
);
COMMENT ON TABLE  poc_products IS '제품 마스터 - 제과 제품';
COMMENT ON COLUMN poc_products.product_id IS '제품 ID (PK)';
COMMENT ON COLUMN poc_products.product_name IS '제품명';
COMMENT ON COLUMN poc_products.category IS '카테고리 (비스킷·스낵·캔디·젤리·초콜릿)';
COMMENT ON COLUMN poc_products.unit_price IS '단위 판매가 (원)';
COMMENT ON COLUMN poc_products.launch_date IS '출시일';
COMMENT ON COLUMN poc_products.is_new IS '신제품 여부 Y/N';

CREATE TABLE poc_displays (
  display_id        NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  store_id          NUMBER NOT NULL REFERENCES poc_stores(store_id),
  product_id        NUMBER NOT NULL REFERENCES poc_products(product_id),
  display_location  VARCHAR2(20 CHAR) DEFAULT '미입력' NOT NULL,
  face_count        NUMBER(2) NOT NULL,
  display_state     VARCHAR2(10 CHAR) DEFAULT '미입력' NOT NULL,
  display_position  VARCHAR2(20 CHAR),
  survey_date       DATE
);
CREATE INDEX displays_ix1 ON poc_displays (store_id, product_id);
COMMENT ON TABLE  poc_displays IS '진열 현황 - 매장별 제품 진열 조사 (진열위치 미입력 약 30%)';
COMMENT ON COLUMN poc_displays.display_id IS '진열 조사 ID (PK)';
COMMENT ON COLUMN poc_displays.store_id IS '매장 ID (FK)';
COMMENT ON COLUMN poc_displays.product_id IS '제품 ID (FK)';
COMMENT ON COLUMN poc_displays.display_location IS '진열 위치(매대): 매장입구·중앙통로·계산대앞·음료코너·시식코너·미입력';
COMMENT ON COLUMN poc_displays.face_count IS '진열 면수 (1~6)';
COMMENT ON COLUMN poc_displays.display_state IS '전시 상태: 단독·혼합·미입력';
COMMENT ON COLUMN poc_displays.display_position IS '전시 위치(매대 안): 전면중앙·전면좌측·전면우측·상단·하단';
COMMENT ON COLUMN poc_displays.survey_date IS '조사일';

CREATE TABLE poc_sales (
  sale_id     NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sale_date   DATE   NOT NULL,
  store_id    NUMBER NOT NULL REFERENCES poc_stores(store_id),
  product_id  NUMBER NOT NULL REFERENCES poc_products(product_id),
  quantity    NUMBER(6)  NOT NULL,
  amount      NUMBER(12) NOT NULL,
  promo_flag  CHAR(1) DEFAULT 'N' CHECK (promo_flag IN ('Y','N'))
);
CREATE INDEX sales_ix1 ON poc_sales (sale_date);
CREATE INDEX sales_ix2 ON poc_sales (store_id, product_id);
COMMENT ON TABLE  poc_sales IS '매출 - 일자별 매장별 제품별 판매 실적';
COMMENT ON COLUMN poc_sales.sale_id IS '매출 ID (PK)';
COMMENT ON COLUMN poc_sales.sale_date IS '판매 일자';
COMMENT ON COLUMN poc_sales.store_id IS '매장 ID (FK)';
COMMENT ON COLUMN poc_sales.product_id IS '제품 ID (FK)';
COMMENT ON COLUMN poc_sales.quantity IS '판매 수량';
COMMENT ON COLUMN poc_sales.amount IS '매출 금액 (원)';
COMMENT ON COLUMN poc_sales.promo_flag IS '프로모션 여부 Y/N';
