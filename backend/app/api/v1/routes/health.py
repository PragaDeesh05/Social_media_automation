from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis

from app.core.config import settings
from app.db.session import get_db
from app.services.storage.minio_service import storage_service
from app.services.ai.gemini_adapter import gemini_adapter

router = APIRouter(tags=["Health & Status"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Comprehensive readiness and liveness check for all infrastructure services."""
    # 1. PostgreSQL check
    db_status = "unhealthy"
    try:
        await db.execute(text("SELECT 1;"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {e}"

    # 2. Redis check
    redis_status = "unhealthy"
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2)
        if r.ping():
            redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {e}"

    # 3. MinIO check
    minio_health = storage_service.health_check()

    # 4. Gemini AI Provider check
    gemini_health = gemini_adapter.check_availability()

    is_overall_healthy = (
        db_status == "healthy" and
        redis_status == "healthy" and
        minio_health.get("connected", False)
    )

    return {
        "status": "healthy" if is_overall_healthy else "degraded",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "services": {
            "database": {"status": db_status, "engine": "PostgreSQL 16"},
            "redis": {"status": redis_status, "url": settings.REDIS_URL},
            "minio": minio_health,
            "ai_provider": gemini_health
        }
    }
