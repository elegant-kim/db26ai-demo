"""개발생산성 향상 라우터 — /api/productivity/* (계획서 5-2 에서 routes.py 에서 분리, 2026-09-05).

경로·응답은 routes.py 에 있던 그대로다. 시뮬레이션 본체는 app/productivity.py.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.database import get_pool

router = APIRouter(prefix="/api/productivity", tags=["productivity"])

from app.productivity import (
    query_prod_recent_sql,
    simulate_lock_free,
    simulate_priority_tx,
)


@router.post("/lockfree")
async def prod_lockfree():
    """26ai Lock-Free Reservations 를 시뮬레이션한다 (동시 예약 시 잠금 경합 없이 처리)."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await simulate_lock_free(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/priority-tx")
async def prod_priority():
    """26ai Priority Transactions 를 시뮬레이션한다 (우선순위 트랜잭션이 낮은 순위를 선점)."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await simulate_priority_tx(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.get("/recent-queries")
async def prod_recent():
    """V$SQL 에서 개발생산성 시뮬레이션 관련 최근 실행 쿼리를 조회한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await query_prod_recent_sql(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
