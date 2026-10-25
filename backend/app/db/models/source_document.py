import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # article, blog, podcast, webinar, video, audio, transcript, document, script
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    minio_object_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    media_duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)  # pending, processing, ready, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", back_populates="source_documents")
    extraction = relationship("SourceExtraction", back_populates="source_document", uselist=False, cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="source_document")


class SourceExtraction(Base):
    __tablename__ = "source_extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), unique=True, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    clean_transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    main_subject: Mapped[str] = mapped_column(String(255), default="")
    audience_intent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topics: Mapped[List[str]] = mapped_column(JSONB, default=list)
    subtopics: Mapped[List[str]] = mapped_column(JSONB, default=list)
    key_claims: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list)
    quotes_with_timestamps: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list)
    content_opportunities: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list)
    chunk_metadata: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    source_document = relationship("SourceDocument", back_populates="extraction")
