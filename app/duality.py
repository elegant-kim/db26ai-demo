"""
JSON Relational Duality View 관리 모듈
- SH 스키마 기반 Duality View 생성/삭제/조회
- 관계형 vs JSON 비교 쿼리
- JSON 문서 CRUD
- ETag 동시성 제어 시뮬레이션
"""

import json
import logging
import time
from decimal import Decimal

from app.select_ai import _lob_to_str

logger = logging.getLogger(__name__)


def _json_serializer(obj):
    """JSON 직렬화 시 bytes, Decimal 등 특수 타입 처리"""
    if isinstance(obj, bytes):
        return obj.hex().upper()
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    return str(obj)


def _sanitize_duality_doc(doc):
    """Duality View에서 반환된 dict를 JSON 직렬화 가능하게 변환"""
    return json.loads(json.dumps(doc, default=_json_serializer))


# === Duality View DDL ===

# SH 스키마 기반 Duality View 정의 (GraphQL 구문)
DUALITY_VIEW_DDLS = {
    "CUSTOMERS_DV": """CREATE OR REPLACE JSON RELATIONAL DUALITY VIEW customers_dv AS
admin.customers @insert @update @delete
{
    _id        : cust_id
    firstName  : cust_first_name
    lastName   : cust_last_name
    gender     : cust_gender
    yearOfBirth: cust_year_of_birth
    city       : cust_city
    incomeLevel: cust_income_level
    creditLimit: cust_credit_limit
    email      : cust_email
}""",
    "PRODUCTS_DV": """CREATE OR REPLACE JSON RELATIONAL DUALITY VIEW products_dv AS
admin.products @insert @update @delete
{
    _id           : prod_id
    prodName      : prod_name
    prodDesc      : prod_desc
    prodCategory  : prod_category
    prodListPrice : prod_list_price
    prodMinPrice  : prod_min_price
}""",
}


async def create_duality_views(pool) -> dict:
    """Duality View들을 생성한다."""
    results = []
    sql_list = []

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            for view_name, ddl in DUALITY_VIEW_DDLS.items():
                try:
                    await cursor.execute(ddl)
                    results.append({"name": view_name, "status": "생성 완료"})
                    sql_list.append(ddl.strip())
                except Exception as e:
                    err_msg = str(e)
                    if "already exists" in err_msg.lower() or "ORA-00955" in err_msg:
                        results.append({"name": view_name, "status": "이미 존재"})
                    else:
                        results.append({"name": view_name, "status": f"오류: {err_msg}"})
                    sql_list.append(f"-- {view_name}: {err_msg[:100]}")

    return {
        "views": results,
        "sql_executed": "\n\n".join(sql_list),
        "message": f"Duality View {len(results)}개 처리 완료",
    }


async def drop_duality_views(pool) -> dict:
    """Duality View들을 삭제한다."""
    results = []
    sql_list = []

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            for view_name in DUALITY_VIEW_DDLS.keys():
                try:
                    await cursor.execute(f"DROP VIEW {view_name}")
                    results.append({"name": view_name, "status": "삭제 완료"})
                    sql_list.append(f"DROP VIEW {view_name}")
                except Exception as e:
                    err_msg = str(e)
                    if "does not exist" in err_msg.lower() or "ORA-00942" in err_msg:
                        results.append({"name": view_name, "status": "존재하지 않음"})
                    else:
                        results.append({"name": view_name, "status": f"오류: {err_msg}"})
                    sql_list.append(f"-- {view_name}: {err_msg[:100]}")

    return {
        "views": results,
        "sql_executed": "\n".join(sql_list),
        "message": f"Duality View {len(results)}개 처리 완료",
    }


async def list_duality_views(pool) -> dict:
    """현재 존재하는 Duality View 목록을 조회한다."""
    sql = """SELECT view_name, json_duality
FROM user_views
WHERE json_duality = 'YES'
ORDER BY view_name"""

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql)
                rows = await cursor.fetchall()
                views = [{"name": row[0], "status": "활성"} for row in rows]
    except Exception:
        # json_duality 컬럼이 없는 경우 폴백
        views = []
        for view_name in DUALITY_VIEW_DDLS.keys():
            try:
                async with pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(f"SELECT 1 FROM {view_name} WHERE ROWNUM = 1")
                        views.append({"name": view_name, "status": "활성"})
            except Exception:
                pass

    return {
        "views": views,
        "sql_executed": sql,
    }


# === 관계형 vs JSON 비교 ===

async def compare_relational_vs_json(pool, view_name: str, limit: int = 5) -> dict:
    """관계형 SQL JOIN과 Duality View JSON을 나란히 비교한다."""

    # 두 쪽이 "같은 행"을 보여줘야 비교가 된다 (개발노하우 §4). 그래서 양쪽 다 _id(PK) 오름차순 + FETCH FIRST.
    # 2026-09-05 이전: 양쪽에 SAMPLE(5) — 관계형 쪽은 별칭 뒤에 SAMPLE 을 둬 ORA-03049 로 5개월간 깨져 있었고,
    # JSON 쪽은 매번 다른 무작위 행이라 애초에 비교가 불가능했다 (레거시 UI 가 오류를 삼켰다).
    limit = max(1, min(int(limit), 50))
    if "CUSTOMER" in view_name.upper():
        relational_sql = f"""SELECT c.cust_id, c.cust_first_name, c.cust_last_name,
       c.cust_city, c.cust_income_level, c.cust_credit_limit
FROM admin.customers c
ORDER BY c.cust_id
FETCH FIRST {limit} ROWS ONLY"""
    elif "PRODUCT" in view_name.upper():
        relational_sql = f"""SELECT p.prod_id, p.prod_name, p.prod_category,
       p.prod_list_price, p.prod_min_price
FROM admin.products p
ORDER BY p.prod_id
FETCH FIRST {limit} ROWS ONLY"""
    else:
        relational_sql = f"SELECT * FROM {view_name} ORDER BY 1 FETCH FIRST {limit} ROWS ONLY"

    json_sql = f"""SELECT data FROM {view_name}
ORDER BY JSON_VALUE(data, '$._id' RETURNING NUMBER)
FETCH FIRST {limit} ROWS ONLY"""

    result = {}

    # 관계형 쿼리 실행
    try:
        start = time.time()
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(relational_sql)
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
        result["relational_sql"] = relational_sql
        result["relational_columns"] = columns
        result["relational_data"] = data
        result["relational_elapsed"] = int((time.time() - start) * 1000)
    except Exception as e:
        result["relational_sql"] = relational_sql
        result["relational_error"] = str(e)

    # JSON Duality 쿼리 실행
    try:
        start = time.time()
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(json_sql)
                rows = await cursor.fetchall()
                json_docs = []
                for row in rows:
                    val = row[0]
                    if isinstance(val, dict):
                        # Decimal → str 변환 후 재파싱
                        json_docs.append(_sanitize_duality_doc(val))
                    elif hasattr(val, 'read'):
                        val = await _lob_to_str(val)
                        try:
                            json_docs.append(json.loads(val))
                        except (json.JSONDecodeError, TypeError):
                            json_docs.append(val)
                    else:
                        try:
                            json_docs.append(json.loads(val))
                        except (json.JSONDecodeError, TypeError):
                            json_docs.append(val)
        result["json_sql"] = json_sql
        result["json_data"] = json_docs
        result["json_elapsed"] = int((time.time() - start) * 1000)
    except Exception as e:
        result["json_sql"] = json_sql
        result["json_error"] = str(e)

    return result


# === JSON 문서 CRUD ===

async def list_duality_docs(pool, view_name: str, limit: int = 10) -> dict:
    """Duality View의 문서 목록 (ID + 요약)을 조회한다."""
    if "CUSTOMER" in view_name.upper():
        sql = f"""SELECT JSON_VALUE(data, '$._id') AS doc_id,
       JSON_VALUE(data, '$.firstName') || ' ' || JSON_VALUE(data, '$.lastName') AS summary
FROM {view_name}
ORDER BY JSON_VALUE(data, '$._id' RETURNING NUMBER)
FETCH FIRST {limit} ROWS ONLY"""
    elif "PRODUCT" in view_name.upper():
        sql = f"""SELECT JSON_VALUE(data, '$._id') AS doc_id,
       JSON_VALUE(data, '$.prodName') AS summary
FROM {view_name}
ORDER BY JSON_VALUE(data, '$._id' RETURNING NUMBER)
FETCH FIRST {limit} ROWS ONLY"""
    else:
        sql = f"""SELECT JSON_VALUE(data, '$._id') AS doc_id, '' AS summary
FROM {view_name}
ORDER BY JSON_VALUE(data, '$._id' RETURNING NUMBER)
FETCH FIRST {limit} ROWS ONLY"""

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(sql)
            rows = await cursor.fetchall()
            docs = [{"id": str(row[0]), "summary": row[1] or ""} for row in rows]
    return {"docs": docs, "sql_executed": sql}


async def fetch_duality_doc(pool, view_name: str, doc_id: str) -> dict:
    """Duality View에서 특정 문서를 조회한다."""
    # _id 필드로 필터 (GraphQL DDL에서 _id : PK로 정의)
    if doc_id:
        pk_filter = f"JSON_VALUE(data, '$._id') = '{doc_id.replace(chr(39), '')}'"
    else:
        pk_filter = "ROWNUM = 1"

    sql = f"""SELECT data FROM {view_name} WHERE {pk_filter}"""

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(sql)
            row = await cursor.fetchone()
            if row is None:
                return {"error": f"ID '{doc_id}'에 해당하는 문서를 찾을 수 없습니다."}

            doc_json = row[0]
            # oracledb가 JSON 타입을 dict로 직접 반환
            if isinstance(doc_json, dict):
                # Decimal → int/float 변환 (JSON 직렬화를 위해)
                doc_json = _sanitize_duality_doc(doc_json)
            elif hasattr(doc_json, 'read'):
                doc_text = await _lob_to_str(doc_json)
                doc_json = json.loads(doc_text)

            doc_text = json.dumps(doc_json, indent=2, ensure_ascii=False)
            etag = None
            if isinstance(doc_json, dict):
                etag = doc_json.get("_metadata", {}).get("etag", None)

            return {
                "document": doc_json,
                "document_text": doc_text,
                "etag": etag,
                "sql_executed": sql,
            }


async def update_duality_doc(pool, view_name: str, doc_json: dict) -> dict:
    """Duality View를 통해 JSON 문서를 업데이트한다."""
    doc_str = json.dumps(doc_json)

    sql = f"""UPDATE {view_name}
SET data = :doc_data
WHERE JSON_VALUE(data, '$._metadata.etag') = :etag
RETURNING JSON_VALUE(data, '$._metadata.etag') INTO :new_etag"""

    etag = doc_json.get("_metadata", {}).get("etag", "")

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                new_etag_var = cursor.var(str)
                await cursor.execute(sql, {
                    "doc_data": doc_str,
                    "etag": etag,
                    "new_etag": new_etag_var,
                })
                await conn.commit()
                rows_affected = cursor.rowcount
                new_etag = new_etag_var.getvalue()

                if rows_affected == 0:
                    return {
                        "success": False,
                        "error": "ETag 불일치 — 다른 사용자가 먼저 수정했습니다. 문서를 다시 조회해주세요.",
                    }

                return {
                    "success": True,
                    "message": "문서가 업데이트되었습니다.",
                    "new_etag": new_etag[0] if new_etag else None,
                    "sql_executed": f"UPDATE {view_name} SET data = :doc WHERE etag = :etag",
                }
    except Exception as e:
        return {"success": False, "error": str(e)}


# === ETag 시뮬레이션 ===

def _extract_etag(doc):
    """dict에서 ETag를 hex 문자열로 추출"""
    if not isinstance(doc, dict):
        return "N/A"
    etag_raw = doc.get("_metadata", {}).get("etag", None)
    if isinstance(etag_raw, bytes):
        return etag_raw.hex().upper()
    elif etag_raw:
        return str(etag_raw)
    return "N/A"


async def simulate_etag_conflict(pool, view_name: str = None) -> dict:
    """ETag 충돌을 실제 DB 작업으로 시뮬레이션한다.
    1. User A 문서 조회 (ETag 획득)
    2. User B 같은 문서 조회 (동일 ETag)
    3. User A UPDATE 성공 → 새 ETag 발급
    4. User B 기존 ETag로 UPDATE 시도 → 실패
    5. 원본 데이터로 원복
    """
    if not view_name:
        view_name = "CUSTOMERS_DV"

    steps = []

    try:
        # Step 1: User A가 문서 조회
        sql_select = f"SELECT data FROM {view_name} FETCH FIRST 1 ROWS ONLY"
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql_select)
                row = await cursor.fetchone()
                if row is None:
                    return {"error": f"{view_name}에 데이터가 없습니다.", "steps": []}
                original_doc = row[0]

        etag_a = _extract_etag(original_doc)
        original_sanitized = _sanitize_duality_doc(original_doc)
        doc_id = original_sanitized.get("_id", "?")

        steps.append({
            "description": f"User A가 문서(ID={doc_id}) 조회 — ETag 획득",
            "etag": etag_a[:16] + "...",
            "sql": sql_select,
            "success": True,
        })

        # Step 2: User B도 같은 문서 조회 (동일 ETag)
        steps.append({
            "description": f"User B도 같은 문서(ID={doc_id}) 조회 — 동일한 ETag 획득",
            "etag": etag_a[:16] + "...",
            "sql": sql_select,
            "success": True,
        })

        # Step 3: User A 가 먼저 수정 — 문서에 실린 _metadata.etag(E1) 가 현재와 같으므로 DB 가 통과시키고 새 ETag 를 발급
        old_credit = original_sanitized.get("creditLimit", 0) or 0
        modified_doc = dict(original_sanitized)
        modified_doc["creditLimit"] = old_credit + 1
        sql_update = f"UPDATE {view_name} SET data = :doc WHERE JSON_VALUE(data, '$._id') = :doc_id"

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql_update, {"doc": json.dumps(modified_doc, ensure_ascii=False), "doc_id": str(doc_id)})
                await conn.commit()
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SELECT data FROM {view_name} WHERE JSON_VALUE(data, '$._id') = :doc_id", {"doc_id": str(doc_id)})
                row = await cursor.fetchone()
                new_etag = _extract_etag(row[0]) if row else "N/A"

        steps.append({
            "description": f"User A 가 creditLimit 을 {old_credit}→{old_credit + 1} 로 수정 — 성공. 문서에 실린 ETag 가 현재와 같아 DB 가 통과시키고 새 ETag 를 발급했다",
            "etag": new_etag[:16] + "...",
            "sql": f"UPDATE {view_name} SET data = :doc_with_old_etag WHERE JSON_VALUE(data, '$._id') = '{doc_id}'",
            "success": True,
        })

        # Step 4: User B 가 옛 ETag(E1) 를 그대로 실은 문서로 수정 시도 → DB 가 ORA-42699 로 거부한다.
        # 2026-09-05 이전에는 WHERE 절로 흉내 냈고 진짜 검사는 원복 단계에서 터져 시뮬레이션이 4단계에서 끊겼다.
        modified_doc_b = dict(original_sanitized)   # _metadata.etag = E1 (구버전)
        modified_doc_b["creditLimit"] = old_credit + 999
        b_error = None
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute(sql_update, {"doc": json.dumps(modified_doc_b, ensure_ascii=False), "doc_id": str(doc_id)})
                    b_rows = cursor.rowcount
                    await conn.rollback()   # 여기 오면 검사가 안 된 것 — 되돌리고 그대로 보고한다
                except Exception as e:      # noqa: BLE001 — ORA-42699 가 기대값
                    b_error = str(e)
                    b_rows = 0
                    await conn.rollback()
        if b_error and "ORA-42699" in b_error:
            desc = "User B 가 같은 문서를 옛 ETag 그대로 수정 시도 — DB 가 거부했다 (ORA-42699: ETag 불일치). Lost Update 방지"
        elif b_error:
            desc = f"User B 의 수정이 실패했다 — {b_error.splitlines()[0][:120]}"
        else:
            desc = f"⚠ User B 의 수정이 통과됐다({b_rows}행) — ETag 검사가 동작하지 않았다. 롤백함"
        steps.append({
            "description": desc,
            "etag": etag_a[:16] + "... (구버전)",
            "sql": f"UPDATE {view_name} SET data = :doc_with_old_etag WHERE JSON_VALUE(data, '$._id') = '{doc_id}'\n-- → {(b_error or '').splitlines()[0] if b_error else '(거부되지 않음)'}",
            "success": False,
        })

        # Step 5: 원복 — _metadata 를 뺀 문서로 UPDATE 하면 ETag 검사를 건너뛴다 (원복은 "마지막 쓰기"가 맞다)
        restore_doc = {k: v for k, v in original_sanitized.items() if k != "_metadata"}
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql_update, {"doc": json.dumps(restore_doc, ensure_ascii=False), "doc_id": str(doc_id)})
                await conn.commit()

        steps.append({
            "description": f"시뮬레이션 완료 — 원본(creditLimit={old_credit})으로 원복. _metadata 없이 UPDATE 하면 ETag 검사를 생략한다",
            "etag": None,
            "sql": f"UPDATE {view_name} SET data = :doc_without_metadata WHERE JSON_VALUE(data, '$._id') = '{doc_id}' -- 원복",
            "success": True,
        })

    except Exception as e:
        logger.warning("ETag 시뮬레이션 실패: %s", e)
        # 에러가 나도 원복은 시도한다 — _metadata 를 빼야 ETag 검사에 안 걸린다
        try:
            if "original_sanitized" in locals() and "doc_id" in locals():
                restore_doc = {k: v for k, v in original_sanitized.items() if k != "_metadata"}
                async with pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            f"UPDATE {view_name} SET data = :doc WHERE JSON_VALUE(data, '$._id') = :doc_id",
                            {"doc": json.dumps(restore_doc, ensure_ascii=False), "doc_id": str(doc_id)},
                        )
                        await conn.commit()
                steps.append({"description": "에러 발생 — 원본 데이터로 원복 완료", "etag": None, "success": True})
        except Exception as e2:
            logger.warning("ETag 시뮬레이션 원복 실패 (데이터가 수정된 채 남았을 수 있다): %s", e2)
        return {"error": str(e), "steps": steps}

    return {"steps": steps}


# === 최근 쿼리 조회 ===

async def query_duality_recent_sql(pool) -> dict:
    """V$SQL에서 Duality View 관련 최근 쿼리를 조회한다."""
    sql = """SELECT sql_id, SUBSTR(sql_text, 1, 200) AS sql_text,
       executions, elapsed_time/1000 AS elapsed_ms,
       TO_CHAR(last_active_time, 'HH24:MI:SS') AS last_active
FROM v$sql
WHERE (UPPER(sql_text) LIKE '%CUSTOMERS\\_DV%' ESCAPE '\\'
    OR UPPER(sql_text) LIKE '%PRODUCTS\\_DV%' ESCAPE '\\'
    OR UPPER(sql_text) LIKE '%DUALITY%')
  AND sql_text NOT LIKE '%v$sql%'
ORDER BY last_active_time DESC NULLS LAST
FETCH FIRST 10 ROWS ONLY"""

    try:
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

        return {
            "columns": columns,
            "data": data,
            "row_count": len(data),
            "sql_executed": sql,
        }
    except Exception as e:
        return {"error": str(e), "sql_executed": sql}
