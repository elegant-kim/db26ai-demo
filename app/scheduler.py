"""ADB Keepalive 스케줄러.

OCI Always Free ADB는 7일 연속 미접속 시 자동 stop되고,
stop 상태 90일 경과 시 삭제될 수 있다.

이 데모 앱은 스케줄러 없이 사용자 웹 접속 시에만 DB를 쓰므로,
장기간 미사용 시 ADB가 회수될 위험이 있다.
→ 주 1회 `SELECT 1 FROM dual` 핑으로 "활동 중" 상태 유지.
"""
from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")


async def keepalive_ping():
    """ADB에 가벼운 쿼리를 날려 '활동 중' 상태 유지."""
    from app.database import get_pool

    try:
        pool = await get_pool()
        if pool is None:
            logger.warning("[keepalive] DB 풀이 초기화되지 않음 — 스킵")
            return

        async with pool.acquire() as conn:
            cursor = conn.cursor()
            try:
                await cursor.execute("SELECT 1 FROM dual")
                row = await cursor.fetchone()
                msg = f"[keepalive] ✅ ADB 핑 성공 ({datetime.now().isoformat()}) → {row}"
                print(msg)
                logger.info(msg)
            finally:
                cursor.close()
    except Exception as exc:
        msg = f"[keepalive] ❌ ADB 핑 실패: {exc}"
        print(msg)
        logger.error(msg)


def init_scheduler():
    """스케줄러 시작 — 매주 월요일 09:00 + 앱 시작 시 1회 즉시 실행."""
    # 매주 월요일 09:00 KST
    scheduler.add_job(
        keepalive_ping,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="adb_keepalive_weekly",
        name="ADB Keepalive (주간 핑)",
        replace_existing=True,
    )

    # 앱 시작 후 30초 뒤 최초 1회 (DB 풀 초기화 완료 보장)
    scheduler.add_job(
        keepalive_ping,
        trigger="date",
        run_date=datetime.now().replace(microsecond=0),
        id="adb_keepalive_initial",
        name="ADB Keepalive (최초 1회)",
        replace_existing=True,
        misfire_grace_time=60,
    )

    scheduler.start()
    msg = f"[keepalive] 스케줄러 시작 — 등록 작업: {len(scheduler.get_jobs())}건"
    print(msg)
    logger.info(msg)
    for job in scheduler.get_jobs():
        print(f"  [{job.id}] {job.name} — 다음 실행: {job.next_run_time}")


def shutdown_scheduler():
    """스케줄러 종료."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[keepalive] 스케줄러 종료")
