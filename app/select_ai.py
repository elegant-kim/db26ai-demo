import json
import oracledb


async def _lob_to_str(value):
    """LOB 객체이면 문자열로 읽어서 반환하고, 아니면 그대로 반환한다."""
    if isinstance(value, oracledb.AsyncLOB):
        return await value.read()
    return value


async def ask_select_ai(pool, prompt: str, action: str, profile_name: str) -> str:
    """Select AI에 자연어 질문을 전달하고 결과를 반환한다."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            sql = """
                SELECT DBMS_CLOUD_AI.GENERATE(
                    prompt       => :prompt,
                    profile_name => :profile,
                    action       => :action
                ) FROM dual
            """
            await cursor.execute(sql, {
                "prompt": prompt,
                "profile": profile_name,
                "action": action,
            })
            row = await cursor.fetchone()
            if row is None:
                return None
            return await _lob_to_str(row[0])


async def submit_feedback(pool, prompt: str, feedback: str, profile_name: str) -> bool:
    """Select AI에 피드백을 제출한다."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            sql = """
                BEGIN
                    DBMS_CLOUD_AI.FEEDBACK(
                        profile_name => :profile,
                        prompt       => :prompt,
                        feedback     => :feedback
                    );
                END;
            """
            await cursor.execute(sql, {
                "profile": profile_name,
                "prompt": prompt,
                "feedback": feedback,
            })
            return True


async def list_profiles(pool) -> list:
    """사용 가능한 AI 프로필 목록을 DBA_CLOUD_AI_PROFILES에서 조회한다."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            try:
                sql = """
                    SELECT profile_name
                    FROM DBA_CLOUD_AI_PROFILES
                    ORDER BY profile_name
                """
                await cursor.execute(sql)
                rows = await cursor.fetchall()
                return [
                    {"profile_name": row[0]}
                    for row in rows
                ]
            except Exception:
                # DBA 뷰 권한이 없으면 user 뷰로 폴백
                sql = """
                    SELECT profile_name, status
                    FROM user_cloud_ai_profiles
                    ORDER BY profile_name
                """
                await cursor.execute(sql)
                rows = await cursor.fetchall()
                return [
                    {"profile_name": row[0], "status": row[1]}
                    for row in rows
                ]


async def set_profile(pool, profile_name: str) -> dict:
    """DBMS_CLOUD_AI.SET_PROFILE을 실행하여 세션 프로필을 설정한다."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            try:
                await cursor.execute("""
                    BEGIN
                        DBMS_CLOUD_AI.SET_PROFILE(:profile_name);
                    END;
                """, {"profile_name": profile_name})
                return {"success": True, "profile_name": profile_name}
            except Exception as e:
                return {"success": False, "error": str(e)}


async def get_profile_attributes(pool, profile_name: str) -> dict:
    """프로필의 상세 속성을 DBA_CLOUD_AI_PROFILE_ATTRIBUTES에서 조회한다."""
    sql = """SELECT profile_name, attribute_name, attribute_value
FROM DBA_CLOUD_AI_PROFILE_ATTRIBUTES
WHERE profile_name = :profile_name"""
    sql_display = sql.replace(":profile_name", f"'{profile_name}'")

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute(sql, {"profile_name": profile_name})
                except Exception:
                    # DBA 뷰 권한 없으면 user 뷰로 폴백
                    sql = """SELECT profile_name, attribute_name, attribute_value
FROM USER_CLOUD_AI_PROFILE_ATTRIBUTES
WHERE profile_name = :profile_name"""
                    sql_display = sql.replace(":profile_name", f"'{profile_name}'")
                    await cursor.execute(sql, {"profile_name": profile_name})

                columns = [col[0] for col in cursor.description]
                rows = await cursor.fetchall()
                data = []
                for row in rows:
                    row_dict = {}
                    for i, val in enumerate(row):
                        if hasattr(val, 'read'):
                            val = await _lob_to_str(val)
                        row_dict[columns[i]] = val
                    data.append(row_dict)
                return {
                    "sql_executed": sql_display,
                    "columns": columns,
                    "data": data,
                    "row_count": len(data),
                }
    except Exception as e:
        return {
            "sql_executed": sql_display,
            "columns": [],
            "data": [],
            "row_count": 0,
            "error": str(e),
        }


async def get_explain_plan(pool, sql: str) -> dict:
    """SQL 텍스트에 대한 EXPLAIN PLAN을 조회한다."""
    stripped = sql.strip().rstrip(';').strip()
    if not stripped.upper().startswith("SELECT"):
        return {"error": "SELECT 문만 실행계획을 조회할 수 있습니다."}

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                stmt_id = "CLAUDE_PLAN"
                # 기존 plan 삭제
                await cursor.execute(
                    "DELETE FROM plan_table WHERE statement_id = :sid",
                    {"sid": stmt_id}
                )
                # EXPLAIN PLAN 실행
                await cursor.execute(
                    f"EXPLAIN PLAN SET STATEMENT_ID = '{stmt_id}' FOR {stripped}"
                )
                # DBMS_XPLAN으로 결과 조회
                await cursor.execute("""
                    SELECT plan_table_output
                    FROM TABLE(DBMS_XPLAN.DISPLAY('PLAN_TABLE', :sid, 'TYPICAL'))
                """, {"sid": stmt_id})
                rows = await cursor.fetchall()
                plan_text = "\n".join(r[0] for r in rows if r[0] is not None)
                # 정리
                await cursor.execute(
                    "DELETE FROM plan_table WHERE statement_id = :sid",
                    {"sid": stmt_id}
                )
                await conn.commit()
                return {"plan": plan_text, "sql_used": stripped}
    except Exception as e:
        return {"error": str(e), "sql_used": stripped}


async def execute_raw_sql(pool, sql: str) -> dict:
    """사용자가 입력한 SQL을 실행하고 결과를 반환한다. SELECT 문만 허용."""
    stripped = sql.strip().rstrip(';').strip()
    upper = stripped.upper()

    # SELECT 또는 SELECT AI만 허용
    if not upper.startswith("SELECT"):
        return {"error": "SELECT 문만 실행할 수 있습니다."}

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(stripped)
                columns = [col[0] for col in cursor.description]
                rows = await cursor.fetchall()
                data = []
                for row in rows:
                    row_dict = {}
                    for i, val in enumerate(row):
                        if hasattr(val, 'read'):
                            val = await _lob_to_str(val)
                        if hasattr(val, 'isoformat'):
                            val = val.isoformat()
                        row_dict[columns[i]] = val
                    data.append(row_dict)
                return {
                    "sql_executed": stripped,
                    "columns": columns,
                    "data": data,
                    "row_count": len(data),
                }
    except Exception as e:
        return {
            "sql_executed": stripped,
            "columns": [],
            "data": [],
            "row_count": 0,
            "error": str(e),
        }


async def get_current_schema(pool) -> str:
    """현재 접속 스키마를 반환한다."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM dual")
            row = await cursor.fetchone()
            return row[0] if row else "UNKNOWN"


async def get_schema_info(pool, profile_name: str) -> dict:
    """프로필의 object_list에 등록된 테이블들의 컬럼 정보를 조회한다."""
    # 1) 프로필 속성에서 object_list 추출
    attrs = await get_profile_attributes(pool, profile_name)
    object_list = []
    for row in attrs.get("data", []):
        attr_name = row.get("ATTRIBUTE_NAME", "")
        attr_value = row.get("ATTRIBUTE_VALUE", "")
        if attr_name.lower() == "object_list" and attr_value:
            try:
                parsed = json.loads(attr_value) if isinstance(attr_value, str) else attr_value
                if isinstance(parsed, list):
                    object_list = parsed
                elif isinstance(parsed, dict) and ("owner" in parsed or "name" in parsed):
                    object_list.append(parsed)
            except (json.JSONDecodeError, TypeError):
                pass
        # 개별 object_list 항목 (object_list[0], object_list[1] 등)
        elif attr_name.lower().startswith("object_list[") and attr_value:
            try:
                parsed = json.loads(attr_value) if isinstance(attr_value, str) else attr_value
                if isinstance(parsed, dict):
                    object_list.append(parsed)
            except (json.JSONDecodeError, TypeError):
                pass

    if not object_list:
        return {"tables": [], "error": "프로필에 object_list가 없습니다."}

    # 2) 각 테이블의 컬럼 정보 조회
    tables = []
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            for obj in object_list:
                owner = obj.get("owner", "").upper()
                name = obj.get("name", "").upper()
                if not owner or not name:
                    continue
                try:
                    await cursor.execute("""
                        SELECT column_name, data_type, nullable, data_length, data_precision, data_scale
                        FROM all_tab_columns
                        WHERE owner = :owner AND table_name = :tname
                        ORDER BY column_id
                    """, {"owner": owner, "tname": name})
                    cols = []
                    for r in await cursor.fetchall():
                        col_type = r[1]
                        if r[4] is not None:  # data_precision
                            col_type += f"({r[4]}" + (f",{r[5]}" if r[5] else "") + ")"
                        elif r[3] and r[1] in ("VARCHAR2", "CHAR", "RAW"):
                            col_type += f"({r[3]})"
                        cols.append({
                            "column_name": r[0],
                            "data_type": col_type,
                            "nullable": r[2],
                        })

                    # 행 수 조회
                    await cursor.execute(f"""
                        SELECT num_rows FROM all_tables
                        WHERE owner = :owner AND table_name = :tname
                    """, {"owner": owner, "tname": name})
                    row_count_row = await cursor.fetchone()
                    num_rows = row_count_row[0] if row_count_row else None

                    # Annotation 조회
                    table_annotation = None
                    col_annotations = {}
                    try:
                        await cursor.execute("""
                            SELECT column_name, annotation_value
                            FROM all_annotations_usage
                            WHERE object_name = :tname AND annotation_name = 'DISPLAY'
                        """, {"tname": name})
                        for arow in await cursor.fetchall():
                            aval = arow[1]
                            if hasattr(aval, 'read'):
                                aval = await _lob_to_str(aval)
                            if arow[0] is None:
                                table_annotation = aval
                            else:
                                col_annotations[arow[0]] = aval
                    except Exception:
                        pass

                    # 컬럼에 annotation 추가
                    for col in cols:
                        col["annotation"] = col_annotations.get(col["column_name"])

                    tables.append({
                        "owner": owner,
                        "table_name": name,
                        "columns": cols,
                        "column_count": len(cols),
                        "num_rows": num_rows,
                        "annotation": table_annotation,
                    })
                except Exception as e:
                    tables.append({
                        "owner": owner,
                        "table_name": name,
                        "columns": [],
                        "column_count": 0,
                        "num_rows": None,
                        "error": str(e),
                    })

    return {"tables": tables}


async def get_annotations(pool, owner: str, table_name: str) -> list:
    """테이블/컬럼의 annotation을 조회한다."""
    annotations = []
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT column_name, annotation_name, annotation_value
                    FROM all_annotations_usage
                    WHERE object_name = :tname AND object_type = 'TABLE'
                    ORDER BY column_name NULLS FIRST, annotation_name
                """, {"tname": table_name.upper()})
                for row in await cursor.fetchall():
                    val = row[2]
                    if hasattr(val, 'read'):
                        val = await _lob_to_str(val)
                    annotations.append({
                        "column_name": row[0],  # None이면 테이블 레벨
                        "annotation_name": row[1],
                        "annotation_value": val,
                    })
    except Exception:
        pass
    return annotations


async def apply_annotations(pool, annotation_set: dict) -> dict:
    """annotation 세트를 DB에 일괄 적용한다."""
    applied = []
    errors = []
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # 현재 스키마 확인
            await cursor.execute("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM dual")
            current_schema = (await cursor.fetchone())[0]

            for table_name, columns in annotation_set.items():
                owner = columns.get("_owner", current_schema)
                fqn = f"{owner}.{table_name}" if owner else table_name

                # 테이블 레벨 annotation
                table_desc = columns.get("_table")
                if table_desc:
                    try:
                        try:
                            await cursor.execute(
                                f'ALTER TABLE {fqn} ANNOTATIONS (DROP Display)')
                        except Exception:
                            pass
                        safe_desc = table_desc.replace("'", "''")
                        await cursor.execute(
                            f"ALTER TABLE {fqn} ANNOTATIONS (ADD Display '{safe_desc}')")
                        applied.append(f"{fqn} (table)")
                    except Exception as e:
                        errors.append(f"{fqn} (table): {str(e)}")

                # 컬럼 레벨 annotation
                for col_name, desc in columns.items():
                    if col_name.startswith("_"):
                        continue
                    try:
                        try:
                            await cursor.execute(
                                f'ALTER TABLE {fqn} MODIFY ({col_name} ANNOTATIONS (DROP Display))')
                        except Exception:
                            pass
                        safe_desc = desc.replace("'", "''")
                        await cursor.execute(
                            f"ALTER TABLE {fqn} MODIFY ({col_name} ANNOTATIONS (ADD Display '{safe_desc}'))")
                        applied.append(f"{fqn}.{col_name}")
                    except Exception as e:
                        errors.append(f"{fqn}.{col_name}: {str(e)}")

            await conn.commit()

    return {"applied_count": len(applied), "error_count": len(errors), "errors": errors[:10]}


async def remove_annotations(pool, table_names: list, owner: str = None) -> dict:
    """지정된 테이블들의 annotation을 일괄 제거한다."""
    removed = 0
    errors = []
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            if not owner:
                await cursor.execute("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM dual")
                owner = (await cursor.fetchone())[0]

            for table_name in table_names:
                fqn = f"{owner}.{table_name}"
                # 테이블 레벨
                try:
                    await cursor.execute(
                        f'ALTER TABLE {fqn} ANNOTATIONS (DROP Display)')
                    removed += 1
                except Exception:
                    pass

                # 컬럼 레벨: 먼저 Display annotation이 있는 컬럼 조회
                try:
                    await cursor.execute("""
                        SELECT DISTINCT column_name FROM all_annotations_usage
                        WHERE object_name = :tname AND column_name IS NOT NULL
                        AND annotation_name = 'DISPLAY'
                    """, {"tname": table_name.upper()})
                    cols = await cursor.fetchall()
                    for (col_name,) in cols:
                        try:
                            await cursor.execute(
                                f'ALTER TABLE {fqn} MODIFY ({col_name} ANNOTATIONS (DROP Display))')
                            removed += 1
                        except Exception as e:
                            errors.append(f"{fqn}.{col_name}: {str(e)}")
                except Exception as e:
                    errors.append(f"{table_name}: {str(e)}")

            await conn.commit()

    return {"removed_count": removed, "error_count": len(errors), "errors": errors[:5]}
