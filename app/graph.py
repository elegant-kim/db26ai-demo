"""
SQL Property Graph 관리 모듈 (SQL/PGQ)
- SH 스키마 기반 Property Graph 생성/삭제
- SQL vs SQL/PGQ 비교 쿼리
- 패턴 매칭 쿼리
- 최근 쿼리 조회
"""

import time

from app.select_ai import _lob_to_str

# === Property Graph DDL ===

GRAPH_DDL = """CREATE PROPERTY GRAPH sales_graph
VERTEX TABLES (
    admin.customers KEY (cust_id)
        PROPERTIES (cust_id, cust_first_name, cust_last_name, cust_city, cust_income_level, cust_credit_limit),
    admin.products KEY (prod_id)
        PROPERTIES (prod_id, prod_name, prod_category, prod_list_price)
)
EDGE TABLES (
    admin.sales KEY (prod_id, cust_id, time_id, channel_id, promo_id)
        SOURCE KEY (cust_id) REFERENCES customers (cust_id)
        DESTINATION KEY (prod_id) REFERENCES products (prod_id)
        PROPERTIES (amount_sold, quantity_sold, time_id)
)"""


async def create_property_graph(pool) -> dict:
    """SH 스키마 기반 Property Graph를 생성한다."""
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(GRAPH_DDL)
        return {"message": "Property Graph 'SALES_GRAPH' 생성 완료", "sql_executed": GRAPH_DDL}
    except Exception as e:
        err = str(e)
        if "ORA-00955" in err or "already" in err.lower():
            return {"message": "Property Graph 'SALES_GRAPH'가 이미 존재합니다.", "sql_executed": GRAPH_DDL}
        return {"error": err, "sql_executed": GRAPH_DDL}


async def drop_property_graph(pool) -> dict:
    """Property Graph를 삭제한다."""
    sql = "DROP PROPERTY GRAPH sales_graph"
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql)
        return {"message": "Property Graph 'SALES_GRAPH' 삭제 완료", "sql_executed": sql}
    except Exception as e:
        err = str(e)
        if "ORA-00942" in err or "does not exist" in err.lower():
            return {"message": "Property Graph 'SALES_GRAPH'가 존재하지 않습니다.", "sql_executed": sql}
        return {"error": err, "sql_executed": sql}


# === SQL vs SQL/PGQ 비교 ===

COMPARE_QUERIES = [
    {
        "label": "고객 524가 구매한 제품 목록",
        "sql": """SELECT p.prod_name, p.prod_category, s.amount_sold
FROM admin.sales s
JOIN admin.products p ON s.prod_id = p.prod_id
WHERE s.cust_id = 524
ORDER BY s.amount_sold DESC
FETCH FIRST 10 ROWS ONLY""",
        "pgq": """SELECT product_name, category, amount
FROM GRAPH_TABLE (sales_graph
    MATCH (c IS customers) -[s IS sales]-> (p IS products)
    WHERE c.cust_id = 524
    COLUMNS (p.prod_name AS product_name,
             p.prod_category AS category,
             s.amount_sold AS amount)
)
ORDER BY amount DESC
FETCH FIRST 10 ROWS ONLY""",
    },
    {
        "label": "제품별 구매 고객 수 및 총 매출 Top-10",
        "sql": """SELECT p.prod_name, p.prod_category,
       COUNT(DISTINCT s.cust_id) AS customer_count,
       SUM(s.amount_sold) AS total_amount
FROM admin.sales s
JOIN admin.products p ON s.prod_id = p.prod_id
GROUP BY p.prod_name, p.prod_category
ORDER BY total_amount DESC
FETCH FIRST 10 ROWS ONLY""",
        # SQL/PGQ 에서는 GRAPH_TABLE() 의 COLUMNS 절 안에 집계함수를 쓸 수 없다
        # (ORA-49011: A group function inside GRAPH_TABLE() must have a group reference).
        # 정석은 그래프에서 원시 행을 투영하고 집계는 바깥 쿼리에서 하는 것이다.
        "pgq": """SELECT product_name, category,
       COUNT(DISTINCT cust_id) AS customer_count,
       SUM(amount) AS total_amount
FROM GRAPH_TABLE (sales_graph
    MATCH (c IS customers) -[s IS sales]-> (p IS products)
    COLUMNS (p.prod_name AS product_name,
             p.prod_category AS category,
             c.cust_id AS cust_id,
             s.amount_sold AS amount)
)
GROUP BY product_name, category
ORDER BY total_amount DESC
FETCH FIRST 10 ROWS ONLY""",
    },
    {
        "label": "고객 524와 같은 제품을 산 고객 (추천 시스템 기초)",
        # 2026-09-04 실측으로 두 가지를 고쳤다.
        #  ① ORDER BY 부재: SQL 과 PGQ 가 거대한 결과에서 서로 다른 10행을 집어와
        #     "같은 결과"라는 이 탭의 주장이 화면에서 깨졌다. → 고객 ID 로 결정적 정렬
        #     (이름은 중복이라 정렬키로 부족).
        #  ② 전체 고객 쌍(제품 13 구매자 2,492명 → 약 310만 쌍) 정렬은 PGQ 14초.
        #     씨앗 고객 하나에서 출발하도록 바꿔 165ms 로 단축(85배). 2-hop 패턴
        #     (고객→제품←고객)이라는 추천 원리는 그대로이고 오히려 더 분명해진다.
        #     씨앗을 524 로 둔 것은 위 첫 번째 쿼리와 맞추기 위함.
        "sql": """SELECT DISTINCT c2.cust_id AS cust_id2,
       c2.cust_first_name AS customer2,
       p.prod_name AS shared_product
FROM admin.sales s1
JOIN admin.sales s2 ON s1.prod_id = s2.prod_id
     AND s2.cust_id <> s1.cust_id
JOIN admin.customers c2 ON s2.cust_id = c2.cust_id
JOIN admin.products p ON s1.prod_id = p.prod_id
WHERE s1.cust_id = 524
ORDER BY cust_id2, shared_product
FETCH FIRST 10 ROWS ONLY""",
        "pgq": """SELECT DISTINCT cust_id2, customer2, shared_product
FROM GRAPH_TABLE (sales_graph
    MATCH (c1 IS customers) -[s1 IS sales]-> (p IS products)
          <-[s2 IS sales]- (c2 IS customers)
    WHERE c1.cust_id = 524 AND c2.cust_id <> 524
    COLUMNS (c2.cust_id AS cust_id2,
             c2.cust_first_name AS customer2,
             p.prod_name AS shared_product)
)
ORDER BY cust_id2, shared_product
FETCH FIRST 10 ROWS ONLY""",
    },
]


async def _run_query(pool, sql):
    """쿼리 실행 후 컬럼/데이터/시간을 반환한다."""
    start = time.time()
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(sql)
            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    if hasattr(val, 'read'):
                        val = await _lob_to_str(val)
                    row_dict[col] = val
                data.append(row_dict)
    elapsed = int((time.time() - start) * 1000)
    return columns, data, elapsed


async def compare_sql_vs_pgq(pool, query_index: int = 0) -> dict:
    """SQL JOIN과 SQL/PGQ를 나란히 실행 비교한다."""
    if query_index < 0 or query_index >= len(COMPARE_QUERIES):
        query_index = 0
    q = COMPARE_QUERIES[query_index]
    result = {"label": q["label"]}

    # SQL 실행
    try:
        cols, data, elapsed = await _run_query(pool, q["sql"])
        result["sql_query"] = q["sql"]
        result["sql_columns"] = cols
        result["sql_data"] = data
        result["sql_elapsed"] = elapsed
    except Exception as e:
        result["sql_query"] = q["sql"]
        result["sql_error"] = str(e)

    # PGQ 실행
    try:
        cols, data, elapsed = await _run_query(pool, q["pgq"])
        result["pgq_query"] = q["pgq"]
        result["pgq_columns"] = cols
        result["pgq_data"] = data
        result["pgq_elapsed"] = elapsed
    except Exception as e:
        result["pgq_query"] = q["pgq"]
        result["pgq_error"] = str(e)

    return result


# === 패턴 매칭 쿼리 ===

PATTERN_QUERIES = [
    {
        "label": "고객 → 제품 구매 관계 (MATCH 패턴)",
        "sql": """SELECT customer, product, category, amount
FROM GRAPH_TABLE (sales_graph
    MATCH (c IS customers) -[s IS sales]-> (p IS products)
    WHERE c.cust_id = 524
    COLUMNS (c.cust_first_name AS customer,
             p.prod_name AS product,
             p.prod_category AS category,
             s.amount_sold AS amount)
)
ORDER BY amount DESC
FETCH FIRST 20 ROWS ONLY""",
    },
    {
        "label": "고가 제품(>1000) 구매 고객과 도시",
        "sql": """SELECT customer, city, product, amount
FROM GRAPH_TABLE (sales_graph
    MATCH (c IS customers) -[s IS sales]-> (p IS products)
    WHERE s.amount_sold > 1000
    COLUMNS (c.cust_first_name AS customer,
             c.cust_city AS city,
             p.prod_name AS product,
             s.amount_sold AS amount)
)
ORDER BY amount DESC
FETCH FIRST 20 ROWS ONLY""",
    },
    {
        "label": "제품 13을 매개로 연결된 고객 쌍",
        "sql": """SELECT customer1, customer2, shared_product
FROM GRAPH_TABLE (sales_graph
    MATCH (c1 IS customers) -[s1 IS sales]-> (p IS products)
          <-[s2 IS sales]- (c2 IS customers)
    WHERE p.prod_id = 13 AND c1.cust_id < c2.cust_id
    COLUMNS (c1.cust_first_name AS customer1,
             c2.cust_first_name AS customer2,
             p.prod_name AS shared_product)
)
FETCH FIRST 20 ROWS ONLY""",
    },
]


async def run_pattern_query(pool, query_index: int = 0) -> dict:
    """패턴 매칭 쿼리를 실행한다."""
    if query_index < 0 or query_index >= len(PATTERN_QUERIES):
        query_index = 0
    q = PATTERN_QUERIES[query_index]

    try:
        cols, data, elapsed = await _run_query(pool, q["sql"])
        return {
            "sql_executed": q["sql"],
            "columns": cols,
            "data": data,
            "elapsed_ms": elapsed,
        }
    except Exception as e:
        return {"sql_executed": q["sql"], "error": str(e)}


# === 최근 쿼리 조회 ===

async def query_graph_recent_sql(pool) -> dict:
    """V$SQL에서 그래프 관련 최근 쿼리를 조회한다."""
    sql = """SELECT sql_id, SUBSTR(sql_text, 1, 200) AS sql_text,
       executions, elapsed_time/1000 AS elapsed_ms,
       TO_CHAR(last_active_time, 'HH24:MI:SS') AS last_active
FROM v$sql
WHERE (UPPER(sql_text) LIKE '%GRAPH\\_TABLE%' ESCAPE '\\'
    OR UPPER(sql_text) LIKE '%SALES\\_GRAPH%' ESCAPE '\\'
    OR UPPER(sql_text) LIKE '%PROPERTY GRAPH%')
  AND sql_text NOT LIKE '%v$sql%'
ORDER BY last_active_time DESC NULLS LAST
FETCH FIRST 10 ROWS ONLY"""

    try:
        cols, data, _ = await _run_query(pool, sql)
        return {"columns": cols, "data": data, "row_count": len(data), "sql_executed": sql}
    except Exception as e:
        return {"error": str(e), "sql_executed": sql}


def get_compare_queries():
    """프론트엔드에 비교 쿼리 목록 제공"""
    return [{"label": q["label"], "index": i} for i, q in enumerate(COMPARE_QUERIES)]


def get_pattern_queries():
    """프론트엔드에 패턴 쿼리 목록 제공"""
    return [{"label": q["label"], "index": i} for i, q in enumerate(PATTERN_QUERIES)]
