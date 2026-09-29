"""NL2SQL(Select AI) 라우터 — /api/ask · profiles · set-profile · annotations · schema-info · explain-plan · execute-sql
(계획서 5-5 에서 routes.py 에서 분리, 2026-09-05). 경로·응답 불변. Select AI 본체는 app/select_ai.py.
"""
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.ai_log import VALID_FEEDBACK, VALID_STATUS, get_query_log, list_query_log, query_log_summary
from app.database import get_pool
from app.presets import create_preset, delete_preset, list_presets, update_preset
from app.presets import validate as validate_preset
from app.select_ai import (
    SELECT_AI_ACTIONS,
    apply_annotations,
    create_conversation,
    drop_conversation,
    execute_raw_sql,
    get_env_info,
    get_explain_plan,
    get_profile_attributes,
    get_schema_info,
    list_profiles,
    remove_annotations,
    run_select_ai,
    set_profile,
)

router = APIRouter(prefix="/api", tags=["nl2sql"])

VALID_ACTIONS = set(SELECT_AI_ACTIONS)  # 정본은 app/select_ai.py — 직접 실행창의 SELECT AI 파서와 같은 목록

# 「환경 확인」 버튼 3종. 조회 SQL 정본은 app/select_ai.py 의 ENV_QUERIES 다.
VALID_ENV_KINDS = {"profile", "acl", "credential"}

class AskRequest(BaseModel):
    prompt: str
    action: str = "runsql"
    profile_name: str = ""
    conversation_id: str = ""   # 멀티턴 — 브라우저가 들고 매 요청 보낸다 (POST /api/conversations 로 발급)


class ConversationRequest(BaseModel):
    title: str = ""


class PresetRequest(BaseModel):
    title: str
    question: str
    action: str = "runsql"
    profile_name: str | None = None   # NULL = 모든 프로필, '%SH%' 같은 LIKE 패턴


class SetProfileRequest(BaseModel):
    profile_name: str


class ExecuteSqlRequest(BaseModel):
    sql: str
    profile_name: str = ""  # `SELECT AI …` 일 때만 쓴다 — 같은 커넥션에서 SET_PROFILE 후 실행


class EnvInfoRequest(BaseModel):
    kind: str = "profile"
    profile_name: str = ""


@router.post("/env-info")
async def env_info(req: EnvInfoRequest):
    """Select AI 환경 3종을 조회한다 — profile(프로필 속성) · acl(네트워크 ACL) · credential(크리덴셜).

    프로필이 무엇을 보는가 / DB 가 LLM 으로 나갈 수 있는가 / 키가 등록돼 있는가를
    화면에서 바로 확인하기 위한 것이다. 크리덴셜의 API 키 값은 어떤 뷰에도 나오지 않는다.
    """
    if req.kind not in VALID_ENV_KINDS:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"유효하지 않은 확인 항목입니다: {req.kind}"},
        )
    pool = await get_pool()
    result = await get_env_info(pool, req.kind, req.profile_name)
    return {"success": "error" not in result, "kind": req.kind, "result": result}


@router.post("/ask")
async def ask(req: AskRequest):
    """Select AI 로 자연어 질문을 처리한다 (action 7종: runsql/showsql/narrate/explainsql/showprompt/summarize/chat)."""
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

    prompt = req.prompt
    if req.action == "explainsql":
        prompt = f"{req.prompt} (Please explain in Korean / 한국어로 설명해 주세요)"

    r = await run_select_ai(pool, prompt, req.action, req.profile_name, conversation_id=req.conversation_id)
    meta = {"action": req.action, "elapsed_ms": r["elapsed_ms"], "log_id": r["log_id"], "conversation_id": r["conversation_id"],
            "model": r["model"], "profile_name": r["profile_name"]}
    if r.get("error"):
        return JSONResponse(status_code=500, content={"success": False, "error": r["error"], **meta})

    # runsql의 경우 JSON 결과를 파싱 시도
    parsed_result = r["result"]
    if req.action == "runsql" and parsed_result:
        try:
            parsed_result = json.loads(parsed_result)
        except (json.JSONDecodeError, TypeError):
            pass
    return {"success": True, "result": parsed_result, **meta}


@router.post("/conversations")
async def conversation_create(req: ConversationRequest):
    """멀티턴 대화 발급 — DBMS_CLOUD_AI.CREATE_CONVERSATION. 돌려준 conversation_id 를 /api/ask 에 실어 보내면 앞 질문을 이어받는다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."})
    try:
        cid = await create_conversation(pool, req.title)
        return {"success": True, "conversation_id": cid}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.delete("/conversations/{conversation_id}")
async def conversation_drop(conversation_id: str):
    """대화 삭제 — DBMS_CLOUD_AI.DROP_CONVERSATION(force). 「새 대화」는 이걸 부르지 않는다(이력 뷰에 남기려고); 정리용."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."})
    try:
        await drop_conversation(pool, conversation_id)
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.get("/profiles")
async def profiles():
    """등록된 AI 프로필 목록을 조회한다."""
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


@router.post("/set-profile")
async def set_profile_endpoint(req: SetProfileRequest):
    """DBMS_CLOUD_AI.SET_PROFILE 실행"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        result = await set_profile(pool, req.profile_name)
        # SET_PROFILE 성공 시 프로필 상세 속성도 조회하여 함께 반환
        if result.get("success"):
            attrs = await get_profile_attributes(pool, req.profile_name)
            result["attributes"] = attrs
        return result
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.post("/apply-annotations")
async def apply_annotations_endpoint(req: Request):
    """annotation 세트를 DB에 일괄 적용한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        body = await req.json()
        annotation_set = body.get("annotation_set", {})
        result = await apply_annotations(pool, annotation_set)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/remove-annotations")
async def remove_annotations_endpoint(req: Request):
    """annotation을 일괄 제거한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "DB 연결 없음"})
    try:
        body = await req.json()
        table_names = body.get("table_names", [])
        owner = body.get("owner")
        result = await remove_annotations(pool, table_names, owner)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/schema-info")
async def schema_info_endpoint(req: SetProfileRequest):
    """프로필에 등록된 테이블의 컬럼 정보를 조회한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )
    try:
        result = await get_schema_info(pool, req.profile_name)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.post("/explain-plan")
async def explain_plan_endpoint(req: ExecuteSqlRequest):
    """SQL에 대한 실행계획을 조회한다."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )
    try:
        result = await get_explain_plan(pool, req.sql)
        if "error" in result:
            return {"success": False, "error": result["error"], "sql_used": result.get("sql_used")}
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.post("/execute-sql")
async def execute_sql_endpoint(req: ExecuteSqlRequest):
    """사용자가 입력한 SQL을 직접 실행. `SELECT AI …` 도 받는다 (profile_name 필요)."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    start = time.time()
    try:
        result = await execute_raw_sql(pool, req.sql, req.profile_name)
        elapsed_ms = int((time.time() - start) * 1000)
        if result.get("error"):
            return {"success": False, "error": result["error"], "sql_executed": result.get("sql_executed", ""), "elapsed_ms": elapsed_ms}
        return {"success": True, **result, "elapsed_ms": elapsed_ms}
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e), "elapsed_ms": elapsed_ms},
        )


# ── 이력 (PoC 1-C) — 읽기 전용, 정본 app/ai_log.py ──

@router.get("/nl2sql/history")
async def nl2sql_history(q: str = "", date_from: str = "", date_to: str = "", profile: str = "", action: str = "",
                         status: str = "", feedback: str = "", page: int = 1, size: int = 20):
    """Select AI 호출 이력(AI_QUERY_LOG) 한 쪽 — 최신순, 필터: 질문 LIKE(대소문자 무시)·기간·프로필·액션·상태·피드백(any/none/positive/negative). 최근 피드백 한 건을 조인."""
    if action and action not in VALID_ACTIONS:
        return JSONResponse(status_code=400, content={"success": False, "error": f"유효하지 않은 action입니다: {action}"})
    if status not in VALID_STATUS or feedback not in VALID_FEEDBACK:
        return JSONResponse(status_code=400, content={"success": False, "error": "status 는 SUCCEEDED/FAILED, feedback 은 any/none/positive/negative 만 됩니다."})
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."})
    try:
        return {"success": True, **await list_query_log(pool, q, date_from, date_to, profile, action, status, feedback, page, size)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.get("/nl2sql/history/summary")
async def nl2sql_history_summary(profile: str = ""):
    """이력 요약 — 총 질의·성공률·평균/최대 elapsed·피드백 비율 + 프로필(모델)별·액션별 평균 elapsed."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."})
    try:
        return {"success": True, **await query_log_summary(pool, profile)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.get("/nl2sql/history/{log_id}")
async def nl2sql_history_detail(log_id: int):
    """이력 한 건 상세 — 질문·생성 SQL·답변 앞부분·오류 전문 + 그 건의 피드백 목록."""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."})
    try:
        d = await get_query_log(pool, log_id)
        if d is None:
            return JSONResponse(status_code=404, content={"success": False, "error": f"이력이 없습니다: {log_id}"})
        return {"success": True, **d}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


# ── 저장 질문 프리셋 (PoC 1-D) — 정본 app/presets.py, 시드 sql/setup/72 ──

def _db_or_503():
    return JSONResponse(status_code=503, content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."})


@router.get("/nl2sql/presets")
async def presets_list(profile: str = ""):
    """예시 질문 프리셋 — profile 을 주면 NULL(전체) + LIKE 패턴이 맞는 것만. 화면의 「예시 질문 고르기」 소스."""
    pool = await get_pool()
    if pool is None:
        return _db_or_503()
    try:
        return {"success": True, "presets": await list_presets(pool, profile)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/nl2sql/presets")
async def presets_create(req: PresetRequest):
    """프리셋 추가 (제목·질문·action·profile_name 패턴)."""
    err = validate_preset(req.title, req.question, req.action)
    if err:
        return JSONResponse(status_code=400, content={"success": False, "error": err})
    pool = await get_pool()
    if pool is None:
        return _db_or_503()
    try:
        pid = await create_preset(pool, req.title, req.question, req.action, req.profile_name)
        return {"success": True, "id": pid}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.put("/nl2sql/presets/{preset_id}")
async def presets_update(preset_id: int, req: PresetRequest):
    """프리셋 수정."""
    err = validate_preset(req.title, req.question, req.action)
    if err:
        return JSONResponse(status_code=400, content={"success": False, "error": err})
    pool = await get_pool()
    if pool is None:
        return _db_or_503()
    try:
        ok = await update_preset(pool, preset_id, req.title, req.question, req.action, req.profile_name)
        if not ok:
            return JSONResponse(status_code=404, content={"success": False, "error": f"프리셋이 없습니다: {preset_id}"})
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.delete("/nl2sql/presets/{preset_id}")
async def presets_delete(preset_id: int):
    """프리셋 삭제."""
    pool = await get_pool()
    if pool is None:
        return _db_or_503()
    try:
        ok = await delete_preset(pool, preset_id)
        if not ok:
            return JSONResponse(status_code=404, content={"success": False, "error": f"프리셋이 없습니다: {preset_id}"})
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

