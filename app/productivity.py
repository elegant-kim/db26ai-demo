"""
개발생산성 향상 기능 모듈
- Lock-Free Column Value Reservations 시뮬레이션
- Priority Transactions 시뮬레이션
- 최근 쿼리 조회
"""

import json
import time

from app.select_ai import _lob_to_str


# === Lock-Free Reservations ===

async def simulate_lock_free(pool) -> dict:
    """Lock-Free Reservations 시뮬레이션.
    RESERVABLE 컬럼이 있는 계좌 테이블에서 동시 차감을 시연한다.
    """
    steps = []
    table_created = False

    try:
        # Step 1: 데모 테이블 생성
        create_sql = """CREATE TABLE demo_lockfree_account (
    account_id NUMBER PRIMARY KEY,
    owner VARCHAR2(50),
    balance NUMBER RESERVABLE
    CONSTRAINT min_balance CHECK (balance >= 0)
)"""
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(create_sql)
                    await cursor.execute(
                        "INSERT INTO demo_lockfree_account VALUES (1, 'Demo Account', 500)")
                    await conn.commit()
            table_created = True
            steps.append({
                "description": "데모 테이블 생성 — balance=500, RESERVABLE 컬럼 + CHECK(balance >= 0)",
                "sql": create_sql,
                "success": True,
            })
        except Exception as e:
            if "ORA-00955" in str(e):
                # 이미 존재 → 초기화
                async with pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            "UPDATE demo_lockfree_account SET balance = 500 WHERE account_id = 1")
                        await conn.commit()
                table_created = True
                steps.append({
                    "description": "기존 데모 테이블 초기화 — balance=500으로 리셋",
                    "sql": "UPDATE demo_lockfree_account SET balance = 500 WHERE account_id = 1",
                    "success": True,
                })
            else:
                raise

        # Step 2: Session A — 200 차감 (커밋하지 않음)
        update_a_sql = "UPDATE demo_lockfree_account SET balance = balance - 200 WHERE account_id = 1"
        async with pool.acquire() as conn_a:
            async with conn_a.cursor() as cursor_a:
                await cursor_a.execute(update_a_sql)
                # 커밋하지 않음 — 예약(reservation)만 됨

                steps.append({
                    "description": "Session A: 잔액에서 200 차감 (미커밋 — 예약만 됨). 기존 방식이면 행 잠금으로 다른 세션은 대기해야 함.",
                    "sql": update_a_sql,
                    "success": True,
                })

                # Step 3: Session B — 100 차감 (동시 실행 가능!)
                update_b_sql = "UPDATE demo_lockfree_account SET balance = balance - 100 WHERE account_id = 1"
                try:
                    async with pool.acquire() as conn_b:
                        async with conn_b.cursor() as cursor_b:
                            await cursor_b.execute(update_b_sql)
                            await conn_b.commit()
                    steps.append({
                        "description": "Session B: 잔액에서 100 차감 — Lock-Free로 동시 실행 성공! (500 - 200(A예약) - 100(B) = 200 ≥ 0)",
                        "sql": update_b_sql,
                        "success": True,
                    })
                except Exception as e:
                    steps.append({
                        "description": f"Session B: 100 차감 시도 — {str(e)[:100]}",
                        "sql": update_b_sql,
                        "success": False,
                    })

                # Step 4: Session C — 300 차감 시도 (CHECK 위반 예상)
                update_c_sql = "UPDATE demo_lockfree_account SET balance = balance - 300 WHERE account_id = 1"
                try:
                    async with pool.acquire() as conn_c:
                        async with conn_c.cursor() as cursor_c:
                            await cursor_c.execute(update_c_sql)
                            await conn_c.commit()
                    steps.append({
                        "description": "Session C: 잔액에서 300 차감 — 예상과 달리 성공 (잔액 여유 있음)",
                        "sql": update_c_sql,
                        "success": True,
                    })
                except Exception as e:
                    steps.append({
                        "description": "Session C: 300 차감 시도 — CHECK 제약 위반! 잔액 부족 (500 - 200(A예약) - 100(B) - 300 = -100 < 0)",
                        "sql": update_c_sql,
                        "success": False,
                    })

                # Session A 롤백 (예약 해제)
                await conn_a.rollback()

        # Step 5: 정리
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT balance FROM demo_lockfree_account WHERE account_id = 1")
                row = await cursor.fetchone()
                final_balance = row[0] if row else '?'

        steps.append({
            "description": f"시뮬레이션 완료 — Session A 롤백, 최종 잔액: {final_balance}",
            "sql": "SELECT balance FROM demo_lockfree_account WHERE account_id = 1",
            "success": True,
        })

    except Exception as e:
        steps.append({"description": f"에러: {str(e)}", "success": False})
    finally:
        # 테이블 정리
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("DROP TABLE demo_lockfree_account PURGE")
                    await conn.commit()
        except Exception:
            pass

    return {"steps": steps}


# === Priority Transactions ===

async def simulate_priority_tx(pool) -> dict:
    """Priority Transactions 시뮬레이션.
    LOW 트랜잭션이 행을 잠근 상태에서 HIGH 트랜잭션이 요청하는 시나리오.
    참고: 실제 자동 롤백은 PRIORITY_TXNS_MODE=ROLLBACK + 대기 시간 설정이 필요하며,
    ADB 환경에서는 설정이 제한될 수 있으므로 설명 중심으로 시뮬레이션.
    """
    steps = []

    try:
        # Step 1: 데모 테이블 생성
        create_sql = """CREATE TABLE demo_priority_orders (
    order_id NUMBER PRIMARY KEY,
    status VARCHAR2(20),
    amount NUMBER
)"""
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(create_sql)
                    await cursor.execute(
                        "INSERT INTO demo_priority_orders VALUES (1, 'pending', 1000)")
                    await conn.commit()
        except Exception as e:
            if "ORA-00955" in str(e):
                async with pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            "UPDATE demo_priority_orders SET status='pending', amount=1000 WHERE order_id=1")
                        await conn.commit()
            else:
                raise

        steps.append({
            "description": "데모 테이블 생성 — order_id=1, status='pending', amount=1000",
            "sql": create_sql,
            "success": True,
        })

        # Step 2: LOW 우선순위 트랜잭션이 행 잠금
        steps.append({
            "description": "Session A (LOW): 주문 상태를 'processing'으로 변경 — 행 잠금 중 (미커밋)",
            "sql": "ALTER SESSION SET TXN_PRIORITY = LOW;\nUPDATE demo_priority_orders SET status = 'processing' WHERE order_id = 1;",
            "success": True,
        })

        # Step 3: HIGH 우선순위 트랜잭션 요청
        steps.append({
            "description": "Session B (HIGH): VIP 결제 처리 — 같은 행 필요. 기존에는 Session A가 커밋할 때까지 무한 대기.",
            "sql": "ALTER SESSION SET TXN_PRIORITY = HIGH;\nUPDATE demo_priority_orders SET status = 'paid' WHERE order_id = 1;\n-- 기존: 대기(블로킹)...",
            "success": True,
        })

        # Step 4: DB가 자동으로 LOW 롤백
        steps.append({
            "description": "Priority Transactions 동작: 대기 시간(PRIORITY_TXNS_HIGH_WAIT_TARGET) 초과 → DB가 Session A(LOW)를 자동 롤백 → Session B(HIGH) 진행!",
            "sql": "-- PRIORITY_TXNS_MODE = ROLLBACK\n-- PRIORITY_TXNS_HIGH_WAIT_TARGET = 3 (초)\n-- → 3초 후 LOW 트랜잭션 자동 롤백",
            "success": True,
        })

        # Step 5: 결과
        steps.append({
            "description": "Session B(HIGH) 성공 — status='paid'. LOW 트랜잭션은 ORA-63300 에러를 받고, 앱에서 재시도 로직을 구현하면 됨.",
            "sql": "-- Session A는 ORA-63300: transaction rolled back due to priority transaction 수신\n-- Session B: COMMIT; → 성공",
            "success": False,  # LOW 입장에서는 실패
        })

        steps.append({
            "description": "핵심: DBA가 개입하지 않아도, DB가 비즈니스 우선순위에 따라 자동으로 트랜잭션 충돌을 해소합니다.",
            "sql": None,
            "success": True,
        })

        # 정리
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DROP TABLE demo_priority_orders PURGE")
                await conn.commit()

    except Exception as e:
        steps.append({"description": f"에러: {str(e)}", "success": False})
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("DROP TABLE demo_priority_orders PURGE")
                    await conn.commit()
        except Exception:
            pass

    return {"steps": steps}


# === 최근 쿼리 조회 ===

async def query_prod_recent_sql(pool) -> dict:
    """V$SQL에서 개발생산성 관련 최근 쿼리를 조회한다."""
    sql = """SELECT sql_id, SUBSTR(sql_text, 1, 200) AS sql_text,
       executions, elapsed_time/1000 AS elapsed_ms,
       TO_CHAR(last_active_time, 'HH24:MI:SS') AS last_active
FROM v$sql
WHERE (UPPER(sql_text) LIKE '%DEMO\\_LOCKFREE%' ESCAPE '\\'
    OR UPPER(sql_text) LIKE '%DEMO\\_PRIORITY%' ESCAPE '\\'
    OR UPPER(sql_text) LIKE '%TXN\\_PRIORITY%' ESCAPE '\\'
    OR UPPER(sql_text) LIKE '%RESERVABLE%')
  AND sql_text NOT LIKE '%v$sql%'
ORDER BY last_active_time DESC NULLS LAST
FETCH FIRST 10 ROWS ONLY"""

    try:
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
        return {"columns": columns, "data": data, "row_count": len(data), "sql_executed": sql}
    except Exception as e:
        return {"error": str(e), "sql_executed": sql}
