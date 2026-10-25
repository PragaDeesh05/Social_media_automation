import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brand_profiles.id", ondelete="SET NULL"), nullable=True)
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    platforms: Mapped[List[str]] = mapped_column(JSONB, default=list)  # ["instagram", "facebook", "youtube", "x"]
    formats: Mapped[List[str]] = mapped_column(JSONB, default=list)    # ["text", "image", "carousel", "short_video"]
    timezone_name: Mapped[str] = mapped_column(String(50), default="UTC")
    posting_times: Mapped[Dict[str, List[str]]] = mapped_column(JSONB, default=dict)  # {"instagram": ["09:00", "17:00"]}
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)  # draft, planning, generated, scheduled, active, completed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", back_populates="campaigns")
    brand_profile = relationship("BrandProfile", back_populates="campaigns")
    source_document = relationship("SourceDocument", back_populates="campaigns")
    plan = relationship("CampaignPlan", back_populates="campaign", uselist=False, cascade="all, delete-orphan")
    assets = relationship("ContentAsset", back_populates="campaign", cascade="all, delete-orphan")


class CampaignPlan(Base):
    __tablename__ = "campaign_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy_summary: Mapped[str] = mapped_column(Text, nullable=False)
    total_slots: Mapped[int] = mapped_column(Integer, default=0)
    pillar_distribution: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    schedule_matrix: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    campaign = relationship("Campaign", back_populates="plan")
