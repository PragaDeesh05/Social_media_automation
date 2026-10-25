from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application
    PROJECT_NAME: str = "IncuBrix AI Social Automation"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8005
    BACKEND_URL: str = "http://localhost:8005"
    FRONTEND_URL: str = "http://localhost:5174"
    DEFAULT_TIMEZONE: str = "UTC"
    SECRET_KEY: str = "incubrix_jwt_super_secret_production_ready_key_12345"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    APP_ENCRYPTION_KEY: str = "0AXpWzyjL_twEUX2QZwEJqxia8g4fl0NyX3BJ_2NTVw="

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8005",
        "http://127.0.0.1:8005",
        "*"
    ]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://incubrix:incubrix_dev@localhost:5434/incubrix_social"
    SYNC_DATABASE_URL: str = "postgresql://incubrix:incubrix_dev@localhost:5434/incubrix_social"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9100"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "incubrix-assets"
    MINIO_SECURE: bool = False

    # AI - Gemini & Vertex AI
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_FALLBACK_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_CAROUSEL_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_CAROUSEL_FALLBACK_MODEL: str = "gemini-3.1-flash-lite"
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # Meta
    META_APP_ID: Optional[str] = None
    META_APP_SECRET: Optional[str] = None
    META_REDIRECT_URI: str = "http://localhost:8005/api/v1/oauth/meta/callback"

    # Live Authenticated Platform Tokens (Backend Integration Alone)
    FACEBOOK_ACCESS_TOKEN: Optional[str] = None
    FACEBOOK_PAGE_ACCESS_TOKEN: Optional[str] = None
    FACEBOOK_PAGE_ID: Optional[str] = "1539128952609697"
    FACEBOOK_PAGE_NAME: Optional[str] = "Incubrix"

    INSTAGRAM_ACCESS_TOKEN: Optional[str] = None
    INSTAGRAM_ACCOUNT_ID: Optional[str] = "28810961191905769"
    INSTAGRAM_USERNAME: Optional[str] = "ish_uu.05"

    YOUTUBE_ACCESS_TOKEN: Optional[str] = None

    # X
    X_CLIENT_ID: Optional[str] = None
    X_CLIENT_SECRET: Optional[str] = None
    X_REDIRECT_URI: str = "http://localhost:8005/api/v1/oauth/x/callback"

    # YouTube
    YOUTUBE_CLIENT_ID: Optional[str] = None
    YOUTUBE_CLIENT_SECRET: Optional[str] = None
    YOUTUBE_REFRESH_TOKEN: Optional[str] = None
    YOUTUBE_REDIRECT_URI: str = "http://localhost:8005/api/v1/oauth/youtube/callback"

    # Ingestion Limits
    MAX_UPLOAD_SIZE_MB: int = 150
    MAX_MEDIA_DURATION_SECONDS: int = 3600  # 1 hour max

    # Worker & Scheduling
    WORKER_CONCURRENCY: int = 4
    SCHEDULER_POLL_INTERVAL_SECONDS: int = 10
    MAX_PUBLISH_RETRIES: int = 3
    RETRY_BACKOFF_BASE_SECONDS: int = 15


from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FINAL_DIR = BASE_DIR / "assets" / "final"
VIDEOS_DIR = FINAL_DIR / "videos"
CAROUSELS_DIR = FINAL_DIR / "carousels"
GRAPHICS_DIR = FINAL_DIR / "graphics"
SOURCE_DIR = BASE_DIR / "assets" / "source"

for d in [VIDEOS_DIR, CAROUSELS_DIR, GRAPHICS_DIR, SOURCE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

settings = Settings()
