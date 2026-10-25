import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.core.security import decrypt_token, encrypt_token
from app.db.models import ScheduledPost, ContentAsset, ConnectedAccount, OAuthCredential, PublishingAttempt, AssetMedia, Campaign
from app.services.storage.minio_service import storage_service
from app.integrations.meta.meta_client import meta_client
from app.integrations.youtube.youtube_client import youtube_client
from app.integrations.x.x_client import x_client


class PublisherService:
    @classmethod
    async def publish_scheduled_post(cls, session: AsyncSession, scheduled_post_id: uuid.UUID) -> Dict[str, Any]:
        """
        Publishes a scheduled post using the official platform API.
        Enforces idempotency, records attempts, decrypts OAuth tokens securely.
        """
        # Fetch post with relationships
        stmt = (
            select(ScheduledPost)
            .where(ScheduledPost.id == scheduled_post_id)
        )
        res = await session.execute(stmt)
        post = res.scalar_one_or_none()
        if not post:
            return {"success": False, "error": f"Scheduled post {scheduled_post_id} not found"}

        # Check idempotency: if already published, skip
        if post.status == "published":
            logger.info(f"Post {post.id} already marked as published ({post.published_post_id}). Skipping.")
            return {"success": True, "already_published": True, "post_id": post.published_post_id, "url": post.published_post_url}

        # Fetch asset
        asset_res = await session.execute(select(ContentAsset).where(ContentAsset.id == post.content_asset_id))
        asset = asset_res.scalar_one_or_none()
        if not asset:
            post.status = "failed"
            post.last_error = "Content asset not found"
            await session.commit()
            return {"success": False, "error": post.last_error}

        # Fetch media items
        media_res = await session.execute(
            select(AssetMedia)
            .where(AssetMedia.content_asset_id == asset.id)
            .order_by(AssetMedia.slide_index.asc())
        )
        media_items = media_res.scalars().all()

        # Fetch connected account and credentials
        account = None
        access_token = None
        if post.connected_account_id:
            acc_res = await session.execute(select(ConnectedAccount).where(ConnectedAccount.id == post.connected_account_id))
            account = acc_res.scalar_one_or_none()

        platform = (account.platform if account else asset.platform).lower()
        fmt = asset.format.lower()

        # If not explicitly linked or linked account was deleted/inactive, resolve user's active account for this platform
        if not account or account.status != "connected":
            user_id = None
            if asset.campaign_id:
                c_res = await session.execute(select(Campaign).where(Campaign.id == asset.campaign_id))
                c = c_res.scalar_one_or_none()
                if c:
                    user_id = c.user_id

            acc_query = select(ConnectedAccount).where(
                ConnectedAccount.platform == platform,
                ConnectedAccount.status == "connected"
            )
            if user_id:
                acc_query = acc_query.where(ConnectedAccount.user_id == user_id)
            acc_query = acc_query.order_by(ConnectedAccount.created_at.desc())

            acc_res = await session.execute(acc_query)
            account = acc_res.scalars().first()
            if account:
                post.connected_account_id = account.id  # Bind persistently to the scheduled post

        if account:
            cred_res = await session.execute(select(OAuthCredential).where(OAuthCredential.connected_account_id == account.id))
            cred = cred_res.scalar_one_or_none()
            if cred and cred.encrypted_access_token:
                access_token = decrypt_token(cred.encrypted_access_token)

            if platform == "facebook":
                if getattr(settings, "FACEBOOK_PAGE_ACCESS_TOKEN", None) and not settings.FACEBOOK_PAGE_ACCESS_TOKEN.startswith("dev_"):
                    access_token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
            elif platform == "instagram":
                if getattr(settings, "INSTAGRAM_ACCESS_TOKEN", None) and not settings.INSTAGRAM_ACCESS_TOKEN.startswith("dev_"):
                    access_token = settings.INSTAGRAM_ACCESS_TOKEN

            # Auto-refresh expired YouTube access token if refresh token is present
            if platform == "youtube":
                ref_token = None
                if cred and cred.encrypted_refresh_token:
                    ref_token = decrypt_token(cred.encrypted_refresh_token)
                elif settings.YOUTUBE_REFRESH_TOKEN:
                    ref_token = settings.YOUTUBE_REFRESH_TOKEN

                if ref_token:
                    try:
                        new_toks = await youtube_client.refresh_access_token(ref_token)
                        if new_toks.get("access_token"):
                            access_token = new_toks["access_token"]
                            if cred:
                                cred.encrypted_access_token = encrypt_token(access_token)
                                cred.encrypted_refresh_token = encrypt_token(ref_token)
                                exp_in = new_toks.get("expires_in", 3600)
                                cred.expires_at = datetime.now(timezone.utc) + timedelta(seconds=exp_in)
                                await session.commit()
                            logger.info("Successfully refreshed YouTube access token via refresh token.")
                    except Exception as e:
                        logger.warning(f"Could not refresh YouTube access token: {e}")

        post_text = f"{asset.hook}\n\n{asset.caption}"
        if asset.tracking_url:
            post_text += f"\n\n{asset.tracking_url}"

        # If no real connected account is linked or access token is missing or a sandbox placeholder, report the limitation honestly!
        if not access_token or access_token.startswith("dev_token_") or access_token.startswith("sandbox_"):
            err_msg = (
                f"Cannot publish live to {platform.upper()}: No active OAuth account connected or credentials missing. "
                f"Please navigate to Connected Accounts and authenticate your official {platform.upper()} account."
            )
            logger.warning(err_msg)
            post.status = "failed"
            post.last_error = err_msg
            post.published_post_url = None

            attempt = PublishingAttempt(
                scheduled_post_id=post.id,
                attempt_number=post.retry_count + 1,
                status="error",
                error_details=err_msg
            )
            session.add(attempt)
            await session.commit()
            return {"success": False, "error": err_msg, "action_required": "connect_oauth"}

        # Check if asset is a multi-slide carousel
        is_carousel = (fmt == "carousel") or (len(media_items) > 1 and any("slide" in (m.media_type or "") for m in media_items))
        carousel_slides = []
        if is_carousel:
            from app.core.config import CAROUSELS_DIR
            aid_name = None
            for m in media_items:
                if m.editable_config and m.editable_config.get("aid"):
                    aid_name = m.editable_config.get("aid")
                    break

            for m in media_items:
                if m.media_type not in ("carousel_slide", "image"):
                    continue
                slide_bytes = None
                try:
                    b = storage_service.download_bytes(m.minio_object_key)
                    if b and len(b) > 0:
                        slide_bytes = b
                except Exception:
                    pass

                if not slide_bytes:
                    cands = []
                    if aid_name:
                        cands.append(CAROUSELS_DIR / aid_name / m.file_name)
                    cands.append(CAROUSELS_DIR / m.file_name)
                    for cand in cands:
                        if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
                            slide_bytes = cand.read_bytes()
                            try:
                                storage_service.upload_bytes(m.minio_object_key, slide_bytes, "image/png")
                            except Exception:
                                pass
                            break

                if slide_bytes:
                    carousel_slides.append({
                        "name": m.file_name,
                        "bytes": slide_bytes,
                        "url": storage_service.get_presigned_url(m.minio_object_key)
                    })

            # If media_items had no direct slides, check local disk carousel folder
            if not carousel_slides and aid_name:
                folder = CAROUSELS_DIR / aid_name
                if folder.exists():
                    for s in sorted(list(folder.glob("slide_*.png"))):
                        b = s.read_bytes()
                        if b:
                            carousel_slides.append({"name": s.name, "bytes": b, "url": None})

        # Dispatch to platform integration
        result = {}
        try:
            if platform == "facebook":
                page_id = account.account_id if account else "me"
                clean_page_id = page_id.replace("page_", "") if page_id.startswith("page_") and not page_id.startswith("page_meta_") else page_id
                clean_user = (account.username or "").lstrip("@").strip() if account else "incubrix_media"

                if is_carousel and len(carousel_slides) >= 2:
                    logger.info(f"Publishing {len(carousel_slides)}-slide carousel to Facebook Page {clean_page_id}...")
                    result = await meta_client.publish_facebook_page_carousel(
                        page_id=clean_page_id,
                        page_access_token=access_token,
                        message=post_text,
                        slides=carousel_slides
                    )
                else:
                    image_url = None
                    video_url = None
                    image_bytes = None
                    video_bytes = None
                    if media_items:
                        m = media_items[0]
                        try:
                            b = storage_service.download_bytes(m.minio_object_key)
                            if "video" in m.media_type or m.file_name.endswith(".mp4"):
                                video_bytes = b
                            else:
                                image_bytes = b
                        except Exception as e:
                            logger.warning(f"Could not load media bytes from MinIO for Facebook: {e}")

                        if not video_bytes and not image_bytes:
                            from app.core.config import VIDEOS_DIR, GRAPHICS_DIR, CAROUSELS_DIR
                            for cand in [VIDEOS_DIR / m.file_name, GRAPHICS_DIR / m.file_name, CAROUSELS_DIR / m.file_name]:
                                if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
                                    b_loc = cand.read_bytes()
                                    if "video" in m.media_type or cand.suffix.lower() == ".mp4":
                                        video_bytes = b_loc
                                    else:
                                        image_bytes = b_loc
                                    try:
                                        storage_service.upload_bytes(m.minio_object_key, b_loc, "video/mp4" if video_bytes else "image/png")
                                    except Exception:
                                        pass
                                    break

                        if "video" in m.media_type or (m.file_name and m.file_name.endswith(".mp4")):
                            video_url = storage_service.get_presigned_url(m.minio_object_key)
                        else:
                            image_url = storage_service.get_presigned_url(m.minio_object_key)

                    result = await meta_client.publish_facebook_page_post(
                        page_id=clean_page_id,
                        page_access_token=access_token,
                        message=post_text,
                        link=asset.tracking_url,
                        image_url=image_url,
                        video_url=video_url,
                        image_bytes=image_bytes,
                        video_bytes=video_bytes
                    )

                if result.get("success") and not result.get("url"):
                    if clean_page_id and clean_page_id != "me" and not clean_page_id.startswith("page_meta_"):
                        result["url"] = f"https://www.facebook.com/{clean_page_id}"
                    elif clean_user and clean_user not in ("incubrix_media", "incubrix_official_media"):
                        result["url"] = f"https://www.facebook.com/{clean_user}"
                    else:
                        result["url"] = None

            elif platform == "instagram":
                ig_user_id = account.account_id if account else "me"
                clean_ig_id = ig_user_id.replace("ig_", "") if ig_user_id.startswith("ig_") and not ig_user_id.startswith("ig_meta_") else ig_user_id
                clean_user = (account.username or "").lstrip("@").strip() if account else None

                if is_carousel and len(carousel_slides) >= 2:
                    logger.info(f"Publishing {len(carousel_slides)}-slide carousel to Instagram {clean_ig_id}...")
                    result = await meta_client.publish_instagram_carousel(
                        ig_user_id=clean_ig_id,
                        page_access_token=access_token,
                        caption=post_text,
                        slides=carousel_slides
                    )
                else:
                    image_url = None
                    video_url = None
                    image_bytes = None
                    video_bytes = None
                    if media_items:
                        m = media_items[0]
                        try:
                            b = storage_service.download_bytes(m.minio_object_key)
                            if "video" in m.media_type or m.file_name.endswith(".mp4"):
                                video_bytes = b
                            else:
                                image_bytes = b
                        except Exception as e:
                            logger.warning(f"Could not load media bytes from MinIO for Instagram: {e}")

                        # Fallback to local disk if bytes weren't in MinIO
                        if not image_bytes and not video_bytes:
                            from pathlib import Path
                            base_assets = Path("assets/final")
                            aid = m.editable_config.get("aid") if m.editable_config else None
                            candidates = []
                            if aid:
                                candidates.extend([
                                    base_assets / "carousels" / aid / m.file_name,
                                    base_assets / "carousels" / aid / "slide_1.png",
                                    base_assets / "carousels" / f"{aid}_slide_1.png",
                                    base_assets / "graphics" / f"{aid}.png",
                                    base_assets / "graphics" / aid / f"{aid}.png",
                                    base_assets / "videos" / f"{aid}.mp4",
                                    base_assets / "videos" / aid / f"{aid}.mp4"
                                ])
                            candidates.extend([
                                base_assets / "carousels" / m.file_name,
                                base_assets / "graphics" / m.file_name,
                                base_assets / "videos" / m.file_name
                            ])
                            for cand in candidates:
                                if cand.exists() and cand.is_file():
                                    b_local = cand.read_bytes()
                                    if "video" in m.media_type or cand.suffix.lower() == ".mp4":
                                        video_bytes = b_local
                                    else:
                                        image_bytes = b_local
                                    logger.info(f"Loaded media bytes from local disk: {cand} ({len(b_local)} bytes)")
                                    try:
                                        storage_service.upload_bytes(m.minio_object_key, b_local, "video/mp4" if video_bytes else "image/png")
                                    except Exception:
                                        pass
                                    break

                        if "video" in m.media_type:
                            video_url = storage_service.get_presigned_url(m.minio_object_key)
                        else:
                            image_url = storage_service.get_presigned_url(m.minio_object_key)

                    result = await meta_client.publish_instagram_media(
                        ig_user_id=clean_ig_id,
                        page_access_token=access_token,
                        caption=post_text,
                        image_url=image_url,
                        video_url=video_url,
                        image_bytes=image_bytes,
                        video_bytes=video_bytes,
                        is_reel=(fmt in ("short_video", "reel"))
                    )

                if result.get("success") and not result.get("url"):
                    if clean_user and clean_user not in ("incubrix_media", "incubrix_official_media"):
                        result["url"] = f"https://www.instagram.com/{clean_user}/"
                    elif clean_ig_id and not clean_ig_id.startswith("ig_meta_") and clean_ig_id != "me":
                        result["url"] = f"https://www.instagram.com/{clean_ig_id}/"
                    else:
                        result["url"] = None

            elif platform == "youtube":
                video_media = next((m for m in media_items if "video" in m.media_type), None)
                if not video_media:
                    result = {"success": False, "error": "YouTube publishing requires a rendered video media file"}
                else:
                    video_bytes = None
                    try:
                        video_bytes = storage_service.download_bytes(video_media.minio_object_key)
                    except Exception as me:
                        logger.warning(f"Could not load video bytes from MinIO for YouTube: {me}")

                    if not video_bytes:
                        from app.core.config import VIDEOS_DIR
                        cand = VIDEOS_DIR / video_media.file_name
                        if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
                            video_bytes = cand.read_bytes()
                            try:
                                storage_service.upload_bytes(video_media.minio_object_key, video_bytes, "video/mp4")
                            except Exception:
                                pass

                    if not video_bytes:
                        result = {"success": False, "error": f"Failed to load video file data for {video_media.file_name}"}
                    else:
                        result = await youtube_client.upload_video(
                        access_token=access_token,
                        video_bytes=video_bytes,
                        title=asset.hook[:100],
                        description=f"{asset.caption}\n\n{asset.tracking_url}",
                        tags=asset.hashtags
                    )
                    if result.get("success") and not result.get("url"):
                        clean_user = (account.username or "").lstrip("@").strip() if account else "incubrix_growth"
                        result["url"] = f"https://www.youtube.com/@{clean_user}" if clean_user else "https://www.youtube.com"

            elif platform == "x":
                result = await x_client.publish_tweet(
                    access_token=access_token,
                    text=post_text[:280]
                )
                if result.get("success") and not result.get("url"):
                    clean_user = (account.username or "").lstrip("@").strip() if account else "incubrix_ai"
                    result["url"] = f"https://x.com/{clean_user}" if clean_user else "https://x.com"

            else:
                result = {"success": False, "error": f"Unsupported publishing platform '{platform}'"}

        except Exception as e:
            logger.error(f"Publishing exception for post {post.id} on {platform}: {e}")
            result = {"success": False, "error": str(e)}

        # Persist outcome
        is_success = result.get("success", False)
        attempt = PublishingAttempt(
            scheduled_post_id=post.id,
            attempt_number=post.retry_count + 1,
            status="success" if is_success else "error",
            response_payload=result.get("response", {}),
            error_details=result.get("error")
        )
        session.add(attempt)

        if is_success:
            post.status = "published"
            post.published_post_id = result.get("post_id")
            post.published_post_url = result.get("url")
            post.published_at = datetime.now(timezone.utc)
            post.last_error = None
            logger.info(f"Post {post.id} successfully published to {platform}: {post.published_post_url}")
        else:
            post.retry_count += 1
            post.last_error = result.get("error")
            if post.retry_count >= post.max_retries:
                post.status = "failed"
            else:
                # Bounded exponential backoff with jitter
                delay = settings.RETRY_BACKOFF_BASE_SECONDS * (2 ** post.retry_count)
                post.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                post.status = "scheduled"

        await session.commit()
        return result


publisher_service = PublisherService()
