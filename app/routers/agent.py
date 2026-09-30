"""⑦ Select AI Agent 라우터 — 정의 · 샘플 팀 · 실행(RUN_TEAM) · Agent History (Phase 4, 2026-09-30). 본체는 app/agent.py."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.agent import (
    DEMO,
    create_demo_team,
    drop_demo_team,
    exec_detail,
    list_definitions,
    run_team,
    team_history,
)
from app.database import get_pool
from app.select_ai import create_conversation

router = APIRouter(prefix="/api/agent", tags=["agent"])


class DemoTeamRequest(BaseModel):
    base_profile: str = "GEMINI_SH_PROFILE"


class RunRequest(BaseModel):
    team_name: str
    prompt: str
    conversation_id: str = ""     # 비우면 새로 발급해 돌려준다


def _503():
    return JSONResponse(status_code=503, content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."})


@router.get("/definitions")
async def definitions():
    """팀·에이전트·태스크·툴 목록 + 속성 JSON (USER_AI_AGENT_* 뷰). 샘플 이름은 demo 로 같이 준다."""
    pool = await get_pool()
    if pool is None:
        return _503()
    try:
        return {"success": True, **await list_definitions(pool), "demo": DEMO}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/demo-team")
async def demo_team_create(req: DemoTeamRequest):
    """샘플 팀 생성 — provider=google 네이티브 프로필(없으면 base 프로필에서 복사 생성) → SQL 툴 → 에이전트 → 태스크 → 팀(sequential). 있으면 지우고 다시."""
    pool = await get_pool()
    if pool is None:
        return _503()
    try:
        return {"success": True, **await create_demo_team(pool, req.base_profile)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.delete("/demo-team")
async def demo_team_drop():
    """샘플 팀·태스크·에이전트·툴 삭제(프로필은 남긴다)."""
    pool = await get_pool()
    if pool is None:
        return _503()
    try:
        await drop_demo_team(pool)
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/run")
async def run(req: RunRequest):
    """DBMS_CLOUD_AI_AGENT.RUN_TEAM — 답 + team_exec_id + 단계(태스크)·툴 호출(Thinking) + AI_QUERY_LOG(source RUN_TEAM). conversation_id 로 멀티턴."""
    if not req.team_name or not req.prompt.strip():
        return JSONResponse(status_code=400, content={"success": False, "error": "team_name 과 prompt 가 필요합니다."})
    pool = await get_pool()
    if pool is None:
        return _503()
    try:
        cid = req.conversation_id or await create_conversation(pool, f"agent · {req.team_name}")
        r = await run_team(pool, req.team_name, req.prompt.strip(), cid)
        if r.get("error"):
            return JSONResponse(status_code=500, content={"success": False, **r})
        return {"success": True, **r}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.get("/history")
async def history(q: str = "", date_from: str = "", date_to: str = "", team: str = "", state: str = "", page: int = 1, size: int = 20):
    """Agent History — USER_AI_AGENT_TEAM_HISTORY ⋈ AI_QUERY_LOG(exec_id) ⋈ 최근 피드백. 필터 질문 LIKE·기간·팀·상태."""
    pool = await get_pool()
    if pool is None:
        return _503()
    try:
        return {"success": True, **await team_history(pool, q, date_from, date_to, team, state, page, size)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.get("/history/{exec_id}")
async def history_detail(exec_id: str):
    """실행 한 건 — 팀 행 + 태스크 단계 + 툴 호출 + 앱 로그(답·SQL) + 피드백."""
    pool = await get_pool()
    if pool is None:
        return _503()
    try:
        d = await exec_detail(pool, exec_id)
        if d is None:
            return JSONResponse(status_code=404, content={"success": False, "error": f"실행 이력이 없습니다: {exec_id}"})
        return {"success": True, **d}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
