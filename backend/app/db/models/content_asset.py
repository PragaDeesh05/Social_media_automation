import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ContentAsset(Base):
    __tablename__ = "content_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True)
    slot_index: Mapped[int] = mapped_column(Integer, default=0, index=True)
    day_number: Mapped[int] = mapped_column(Integer, default=1, index=True)  # 1 to 30
    scheduled_slot_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # instagram, facebook, youtube, x
    format: Mapped[str] = mapped_column(String(50), nullable=False, index=True)    # text, image, carousel, short_video, reel, shorts
    hook: Mapped[str] = mapped_column(Text, default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[List[str]] = mapped_column(JSONB, default=list)
    cta: Mapped[str] = mapped_column(String(255), default="")
    tracking_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    utm_parameters: Mapped[Dict[str, str]] = mapped_column(JSONB, default=dict)
    source_references: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list)  # quotes, timestamps, evidence
    approval_status: Mapped[str] = mapped_column(String(50), default="pending_approval", index=True)  # draft, pending_approval, approved, rejected
    quality_status: Mapped[str] = mapped_column(String(50), default="pending", index=True)  # pending, passed, warnings, failed
    quality_checks: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    duplicate_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    campaign = relationship("Campaign", back_populates="assets")
    versions = relationship("AssetVersion", back_populates="content_asset", cascade="all, delete-orphan", order_by="AssetVersion.version_number.desc()")
    media = relationship("AssetMedia", back_populates="content_asset", cascade="all, delete-orphan", order_by="AssetMedia.slide_index.asc()")
    scheduled_posts = relationship("ScheduledPost", back_populates="content_asset", cascade="all, delete-orphan")


class AssetVersion(Base):
    __tablename__ = "asset_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    hook: Mapped[str] = mapped_column(Text, default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[List[str]] = mapped_column(JSONB, default=list)
    cta: Mapped[str] = mapped_column(String(255), default="")
    tracking_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    content_asset = relationship("ContentAsset", back_populates="versions")


class AssetMedia(Base):
    __tablename__ = "asset_media"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    media_type: Mapped[str] = mapped_column(String(50), nullable=False)  # image, carousel_slide, video, audio, subtitles, editable_source
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    minio_object_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    slide_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    editable_config: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)  # scenes JSON, layout JSON, prompt JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    content_asset = relationship("ContentAsset", back_populates="media")
