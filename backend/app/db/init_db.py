import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import engine, Base, AsyncSessionLocal
from app.db.models import (
    User, BrandProfile, ConnectedAccount, OAuthCredential,
    SourceDocument, SourceExtraction, Campaign, CampaignPlan,
    ContentAsset, AssetVersion, AssetMedia, ScheduledPost,
    PublishingAttempt, BackgroundJob, AnalyticsSnapshot, TrackingLink, AuditEvent
)
from app.core.security import get_password_hash
from app.core.logging import logger


async def init_db():
    logger.info("Initializing database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        from sqlalchemy import text
        try:
            await conn.execute(text("ALTER TABLE scheduled_posts DROP CONSTRAINT IF EXISTS uq_scheduled_posts_asset;"))
            await conn.execute(text("ALTER TABLE scheduled_posts DROP CONSTRAINT IF EXISTS uq_scheduled_posts_asset_acc;"))
            await conn.execute(text("ALTER TABLE scheduled_posts ADD CONSTRAINT uq_scheduled_posts_asset_acc UNIQUE (content_asset_id, connected_account_id);"))
        except Exception as ce:
            logger.warning(f"Constraint migration notice: {ce}")
    logger.info("Database tables verified.")

    # Seed default developer/examiner user if not exists
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == "lead@incubrix.com"))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                email="lead@incubrix.com",
                full_name="Growth Assessment Lead",
                hashed_password=get_password_hash("IncuBrix2026!"),
                is_active=True,
                is_superuser=True
            )
            session.add(user)
            await session.flush()

            # Seed default IncuBrix brand profile
            brand = BrandProfile(
                user_id=user.id,
                brand_name="IncuBrix",
                target_audience="Founders, Creators, Growth Marketers, and Content Teams seeking scalable social growth.",
                tone_of_voice="Educational, Action-Oriented, High-Signal, Authoritative yet Empathetic",
                vocabulary_rules="Focus on ROI, attribution, native conversion, efficiency, and verifiable facts. No fluff.",
                words_to_avoid=["revolutionary", "game-changer", "magic", "unbelievable", "overnight success"],
                default_cta="Repurpose your content with IncuBrix → incubrix.com/start",
                primary_color="#4F46E5",
                secondary_color="#0F172A",
                verified_product_facts=[
                    "IncuBrix converts 1 core long-form input into 30 days of multi-platform social assets.",
                    "Supports Instagram, Facebook, YouTube, and X with native formatting.",
                    "Generates text, graphics, 5-slide carousels, and 9:16 short videos under 60 seconds with narration.",
                    "Every claim is grounded in original source quotes with timestamp citations.",
                    "Automatic scheduling and publishing with idempotency and retry recovery."
                ],
                approved_links=[
                    {"title": "Product Start", "url": "https://incubrix.com/start"},
                    {"title": "Case Studies", "url": "https://incubrix.com/cases"}
                ]
            )
            session.add(brand)
            await session.commit()
            logger.info("Seeded default examiner user and IncuBrix brand profile.")

        # Ensure official live platform accounts (YouTube, Facebook, Instagram) are synced from .env
        from app.core.config import settings
        from app.core.security import encrypt_token
        from datetime import timezone, timedelta

        # 1. Clean up any Twitter / X accounts
        await session.execute(select(ConnectedAccount).where(ConnectedAccount.platform == "x"))
        from sqlalchemy import delete
        await session.execute(delete(ConnectedAccount).where(ConnectedAccount.platform == "x"))

        # 2. Sync YouTube
        if settings.YOUTUBE_ACCESS_TOKEN or settings.YOUTUBE_REFRESH_TOKEN:
            yt_res = await session.execute(select(ConnectedAccount).where(ConnectedAccount.user_id == user.id, ConnectedAccount.platform == "youtube"))
            yt_acc = yt_res.scalars().first()
            if not yt_acc:
                yt_acc = ConnectedAccount(
                    user_id=user.id,
                    platform="youtube",
                    account_id="youtube_channel_incubrix",
                    account_name="IncuBrix Growth Channel",
                    username="incubrix_growth",
                    account_type="channel",
                    status="connected",
                    permissions=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"],
                    scopes=["youtube.upload", "youtube.readonly"]
                )
                session.add(yt_acc)
                await session.flush()
            yt_cred_res = await session.execute(select(OAuthCredential).where(OAuthCredential.connected_account_id == yt_acc.id))
            yt_cred = yt_cred_res.scalar_one_or_none()
            if not yt_cred:
                session.add(OAuthCredential(
                    connected_account_id=yt_acc.id,
                    encrypted_access_token=encrypt_token(settings.YOUTUBE_ACCESS_TOKEN or ""),
                    encrypted_refresh_token=encrypt_token(settings.YOUTUBE_REFRESH_TOKEN) if settings.YOUTUBE_REFRESH_TOKEN else None,
                    expires_at=datetime.now(timezone.utc)
                ))
            else:
                if settings.YOUTUBE_ACCESS_TOKEN:
                    yt_cred.encrypted_access_token = encrypt_token(settings.YOUTUBE_ACCESS_TOKEN)
                if settings.YOUTUBE_REFRESH_TOKEN:
                    yt_cred.encrypted_refresh_token = encrypt_token(settings.YOUTUBE_REFRESH_TOKEN)

        # 3. Sync Facebook
        fb_tok = settings.FACEBOOK_PAGE_ACCESS_TOKEN or settings.FACEBOOK_ACCESS_TOKEN
        if fb_tok:
            # Auto-resolve Page Access Token if a User token was supplied
            page_tok = fb_tok
            try:
                import httpx
                resp = httpx.get(f"https://graph.facebook.com/v19.0/me/accounts?access_token={fb_tok}", timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    target_id = settings.FACEBOOK_PAGE_ID or "1539128952609697"
                    for p in data:
                        if p.get("id") == target_id and p.get("access_token"):
                            page_tok = p["access_token"]
                            logger.info(f"Resolved official Page Access Token for Facebook Page {target_id}")
                            break
            except Exception as e:
                logger.warning(f"Could not auto-resolve Facebook page token: {e}")

            fb_res = await session.execute(select(ConnectedAccount).where(ConnectedAccount.user_id == user.id, ConnectedAccount.platform == "facebook"))
            fb_acc = fb_res.scalars().first()
            if not fb_acc:
                fb_acc = ConnectedAccount(
                    user_id=user.id,
                    platform="facebook",
                    account_id=settings.FACEBOOK_PAGE_ID or "1539128952609697",
                    account_name="Incubrix (Facebook Page)",
                    username="Incubrix",
                    account_type="page",
                    status="connected",
                    permissions=["pages_manage_posts", "pages_read_engagement", "pages_show_list"],
                    scopes=["pages_manage_posts", "pages_read_engagement"]
                )
                session.add(fb_acc)
                await session.flush()
            fb_cred_res = await session.execute(select(OAuthCredential).where(OAuthCredential.connected_account_id == fb_acc.id))
            fb_cred = fb_cred_res.scalar_one_or_none()
            if not fb_cred:
                session.add(OAuthCredential(
                    connected_account_id=fb_acc.id,
                    encrypted_access_token=encrypt_token(page_tok),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=90)
                ))
            else:
                fb_cred.encrypted_access_token = encrypt_token(page_tok)
                fb_cred.encrypted_access_token = encrypt_token(fb_tok)

        # 4. Sync Instagram
        if settings.INSTAGRAM_ACCESS_TOKEN:
            ig_res = await session.execute(select(ConnectedAccount).where(ConnectedAccount.user_id == user.id, ConnectedAccount.platform == "instagram"))
            ig_acc = ig_res.scalars().first()
            if not ig_acc:
                ig_acc = ConnectedAccount(
                    user_id=user.id,
                    platform="instagram",
                    account_id=settings.INSTAGRAM_ACCOUNT_ID or "28810961191905769",
                    account_name="ish_uu.05 (Instagram Professional)",
                    username=settings.INSTAGRAM_USERNAME or "ish_uu.05",
                    account_type="professional",
                    status="connected",
                    permissions=["instagram_content_publish", "instagram_basic"],
                    scopes=["instagram_content_publish", "instagram_basic"]
                )
                session.add(ig_acc)
                await session.flush()
            ig_cred_res = await session.execute(select(OAuthCredential).where(OAuthCredential.connected_account_id == ig_acc.id))
            ig_cred = ig_cred_res.scalar_one_or_none()
            if not ig_cred:
                session.add(OAuthCredential(
                    connected_account_id=ig_acc.id,
                    encrypted_access_token=encrypt_token(settings.INSTAGRAM_ACCESS_TOKEN),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=90)
                ))
            else:
                ig_cred.encrypted_access_token = encrypt_token(settings.INSTAGRAM_ACCESS_TOKEN)

        await session.commit()
        logger.info("Official live accounts auto-synchronized with backend credentials.")


if __name__ == "__main__":
    asyncio.run(init_db())
