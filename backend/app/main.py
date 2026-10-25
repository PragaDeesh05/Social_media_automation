import time
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import logger, correlation_id_ctx
from app.core.exceptions import IncuBrixException
from app.db.init_db import init_db
from app.api.v1.router import api_router

BASE_DIR = Path(__file__).resolve().parent.parent
FINAL_DIR = BASE_DIR / "assets" / "final"
VIDEOS_DIR = FINAL_DIR / "videos"
CAROUSELS_DIR = FINAL_DIR / "carousels"
GRAPHICS_DIR = FINAL_DIR / "graphics"
SOURCE_DIR = BASE_DIR / "assets" / "source"

for d in [VIDEOS_DIR, CAROUSELS_DIR, GRAPHICS_DIR, SOURCE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up IncuBrix Social Media Automation Engine...")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database initialization warning: {e}")
    yield
    logger.info("Shutting down IncuBrix Social Media Automation Engine...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-Powered Social Media Content & Automation Engine for IncuBrix",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Correlation ID Middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    cid = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex[:12]
    token = correlation_id_ctx.set(cid)
    t0 = time.time()
    try:
        response = await call_next(request)
        elapsed = time.time() - t0
        response.headers["X-Correlation-ID"] = cid
        response.headers["X-Process-Time"] = f"{elapsed:.4f}s"
        return response
    finally:
        correlation_id_ctx.reset(token)


# Exception Handlers
@app.exception_handler(IncuBrixException)
async def incubrix_exception_handler(request: Request, exc: IncuBrixException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.error_code,
            "detail": exc.detail,
            "extra": exc.extra
        }
    )


# Mount Static Media Directories for Direct Streaming
app.mount("/media/videos", StaticFiles(directory=str(VIDEOS_DIR)), name="videos")
app.mount("/media/carousels", StaticFiles(directory=str(CAROUSELS_DIR)), name="carousels")
app.mount("/media/graphics", StaticFiles(directory=str(GRAPHICS_DIR)), name="graphics")
app.mount("/media/source", StaticFiles(directory=str(SOURCE_DIR)), name="source")

# Mount API Router
app.include_router(api_router)

# Also expose /api/generate/... and /api/assets/... aliases for studio compatibility
api_alias = APIRouter(prefix="/api")
api_alias.include_router(api_router, prefix="")
from app.api.v1.routes.generation import generate_video_module, generate_carousel_module, generate_poster_module
from app.api.v1.routes.publishing import publish_asset_directly, schedule_asset_directly
api_alias.add_api_route("/generate/video", generate_video_module, methods=["POST"])
api_alias.add_api_route("/generate/carousel", generate_carousel_module, methods=["POST"])
api_alias.add_api_route("/generate/image", generate_poster_module, methods=["POST"])
api_alias.add_api_route("/publish/{asset_id}", publish_asset_directly, methods=["POST"])
api_alias.add_api_route("/schedule", schedule_asset_directly, methods=["POST"])
app.include_router(api_alias)


@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "api_prefix": "/api/v1"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
