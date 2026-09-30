/**
 * Display Annotation 세트 — 레거시 app.js 의 annotationSets 를 그대로 옮겼다(2026-09-05, 5-5).
 * 키 = 테이블, `_table` = 테이블 설명, 나머지 = 컬럼 설명. 적용 시 `_owner` 가 주입된다.
 * 프로필 이름에 'SH' 가 들어가면 SH 세트를 쓴다 (CLAUDE.md Important Conventions).
 */
export type AnnotationSet = Record<string, Record<string, string>>

export const ANNOTATION_SETS: Record<string, AnnotationSet> = {
    SH: {
        CUSTOMERS: {
            _table: '고객 마스터 테이블 - 인구통계 및 신용정보 포함',
            CUST_ID: '고객 고유 식별자 (PK)',
            CUST_FIRST_NAME: '고객 이름 (First Name)',
            CUST_LAST_NAME: '고객 성 (Last Name)',
            CUST_GENDER: '성별: M=Male, F=Female',
            CUST_YEAR_OF_BIRTH: '출생연도 (4자리)',
            CUST_MARITAL_STATUS: '결혼상태: married, single 등',
            CUST_STREET_ADDRESS: '거주지 주소',
            CUST_POSTAL_CODE: '우편번호',
            CUST_CITY: '거주 도시',
            CUST_STATE_PROVINCE: '거주 주/도',
            CUST_MAIN_PHONE_NUMBER: '주요 전화번호',
            CUST_INCOME_LEVEL: '소득구간: A: Under 30,000 ~ L: 300,000 and above',
            CUST_CREDIT_LIMIT: '신용한도 (USD)',
            CUST_EMAIL: '이메일 주소',
            CUST_VALID: '고객 유효 상태: A=Active, I=Inactive',
        },
        SALES: {
            _table: '판매 트랜잭션 팩트 테이블',
            PROD_ID: '제품 ID (FK: PRODUCTS.PROD_ID)',
            CUST_ID: '고객 ID (FK: CUSTOMERS.CUST_ID)',
            TIME_ID: '판매 일자 (FK: TIMES.TIME_ID)',
            CHANNEL_ID: '판매 채널 ID (FK: CHANNELS.CHANNEL_ID)',
            PROMO_ID: '프로모션 ID (FK: PROMOTIONS.PROMO_ID)',
            QUANTITY_SOLD: '판매 수량',
            AMOUNT_SOLD: '판매 금액 (USD)',
        },
        PRODUCTS: {
            _table: '제품 마스터 테이블',
            PROD_ID: '제품 고유 식별자 (PK)',
            PROD_NAME: '제품명',
            PROD_DESC: '제품 설명',
            PROD_SUBCATEGORY: '제품 소분류',
            PROD_CATEGORY: '제품 대분류',
            PROD_STATUS: '제품 상태: Status 값으로 활성여부 판단',
            PROD_LIST_PRICE: '정가 (USD)',
            PROD_MIN_PRICE: '최저가 (USD)',
        },
        CHANNELS: {
            _table: '판매 채널 (Direct Sales, Internet, Catalog, Partners)',
            CHANNEL_ID: '채널 고유 식별자 (PK)',
            CHANNEL_DESC: '채널명: Direct Sales, Internet, Catalog, Partners',
            CHANNEL_CLASS: '채널 분류: Direct, Indirect, Others',
        },
        TIMES: {
            _table: '시간 차원 테이블 (1998~2001년)',
            TIME_ID: '날짜 (PK)',
            DAY_NAME: '요일명 (Monday~Sunday)',
            CALENDAR_MONTH_DESC: '월 (예: 2000-01)',
            CALENDAR_QUARTER_DESC: '분기 (예: 2000-Q1)',
            CALENDAR_YEAR: '연도 (예: 2000)',
            FISCAL_YEAR: '회계연도',
        },
        PROMOTIONS: {
            _table: '프로모션 정보',
            PROMO_ID: '프로모션 ID (PK)',
            PROMO_NAME: '프로모션명',
            PROMO_SUBCATEGORY: '프로모션 소분류',
            PROMO_CATEGORY: '프로모션 대분류',
        },
        COUNTRIES: {
            _table: '국가 정보 (고객 국가 참조)',
            COUNTRY_ID: '국가 ID (PK)',
            COUNTRY_NAME: '국가명',
            COUNTRY_REGION: '대륙/지역 (Americas, Europe, Asia 등)',
            COUNTRY_SUBREGION: '세부지역',
        },
        COSTS: {
            _table: '제품 원가 테이블',
            PROD_ID: '제품 ID (FK)',
            TIME_ID: '날짜 (FK)',
            UNIT_COST: '단위 원가 (USD)',
            UNIT_PRICE: '단위 판매가 (USD)',
        },
    },
    // 유통 시연용 샘플(PoC 3-B, 2026-09-30) — sql/seed/retail_demo/. 03_annotations.sql 은 여기서 생성한다.
    // 테이블 이름은 POC_ 접두어 — ADMIN 에 SH 의 PRODUCTS·SALES 가 이미 있어 이름이 겹친다(첫 적재 때 SH 설명을 덮어쓴 사고, 09-30)
    RETAIL: {
        POC_STORES: {
            _table: '매장 마스터 - 제과 유통 매장(대형마트·편의점·슈퍼·온라인)',
            STORE_ID: '매장 고유 식별자 (PK)',
            STORE_NAME: '매장명',
            REGION: '지역: 서울, 경기, 인천, 부산, 대구, 광주, 대전, 강원, 충청, 전라, 경상, 제주',
            CHANNEL: '유통 채널: 대형마트, 편의점, 슈퍼마켓, 온라인',
            OPEN_DATE: '개점일',
            STORE_SIZE_SQM: '매장 면적 (제곱미터)',
        },
        POC_PRODUCTS: {
            _table: '제품 마스터 - 제과 제품(비스킷·스낵·캔디·젤리·초콜릿)',
            PRODUCT_ID: '제품 고유 식별자 (PK)',
            PRODUCT_NAME: '제품명',
            CATEGORY: '제품 카테고리: 비스킷, 스낵, 캔디, 젤리, 초콜릿',
            UNIT_PRICE: '단위 판매가 (원, KRW)',
            LAUNCH_DATE: '출시일',
            IS_NEW: '신제품 여부: Y=출시 1년 이내, N=기존 제품',
        },
        POC_DISPLAYS: {
            _table: '진열 현황 - 매장별 제품의 진열 위치·면수·전시 상태 조사 결과. DISPLAY_LOCATION 이 미입력인 행이 약 30% 있다 (데이터 품질 이슈)',
            DISPLAY_ID: '진열 조사 고유 식별자 (PK)',
            STORE_ID: '매장 ID (FK → POC_STORES)',
            PRODUCT_ID: '제품 ID (FK → POC_PRODUCTS)',
            DISPLAY_LOCATION: '진열 위치(매대): 매장입구, 중앙통로, 계산대앞, 음료코너, 시식코너, 미입력. 미입력은 조사 누락이며 집계에서 제외해야 할 수 있다',
            FACE_COUNT: '진열 면수 - 매대에서 제품이 정면으로 보이는 칸 수 (1~6)',
            DISPLAY_STATE: '전시 상태: 단독(단독 진열), 혼합(타사 제품과 혼합 진열), 미입력',
            DISPLAY_POSITION: '전시 위치(매대 안 위치): 전면중앙, 전면좌측, 전면우측, 상단, 하단',
            SURVEY_DATE: '진열 조사일',
        },
        POC_SALES: {
            _table: '매출 - 일자별 매장별 제품별 판매 실적 (2025-10 ~ 2026-09, 약 6만 행)',
            SALE_ID: '매출 고유 식별자 (PK)',
            SALE_DATE: '판매 일자',
            STORE_ID: '매장 ID (FK → POC_STORES)',
            PRODUCT_ID: '제품 ID (FK → POC_PRODUCTS)',
            QUANTITY: '판매 수량 (개)',
            AMOUNT: '매출 금액 (원, KRW) = 수량 × 단가 × (1 - 할인율)',
            PROMO_FLAG: '프로모션 적용 여부: Y=행사가 판매, N=정가 판매',
        },
    },
};
export function annotationSetFor(profile: string): { owner: string; tables: AnnotationSet } | null {
  const p = (profile || '').toUpperCase()
  if (p.includes('RETAIL')) return { owner: 'ADMIN', tables: ANNOTATION_SETS.RETAIL }
  if (p.includes('SH')) return { owner: 'ADMIN', tables: ANNOTATION_SETS.SH }
  return null
}
