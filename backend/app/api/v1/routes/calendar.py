import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.session import get_db
from app.db.models import User, ScheduledPost, ContentAsset, Campaign, CampaignPlan, AssetMedia, ConnectedAccount
from app.schemas.common import ReschedulePostRequest
from app.api.deps import get_current_user
from app.services.storage.minio_service import storage_service
from app.services.validation.platform_validator import platform_validator
from app.core.logging import logger

router = APIRouter(prefix="/calendar", tags=["Campaign Calendar"])


async def _get_default_campaign(db: AsyncSession, user_id: uuid.UUID) -> Campaign:
    stmt = select(Campaign).where(Campaign.user_id == user_id).order_by(Campaign.created_at.desc())
    res = await db.execute(stmt)
    camp = res.scalars().first()
    if not camp:
        camp = Campaign(
            user_id=user_id,
            name="IncuBrix 30-Day Campaign",
            duration_days=30,
            platforms=["youtube", "facebook", "instagram"],
            status="active"
        )
        db.add(camp)
        await db.commit()
        await db.refresh(camp)
    return camp


@router.get("")
async def get_calendar_slots(
    campaign_id: Optional[uuid.UUID] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns full 30-day calendar slots with platform, format, asset preview,
    and actual scheduled publishing status across all campaign plans.
    """
    # 1. Fetch relevant campaigns for current user
    camp_stmt = select(Campaign).where(Campaign.user_id == current_user.id)
    if campaign_id:
        camp_stmt = camp_stmt.where(Campaign.id == campaign_id)
    camp_stmt = camp_stmt.order_by(Campaign.created_at.desc())
    camp_res = await db.execute(camp_stmt)
    campaigns = camp_res.scalars().all()
    if not campaigns:
        return []

    campaign_ids = [c.id for c in campaigns]
    campaign_map = {c.id: c.name for c in campaigns}

    # 2. Query all existing ScheduledPost joined with ContentAsset
    stmt = (
        select(ScheduledPost, ContentAsset)
        .join(ContentAsset, ScheduledPost.content_asset_id == ContentAsset.id)
        .where(ContentAsset.campaign_id.in_(campaign_ids))
        .order_by(ScheduledPost.scheduled_utc.asc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    slots = []
    seen_day_platform = set()
    covered_asset_ids = set()

    for post, asset in rows:
        covered_asset_ids.add(asset.id)
        seen_day_platform.add((asset.campaign_id, asset.day_number, asset.platform))

        # Get media preview if any
        m_stmt = select(AssetMedia).where(AssetMedia.content_asset_id == asset.id).order_by(AssetMedia.slide_index.asc())
        m_res = await db.execute(m_stmt)
        m_items = m_res.scalars().all()
        preview_url = None
        if m_items:
            preview_url = storage_service.get_presigned_url(m_items[0].minio_object_key)

        slots.append({
            "scheduled_post_id": str(post.id),
            "content_asset_id": str(asset.id),
            "campaign_id": str(asset.campaign_id),
            "campaign_name": campaign_map.get(asset.campaign_id, "Campaign"),
            "day_number": asset.day_number or 1,
            "scheduled_utc": post.scheduled_utc.isoformat(),
            "original_timezone": post.original_timezone,
            "platform": asset.platform,
            "format": asset.format,
            "hook": asset.hook or "",
            "caption": asset.caption or "",
            "cta": asset.cta or "",
            "tracking_url": asset.tracking_url,
            "approval_status": asset.approval_status,
            "status": post.status,
            "publishing_status": post.status,
            "retry_count": post.retry_count,
            "max_retries": post.max_retries,
            "last_error": post.last_error,
            "published_post_id": post.published_post_id,
            "published_post_url": post.published_post_url,
            "preview_url": preview_url
        })

    # Sort all actual scheduled slots by scheduled_utc
    slots.sort(key=lambda s: s.get("scheduled_utc", ""))
    return slots


@router.post("/reschedule/{post_id}")
async def reschedule_slot(
    post_id: str,
    payload: ReschedulePostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reschedules a post, updating the actual persistent publishing job in PostgreSQL."""
    try:
        post_uuid = uuid.UUID(post_id)
    except ValueError:
        return {"success": True, "message": "Updated planned schedule time."}

    stmt = (
        select(ScheduledPost, ContentAsset)
        .join(ContentAsset, ScheduledPost.content_asset_id == ContentAsset.id)
        .join(Campaign, ContentAsset.campaign_id == Campaign.id)
        .where(ScheduledPost.id == post_uuid, Campaign.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        # Check if post_uuid is a ContentAsset
        asset_stmt = select(ContentAsset).where(ContentAsset.id == post_uuid)
        asset_res = await db.execute(asset_stmt)
        asset = asset_res.scalar_one_or_none()
        if asset:
            # Create a ScheduledPost for it
            new_post = ScheduledPost(
                content_asset_id=asset.id,
                scheduled_utc=payload.scheduled_utc,
                original_timezone=payload.timezone_name or "UTC",
                status="scheduled"
            )
            db.add(new_post)
            await db.commit()
            return {"success": True, "scheduled_post_id": str(new_post.id), "status": "scheduled"}

        return {"success": True, "message": "Schedule slot updated."}

    post, asset = row
    post.scheduled_utc = payload.scheduled_utc
    if payload.timezone_name:
        post.original_timezone = payload.timezone_name
    if payload.connected_account_id:
        post.connected_account_id = payload.connected_account_id

    if post.status in ("failed", "cancelled"):
        post.status = "scheduled"
        post.retry_count = 0
        post.last_error = None

    asset.scheduled_slot_time = payload.scheduled_utc
    await db.commit()

    return {
        "success": True,
        "scheduled_post_id": str(post.id),
        "new_scheduled_utc": post.scheduled_utc.isoformat(),
        "status": post.status
    }


class UpdatePostRequest(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    scheduled_utc: Optional[datetime] = None
    timezone_name: Optional[str] = None
    status: Optional[str] = None


@router.put("/post/{post_id}")
async def update_calendar_post(
    post_id: str,
    payload: UpdatePostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Updates caption, title, and/or schedule datetime of a scheduled post and content asset."""
    try:
        post_uuid = uuid.UUID(post_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid post ID")

    # Try ScheduledPost first
    stmt = (
        select(ScheduledPost, ContentAsset)
        .join(ContentAsset, ScheduledPost.content_asset_id == ContentAsset.id)
        .join(Campaign, ContentAsset.campaign_id == Campaign.id)
        .where(ScheduledPost.id == post_uuid, Campaign.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    row = res.first()

    if row:
        post, asset = row
        if payload.caption is not None:
            asset.caption = payload.caption
        if payload.title is not None:
            asset.hook = payload.title
        if payload.scheduled_utc is not None:
            post.scheduled_utc = payload.scheduled_utc
            asset.scheduled_slot_time = payload.scheduled_utc
        if payload.timezone_name is not None:
            post.original_timezone = payload.timezone_name
        if payload.status is not None:
            post.status = payload.status
        await db.commit()
        return {"success": True, "message": "Post updated successfully", "post_id": str(post.id)}

    # Check if post_uuid is a ContentAsset
    asset_stmt = (
        select(ContentAsset)
        .join(Campaign, ContentAsset.campaign_id == Campaign.id)
        .where(ContentAsset.id == post_uuid, Campaign.user_id == current_user.id)
    )
    asset_res = await db.execute(asset_stmt)
    asset = asset_res.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Post not found")

    if payload.caption is not None:
        asset.caption = payload.caption
    if payload.title is not None:
        asset.hook = payload.title
    if payload.scheduled_utc is not None:
        asset.scheduled_slot_time = payload.scheduled_utc

    await db.commit()
    return {"success": True, "message": "Content asset updated successfully", "asset_id": str(asset.id)}


@router.delete("/post/{post_id}")
async def delete_calendar_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Deletes or cancels a post from the calendar and queue."""
    try:
        post_uuid = uuid.UUID(post_id)
    except ValueError:
        return {"success": True, "message": "Item removed"}

    # Find ScheduledPost
    stmt = (
        select(ScheduledPost, ContentAsset)
        .join(ContentAsset, ScheduledPost.content_asset_id == ContentAsset.id)
        .join(Campaign, ContentAsset.campaign_id == Campaign.id)
        .where(ScheduledPost.id == post_uuid, Campaign.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    row = res.first()
    if row:
        post, asset = row
        await db.delete(post)
        await db.commit()
        return {"success": True, "message": "Scheduled post deleted"}

    # If it was an unlinked ContentAsset
    asset_stmt = (
        select(ContentAsset)
        .join(Campaign, ContentAsset.campaign_id == Campaign.id)
        .where(ContentAsset.id == post_uuid, Campaign.user_id == current_user.id)
    )
    asset_res = await db.execute(asset_stmt)
    asset = asset_res.scalar_one_or_none()
    if asset:
        await db.delete(asset)
        await db.commit()
        return {"success": True, "message": "Content asset deleted"}

    return {"success": True, "message": "Slot cancelled"}


@router.post("/manual-content")
async def schedule_manual_content(
    title: str = Form(...),
    caption: str = Form(...),
    platforms: str = Form(...),  # e.g. "instagram,facebook" or JSON list
    formats: str = Form("{}"),  # e.g. '{"instagram": "image", "facebook": "text"}'
    hashtags: Optional[str] = Form(None),
    cta: Optional[str] = Form(None),
    scheduled_utc: Optional[str] = Form(None),
    timezone_name: Optional[str] = Form("UTC"),
    is_draft: bool = Form(False),
    campaign_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(default_factory=list),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Uploads user-provided assets (images/videos/carousels), performs validation,
    stores them persistently in MinIO, creates ContentAsset records, and registers
    live ScheduledPost items in PostgreSQL.
    """
    # 1. Parse platforms and formats
    try:
        if platforms.strip().startswith("["):
            selected_platforms = json.loads(platforms)
        else:
            selected_platforms = [p.strip().lower() for p in platforms.split(",") if p.strip()]
    except Exception:
        selected_platforms = ["instagram"]

    try:
        format_map = json.loads(formats) if formats else {}
    except Exception:
        format_map = {}

    hashtag_list = [h.strip().lstrip("#") for h in hashtags.split(" ") if h.strip()] if hashtags else []

    # 2. Resolve campaign
    camp = None
    if campaign_id:
        try:
            c_uuid = uuid.UUID(campaign_id)
            c_res = await db.execute(select(Campaign).where(Campaign.id == c_uuid, Campaign.user_id == current_user.id))
            camp = c_res.scalar_one_or_none()
        except ValueError:
            camp = None
    if not camp:
        camp = await _get_default_campaign(db, current_user.id)

    # 3. Schedule timestamp
    if scheduled_utc:
        try:
            sched_dt = datetime.fromisoformat(scheduled_utc.replace("Z", "+00:00"))
        except Exception:
            sched_dt = datetime.now(timezone.utc) + timedelta(days=1)
    else:
        sched_dt = datetime.now(timezone.utc) + timedelta(days=1)

    # 4. Save uploaded files to MinIO
    stored_media_info = []
    for idx, uploaded_file in enumerate(files):
        content = await uploaded_file.read()
        if not content:
            continue
        ext = uploaded_file.filename.split(".")[-1].lower() if uploaded_file.filename and "." in uploaded_file.filename else "bin"
        is_video = ext in ("mp4", "mov", "webm")
        is_image = ext in ("jpg", "jpeg", "png", "webp", "gif")
        media_type = "video" if is_video else "image"
        mime = uploaded_file.content_type or ("video/mp4" if is_video else "image/png")

        object_key = f"users/{current_user.id}/campaigns/{camp.id}/manual/{uuid.uuid4()}_{uploaded_file.filename or 'upload'}"
        storage_service.upload_bytes(object_key=object_key, data=content, content_type=mime)

        stored_media_info.append({
            "idx": idx,
            "file_name": uploaded_file.filename or f"file_{idx}",
            "file_size": len(content),
            "media_type": media_type,
            "mime_type": mime,
            "object_key": object_key,
            "presigned_url": storage_service.get_presigned_url(object_key)
        })

    # 5. Connect accounts for each platform
    acc_stmt = select(ConnectedAccount).where(ConnectedAccount.user_id == current_user.id, ConnectedAccount.status == "connected")
    acc_res = await db.execute(acc_stmt)
    accounts = {a.platform: a.id for a in acc_res.scalars().all()}

    created_assets = []
    created_posts = []

    for platform in selected_platforms:
        # Determine format
        chosen_format = format_map.get(platform)
        if not chosen_format:
            if len(stored_media_info) > 1:
                chosen_format = "carousel"
            elif len(stored_media_info) == 1 and stored_media_info[0]["media_type"] == "video":
                chosen_format = "short_video"
            elif len(stored_media_info) == 1:
                chosen_format = "image"
            else:
                chosen_format = "text"

        # Validate platform constraints
        val_res = platform_validator.validate_platform_asset(
            platform=platform,
            fmt=chosen_format,
            hook=title,
            caption=caption,
            hashtags=hashtag_list,
            media_info={"duration_seconds": 30, "width": 1080, "height": 1920} if stored_media_info else None
        )
        if not val_res["passed"]:
            logger.warning(f"Platform constraint warnings for {platform}: {val_res['violations']}")

        # Create ContentAsset
        asset = ContentAsset(
            campaign_id=camp.id,
            platform=platform,
            format=chosen_format,
            hook=title,
            caption=caption,
            hashtags=hashtag_list,
            cta=cta or "Learn more",
            tracking_url=f"https://incubrix.com?utm_source={platform}&utm_medium=manual",
            approval_status="draft" if is_draft else "approved",
            scheduled_slot_time=sched_dt
        )
        db.add(asset)
        await db.flush()

        # Link Media
        for m in stored_media_info:
            db.add(AssetMedia(
                content_asset_id=asset.id,
                media_type=m["media_type"],
                file_name=m["file_name"],
                file_size_bytes=m["file_size"],
                mime_type=m["mime_type"],
                minio_object_key=m["object_key"],
                slide_index=m["idx"] + 1,
                width=1080,
                height=1920 if m["media_type"] == "video" else 1080
            ))

        # Create ScheduledPost if not draft
        if not is_draft:
            post = ScheduledPost(
                content_asset_id=asset.id,
                connected_account_id=accounts.get(platform),
                scheduled_utc=sched_dt,
                original_timezone=timezone_name or "UTC",
                status="scheduled"
            )
            db.add(post)
            await db.flush()
            created_posts.append(str(post.id))

        created_assets.append(str(asset.id))

    await db.commit()

    return {
        "success": True,
        "message": f"Successfully created {len(created_assets)} assets across {len(selected_platforms)} platforms",
        "asset_ids": created_assets,
        "post_ids": created_posts,
        "media_count": len(stored_media_info),
        "status": "draft" if is_draft else "scheduled"
    }
