import io
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import User, AssetMedia, ContentAsset, Campaign
from app.api.deps import get_current_user
from app.services.storage.minio_service import storage_service

router = APIRouter(prefix="/media", tags=["Media Library"])


@router.get("")
async def list_media_files(
    media_type: Optional[str] = Query(None),
    campaign_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists files from MinIO through authenticated backend endpoint."""
    stmt = (
        select(AssetMedia, ContentAsset)
        .join(ContentAsset, AssetMedia.content_asset_id == ContentAsset.id)
        .join(Campaign, ContentAsset.campaign_id == Campaign.id)
        .where(Campaign.user_id == current_user.id)
    )
    if media_type:
        stmt = stmt.where(AssetMedia.media_type == media_type)
    if campaign_id:
        stmt = stmt.where(ContentAsset.campaign_id == campaign_id)

    stmt = stmt.order_by(AssetMedia.created_at.desc())
    res = await db.execute(stmt)
    rows = res.all()

    items = []
    for media, asset in rows:
        ed = media.editable_config or {}
        local_url = ed.get("png_url") or ed.get("svg_url") or (f"/media/graphics/{media.file_name}" if media.media_type == "image" else None)
        items.append({
            "id": media.id,
            "asset_id": asset.id,
            "campaign_id": asset.campaign_id,
            "platform": asset.platform,
            "format": asset.format,
            "media_type": media.media_type,
            "file_name": media.file_name,
            "file_size_bytes": media.file_size_bytes,
            "mime_type": media.mime_type,
            "minio_object_key": media.minio_object_key,
            "duration_seconds": media.duration_seconds,
            "width": media.width,
            "height": media.height,
            "presigned_url": storage_service.get_presigned_url(media.minio_object_key),
            "stream_url": f"/api/v1/media/stream?key={media.minio_object_key}",
            "fallback_url": local_url,
            "editable_config": ed,
            "created_at": media.created_at.isoformat()
        })
    return items


@router.get("/stream")
async def stream_media(
    key: str = Query(...),
    download: Optional[int] = Query(0),
    filename: Optional[str] = Query(None)
):
    """Directly streams MinIO media bytes for frontend rendering/player with self-healing local disk fallback."""
    from pathlib import Path
    from app.core.config import GRAPHICS_DIR, CAROUSELS_DIR, VIDEOS_DIR

    file_name = filename or key.split("/")[-1]
    data = None

    # 1. Try MinIO first
    try:
        data = storage_service.download_bytes(key)
    except Exception:
        data = None

    # 2. If MinIO download fails, fallback to local disk and self-heal MinIO
    if not data or len(data) == 0:
        parent_folder = key.split("/")[-2] if "/" in key else ""
        candidates = [
            GRAPHICS_DIR / file_name,
            GRAPHICS_DIR / parent_folder / file_name,
            CAROUSELS_DIR / parent_folder / file_name,
            CAROUSELS_DIR / file_name,
            VIDEOS_DIR / file_name,
        ]
        for cand in candidates:
            if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
                data = cand.read_bytes()
                # Self-heal upload to MinIO
                try:
                    ext = file_name.split(".")[-1].lower()
                    ctype = "video/mp4" if ext == "mp4" else ("image/png" if ext == "png" else ("image/svg+xml" if ext == "svg" else "application/octet-stream"))
                    storage_service.upload_bytes(key, data, ctype)
                except Exception:
                    pass
                break

    if not data:
        raise HTTPException(status_code=404, detail="Media object not found")

    ext = file_name.split(".")[-1].lower()
    content_type = "video/mp4" if ext == "mp4" else ("image/png" if ext == "png" else ("image/svg+xml" if ext == "svg" else "application/octet-stream"))

    disp = "attachment" if download == 1 else "inline"
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'{disp}; filename="{file_name}"'}
    )
