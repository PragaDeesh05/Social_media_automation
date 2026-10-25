import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    __table_args__ = (
        UniqueConstraint("content_asset_id", "connected_account_id", name="uq_scheduled_posts_asset_acc"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    connected_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("connected_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    scheduled_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    original_timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    status: Mapped[str] = mapped_column(String(50), default="scheduled", index=True)  # pending, scheduled, publishing, published, failed, cancelled
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), default=lambda: uuid.uuid4().hex, index=True)
    published_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_post_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    content_asset = relationship("ContentAsset", back_populates="scheduled_posts")
    connected_account = relationship("ConnectedAccount", back_populates="scheduled_posts")
    attempts = relationship("PublishingAttempt", back_populates="scheduled_post", cascade="all, delete-orphan", order_by="PublishingAttempt.attempt_number.asc()")
    analytics = relationship("AnalyticsSnapshot", back_populates="scheduled_post", cascade="all, delete-orphan")


class PublishingAttempt(Base):
    __tablename__ = "publishing_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheduled_post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduled_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # success, error
    http_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    scheduled_post = relationship("ScheduledPost", back_populates="attempts")
