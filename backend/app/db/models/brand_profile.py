import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class BrandProfile(Base):
    __tablename__ = "brand_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_audience: Mapped[str] = mapped_column(Text, nullable=False)
    tone_of_voice: Mapped[str] = mapped_column(String(100), default="Conversational, Authoritative, Action-Oriented")
    vocabulary_rules: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    words_to_avoid: Mapped[List[str]] = mapped_column(JSONB, default=list)
    default_cta: Mapped[str] = mapped_column(String(255), default="Learn more → incubrix.com")
    primary_color: Mapped[str] = mapped_column(String(20), default="#4F46E5")
    secondary_color: Mapped[str] = mapped_column(String(20), default="#0F172A")
    font_family: Mapped[str] = mapped_column(String(50), default="Inter, sans-serif")
    verified_product_facts: Mapped[List[str]] = mapped_column(JSONB, default=list)
    approved_links: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list)
    disclosure_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", back_populates="brand_profiles")
    campaigns = relationship("Campaign", back_populates="brand_profile")
