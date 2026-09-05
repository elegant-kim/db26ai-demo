"""Property Graph 라우터 — /api/graph/* (계획서 5-1 에서 routes.py 에서 분리, 2026-09-05).

경로·응답은 routes.py 에 있던 그대로다. 정본 쿼리는 app/graph.py 의 COMPARE_QUERIES / PATTERN_QUERIES.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.database import get_pool

router = APIRouter(prefix="/api/graph", tags=["graph"])

from app.graph import (
    compare_sql_vs_pgq,
    create_property_graph,
    drop_property_graph,
    get_compare_queries,
    get_pattern_queries,
    query_graph_recent_sql,
    run_pattern_query,
)


class GraphQueryRequest(BaseModel):
    query_index: int = 0


@router.post("/create")
async def graph_create():
    """SH 스키마(CUSTOMERS·PRODUCTS·SALES) 기반 SQL Property Graph 를 생성한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await create_property_graph(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/drop")
async def graph_drop():
    """Property Graph 를 삭제한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await drop_property_graph(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.get("/queries")
async def graph_queries():
    """비교 쿼리·패턴 쿼리 목록을 반환한다 (정본은 graph.py 의 COMPARE_QUERIES/PATTERN_QUERIES)."""
    return {"success": True, "compare": get_compare_queries(), "pattern": get_pattern_queries()}


@router.post("/compare")
async def graph_compare(req: GraphQueryRequest):
    """같은 질문을 기존 SQL JOIN 과 SQL/PGQ 로 각각 실행해 결과·소요시간을 비교한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await compare_sql_vs_pgq(pool, req.query_index)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/pattern")
async def graph_pattern(req: GraphQueryRequest):
    """SQL/PGQ MATCH 패턴 질의를 실행한다 (관계 탐색)."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await run_pattern_query(pool, req.query_index)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.get("/recent-queries")
async def graph_recent():
    """V$SQL 에서 GRAPH_TABLE 관련 최근 실행 쿼리를 조회한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await query_graph_recent_sql(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


# === 개발생산성 향상 Endpoints ===
