import json
import os
import tempfile
import time

from fastapi import APIRouter, Form, Request, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

from app.database import get_pool, check_connection
from app.select_ai import (
    ask_select_ai, list_profiles, set_profile, get_profile_attributes,
    execute_raw_sql, get_current_schema, get_schema_info, get_explain_plan,
    get_annotations, apply_annotations, remove_annotations,
)
from app.awr_analyzer import (
    parse_awr_html,
    build_analysis_prompt,
    build_followup_prompt,
    analyze_awr_with_llm,
    followup_question,
)
from app.llm_client import get_available_providers
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
    drop_vector_tables,
    create_vector_tables_explicit,
    query_table_definition,
    query_table_data,
    query_table_indexes,
    query_recent_sql,
    query_explain_plan,
)

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


class SetProfileRequest(BaseModel):
    profile_name: str


class ExecuteSqlRequest(BaseModel):
    sql: str


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


# === AWR Analyzer Endpoints ===

# 서버 메모리에 최근 AWR 파싱 결과 캐싱 (후속 질문용)
_awr_cache: dict = {}

MAX_AWR_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB


class AWRFollowupRequest(BaseModel):
    question: str
    session_id: str = "default"
    provider: str = ""


@router.get("/llm/providers")
async def llm_providers():
    """사용 가능한 LLM 제공자 목록 반환"""
    return {"success": True, "providers": get_available_providers()}


@router.post("/awr/analyze")
async def awr_analyze(file: UploadFile = File(...), provider: str = Form("")):
    """AWR HTML 파일 업로드 → 파싱 → LLM 분석"""
    # 파일 유효성 검사
    if not file.filename.lower().endswith((".html", ".htm")):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "HTML 파일만 업로드 가능합니다."},
        )

    content = await file.read()
    if len(content) > MAX_AWR_UPLOAD_SIZE:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "파일 크기가 20MB를 초과합니다."},
        )

    start = time.time()
    try:
        # 1) HTML 파싱
        html_text = content.decode("utf-8", errors="replace")
        parsed = parse_awr_html(html_text)

        if parsed["section_count"] == 0:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "AWR 리포트에서 분석 가능한 섹션을 찾지 못했습니다. 유효한 AWR HTML 파일인지 확인해 주세요."},
            )

        parse_ms = int((time.time() - start) * 1000)

        # 2) LLM 분석 프롬프트 생성 및 호출 (제공자별 입력 크기 적용)
        from app.llm_client import get_max_input_chars
        llm_provider = provider or None
        max_chars = get_max_input_chars(llm_provider)
        prompt = build_analysis_prompt(parsed, max_input_chars=max_chars)
        llm_result = await analyze_awr_with_llm(prompt, provider=llm_provider)
        total_ms = int((time.time() - start) * 1000)

        # 캐싱 (후속 질문 + 원문 보기용)
        session_id = f"awr_{int(time.time())}"
        _awr_cache[session_id] = {
            "parsed": parsed,
            "summary": llm_result.get("summary", ""),
            "provider": provider,
            "html": html_text,  # 원문 HTML 저장 (원문 보기 기능용)
        }

        return {
            "success": True,
            "session_id": session_id,
            "analysis": llm_result,
            "parse_info": {
                "section_count": parsed["section_count"],
                "total_tables": parsed["total_tables"],
                "is_exadata": parsed["is_exadata"],
                "parse_ms": parse_ms,
            },
            "elapsed_ms": total_ms,
            "filename": file.filename,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        elapsed_ms = int((time.time() - start) * 1000)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e), "elapsed_ms": elapsed_ms},
        )


@router.post("/awr/followup")
async def awr_followup(req: AWRFollowupRequest):
    """AWR 분석 결과에 대한 후속 질문"""
    cached = _awr_cache.get(req.session_id)
    if not cached:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "이전 AWR 분석 세션을 찾을 수 없습니다. 파일을 다시 업로드해 주세요."},
        )

    start = time.time()
    try:
        prompt = build_followup_prompt(
            cached["parsed"],
            cached["summary"],
            req.question,
        )
        llm_provider = req.provider or cached.get("provider") or None
        answer = await followup_question(prompt, provider=llm_provider)
        elapsed_ms = int((time.time() - start) * 1000)

        return {
            "success": True,
            "answer": answer,
            "elapsed_ms": elapsed_ms,
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e), "elapsed_ms": elapsed_ms},
        )


@router.get("/awr/source/{session_id}")
async def awr_source_html(session_id: str, section: str = ""):
    """업로드된 AWR HTML 원문을 새 탭에서 볼 수 있도록 제공 (앵커 이동 지원)"""
    cached = _awr_cache.get(session_id)
    if not cached or "html" not in cached:
        return HTMLResponse(
            "<h2>AWR 원문을 찾을 수 없습니다. 파일을 다시 업로드해 주세요.</h2>",
            status_code=404,
        )

    html = cached["html"]

    # section 파라미터가 있으면 해당 텍스트 위치로 자동 스크롤 + 하이라이트
    if section:
        safe_target = section.replace("'", "\\'")
        scroll_script = f"""
<script>
(function() {{
    var target = '{safe_target}';
    var elems = document.querySelectorAll('h2, h3, caption, th, a[name], td');
    for (var i = 0; i < elems.length; i++) {{
        if (elems[i].textContent && elems[i].textContent.indexOf(target) >= 0) {{
            elems[i].scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            elems[i].style.backgroundColor = '#fff3cd';
            elems[i].style.padding = '4px 8px';
            elems[i].style.borderLeft = '4px solid #f59e0b';
            break;
        }}
    }}
}})();
</script>
"""
        if "</body>" in html.lower():
            idx = html.lower().rfind("</body>")
            html = html[:idx] + scroll_script + html[idx:]
        else:
            html += scroll_script

    return HTMLResponse(html)
