import oracledb
from app.config import settings

pool = None


async def init_pool():
    """비동기 연결 풀을 초기화한다."""
    global pool

    connect_params = {}

    if settings.ORACLE_WALLET_DIR:
        connect_params["config_dir"] = settings.ORACLE_WALLET_DIR
        connect_params["wallet_location"] = settings.ORACLE_WALLET_DIR
        if settings.ORACLE_WALLET_PASSWORD:
            connect_params["wallet_password"] = settings.ORACLE_WALLET_PASSWORD

    pool = oracledb.create_pool_async(
        user=settings.ORACLE_USER,
        password=settings.ORACLE_PASSWORD,
        dsn=settings.ORACLE_DSN,
        min=1,
        max=5,
        increment=1,
        **connect_params,
    )


async def close_pool():
    """연결 풀을 종료한다."""
    global pool
    if pool is not None:
        await pool.close()
        pool = None


async def get_pool():
    """현재 연결 풀을 반환한다."""
    return pool


async def check_connection() -> bool:
    """DB 연결 상태를 확인한다."""
    try:
        if pool is None:
            return False
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1 FROM dual")
                await cursor.fetchone()
        return True
    except Exception:
        return False
