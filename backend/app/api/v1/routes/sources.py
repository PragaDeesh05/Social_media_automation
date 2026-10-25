import os
import uuid
import tempfile
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.session import get_db, AsyncSessionLocal
from app.db.models import User, SourceDocument, SourceExtraction
from app.api.deps import get_current_user
from app.services.storage.minio_service import storage_service
from app.services.ingestion.document_extractor import DocumentExtractor
from app.services.ingestion.video_inspector import VideoInspector
from app.services.ingestion.audio_transcriber import AudioTranscriber
from app.services.ai.content_analyzer import content_analyzer
from app.core.logging import logger

router = APIRouter(prefix="/sources", tags=["Source Ingestion"])


class TextIngestRequest(BaseModel):
    title: str
    text_content: Optional[str] = None
    url: Optional[str] = None
    source_type: str = "article"


class ExtractionUpdateRequest(BaseModel):
    clean_transcript: Optional[str] = None
    main_subject: Optional[str] = None
    topics: Optional[list] = None


async def run_source_analysis_background(source_id: uuid.UUID, raw_text: str, source_type: str):
    """Background task for comprehensive AI content analysis."""
    async with AsyncSessionLocal() as session:
        try:
            analysis = await content_analyzer.analyze_source(raw_text, source_type=source_type)
            # Update extraction
            ext_res = await session.execute(select(SourceExtraction).where(SourceExtraction.source_document_id == source_id))
            extraction = ext_res.scalar_one_or_none()
            if extraction:
                extraction.main_subject = analysis.get("main_subject", "")
                extraction.audience_intent = analysis.get("audience_intent", "")
                extraction.topics = analysis.get("topics", [])
                extraction.subtopics = analysis.get("subtopics", [])
                extraction.key_claims = analysis.get("key_claims", [])
                extraction.quotes_with_timestamps = analysis.get("quotes_with_timestamps", [])
                extraction.content_opportunities = analysis.get("content_opportunities", [])

            # Update document status
            doc_res = await session.execute(select(SourceDocument).where(SourceDocument.id == source_id))
            doc = doc_res.scalar_one_or_none()
            if doc:
                doc.status = "ready"
            await session.commit()
            logger.info(f"Source {source_id} AI analysis complete.")
        except Exception as e:
            logger.error(f"Error in background source analysis for {source_id}: {e}")
            doc_res = await session.execute(select(SourceDocument).where(SourceDocument.id == source_id))
            doc = doc_res.scalar_one_or_none()
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)
                await session.commit()


@router.post("/upload")
async def upload_source_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Uploads file to MinIO, inspects metadata, extracts text/audio, and analyzes."""
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    source_title = title or os.path.splitext(filename)[0]

    # Map source type
    if ext in (".mp4", ".mov", ".avi", ".mkv"):
        source_type = "video"
    elif ext in (".mp3", ".wav", ".m4a", ".aac"):
        source_type = "audio"
    elif ext == ".pdf":
        source_type = "pdf"
    elif ext in (".docx", ".doc"):
        source_type = "docx"
    else:
        source_type = "document"

    source_id = uuid.uuid4()
    object_key = f"users/{current_user.id}/sources/{source_id}/original{ext}"

    # Read bytes
    file_bytes = await file.read()
    file_size = len(file_bytes)

    # Upload to MinIO
    storage_service.upload_bytes(
        object_key=object_key,
        data=file_bytes,
        content_type=file.content_type or "application/octet-stream"
    )

    # Create SourceDocument record
    doc = SourceDocument(
        id=source_id,
        user_id=current_user.id,
        title=source_title,
        source_type=source_type,
        original_filename=filename,
        file_size_bytes=file_size,
        mime_type=file.content_type,
        minio_object_key=object_key,
        status="processing"
    )
    db.add(doc)
    await db.flush()

    # Extract text based on file type
    extracted_text = ""
    duration_sec = None

    if source_type in ("video", "audio"):
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_input = os.path.join(tmp_dir, f"input{ext}")
            with open(temp_input, "wb") as f:
                f.write(file_bytes)

            probe = VideoInspector.probe_media(temp_input)
            duration_sec = probe.get("duration_seconds")
            doc.media_duration_seconds = duration_sec

            if source_type == "video":
                wav_path = os.path.join(tmp_dir, "extracted.wav")
                VideoInspector.extract_audio(temp_input, wav_path)
                transcription = await AudioTranscriber.transcribe_audio_file(wav_path)
            else:
                transcription = await AudioTranscriber.transcribe_audio_file(temp_input)

            extracted_text = transcription.get("full_transcript", "")
    elif source_type == "pdf":
        extracted_text = DocumentExtractor.extract_from_pdf_bytes(file_bytes)
    elif source_type == "docx":
        extracted_text = DocumentExtractor.extract_from_docx_bytes(file_bytes)
    else:
        extracted_text = DocumentExtractor.extract_from_text(file_bytes.decode("utf-8", errors="ignore"))

    # Create extraction
    extraction = SourceExtraction(
        source_document_id=doc.id,
        raw_text=extracted_text,
        clean_transcript=extracted_text,
        main_subject=source_title
    )
    db.add(extraction)
    await db.commit()

    # Launch background AI analysis
    background_tasks.add_task(run_source_analysis_background, doc.id, extracted_text, source_type)

    return {
        "id": doc.id,
        "title": doc.title,
        "source_type": doc.source_type,
        "status": doc.status,
        "media_duration_seconds": duration_sec,
        "message": "File uploaded successfully. Source analysis in progress."
    }


@router.post("/text")
async def ingest_source_text(
    payload: TextIngestRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Ingest plain text, blog markdown, or public article URL."""
    source_title = payload.title
    extracted_text = payload.text_content or ""
    source_type = payload.source_type

    if payload.url:
        source_type = "url"
        url_title, url_text = await DocumentExtractor.extract_from_url(payload.url)
        source_title = source_title or url_title
        extracted_text = url_text

    if not extracted_text:
        raise HTTPException(status_code=400, detail="Either text_content or a valid public URL must be provided")

    source_id = uuid.uuid4()
    object_key = f"users/{current_user.id}/sources/{source_id}/original.txt"

    # Save to MinIO
    storage_service.upload_bytes(
        object_key=object_key,
        data=extracted_text.encode("utf-8"),
        content_type="text/plain"
    )

    doc = SourceDocument(
        id=source_id,
        user_id=current_user.id,
        title=source_title,
        source_type=source_type,
        original_filename=f"{source_title[:20]}.txt",
        file_size_bytes=len(extracted_text.encode("utf-8")),
        mime_type="text/plain",
        minio_object_key=object_key,
        status="processing"
    )
    db.add(doc)
    await db.flush()

    extraction = SourceExtraction(
        source_document_id=doc.id,
        raw_text=extracted_text,
        clean_transcript=extracted_text,
        main_subject=source_title
    )
    db.add(extraction)
    await db.commit()

    background_tasks.add_task(run_source_analysis_background, doc.id, extracted_text, source_type)

    return {
        "id": doc.id,
        "title": doc.title,
        "source_type": doc.source_type,
        "status": doc.status,
        "message": "Source ingested successfully. Content analysis running in background."
    }


@router.get("")
async def list_sources(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SourceDocument).where(SourceDocument.user_id == current_user.id).order_by(SourceDocument.created_at.desc())
    res = await db.execute(stmt)
    docs = res.scalars().all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "source_type": d.source_type,
            "status": d.status,
            "file_size_bytes": d.file_size_bytes,
            "media_duration_seconds": d.media_duration_seconds,
            "created_at": d.created_at.isoformat()
        }
        for d in docs
    ]


@router.get("/{source_id}")
async def get_source(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SourceDocument).where(SourceDocument.id == source_id, SourceDocument.user_id == current_user.id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Source document not found")

    ext_stmt = select(SourceExtraction).where(SourceExtraction.source_document_id == source_id)
    ext_res = await db.execute(ext_stmt)
    extraction = ext_res.scalar_one_or_none()

    presigned = storage_service.get_presigned_url(doc.minio_object_key) if doc.minio_object_key else None

    return {
        "id": doc.id,
        "title": doc.title,
        "source_type": doc.source_type,
        "status": doc.status,
        "error_message": doc.error_message,
        "file_size_bytes": doc.file_size_bytes,
        "media_duration_seconds": doc.media_duration_seconds,
        "minio_object_key": doc.minio_object_key,
        "download_url": presigned,
        "created_at": doc.created_at.isoformat(),
        "extraction": {
            "clean_transcript": extraction.clean_transcript if extraction else "",
            "main_subject": extraction.main_subject if extraction else "",
            "audience_intent": extraction.audience_intent if extraction else "",
            "topics": extraction.topics if extraction else [],
            "subtopics": extraction.subtopics if extraction else [],
            "key_claims": extraction.key_claims if extraction else [],
            "quotes_with_timestamps": extraction.quotes_with_timestamps if extraction else [],
            "content_opportunities": extraction.content_opportunities if extraction else []
        } if extraction else None
    }


@router.put("/{source_id}/extraction")
async def update_extraction(
    source_id: uuid.UUID,
    payload: ExtractionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Allows user to inspect and correct extracted text before generating campaigns."""
    doc_stmt = select(SourceDocument).where(SourceDocument.id == source_id, SourceDocument.user_id == current_user.id)
    doc_res = await db.execute(doc_stmt)
    if not doc_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Source not found")

    ext_stmt = select(SourceExtraction).where(SourceExtraction.source_document_id == source_id)
    ext_res = await db.execute(ext_stmt)
    extraction = ext_res.scalar_one_or_none()
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")

    if payload.clean_transcript is not None:
        extraction.clean_transcript = payload.clean_transcript
    if payload.main_subject is not None:
        extraction.main_subject = payload.main_subject
    if payload.topics is not None:
        extraction.topics = payload.topics

    await db.commit()
    return {"success": True, "message": "Extraction updated successfully"}
