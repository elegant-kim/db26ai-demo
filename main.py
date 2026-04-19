import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import init_pool, close_pool, get_pool
from app.routes import router as api_router
from app.scheduler import init_scheduler, shutdown_scheduler
from app.vector_search import init_vector_tables

app = FastAPI(title="Oracle AI Database 26ai 데모")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(api_router)


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


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"default_profile": settings.SELECT_AI_PROFILE},
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
    )
