import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.database import check_connection, get_pool
from app.feature_registry import grouped as grouped_features
from app.guide_docs import list_docs as list_guide_docs
from app.guide_docs import read_doc as read_guide_doc
from app.llm_client import get_available_providers
from app.select_ai import (
    get_current_schema,
    list_profiles,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


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


# === 공통 ===



@router.get("/llm/providers")
async def llm_providers():
    """사용 가능한 LLM 제공자 목록 반환 (기본 제공자 포함)"""
    from app.config import settings
    return {"success": True, "providers": get_available_providers(), "default": settings.LLM_PROVIDER}


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
