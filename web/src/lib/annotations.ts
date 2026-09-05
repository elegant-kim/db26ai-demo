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
};
export function annotationSetFor(profile: string): { owner: string; tables: AnnotationSet } | null {
  const p = (profile || '').toUpperCase()
  if (p.includes('SH')) return { owner: 'ADMIN', tables: ANNOTATION_SETS.SH }
  return null
}
