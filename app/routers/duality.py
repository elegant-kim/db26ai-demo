"""JSON Relational Duality 라우터 — /api/duality/* (계획서 5-3 에서 routes.py 에서 분리, 2026-09-05).

경로·응답은 routes.py 에 있던 그대로다. 뷰 정의 정본은 app/duality.py 의 DUALITY_VIEW_DDLS.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.database import get_pool

router = APIRouter(prefix="/api/duality", tags=["duality"])

from app.duality import (
    compare_relational_vs_json,
    create_duality_views,
    drop_duality_views,
    fetch_duality_doc,
    list_duality_docs,
    list_duality_views,
    query_duality_recent_sql,
    simulate_etag_conflict,
    update_duality_doc,
)


class DualityCompareRequest(BaseModel):
    view_name: str = "CUSTOMERS_DV"
    limit: int = 5


class DualityCrudRequest(BaseModel):
    view_name: str
    doc_id: str = ""
    doc_json: dict = {}


@router.post("/create-views")
async def duality_create():
    """SH 스키마 기반 JSON Relational Duality View 들을 생성한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await create_duality_views(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/drop-views")
async def duality_drop():
    """Duality View 들을 삭제한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await drop_duality_views(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.get("/views")
async def duality_list():
    """현재 존재하는 Duality View 목록을 조회한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await list_duality_views(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/compare")
async def duality_compare(req: DualityCompareRequest):
    """같은 데이터를 관계형 SQL JOIN 과 Duality View JSON 으로 각각 조회해 비교한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await compare_relational_vs_json(pool, req.view_name, req.limit)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/docs")
async def duality_list_docs(req: DualityCrudRequest):
    """Duality View 문서 목록 (ID + 요약) 조회"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await list_duality_docs(pool, req.view_name)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/doc")
async def duality_fetch_doc(req: DualityCrudRequest):
    """Duality View 의 단일 JSON 문서를 조회한다 (ETag 포함)."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await fetch_duality_doc(pool, req.view_name, req.doc_id)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/doc/update")
async def duality_update_doc(req: DualityCrudRequest):
    """Duality View 의 JSON 문서를 수정한다 — 관계형 테이블에 그대로 반영된다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await update_duality_doc(pool, req.view_name, req.doc_json)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/etag-simulation")
async def duality_etag():
    """ETag 낙관적 동시성 제어를 시뮬레이션한다 (동시 수정 충돌 재현)."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await simulate_etag_conflict(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.get("/recent-queries")
async def duality_recent_sql():
    """V$SQL 에서 Duality View 관련 최근 실행 쿼리를 조회한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        result = await query_duality_recent_sql(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
