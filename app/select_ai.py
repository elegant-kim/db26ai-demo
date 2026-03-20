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
    """사용 가능한 AI 프로필 목록을 조회한다."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
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


async def get_current_schema(pool) -> str:
    """현재 접속 스키마를 반환한다."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM dual")
            row = await cursor.fetchone()
            return row[0] if row else "UNKNOWN"
