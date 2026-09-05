import asyncio
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import close_pool, get_pool, init_pool
from app.routers import duality as duality_router
from app.routers import graph as graph_router
from app.routers import productivity as productivity_router
from app.routes import router as api_router
from app.scheduler import init_scheduler, shutdown_scheduler
from app.vector_search import init_vector_tables, warm_embedding_pool

app = FastAPI(title="Oracle AI Database 26ai 데모")

# ── 프론트 공존 서빙 (SPA 이식 기간, 설계서 05 §5.1) ──
#   /api/*   → 라우터 (아래 include_router — 가장 먼저 매칭)
#   /static  → 레거시 정적파일 (이식 완료 시 제거)
#   /assets  → SPA 빌드 산출물 (web/dist/assets)
#   /legacy  → 레거시 화면 (templates/index.html)
#   /{path}  → SPA index.html. dist 가 없으면 레거시로 폴백 = 롤백은 `rm -rf web/dist` 한 동작
BASE_DIR = Path(__file__).resolve().parent
DIST = BASE_DIR / "web" / "dist"

app.mount("/static", StaticFiles(directory="static"), name="static")
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(DIST / "assets")), name="spa-assets")
templates = Jinja2Templates(directory="templates")

app.include_router(api_router)
app.include_router(graph_router.router)   # 탭을 이식할 때마다 하나씩 늘어난다 (설계서 05 §7)
app.include_router(productivity_router.router)
app.include_router(duality_router.router)


@app.on_event("startup")
async def startup():
    try:
        await init_pool()
        print("✓ 데이터베이스 연결 풀이 초기화되었습니다.")

        # Vector Search 테이블 초기화
        pool = await get_pool()
        if pool is not None:
            try:
                await init_vector_tables(pool)
                print("✓ Vector Search 테이블이 초기화되었습니다.")
            except Exception as e:
                print(f"⚠ Vector Search 테이블 초기화 실패 (무시됨): {e}")

        # 커넥션 풀 워밍 — ONNX 모델은 커넥션마다 최초 1회 로드에 수 초가 걸린다.
        # 서버 기동을 막지 않도록 백그라운드 태스크로 돌린다(사용자가 첫 클릭을
        # 하기 전에 끝난다). 자세한 배경은 warm_embedding_pool docstring 참조.
        if pool is not None:
            async def _warm():
                try:
                    r = await warm_embedding_pool(pool)
                    if r.get("skipped"):
                        print(f"· 커넥션 풀 워밍 생략: {r['skipped']}")
                    else:
                        print(f"✓ 커넥션 풀 워밍 완료: {r['warmed']}/{r['target']}개 "
                              f"({r['model']}, {r['elapsed_ms']}ms)")
                except Exception as e:
                    print(f"⚠ 커넥션 풀 워밍 실패 (무시됨): {e}")

            asyncio.create_task(_warm())

        # ADB Keepalive 스케줄러 시작 (주 1회 SELECT 1 핑)
        try:
            init_scheduler()
            print("✓ ADB Keepalive 스케줄러가 시작되었습니다 (매주 월 09:00).")
        except Exception as e:
            print(f"⚠ Keepalive 스케줄러 시작 실패 (무시됨): {e}")
    except Exception as e:
        print(f"✗ 데이터베이스 연결 실패: {e}")


@app.on_event("shutdown")
async def shutdown():
    try:
        shutdown_scheduler()
    except Exception:
        pass
    await close_pool()
    print("✓ 데이터베이스 연결 풀이 종료되었습니다.")


@app.get("/legacy", include_in_schema=False)
async def legacy(request: Request):
    """이식 전 탭이 열리는 기존 화면. `/legacy#vector` 처럼 해시로 탭을 지정한다."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"default_profile": settings.SELECT_AI_PROFILE},
    )


@app.get("/{path:path}", include_in_schema=False)
async def spa(path: str, request: Request):
    """SPA 엔트리. dist 안의 실제 파일(favicon 등)은 그대로, 그 외 경로는 index.html (history 라우팅)."""
    # 알 수 없는 /api/* 는 SPA 셸이 아니라 JSON 404 — API 클라이언트가 HTML 을 받으면 안 된다
    if path.startswith("api/") or path == "api":
        return JSONResponse(status_code=404, content={"success": False, "error": f"알 수 없는 API 경로: /{path}"})
    index = DIST / "index.html"
    if index.is_file():
        if path:
            cand = (DIST / path).resolve()
            if cand.is_file() and str(cand).startswith(str(DIST.resolve()) + "/"):
                return FileResponse(cand)
        return FileResponse(index)
    return await legacy(request)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
    )
