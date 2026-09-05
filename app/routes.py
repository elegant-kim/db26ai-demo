import asyncio
import json
import logging
import os
import tempfile
import time

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.database import check_connection, get_pool
from app.feature_registry import grouped as grouped_features
from app.guide_docs import list_docs as list_guide_docs
from app.guide_docs import read_doc as read_guide_doc
from app.llm_client import get_available_providers
from app.select_ai import (
    apply_annotations,
    ask_select_ai,
    execute_raw_sql,
    get_current_schema,
    get_explain_plan,
    get_profile_attributes,
    get_schema_info,
    list_profiles,
    remove_annotations,
    set_profile,
)
from app.vector_search import (
    compare_search,
    create_vector_tables_explicit,
    delete_document,
    drop_onnx_model,
    drop_vector_tables,
    generate_rag_answer,
    get_embedding_info,
    get_index_info,
    get_onnx_model_detail,
    get_onnx_models,
    get_vector_visualization,
    hybrid_search,
    keyword_search,
    list_documents,
    load_onnx_model,
    load_onnx_model_cloud,
    query_explain_plan,
    query_recent_sql,
    query_table_data,
    query_table_definition,
    query_table_indexes,
    test_onnx_model,
    upload_document,
    vector_search,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

VALID_ACTIONS = {"runsql", "showsql", "narrate", "explainsql", "showprompt", "summarize", "chat"}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB


class AskRequest(BaseModel):
    prompt: str
    action: str = "runsql"
    profile_name: str = ""


class VectorSearchRequest(BaseModel):
    query: str
    mode: str = "vector"  # "vector", "keyword", "compare"
    top_k: int = 5
    profile_name: str = ""
    provider: str = ""


class SetProfileRequest(BaseModel):
    profile_name: str


class ExecuteSqlRequest(BaseModel):
    sql: str


class EmbeddingInfoRequest(BaseModel):
    text: str


# === Existing NL2SQL Endpoints ===

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

    start = time.time()
    try:
        result = await ask_select_ai(pool, prompt, req.action, req.profile_name)
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
    """사용자가 입력한 SQL을 직접 실행"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    start = time.time()
    try:
        result = await execute_raw_sql(pool, req.sql)
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


@router.get("/health")
async def health():
    """DB 연결·스키마·버전·프로필 수·문서/청크/임베딩 수·ONNX 모델·벡터 인덱스 상태를 한 번에 반환한다."""
    connected = await check_connection()
    schema = None
    db_version = None
    profile_count = 0
    doc_count = 0
    chunk_count = 0
    embedded_count = 0
    onnx_models = []
    vector_index_status = None

    if connected:
        pool = await get_pool()
        try:
            schema = await get_current_schema(pool)
        except Exception as e:
            logger.warning("[health] 스키마 조회 실패: %s", e)

        # DB 버전
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT banner_full FROM v$version WHERE ROWNUM = 1")
                    row = await cur.fetchone()
                    if row:
                        db_version = row[0]
        except Exception as e:
            logger.warning("[health] DB 버전 조회 실패: %s", e)

        # 프로필 수
        try:
            result = await list_profiles(pool)
            profile_count = len(result)
        except Exception as e:
            logger.warning("[health] AI 프로필 조회 실패: %s", e)

        # 문서/청크/임베딩 수
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT COUNT(*) FROM documents WHERE status = 'indexed'")
                    row = await cur.fetchone()
                    doc_count = row[0] if row else 0

                    await cur.execute("SELECT COUNT(*), SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) FROM doc_chunks")
                    row = await cur.fetchone()
                    chunk_count = row[0] if row else 0
                    embedded_count = row[1] if row and row[1] else 0
        except Exception as e:
            logger.warning("[health] 문서/청크 수 조회 실패: %s", e)

        # ONNX 모델 목록
        # get_onnx_models()는 dict가 아니라 list를 반환한다(vector_search.py:801).
        # 2026-09-04 이전에는 .get("models")를 호출해 AttributeError가 났고, 아래 except가
        # 조용히 삼켜서 /health가 5개월간 onnx_models=[] 로 거짓 보고했다(실제로는 2개 존재).
        # 예외를 삼키더라도 로그는 남긴다 — 발화하지 않는 실패는 없는 실패와 같다.
        try:
            from app.vector_search import get_onnx_models
            onnx_models = await get_onnx_models(pool)
        except Exception as e:
            logger.warning("[health] ONNX 모델 목록 조회 실패: %s", e)

        # 벡터 인덱스 상태
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT index_name, status FROM user_indexes
                        WHERE index_name LIKE '%HNSW%' OR index_name LIKE '%VECTOR%'
                    """)
                    rows = await cur.fetchall()
                    if rows:
                        vector_index_status = [{"name": r[0], "status": r[1]} for r in rows]
        except Exception as e:
            logger.warning("[health] 벡터 인덱스 상태 조회 실패: %s", e)

    from app.config import settings
    return {
        "status": "ok" if connected else "error",
        "database_connected": connected,
        "schema": schema,
        "db_version": db_version,
        "profile_count": profile_count,
        "doc_count": doc_count,
        "chunk_count": chunk_count,
        "embedded_count": embedded_count,
        "onnx_models": onnx_models,
        "vector_index_status": vector_index_status,
        "embedding_source": settings.EMBEDDING_SOURCE,
        "embedding_model": settings.EMBEDDING_MODEL,
        "llm_provider": settings.LLM_PROVIDER,
    }


# === Vector Search Endpoints ===

@router.post("/vector/upload")
async def vector_upload(file: UploadFile = File(...)):
    """PDF 파일 업로드 -> SSE 스트리밍으로 실시간 진행 상황 전달"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "파일 크기가 10MB를 초과합니다."},
        )

    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "PDF 파일만 업로드 가능합니다."},
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

    fname = file.filename
    tmp = tmp_path

    async def event_stream():
        queue = asyncio.Queue()

        async def on_progress(event_type, data):
            await queue.put((event_type, data))

        async def run_pipeline():
            try:
                await upload_document(pool, tmp, fname, progress_callback=on_progress)
            except Exception as e:
                await queue.put(("error", {"message": str(e)}))
            finally:
                await queue.put(None)  # sentinel

        task = asyncio.create_task(run_pipeline())

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event_type, data = item
                yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
            if not task.done():
                task.cancel()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
        elif req.mode == "hybrid":
            search_result = await hybrid_search(pool, req.query, req.top_k)
        elif req.mode == "keyword":
            search_result = await keyword_search(pool, req.query, req.top_k)
        else:
            search_result = await vector_search(pool, req.query, req.top_k)

        # RAG 답변 생성 (외부 LLM API 사용)
        answer = ""
        if search_result["chunks"]:
            answer = await generate_rag_answer(req.query, search_result["chunks"], provider=req.provider or None)

        elapsed_ms = int((time.time() - start) * 1000)

        result_data = {
            "success": True,
            "mode": req.mode,
            "answer": answer,
            "chunks": search_result["chunks"],
            "match_count": search_result["match_count"],
            "sql_executed": search_result["sql_executed"],
            "elapsed_ms": elapsed_ms,
        }
        # 하이브리드 검색 추가 정보
        if req.mode == "hybrid":
            result_data["vector_weight"] = search_result.get("vector_weight", 0.7)
            result_data["keyword_weight"] = search_result.get("keyword_weight", 0.3)
            if search_result.get("hybrid_fallback"):
                result_data["hybrid_fallback"] = True
                result_data["hybrid_note"] = search_result.get("hybrid_note", "")
        return result_data

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


# === Vector Store Table Management Endpoints ===

@router.post("/vector/drop-tables")
async def vector_drop_tables():
    """Vector Store 테이블 삭제"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        result = await drop_vector_tables(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.post("/vector/create-tables")
async def vector_create_tables():
    """Vector Store 테이블 생성/연결"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        result = await create_vector_tables_explicit(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


class TableQueryRequest(BaseModel):
    table_name: str = "DOC_CHUNKS"
    limit: int = 50


@router.post("/vector/table-definition")
async def vector_table_definition(req: TableQueryRequest):
    """테이블 컬럼 정의 조회"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        result = await query_table_definition(pool, req.table_name)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.post("/vector/table-data")
async def vector_table_data(req: TableQueryRequest):
    """테이블 데이터 조회"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        result = await query_table_data(pool, req.table_name, req.limit)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.post("/vector/table-indexes")
async def vector_table_indexes(req: TableQueryRequest):
    """테이블 인덱스 조회"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        result = await query_table_indexes(pool, req.table_name)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.get("/vector/recent-queries")
async def vector_recent_queries():
    """V$SQL에서 최근 벡터 관련 쿼리 조회"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        result = await query_recent_sql(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.post("/vector/explain-plan")
async def vector_explain_plan():
    """벡터 검색 SQL의 실행 계획 조회"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        result = await query_explain_plan(pool)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


class VectorVisRequest(BaseModel):
    query: str
    matched_chunk_ids: list = []


@router.post("/vector/visualize")
async def vector_visualize(req: VectorVisRequest):
    """청크 임베딩을 2D PCA로 축소하여 시각화 데이터 반환"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        result = await get_vector_visualization(pool, req.query, req.matched_chunk_ids)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


# === JSON Relational Duality Endpoints ===



@router.get("/llm/providers")
async def llm_providers():
    """사용 가능한 LLM 제공자 목록 반환 (기본 제공자 포함)"""
    from app.config import settings
    return {"success": True, "providers": get_available_providers(), "default": settings.LLM_PROVIDER}


# === Embedding Config Endpoints ===

class EmbeddingConfigRequest(BaseModel):
    source: str = ""  # "database" or "external"
    model: str = ""
    reset_model: bool = False  # True이면 소스에 맞는 기본 모델로 자동 설정


@router.get("/vector/embedding-config")
async def get_embedding_config():
    """현재 임베딩 설정 반환"""
    from app.config import settings
    return {
        "success": True,
        "source": settings.EMBEDDING_SOURCE,
        "model": settings.EMBEDDING_MODEL,
        "external_api_url": settings.EMBEDDING_API_URL or "(미설정)",
        "external_api_key_set": bool(settings.EMBEDDING_API_KEY),
    }


@router.post("/vector/embedding-config")
async def update_embedding_config(req: EmbeddingConfigRequest):
    """임베딩 설정 런타임 변경 (서버 재시작 시 .env 값으로 복원)"""
    from app.config import settings
    changed = []
    if req.source and req.source in ("database", "external"):
        settings.EMBEDDING_SOURCE = req.source
        changed.append(f"source → {req.source}")

        # 소스 전환 시 기본 모델 자동 설정
        if req.reset_model and not req.model:
            if req.source == "external":
                default_model = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
                settings.EMBEDDING_MODEL = default_model
                changed.append(f"model → {default_model}")
            # database의 경우 ONNX 모델 목록에서 첫 번째를 자동 선택 (프론트에서 처리)

    if req.model:
        settings.EMBEDDING_MODEL = req.model
        changed.append(f"model → {req.model}")

    if not changed:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "변경할 설정이 없습니다."},
        )

    return {
        "success": True,
        "message": f"임베딩 설정 변경: {', '.join(changed)}",
        "source": settings.EMBEDDING_SOURCE,
        "model": settings.EMBEDDING_MODEL,
    }


@router.get("/vector/onnx-models")
async def vector_onnx_models():
    """DB에 로드된 ONNX 임베딩 모델 목록 조회"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        models = await get_onnx_models(pool)
        return {"success": True, "models": models}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


MAX_ONNX_SIZE = 3 * 1024 * 1024 * 1024  # 3GB


@router.post("/vector/onnx-models/upload")
async def vector_onnx_upload(
    file: UploadFile = File(...),
    model_name: str = Form(...),
):
    """ONNX 파일 업로드 → DB 모델 적재"""
    if not file.filename.lower().endswith(".onnx"):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": ".onnx 파일만 업로드 가능합니다."},
        )

    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    # 모델명 정규화 (대문자, 특수문자 제거)
    clean_name = model_name.strip().upper().replace("-", "_").replace(" ", "_")
    if not clean_name:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "모델명을 입력해 주세요."},
        )

    start = time.time()
    try:
        onnx_data = await file.read()
        if len(onnx_data) > MAX_ONNX_SIZE:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "파일 크기가 3GB를 초과합니다."},
            )

        result = await load_onnx_model(pool, clean_name, onnx_data)
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "success": True,
            "model_name": result["model_name"],
            "size_mb": round(result["size_bytes"] / (1024 * 1024), 1),
            "elapsed_ms": elapsed_ms,
            "message": f"모델 '{clean_name}'이(가) DB에 적재되었습니다.",
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e), "elapsed_ms": elapsed_ms},
        )


@router.post("/vector/onnx-models/load-cloud")
async def vector_onnx_load_cloud(req: Request):
    """OCI Object Storage에서 ONNX 모델을 가져와 DB에 적재"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    body = await req.json()
    location_uri = body.get("location_uri", "").strip()
    onnx_file_name = body.get("onnx_file_name", "").strip()
    model_name = body.get("model_name", "").strip()

    if not location_uri or not onnx_file_name:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Location URI와 ONNX 파일명을 입력해 주세요."},
        )

    # 모델명이 없으면 파일명에서 추출
    if not model_name:
        model_name = onnx_file_name.replace(".onnx", "").replace(".", "_").upper()

    try:
        result = await load_onnx_model_cloud(pool, model_name, location_uri, onnx_file_name)
        return {
            "success": True,
            **result,
            "message": f"모델 '{result['model_name']}'이(가) Object Storage에서 DB에 적재되었습니다.",
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.delete("/vector/onnx-models/{model_name}")
async def vector_onnx_delete(model_name: str):
    """DB에서 ONNX 모델 삭제"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        result = await drop_onnx_model(pool, model_name.upper())
        return {"success": True, **result, "message": f"모델 '{model_name}'이(가) 삭제되었습니다."}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.post("/vector/onnx-models/test")
async def vector_onnx_test(req: Request):
    """ONNX 모델 테스트 (샘플 임베딩 생성)"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    body = await req.json()
    model_name = body.get("model_name", "")
    sample_text = body.get("sample_text", "한국어 임베딩 테스트 문장입니다.")

    if not model_name:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "모델명을 지정해 주세요."},
        )

    try:
        result = await test_onnx_model(pool, model_name.upper(), sample_text)
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@router.get("/vector/onnx-models/{model_name}/detail")
async def vector_onnx_detail(model_name: str):
    """ONNX 모델 상세 정보 조회"""
    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "데이터베이스에 연결되지 않았습니다."},
        )

    try:
        detail = await get_onnx_model_detail(pool, model_name.upper())
        return {"success": True, **detail}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )



# === 인앱 매뉴얼 (「매뉴얼」 탭) ===
#
# docs/ 의 마크다운을 앱 화면에서 바로 읽게 한다(계획서 3-1·3-2).
# 소스 폴더를 뒤지지 않아도 되게 하는 것이 목적이며, 특히 몇 달 뒤에 다시 열었을 때
# "이 앱이 지금 어떤 상태인가"를 화면에서 확인할 수 있어야 한다.
#
# 화이트리스트에 없는 key 는 절대 열지 않는다. 새 가이드를 만들면 여기 한 줄 추가해야
# 화면에 뜬다 — docs/README.md 에도 같이 적을 것.

_GUIDE_WHITELIST = {
    "user-guide":      ("01", "사용자 가이드", "6탭 전 기능의 사용법과 취지"),
    "ops-guide":       ("02", "운영 가이드", "기동·배포·백업·DB 접속"),
    "troubleshooting": ("03", "트러블슈팅", "증상 → 원인 → 조치"),
    "demo-guide":      ("04", "데모 시연 가이드", "발표용 시연 시나리오와 준비 체크리스트"),
}

# docs/ 최상위에 있는 문서(가이드가 아니라 현황·계획 문서)
_ROOT_DOC_WHITELIST = {
    "handoff":  ("SESSION_HANDOFF", "현재 상태", "환경 실측 스냅샷 · 직전 세션 · 열린 과제"),
    "features": ("FEATURES", "기능 설명서", "6탭 기능 상세 (2026-04 작성)"),
    "roadmap":  ("ROADMAP", "업데이트 계획서", "Phase 0~6 · 작업별 권고 모델·공수"),
}


@router.get("/guide/docs")
async def guide_doc_list():
    """앱에서 열람 가능한 문서 목록을 반환한다 (가이드 + 현황 문서)."""
    return {
        "success": True,
        "guides": list_guide_docs(_GUIDE_WHITELIST, "guides"),
        "docs": list_guide_docs(_ROOT_DOC_WHITELIST, ""),
    }


@router.get("/guide/docs/{key}")
async def guide_doc(key: str):
    """단일 문서의 마크다운 원문을 반환한다 (화이트리스트 key 만)."""
    d = read_guide_doc(_GUIDE_WHITELIST, key, "guides")
    if d is None:
        d = read_guide_doc(_ROOT_DOC_WHITELIST, key, "")
    if d is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": f"문서를 찾을 수 없습니다: {key}"},
        )
    return {"success": True, **d}


@router.get("/guide/features")
async def guide_features():
    """기능 지도 — 6탭 전 기능 카탈로그 (정본: app/feature_registry.py)."""
    groups = grouped_features()
    return {
        "success": True,
        "groups": groups,
        "total": sum(len(g["items"]) for g in groups),
    }
