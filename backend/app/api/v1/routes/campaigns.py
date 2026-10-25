import os
import json
import uuid
import shutil
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db, AsyncSessionLocal
from app.db.models import (
    User, Campaign, CampaignPlan, SourceDocument, SourceExtraction,
    BrandProfile, ContentAsset, AssetVersion, AssetMedia, ScheduledPost, ConnectedAccount
)
from app.schemas.common import CampaignCreate
from app.api.deps import get_current_user
from app.services.ai.campaign_planner import campaign_planner
from app.services.content.post_generator import post_generator
from app.services.validation.brand_validator import brand_validator
from app.services.validation.platform_validator import platform_validator
from app.services.validation.duplicate_checker import duplicate_checker
from app.services.storage.minio_service import storage_service
from app.core.config import VIDEOS_DIR, CAROUSELS_DIR, GRAPHICS_DIR, SOURCE_DIR
from app.services.engines.ad_video_maker import generate_animated_ad_video
from app.services.engines.animated_svg_carousel import generate_and_render_animated_carousel
from app.services.engines.ad_image import generate_poster
from app.core.logging import logger

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


async def run_asset_generation_pipeline(campaign_id: uuid.UUID, user_id: uuid.UUID):
    """
    Background worker task to generate all assets (copy, images, carousels, videos).
    Produces complete, validated outputs with editable source JSONs stored in MinIO.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Load campaign and related data
            camp_stmt = select(Campaign).where(Campaign.id == campaign_id)
            c_res = await session.execute(camp_stmt)
            campaign = c_res.scalar_one_or_none()
            if not campaign:
                return

            plan_stmt = select(CampaignPlan).where(CampaignPlan.campaign_id == campaign_id)
            p_res = await session.execute(plan_stmt)
            plan = p_res.scalar_one_or_none()
            if not plan:
                return

            brand_stmt = select(BrandProfile).where(BrandProfile.id == campaign.brand_profile_id)
            b_res = await session.execute(brand_stmt)
            brand = b_res.scalar_one_or_none()
            brand_dict = {
                "brand_name": brand.brand_name if brand else "IncuBrix",
                "tone_of_voice": brand.tone_of_voice if brand else "Educational, High-Signal",
                "default_cta": brand.default_cta if brand else "Repurpose with IncuBrix → incubrix.com/start",
                "primary_color": brand.primary_color if brand else "#4F46E5",
                "secondary_color": brand.secondary_color if brand else "#0F172A",
                "words_to_avoid": brand.words_to_avoid if brand else [],
                "verified_product_facts": brand.verified_product_facts if brand else []
            }

            slots = plan.schedule_matrix or []
            existing_fingerprints = set()

            logger.info(f"Generating assets for campaign {campaign.id} across {len(slots)} slots")

            for slot in slots:
                asset_id = uuid.uuid4()
                fmt = slot.get("format", "text")
                platform = slot.get("platform", "x")
                topic = slot.get("topic", "Content Growth")
                hook_concept = slot.get("hook_concept", "")
                source_ref = slot.get("source_reference", "")
                day = slot.get("day", 1)
                scheduled_str = slot.get("scheduled_utc")
                scheduled_dt = datetime.fromisoformat(scheduled_str) if scheduled_str else datetime.now(timezone.utc)

                # 1. Generate Platform Native Copy
                copy_result = await post_generator.generate_post_copy(
                    slot_brief=slot,
                    brand_profile=brand_dict,
                    campaign_name=campaign.name,
                    asset_id=str(asset_id)
                )

                hook = copy_result["hook"]
                caption = copy_result["caption"]
                hashtags = copy_result["hashtags"]
                cta = copy_result["cta"]
                tracking_url = copy_result["tracking_url"]
                utm_params = copy_result["utm_parameters"]

                # 2. Check for Duplicates
                fingerprint = duplicate_checker.generate_fingerprint(caption, source_ref)
                is_duplicate = duplicate_checker.check_duplicate(fingerprint, existing_fingerprints)
                existing_fingerprints.add(fingerprint)

                # 3. Create ContentAsset record
                asset = ContentAsset(
                    id=asset_id,
                    campaign_id=campaign.id,
                    source_document_id=campaign.source_document_id,
                    slot_index=slot.get("slot_index", 0),
                    day_number=day,
                    scheduled_slot_time=scheduled_dt,
                    platform=platform,
                    format=fmt,
                    hook=hook,
                    caption=caption,
                    hashtags=hashtags,
                    cta=cta,
                    tracking_url=tracking_url,
                    utm_parameters=utm_params,
                    source_references=[{"quote": source_ref, "pillar": slot.get("pillar")}],
                    approval_status="approved",  # Pre-approve generated assets for assessment workflow
                    duplicate_fingerprint=fingerprint
                )
                session.add(asset)
                await session.flush()

                # Version 1
                version = AssetVersion(
                    content_asset_id=asset.id,
                    version_number=1,
                    hook=hook,
                    caption=caption,
                    hashtags=hashtags,
                    cta=cta,
                    tracking_url=tracking_url,
                    change_notes="Initial AI generation grounded in source citations"
                )
                session.add(version)

                # 4. Generate Media using Creative Studios (Poster Studio, Carousel Studio, Video Studio)
                media_info = None
                try:
                    if fmt in ("image", "poster", "graphic"):
                        aid = f"INC-PST-{uuid.uuid4().hex[:6].upper()}"
                        target_dir = GRAPHICS_DIR / aid
                        target_dir.mkdir(parents=True, exist_ok=True)

                        aspect = "1:1" if platform in ("facebook", "x") else ("4:5" if platform == "instagram" else "1:1")
                        dims = {"1:1": (1080, 1080), "4:5": (1080, 1350), "9:16": (1080, 1920), "16:9": (1920, 1080)}
                        w, h = dims.get(aspect, (1080, 1080))

                        uc = f"Brand: {brand_dict.get('brand_name', 'IncuBrix')}. Goal: {campaign.name}. Topic: {topic}. Hook: {hook}. Takeaway: {source_ref}."

                        logger.info(f"Generating campaign poster via Poster Studio for asset {asset.id} ({aid})...")
                        res = await asyncio.to_thread(
                            generate_poster,
                            use_case=uc,
                            output_dir=target_dir,
                            name=aid,
                            aspect=aspect,
                            language="English",
                            direction="bold, high-contrast and punchy",
                            variants=1,
                            render=True
                        )

                        posters = res.get("posters", [])
                        if posters:
                            first = posters[0]
                            svg_file = Path(first["svg"])
                            png_file = Path(first["png"]) if first.get("png") else None

                            std_svg = GRAPHICS_DIR / f"{aid}.svg"
                            std_png = GRAPHICS_DIR / f"{aid}.png"
                            std_brief = GRAPHICS_DIR / f"{aid}.brief.json"

                            if svg_file.exists():
                                shutil.copy2(svg_file, std_svg)
                            if png_file and png_file.exists():
                                shutil.copy2(png_file, std_png)
                            if Path(first.get("brief", "")).exists():
                                shutil.copy2(Path(first["brief"]), std_brief)

                            # Guarantee PNG exists: render via Playwright if needed
                            if (not std_png.exists() or std_png.stat().st_size == 0) and std_svg.exists() and std_svg.stat().st_size > 0:
                                try:
                                    from playwright.async_api import async_playwright
                                    async with async_playwright() as p:
                                        b = await p.chromium.launch(headless=True)
                                        page = await b.new_page(viewport={"width": w, "height": h})
                                        await page.goto(std_svg.resolve().as_uri(), wait_until="networkidle", timeout=30000)
                                        await page.wait_for_timeout(600)
                                        await page.screenshot(path=str(std_png), type="png")
                                        if png_file:
                                            shutil.copy2(std_png, png_file)
                                        await b.close()
                                except Exception as render_err:
                                    logger.error(f"Failed to render poster PNG via playwright: {render_err}")

                            png_key = f"users/{user_id}/campaigns/{campaign.id}/assets/{asset.id}/{aid}.png"
                            svg_key = f"users/{user_id}/campaigns/{campaign.id}/assets/{asset.id}/{aid}.svg"

                            png_bytes = std_png.read_bytes() if (std_png.exists() and std_png.stat().st_size > 0) else (png_file.read_bytes() if png_file and png_file.exists() and png_file.stat().st_size > 0 else b"")
                            svg_bytes = std_svg.read_bytes() if (std_svg.exists() and std_svg.stat().st_size > 0) else (svg_file.read_bytes() if svg_file.exists() and svg_file.stat().st_size > 0 else b"")

                            if png_bytes:
                                storage_service.upload_bytes(object_key=png_key, data=png_bytes, content_type="image/png")
                            if svg_bytes:
                                storage_service.upload_bytes(object_key=svg_key, data=svg_bytes, content_type="image/svg+xml")

                            media_record = AssetMedia(
                                content_asset_id=asset.id,
                                media_type="image",
                                file_name=f"{aid}.png",
                                file_size_bytes=len(png_bytes),
                                mime_type="image/png",
                                minio_object_key=png_key,
                                width=w,
                                height=h,
                                editable_config={
                                    "aid": aid,
                                    "aspect": aspect,
                                    "svg_url": f"/media/graphics/{aid}.svg",
                                    "png_url": f"/media/graphics/{aid}.png"
                                }
                            )
                            session.add(media_record)
                            media_info = {"width": w, "height": h}

                    elif fmt == "carousel":
                        aid = f"INC-CAR-{uuid.uuid4().hex[:6].upper()}"
                        target_dir = CAROUSELS_DIR / aid
                        target_dir.mkdir(parents=True, exist_ok=True)
                        num_slides = 4

                        use_case = {
                            "brand": brand_dict.get("brand_name", "IncuBrix"),
                            "goal": campaign.name,
                            "audience": "B2B SaaS Founders & Growth Engineers",
                            "tone": brand_dict.get("tone_of_voice", "High-Authority, Technical, Sharp"),
                            "offer": brand_dict.get("default_cta", "Try IncuBrix free at incubrix.com"),
                            "num_slides": num_slides,
                            "topic": topic,
                            "hook": hook,
                            "source_context": source_ref
                        }

                        logger.info(f"Generating campaign carousel via Carousel Studio for asset {asset.id} ({aid})...")
                        res = await asyncio.to_thread(
                            generate_and_render_animated_carousel,
                            use_case=use_case,
                            output_dir=target_dir,
                            asset_id=aid,
                            render_videos=False
                        )

                        actual_count = len(res.get("svg_paths", []))
                        total_slides_count = actual_count if actual_count > 0 else num_slides
                        for idx in range(1, total_slides_count + 1):
                            svg_path = target_dir / f"slide_{idx}.svg"
                            png_path = target_dir / f"slide_{idx}.png"

                            svg_bytes = svg_path.read_bytes() if svg_path.exists() else b""
                            png_bytes = png_path.read_bytes() if png_path.exists() else b""

                            svg_key = f"users/{user_id}/campaigns/{campaign.id}/assets/{asset.id}/slide_{idx}.svg"
                            png_key = f"users/{user_id}/campaigns/{campaign.id}/assets/{asset.id}/slide_{idx}.png"

                            if png_bytes:
                                storage_service.upload_bytes(object_key=png_key, data=png_bytes, content_type="image/png")
                            if svg_bytes:
                                storage_service.upload_bytes(object_key=svg_key, data=svg_bytes, content_type="image/svg+xml")

                            session.add(AssetMedia(
                                content_asset_id=asset.id,
                                media_type="carousel_slide",
                                file_name=f"slide_{idx}.png",
                                file_size_bytes=len(png_bytes),
                                mime_type="image/png",
                                minio_object_key=png_key,
                                slide_index=idx,
                                width=1080,
                                height=1350,
                                editable_config={
                                    "aid": aid,
                                    "slide_idx": idx,
                                    "svg_url": f"/media/carousels/{aid}/slide_{idx}.svg",
                                    "png_url": f"/media/carousels/{aid}/slide_{idx}.png"
                                }
                            ))

                        # Multi-page PDF
                        pdf_file = target_dir / f"{aid}.pdf"
                        if not pdf_file.exists():
                            alt_pdf = list(target_dir.glob("*.pdf"))
                            if alt_pdf:
                                pdf_file = alt_pdf[0]

                        pdf_bytes = pdf_file.read_bytes() if pdf_file.exists() else b""
                        pdf_key = f"users/{user_id}/campaigns/{campaign.id}/assets/{asset.id}/{aid}.pdf"
                        if pdf_bytes:
                            storage_service.upload_bytes(object_key=pdf_key, data=pdf_bytes, content_type="application/pdf")
                            session.add(AssetMedia(
                                content_asset_id=asset.id,
                                media_type="carousel_pdf",
                                file_name=f"{aid}.pdf",
                                file_size_bytes=len(pdf_bytes),
                                mime_type="application/pdf",
                                minio_object_key=pdf_key,
                                slide_index=0,
                                editable_config={"aid": aid, "pdf_url": f"/media/carousels/{aid}/{aid}.pdf"}
                            ))

                        media_info = {"total_slides": total_slides_count}

                    elif fmt in ("short_video", "video", "reel", "shorts"):
                        aid = f"INC-VID-{uuid.uuid4().hex[:6].upper()}"
                        target_dir = VIDEOS_DIR / aid
                        target_dir.mkdir(parents=True, exist_ok=True)
                        aspect = "9:16"

                        uc = (
                            f"Brand: {brand_dict.get('brand_name', 'IncuBrix')}. Goal: {campaign.name}. "
                            f"Topic: {topic}. Hook: {hook}. Takeaway: {source_ref}. "
                            f"Audience: B2B SaaS Founders & Growth Engineers. Tone: {brand_dict.get('tone_of_voice', 'High-Authority, Technical, Sharp')}. "
                            f"Offer: {brand_dict.get('default_cta', 'Try IncuBrix free at incubrix.com')}."
                        )

                        logger.info(f"Generating campaign video via Video Studio for asset {asset.id} ({aid})...")
                        res = await asyncio.to_thread(
                            generate_animated_ad_video,
                            use_case=uc,
                            output_dir=target_dir,
                            asset_id=aid,
                            aspect=aspect,
                            seconds=0,
                            scenes_count=3,
                            voice=None
                        )

                        chosen_voice = res.get("voice") or "Kore"
                        storyboard = res.get("storyboard") or {}
                        sb_scenes = storyboard.get("scenes", [])
                        total_scenes = res.get("scenes_count") or len(sb_scenes)
                        duration_s = float(res.get("duration", 15.0))

                        final_file = Path(res["video_path"]) if res.get("video_path") else (target_dir / f"{aid}.mp4")
                        std_path = VIDEOS_DIR / f"{aid}.mp4"
                        if final_file.exists() and final_file != std_path:
                            shutil.copy2(final_file, std_path)

                        minio_key = f"users/{user_id}/campaigns/{campaign.id}/assets/{asset.id}/{aid}.mp4"
                        file_bytes = final_file.read_bytes() if final_file.exists() else b""
                        if file_bytes:
                            storage_service.upload_bytes(
                                object_key=minio_key,
                                data=file_bytes,
                                content_type="video/mp4"
                            )

                        media_rec = AssetMedia(
                            content_asset_id=asset.id,
                            media_type="video",
                            file_name=f"{aid}.mp4",
                            file_size_bytes=len(file_bytes),
                            mime_type="video/mp4",
                            minio_object_key=minio_key,
                            duration_seconds=duration_s,
                            width=1080,
                            height=1920,
                            editable_config={
                                "aid": aid,
                                "voice": chosen_voice,
                                "storyboard": storyboard,
                                "scenes": sb_scenes,
                                "local_stream_url": f"/media/videos/{aid}.mp4",
                                "aspect": aspect
                            }
                        )
                        session.add(media_rec)
                        media_info = {
                            "duration_seconds": duration_s,
                            "width": 1080,
                            "height": 1920
                        }
                except Exception as media_err:
                    logger.error(f"Media generation failed for asset {asset.id} ({fmt}): {media_err}", exc_info=True)

                # 5. Validate Brand and Platform Rules
                brand_check = brand_validator.validate_asset(
                    hook=hook,
                    caption=caption,
                    cta=cta,
                    tracking_url=tracking_url,
                    brand_profile=brand_dict
                )
                platform_check = platform_validator.validate_platform_asset(
                    platform=platform,
                    fmt=fmt,
                    hook=hook,
                    caption=caption,
                    hashtags=hashtags,
                    media_info=media_info
                )

                quality_status = "passed" if (brand_check["passed"] and platform_check["passed"]) else "warnings"
                asset.quality_status = quality_status
                asset.quality_checks = {
                    "brand": brand_check,
                    "platform": platform_check,
                    "is_duplicate": is_duplicate
                }

                # 6. Look up active ConnectedAccount and Create Persistent ScheduledPost (safely checking for existing)
                conn_acc_res = await session.execute(
                    select(ConnectedAccount)
                    .where(
                        ConnectedAccount.user_id == campaign.user_id,
                        ConnectedAccount.platform == asset.platform.lower(),
                        ConnectedAccount.status == "connected"
                    )
                    .order_by(ConnectedAccount.created_at.desc())
                )
                conn_acc = conn_acc_res.scalars().first()

                existing_post_res = await session.execute(
                    select(ScheduledPost).where(
                        ScheduledPost.content_asset_id == asset.id
                    )
                )
                existing_post = existing_post_res.scalars().first()

                if not existing_post:
                    scheduled_post = ScheduledPost(
                        content_asset_id=asset.id,
                        connected_account_id=conn_acc.id if conn_acc else None,
                        scheduled_utc=scheduled_dt,
                        original_timezone=campaign.timezone_name or "UTC",
                        status="scheduled"
                    )
                    session.add(scheduled_post)
                else:
                    if conn_acc:
                        existing_post.connected_account_id = conn_acc.id
                    existing_post.scheduled_utc = scheduled_dt
                    existing_post.status = "scheduled"

                await session.commit()

            campaign.status = "generated"
            await session.commit()
            logger.info(f"Campaign {campaign.id} assets and scheduling fully completed.")
        except Exception as e:
            logger.error(f"Asset pipeline error for campaign {campaign_id}: {e}")


@router.post("", status_code=201)
async def create_campaign(
    campaign_in: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Creates a campaign record and links brand profile and source."""
    brand_id = campaign_in.brand_profile_id
    if not brand_id:
        res = await db.execute(select(BrandProfile).where(BrandProfile.user_id == current_user.id))
        brand = res.scalar_one_or_none()
        brand_id = brand.id if brand else None

    campaign = Campaign(
        user_id=current_user.id,
        brand_profile_id=brand_id,
        source_document_id=campaign_in.source_document_id,
        name=campaign_in.name,
        duration_days=campaign_in.duration_days,
        platforms=campaign_in.platforms,
        formats=campaign_in.formats,
        timezone_name=campaign_in.timezone_name,
        status="draft"
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    return {
        "id": campaign.id,
        "name": campaign.name,
        "duration_days": campaign.duration_days,
        "platforms": campaign.platforms,
        "status": campaign.status,
        "created_at": campaign.created_at.isoformat()
    }


@router.post("/{campaign_id}/plan")
async def plan_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generates the 30-day schedule matrix with 5 content pillars."""
    camp_res = await db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == current_user.id))
    campaign = camp_res.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Load extraction and brand profile
    extraction_data = {}
    if campaign.source_document_id:
        ext_res = await db.execute(select(SourceExtraction).where(SourceExtraction.source_document_id == campaign.source_document_id))
        extraction = ext_res.scalar_one_or_none()
        if extraction:
            extraction_data = {
                "main_subject": extraction.main_subject,
                "topics": extraction.topics,
                "subtopics": extraction.subtopics,
                "key_facts": extraction.key_claims,
                "quotes_with_timestamps": extraction.quotes_with_timestamps
            }

    brand_data = {}
    if campaign.brand_profile_id:
        b_res = await db.execute(select(BrandProfile).where(BrandProfile.id == campaign.brand_profile_id))
        brand = b_res.scalar_one_or_none()
        if brand:
            brand_data = {
                "brand_name": brand.brand_name,
                "tone_of_voice": brand.tone_of_voice,
                "default_cta": brand.default_cta
            }

    # Generate plan
    plan_dict = await campaign_planner.create_plan(
        campaign_name=campaign.name,
        source_analysis=extraction_data,
        brand_profile=brand_data,
        platforms=campaign.platforms,
        duration_days=campaign.duration_days,
        formats=campaign.formats
    )

    # Save CampaignPlan
    plan = CampaignPlan(
        campaign_id=campaign.id,
        title=plan_dict.get("title", f"Plan for {campaign.name}"),
        strategy_summary=plan_dict.get("strategy_summary", ""),
        total_slots=plan_dict.get("total_slots", len(plan_dict.get("slots", []))),
        pillar_distribution=plan_dict.get("pillar_distribution", {}),
        schedule_matrix=plan_dict.get("slots", [])
    )
    db.add(plan)
    campaign.status = "planning"
    await db.commit()
    await db.refresh(plan)

    return {
        "campaign_id": campaign.id,
        "title": plan.title,
        "strategy_summary": plan.strategy_summary,
        "total_slots": plan.total_slots,
        "pillar_distribution": plan.pillar_distribution,
        "slots_count": len(plan.schedule_matrix)
    }


@router.post("/{campaign_id}/generate-assets")
async def generate_assets(
    campaign_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Triggers generation of all assets across the planned schedule slots."""
    camp_res = await db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == current_user.id))
    campaign = camp_res.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    plan_res = await db.execute(select(CampaignPlan).where(CampaignPlan.campaign_id == campaign_id))
    plan = plan_res.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=400, detail="Campaign plan must be generated first")

    # Launch generation pipeline in background
    background_tasks.add_task(run_asset_generation_pipeline, campaign.id, current_user.id)

    return {
        "success": True,
        "message": f"Asset generation initiated for {len(plan.schedule_matrix)} slots.",
        "campaign_id": campaign.id
    }


@router.get("")
async def list_campaigns(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Campaign).where(Campaign.user_id == current_user.id).order_by(Campaign.created_at.desc())
    res = await db.execute(stmt)
    campaigns = res.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "duration_days": c.duration_days,
            "platforms": c.platforms,
            "formats": c.formats,
            "status": c.status,
            "created_at": c.created_at.isoformat()
        }
        for c in campaigns
    ]


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
    res = await db.execute(stmt)
    campaign = res.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    plan_res = await db.execute(select(CampaignPlan).where(CampaignPlan.campaign_id == campaign_id))
    plan = plan_res.scalar_one_or_none()

    assets_res = await db.execute(select(ContentAsset).where(ContentAsset.campaign_id == campaign_id))
    assets = assets_res.scalars().all()

    return {
        "id": campaign.id,
        "name": campaign.name,
        "duration_days": campaign.duration_days,
        "platforms": campaign.platforms,
        "formats": campaign.formats,
        "timezone_name": campaign.timezone_name,
        "status": campaign.status,
        "created_at": campaign.created_at.isoformat(),
        "total_assets": len(assets),
        "plan": {
            "title": plan.title,
            "strategy_summary": plan.strategy_summary,
            "total_slots": plan.total_slots,
            "pillar_distribution": plan.pillar_distribution
        } if plan else None
    }


@router.get("/{campaign_id}/export")
async def export_campaign_launch_kit(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generates a complete launch-ready Markdown & CSV content calendar export."""
    camp_res = await db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == current_user.id))
    campaign = camp_res.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    assets_res = await db.execute(
        select(ContentAsset)
        .where(ContentAsset.campaign_id == campaign_id)
        .order_by(ContentAsset.day_number.asc(), ContentAsset.slot_index.asc())
    )
    assets = assets_res.scalars().all()

    # Build Markdown Launch Kit
    md_lines = [
        f"# IncuBrix 30-Day Social Media Launch Kit: {campaign.name}",
        f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"**Duration**: {campaign.duration_days} Days | **Total Assets**: {len(assets)}",
        f"**Platforms**: {', '.join(campaign.platforms or [])}",
        "\n---\n",
        "## Scheduled Assets Matrix\n",
        "| Day | Platform | Format | Hook | CTA | Status |",
        "|:---:|:--------:|:------:|:-----|:----|:------:|"
    ]
    for a in assets:
        clean_hook = a.hook.replace("|", "/").replace("\n", " ")[:60]
        md_lines.append(f"| Day {a.day_number} | {a.platform.upper()} | {a.format} | {clean_hook} | {a.cta[:25]} | {a.approval_status.upper()} |")

    md_content = "\n".join(md_lines)
    return {
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "total_assets": len(assets),
        "launch_kit_markdown": md_content
    }
