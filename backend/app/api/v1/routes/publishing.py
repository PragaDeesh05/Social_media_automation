import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.db.models import User, ScheduledPost, ContentAsset, Campaign, PublishingAttempt, ConnectedAccount, AssetMedia
from app.api.deps import get_current_user
from app.services.publishing.publisher_service import publisher_service

router = APIRouter(prefix="/publishing", tags=["Publishing Queue"])


@router.get("/queue")
async def get_publishing_queue(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns persistent publishing queue with status, error details, and published post links."""
    stmt = (
        select(ScheduledPost, ContentAsset)
        .join(ContentAsset, ScheduledPost.content_asset_id == ContentAsset.id)
        .join(Campaign, ContentAsset.campaign_id == Campaign.id)
        .where(Campaign.user_id == current_user.id)
    )
    if status_filter:
        stmt = stmt.where(ScheduledPost.status == status_filter.lower())

    stmt = stmt.order_by(ScheduledPost.scheduled_utc.asc())
    res = await db.execute(stmt)
    rows = res.all()

    queue = []
    for post, asset in rows:
        # Fetch latest attempt
        att_stmt = select(PublishingAttempt).where(PublishingAttempt.scheduled_post_id == post.id).order_by(PublishingAttempt.attempt_number.desc())
        att_res = await db.execute(att_stmt)
        latest_att = att_res.scalars().first()

        # Resolve authentic platform URL for the connected account
        pub_url = post.published_post_url
        if pub_url and ("media/stream" in pub_url or "incubrix-assets" in pub_url or "localhost:9100" in pub_url or "page_meta_" in pub_url or "/p/ig_" in pub_url or "sandbox" in (post.published_post_id or "")):
            # Look up the connected account to get the real account username or ID
            acc = None
            if post.connected_account_id:
                acc_res = await db.execute(select(ConnectedAccount).where(ConnectedAccount.id == post.connected_account_id))
                acc = acc_res.scalar_one_or_none()
            if not acc:
                acc_query = select(ConnectedAccount).where(
                    ConnectedAccount.platform == asset.platform,
                    ConnectedAccount.status == "connected"
                ).order_by(ConnectedAccount.created_at.desc())
                acc_res = await db.execute(acc_query)
                acc = acc_res.scalars().first()

            clean_user = (acc.username or "").lstrip("@").strip() if acc else None

            if asset.platform == "facebook":
                clean_page = acc.account_id.replace("page_", "") if acc and acc.account_id and not acc.account_id.startswith("page_meta_") else None
                if clean_page:
                    pub_url = f"https://www.facebook.com/{clean_page}"
                elif clean_user:
                    pub_url = f"https://www.facebook.com/{clean_user}"
                else:
                    pub_url = "https://www.facebook.com"
            elif asset.platform == "instagram":
                clean_ig = acc.account_id.replace("ig_", "") if acc and acc.account_id and not acc.account_id.startswith("ig_meta_") else None
                if clean_user:
                    pub_url = f"https://www.instagram.com/{clean_user}/"
                elif clean_ig:
                    pub_url = f"https://www.instagram.com/{clean_ig}/"
                else:
                    pub_url = "https://www.instagram.com"
            elif asset.platform == "youtube":
                if "youtube.com/watch" in pub_url or "youtube.com/shorts" in pub_url:
                    pass  # keep live YouTube video URL
                elif clean_user:
                    pub_url = f"https://www.youtube.com/@{clean_user}"
                else:
                    pub_url = "https://www.youtube.com"
            elif asset.platform == "x":
                if clean_user:
                    pub_url = f"https://x.com/{clean_user}"
                else:
                    pub_url = "https://x.com"

        queue.append({
            "scheduled_post_id": post.id,
            "content_asset_id": asset.id,
            "campaign_id": asset.campaign_id,
            "platform": asset.platform,
            "format": asset.format,
            "hook": asset.hook,
            "caption": asset.caption,
            "scheduled_utc": post.scheduled_utc.isoformat(),
            "status": post.status,
            "retry_count": post.retry_count,
            "max_retries": post.max_retries,
            "last_error": post.last_error,
            "published_post_id": post.published_post_id,
            "published_post_url": pub_url,
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "latest_attempt": {
                "attempt_number": latest_att.attempt_number,
                "status": latest_att.status,
                "error_details": latest_att.error_details,
                "attempted_at": latest_att.attempted_at.isoformat()
            } if latest_att else None
        })

    return queue


class AssetPublishNowRequest(BaseModel):
    platform: Optional[str] = None
    custom_caption: Optional[str] = None


class AssetScheduleRequest(BaseModel):
    asset_id: str
    scheduled_date: str
    platform: Optional[str] = None
    custom_caption: Optional[str] = None


@router.post("/publish/{asset_id}")
async def publish_asset_directly(
    asset_id: str,
    payload: AssetPublishNowRequest = AssetPublishNowRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Directly publishes a content asset to the connected account."""
    asset = None
    try:
        parsed_uuid = uuid.UUID(asset_id)
        res = await db.execute(
            select(ContentAsset)
            .join(Campaign, ContentAsset.campaign_id == Campaign.id)
            .where(ContentAsset.id == parsed_uuid, Campaign.user_id == current_user.id)
        )
        asset = res.scalar_one_or_none()
    except ValueError:
        pass

    if not asset:
        m_res = await db.execute(
            select(ContentAsset)
            .join(Campaign, ContentAsset.campaign_id == Campaign.id)
            .join(AssetMedia, AssetMedia.content_asset_id == ContentAsset.id)
            .where(
                Campaign.user_id == current_user.id,
                (AssetMedia.file_name.ilike(f"%{asset_id}%")) | 
                (AssetMedia.editable_config["aid"].astext == asset_id)
            )
        )
        asset = m_res.scalars().first()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    target_platform = (payload.platform or asset.platform or "youtube").lower()
    if "youtube" in target_platform:
        platform_key = "youtube"
    elif "facebook" in target_platform:
        platform_key = "facebook"
    elif "instagram" in target_platform:
        platform_key = "instagram"
    else:
        platform_key = target_platform

    # Find connected account
    acc_res = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == current_user.id,
            ConnectedAccount.platform == platform_key,
            ConnectedAccount.status == "connected"
        )
    )
    acc = acc_res.scalars().first()
    if not acc:
        raise HTTPException(
            status_code=400,
            detail=f"No connected {platform_key.title()} account found. Please check connected credentials in backend .env."
        )

    # Check for existing scheduled post
    # 1. Check for existing scheduled post on this specific account
    p_res = await db.execute(
        select(ScheduledPost).where(
            ScheduledPost.content_asset_id == asset.id,
            ScheduledPost.connected_account_id == acc.id
        )
    )
    post = p_res.scalars().first()

    # 2. Check if a post already exists for this asset on any connected account for this same platform
    if not post:
        same_plat_res = await db.execute(
            select(ScheduledPost)
            .join(ConnectedAccount, ScheduledPost.connected_account_id == ConnectedAccount.id)
            .where(
                ScheduledPost.content_asset_id == asset.id,
                ConnectedAccount.platform == platform_key
            )
        )
        post = same_plat_res.scalars().first()
        if post:
            post.connected_account_id = acc.id

    # 3. Check for an unassigned scheduled post
    if not post:
        unassigned_res = await db.execute(
            select(ScheduledPost).where(
                ScheduledPost.content_asset_id == asset.id,
                ScheduledPost.connected_account_id.is_(None)
            )
        )
        post = unassigned_res.scalars().first()
        if post:
            post.connected_account_id = acc.id

    # 4. If none exists, create a new ScheduledPost
    if not post:
        post = ScheduledPost(
            content_asset_id=asset.id,
            connected_account_id=acc.id,
            scheduled_utc=datetime.now(timezone.utc),
            status="pending"
        )
        db.add(post)
    else:
        post.status = "pending"
        post.scheduled_utc = datetime.now(timezone.utc)
        post.last_error = None

    if payload.custom_caption:
        asset.caption = payload.custom_caption
    asset.approval_status = "approved"
    asset.platform = platform_key
    await db.commit()

    result = await publisher_service.publish_scheduled_post(db, post.id)
    if not result.get("success"):
        err_detail = result.get("error") or "Publishing failed on platform"
        raise HTTPException(status_code=400, detail=err_detail)
    return result


@router.post("/schedule")
async def schedule_asset_directly(
    payload: AssetScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Schedules a generated asset into the content calendar and queue."""
    asset = None
    try:
        parsed_uuid = uuid.UUID(payload.asset_id)
        res = await db.execute(
            select(ContentAsset)
            .join(Campaign, ContentAsset.campaign_id == Campaign.id)
            .where(ContentAsset.id == parsed_uuid, Campaign.user_id == current_user.id)
        )
        asset = res.scalar_one_or_none()
    except ValueError:
        pass

    if not asset:
        m_res = await db.execute(
            select(ContentAsset)
            .join(Campaign, ContentAsset.campaign_id == Campaign.id)
            .join(AssetMedia, AssetMedia.content_asset_id == ContentAsset.id)
            .where(
                Campaign.user_id == current_user.id,
                (AssetMedia.file_name.ilike(f"%{payload.asset_id}%")) | 
                (AssetMedia.editable_config["aid"].astext == payload.asset_id)
            )
        )
        asset = m_res.scalars().first()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    target_platform = (payload.platform or asset.platform or "youtube").lower()
    if "youtube" in target_platform:
        platform_key = "youtube"
    elif "facebook" in target_platform:
        platform_key = "facebook"
    elif "instagram" in target_platform:
        platform_key = "instagram"
    else:
        platform_key = target_platform

    # Find connected account
    acc_res = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == current_user.id,
            ConnectedAccount.platform == platform_key,
            ConnectedAccount.status == "connected"
        )
    )
    acc = acc_res.scalars().first()

    # Parse scheduled date
    try:
        clean_date = payload.scheduled_date.replace("Z", "+00:00")
        sched_dt = datetime.fromisoformat(clean_date)
    except Exception:
        sched_dt = datetime.now(timezone.utc)

    asset.scheduled_slot_time = sched_dt
    if payload.custom_caption:
        asset.caption = payload.custom_caption
    asset.approval_status = "approved"

    # Check if a scheduled post already exists for this asset and account
    if acc:
        existing_p = await db.execute(
            select(ScheduledPost).where(
                ScheduledPost.content_asset_id == asset.id,
                ScheduledPost.connected_account_id == acc.id
            )
        )
    else:
        existing_p = await db.execute(
            select(ScheduledPost).where(ScheduledPost.content_asset_id == asset.id)
        )
    post = existing_p.scalars().first()
    if post:
        post.scheduled_utc = sched_dt
        post.status = "scheduled"
        if acc:
            post.connected_account_id = acc.id
    else:
        post = ScheduledPost(
            content_asset_id=asset.id,
            connected_account_id=acc.id if acc else None,
            scheduled_utc=sched_dt,
            status="scheduled"
        )
        db.add(post)
    await db.commit()

    return {
        "status": "success",
        "asset_id": str(asset.id),
        "scheduled_date": sched_dt.isoformat(),
        "platform": target_platform
    }


@router.post("/publish-now/{post_id}")
async def publish_now(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Triggers immediate publishing for an asset."""
    stmt = (
        select(ScheduledPost, ContentAsset)
        .join(ContentAsset, ScheduledPost.content_asset_id == ContentAsset.id)
        .join(Campaign, ContentAsset.campaign_id == Campaign.id)
        .where(ScheduledPost.id == post_id, Campaign.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Scheduled post not found")

    post, asset = row
    if asset.approval_status != "approved":
        # Auto-approve if user manually triggers Publish Now
        asset.approval_status = "approved"
        await db.flush()

    # Reset retry state before attempting publish
    post.last_error = None
    result = await publisher_service.publish_scheduled_post(db, post.id)
    return result


@router.post("/retry/{post_id}")
async def retry_failed_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Resets failed post to scheduled state for retry and resolves connected account."""
    stmt = (
        select(ScheduledPost, ContentAsset)
        .join(ContentAsset, ScheduledPost.content_asset_id == ContentAsset.id)
        .join(Campaign, ContentAsset.campaign_id == Campaign.id)
        .where(ScheduledPost.id == post_id, Campaign.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Scheduled post not found")

    post, asset = row

    # Auto-resolve connected account if not yet bound
    if not post.connected_account_id:
        acc_res = await db.execute(
            select(ConnectedAccount)
            .where(
                ConnectedAccount.user_id == current_user.id,
                ConnectedAccount.platform == asset.platform.lower(),
                ConnectedAccount.status == "connected"
            )
            .order_by(ConnectedAccount.created_at.desc())
        )
        acc = acc_res.scalars().first()
        if acc:
            post.connected_account_id = acc.id

    post.status = "scheduled"
    post.retry_count = 0
    post.next_retry_at = None
    post.last_error = None
    await db.commit()
    return {"success": True, "message": "Post reset for publishing retry"}


@router.post("/cancel/{post_id}")
async def cancel_scheduled_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancels a scheduled post."""
    stmt = (
        select(ScheduledPost)
        .join(ContentAsset, ScheduledPost.content_asset_id == ContentAsset.id)
        .join(Campaign, ContentAsset.campaign_id == Campaign.id)
        .where(ScheduledPost.id == post_id, Campaign.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Scheduled post not found")

    post.status = "cancelled"
    await db.commit()
    return {"success": True, "message": "Scheduled post cancelled"}
