import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.database import get_pool, check_connection
from app.select_ai import ask_select_ai, submit_feedback, list_profiles, get_current_schema

router = APIRouter(prefix="/api")

VALID_ACTIONS = {"runsql", "showsql", "narrate", "explainsql", "showprompt", "summarize", "chat"}


class AskRequest(BaseModel):
    prompt: str
    action: str = "runsql"
    profile_name: str = "GROQ_PROFILE"


class FeedbackRequest(BaseModel):
    prompt: str
    feedback: str
    profile_name: str = "GROQ_PROFILE"


@router.post("/ask")
async def ask(req: AskRequest):
    if req.action not in VALID_ACTIONS:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"유효하지 않은 action입니다: {req.action}"},
        )

    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    start = time.time()
    try:
        result = await ask_select_ai(pool, req.prompt, req.action, req.profile_name)
        elapsed_ms = int((time.time() - start) * 1000)

        # runsql의 경우 JSON 결과를 파싱 시도
        parsed_result = result
        if req.action == "runsql" and result:
            try:
                parsed_result = json.loads(result)
            except (json.JSONDecodeError, TypeError):
                parsed_result = result

        return {
            "success": True,
            "action": req.action,
            "result": parsed_result,
            "elapsed_ms": elapsed_ms,
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "elapsed_ms": elapsed_ms,
            },
        )


@router.post("/feedback")
async def feedback(req: FeedbackRequest):
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        await submit_feedback(pool, req.prompt, req.feedback, req.profile_name)
        return {"success": True, "message": "피드백이 제출되었습니다."}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.get("/profiles")
async def profiles():
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        result = await list_profiles(pool)
        return {"success": True, "profiles": result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.get("/health")
async def health():
    connected = await check_connection()
    schema = None
    if connected:
        pool = await get_pool()
        try:
            schema = await get_current_schema(pool)
        except Exception:
            pass

    return {
        "status": "ok" if connected else "error",
        "database_connected": connected,
        "schema": schema,
    }
