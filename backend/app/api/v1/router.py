from fastapi import APIRouter

from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.brand_profiles import router as brand_router
from app.api.v1.routes.sources import router as sources_router
from app.api.v1.routes.campaigns import router as campaigns_router
from app.api.v1.routes.assets import router as assets_router
from app.api.v1.routes.calendar import router as calendar_router
from app.api.v1.routes.oauth import router as oauth_router
from app.api.v1.routes.connected_accounts import router as accounts_router
from app.api.v1.routes.publishing import router as publishing_router
from app.api.v1.routes.media import router as media_router
from app.api.v1.routes.analytics import router as analytics_router
from app.api.v1.routes.generation import router as generation_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(brand_router)
api_router.include_router(sources_router)
api_router.include_router(campaigns_router)
api_router.include_router(assets_router)
api_router.include_router(calendar_router)
api_router.include_router(oauth_router)
api_router.include_router(accounts_router)
api_router.include_router(publishing_router)
api_router.include_router(media_router)
api_router.include_router(analytics_router)
api_router.include_router(generation_router)
