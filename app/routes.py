import json
import os
import tempfile
import time

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.database import get_pool, check_connection
from app.select_ai import ask_select_ai, submit_feedback, list_profiles, get_current_schema
from app.vector_search import (
    upload_document,
    vector_search,
    keyword_search,
    compare_search,
    generate_rag_answer,
    list_documents,
    delete_document,
    get_index_info,
    get_embedding_info,
)

router = APIRouter(prefix="/api")

VALID_ACTIONS = {"runsql", "showsql", "narrate", "explainsql", "showprompt", "summarize", "chat"}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB


class AskRequest(BaseModel):
    prompt: str
    action: str = "runsql"
    profile_name: str = "GROQ_PROFILE"


class FeedbackRequest(BaseModel):
    prompt: str
    feedback: str
    profile_name: str = "GROQ_PROFILE"


class VectorSearchRequest(BaseModel):
    query: str
    mode: str = "vector"  # "vector", "keyword", "compare"
    top_k: int = 5
    profile_name: str = "GROQ_PROFILE"


class EmbeddingInfoRequest(BaseModel):
    text: str


# === Existing NL2SQL Endpoints ===

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


# === Vector Search Endpoints ===

@router.post("/vector/upload")
async def vector_upload(file: UploadFile = File(...)):
    """PDF 파일 업로드 -> 청킹 -> 임베딩 -> DB 저장"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    # 파일 크기 확인
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"파일 크기가 10MB를 초과합니다."},
        )

    # PDF 확인
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "PDF 파일만 업로드 가능합니다."},
        )

    # 임시 파일로 저장
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        result = await upload_document(pool, tmp_path, file.filename)
        return result

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/vector/search")
async def vector_search_endpoint(req: VectorSearchRequest):
    """벡터 유사도 검색 / 키워드 검색 / 비교 검색"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    start = time.time()
    try:
        if req.mode == "compare":
            result = await compare_search(pool, req.query, req.top_k)
            elapsed_ms = int((time.time() - start) * 1000)
            return {
                "success": True,
                "mode": "compare",
                "keyword_results": result["keyword_results"],
                "vector_results": result["vector_results"],
                "elapsed_ms": elapsed_ms,
            }
        elif req.mode == "keyword":
            search_result = await keyword_search(pool, req.query, req.top_k)
        else:
            search_result = await vector_search(pool, req.query, req.top_k)

        # RAG 답변 생성
        answer = ""
        if search_result["chunks"]:
            answer = await generate_rag_answer(pool, req.query, search_result["chunks"], req.profile_name)

        elapsed_ms = int((time.time() - start) * 1000)

        return {
            "success": True,
            "mode": req.mode,
            "answer": answer,
            "chunks": search_result["chunks"],
            "match_count": search_result["match_count"],
            "sql_executed": search_result["sql_executed"],
            "elapsed_ms": elapsed_ms,
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e), "elapsed_ms": elapsed_ms},
        )


@router.get("/vector/documents")
async def vector_documents():
    """업로드된 문서 목록 조회"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        docs = await list_documents(pool)
        return {"success": True, "documents": docs}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.delete("/vector/documents/{doc_id}")
async def vector_delete_document(doc_id: int):
    """특정 문서 및 관련 청크 삭제"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        await delete_document(pool, doc_id)
        return {"success": True, "message": "문서가 삭제되었습니다."}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.get("/vector/index-info")
async def vector_index_info():
    """벡터 인덱스 메타데이터 조회"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        info = await get_index_info(pool)
        return {"success": True, **info}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.post("/vector/embedding-info")
async def vector_embedding_info(req: EmbeddingInfoRequest):
    """질문 텍스트의 임베딩 과정 정보 반환"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        info = await get_embedding_info(pool, req.text)
        return {"success": True, **info}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )
