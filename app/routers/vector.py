"""AI Vector Search 라우터 — /api/vector/* (계획서 5-6 에서 routes.py 에서 분리, 2026-09-05).

경로·응답 불변. 검색·업로드·테이블·임베딩 설정·ONNX 관리 25개. 본체는 app/vector_search.py.
업로드(/upload)만 SSE(text/event-stream) — event: step | progress | done | error.
"""
import asyncio
import json
import logging
import os
import tempfile
import time

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.database import get_pool
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

router = APIRouter(prefix="/api/vector", tags=["vector"])

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB


class VectorSearchRequest(BaseModel):
    query: str
    mode: str = "vector"  # "vector", "keyword", "compare"
    top_k: int = 5
    profile_name: str = ""
    provider: str = ""


class EmbeddingInfoRequest(BaseModel):
    text: str



@router.post("/upload")
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


@router.post("/search")
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


@router.get("/documents")
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


@router.delete("/documents/{doc_id}")
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


@router.get("/index-info")
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


@router.post("/embedding-info")
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

@router.post("/drop-tables")
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


@router.post("/create-tables")
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


@router.post("/table-definition")
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


@router.post("/table-data")
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


@router.post("/table-indexes")
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


@router.get("/recent-queries")
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


@router.post("/explain-plan")
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


@router.post("/visualize")
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


# === 임베딩 설정 · ONNX 모델 ===

class EmbeddingConfigRequest(BaseModel):
    source: str = ""  # "database" or "external"
    model: str = ""
    reset_model: bool = False  # True이면 소스에 맞는 기본 모델로 자동 설정


@router.get("/embedding-config")
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


@router.post("/embedding-config")
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


@router.get("/onnx-models")
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


@router.post("/onnx-models/upload")
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


@router.post("/onnx-models/load-cloud")
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


@router.delete("/onnx-models/{model_name}")
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


@router.post("/onnx-models/test")
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


@router.get("/onnx-models/{model_name}/detail")
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
