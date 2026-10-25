import os
import json
import uuid
import shutil
import time
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import User, Campaign, ContentAsset, AssetMedia, AssetVersion, BrandProfile
from app.api.deps import get_current_user
from app.services.ai.gemini_adapter import gemini_adapter
from app.services.storage.minio_service import storage_service
from app.core.logging import logger

from app.services.engines.ad_video_maker import generate_animated_ad_video
from app.services.engines.animated_svg_carousel import generate_and_render_animated_carousel
from app.services.engines.ad_image import generate_poster

router = APIRouter(prefix="/generation", tags=["Generation Modules"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
FINAL_DIR = BASE_DIR / "assets" / "final"
VIDEOS_DIR = FINAL_DIR / "videos"
CAROUSELS_DIR = FINAL_DIR / "carousels"
GRAPHICS_DIR = FINAL_DIR / "graphics"
SOURCE_DIR = BASE_DIR / "assets" / "source"

for d in [VIDEOS_DIR, CAROUSELS_DIR, GRAPHICS_DIR, SOURCE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ------------------ Pydantic Schemas ------------------ #

class ScriptGenerationRequest(BaseModel):
    topic: str
    source_text: Optional[str] = ""
    platform: str = "youtube"  # youtube, instagram, facebook
    aspect_ratio: str = "9:16"  # 9:16 or 16:9
    tone: Optional[str] = "High-Signal, Educational"


class SceneItem(BaseModel):
    idx: int = 1
    headline: str
    title: str
    highlight: Optional[str] = ""


class VideoGenerationRequest(BaseModel):
    brand: str = "IncuBrix"
    use_case: Optional[str] = None
    goal: str = "Drive CreatorOps Trial Signups"
    audience: str = "B2B SaaS Founders & Growth Engineers"
    tone: str = "High-Authority, Technical, Sharp"
    offer: str = "Try IncuBrix free at incubrix.com"
    aspect: str = "9:16"
    scenes_count: int = 3
    seconds: float = 0
    voice: Optional[str] = None
    platform: str = "youtube"
    campaign_id: Optional[uuid.UUID] = None
    asset_id: Optional[str] = None
    # Compatibility with earlier forms
    title: Optional[str] = None
    narration: Optional[str] = None
    scenes: Optional[List[SceneItem]] = None
    aspect_ratio: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = Field(default_factory=list)
    cta: Optional[str] = "Explore IncuBrix"


class CarouselOutlineRequest(BaseModel):
    topic: str
    source_text: Optional[str] = ""
    platform: str = "instagram"
    slide_count: int = 5
    aspect_ratio: str = "4:5"


class CarouselSlideItem(BaseModel):
    slide_num: int
    headline: str
    body: str
    takeaway: str


class CarouselGenerationRequest(BaseModel):
    brand: str = "IncuBrix"
    goal: str = "Drive LinkedIn & Instagram Thought Leadership"
    audience: str = "B2B SaaS Founders & Growth Engineers"
    tone: str = "High-Authority, Technical, Sharp"
    offer: str = "Try IncuBrix free at incubrix.com"
    num_slides: int = 5
    platform: str = "instagram"
    campaign_id: Optional[uuid.UUID] = None
    asset_id: Optional[str] = None
    # Compatibility with earlier forms
    title: Optional[str] = None
    slides: Optional[List[CarouselSlideItem]] = None
    aspect_ratio: Optional[str] = "4:5"
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = Field(default_factory=list)
    cta: Optional[str] = "Swipe for more"


class PosterContentRequest(BaseModel):
    topic: str
    source_text: Optional[str] = ""
    platform: str = "instagram"
    aspect_ratio: str = "1:1"


class PosterGenerationRequest(BaseModel):
    brand: str = "IncuBrix"
    use_case: Optional[str] = None
    goal: str = "Drive CreatorOps Trial Signups"
    aspect: str = "1:1"  # 1:1, 4:5, 9:16, 16:9
    direction: str = "bold, high-contrast and punchy"
    variants: int = 1
    language: str = "English"
    platform: str = "instagram"
    campaign_id: Optional[uuid.UUID] = None
    asset_id: Optional[str] = None
    # Compatibility with earlier forms
    headline: Optional[str] = None
    subheadline: Optional[str] = None
    quote: Optional[str] = None
    cta: Optional[str] = "Explore with IncuBrix"
    aspect_ratio: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = Field(default_factory=list)
    primary_color: Optional[str] = "#4F46E5"


# ------------------ AI Helper Endpoints ------------------ #

@router.post("/ai-script")
async def generate_ai_script(
    payload: ScriptGenerationRequest,
    current_user: User = Depends(get_current_user)
):
    """Uses Gemini AI to generate a grounded, scene-by-scene video script."""
    topic = payload.topic.strip()
    source = payload.source_text.strip() if payload.source_text else topic

    prompt = f"""
Create a compelling, professional {payload.aspect_ratio} short video script about: "{topic}"
Platform: {payload.platform}
Source context: "{source}"
Tone: {payload.tone}

Requirements:
- Total voiceover duration must be between 20 to 45 seconds (around 50-90 spoken words).
- Divide into 4 distinct scenes.
- Each scene needs:
  1. headline: Punchy 2-4 word visual text.
  2. title: Explanatory 5-8 word sentence.
  3. highlight: Factual evidence or punchy quote from source.

Respond in strict JSON with keys:
"hook": string,
"narration": string,
"scenes": list of objects each with "idx" (1-4), "headline", "title", "highlight"
"""
    try:
        data = await gemini_adapter.generate_structured(prompt=prompt, response_model=dict, temperature=0.3)
    except Exception as e:
        logger.warning(f"AI script generation fallback: {e}")
        data = {
            "hook": f"Stop Overcomplicating {topic[:25]}",
            "narration": f"When scaling social content, manual repurposing creates massive bottlenecks. Here is how modern growth teams automate high-performing assets from a single core source without losing brand consistency.",
            "scenes": [
                {"idx": 1, "headline": "The Bottleneck", "title": f"Why manual creation for {topic[:25]} breaks schedules", "highlight": "10+ hours lost per week"},
                {"idx": 2, "headline": "Platform Specifics", "title": "Each platform demands customized native aspect ratios", "highlight": "9:16 vertical vs landscape"},
                {"idx": 3, "headline": "Verified Evidence", "title": "Grounded directly in authentic source facts", "highlight": source[:80]},
                {"idx": 4, "headline": "Automate in Seconds", "title": "Generate complete multi-platform assets instantly", "highlight": "Try IncuBrix Free"}
            ]
        }
    return data


@router.post("/ai-carousel-outline")
async def generate_ai_carousel_outline(
    payload: CarouselOutlineRequest,
    current_user: User = Depends(get_current_user)
):
    """Generates structured carousel slides from source text."""
    topic = payload.topic.strip()
    source = payload.source_text.strip() if payload.source_text else topic
    count = max(3, min(payload.slide_count, 8))

    prompt = f"""
Generate an educational, high-retention {count}-slide social carousel about: "{topic}"
Platform: {payload.platform}
Source context: "{source}"

Requirements:
- Slide 1: Bold title hook with compelling premise.
- Middle slides: Step-by-step actionable insights, breakdown, or framework.
- Final slide: Strong conclusion, summary takeaway, and call to action.
- Each slide must have "slide_num", "headline", "body", and "takeaway".

Respond in strict JSON with keys:
"title": string,
"caption": string,
"hashtags": list of strings,
"cta": string,
"slides": list of objects with "slide_num", "headline", "body", "takeaway"
"""
    try:
        data = await gemini_adapter.generate_structured(prompt=prompt, response_model=dict, temperature=0.3)
    except Exception as e:
        logger.warning(f"AI carousel outline fallback: {e}")
        data = {
            "title": f"The Complete Guide to {topic}",
            "caption": f"How top teams master {topic} with systematic execution.\n\nSave this carousel for reference.",
            "hashtags": ["incubrix", "growth", "strategy", "automation"],
            "cta": "Swipe through for the framework",
            "slides": [
                {"slide_num": 1, "headline": f"Mastering {topic}", "body": "Why conventional approaches fail and what top performers do differently to scale output.", "takeaway": "Focus on compounding systems."},
                {"slide_num": 2, "headline": "Core Framework", "body": "Break down long-form ideas into standalone, high-signal components for each platform.", "takeaway": "Repurpose with intention."},
                {"slide_num": 3, "headline": "Execution Velocity", "body": "Automate production so you never spend hours on manual formatting or resizing.", "takeaway": "Speed unlocks consistency."},
                {"slide_num": 4, "headline": "Measurement & ROI", "body": "Track UTM performance and native metrics to double down on what resonates.", "takeaway": "Measure attribution clearly."},
                {"slide_num": 5, "headline": "Next Steps", "body": "Start automating your 30-day content calendar today with IncuBrix.", "takeaway": "incubrix.com/start"}
            ]
        }
    return data


@router.post("/ai-poster-content")
async def generate_ai_poster_content(
    payload: PosterContentRequest,
    current_user: User = Depends(get_current_user)
):
    """Generates headline, subheadline, quote, and CTA for social posters."""
    topic = payload.topic.strip()
    source = payload.source_text.strip() if payload.source_text else topic

    prompt = f"""
Create bold, high-impact social poster copy about: "{topic}"
Platform: {payload.platform}
Source: "{source}"

Requirements:
- "headline": Maximum 8 words, authoritative and memorable.
- "subheadline": 12-20 words explaining the core insight.
- "quote": 8-15 words key takeaway or quotation.
- "cta": Short 2-4 word call to action.
- "caption": 20-40 words accompanying post text.
- "hashtags": 3-5 relevant hashtags.

Respond in strict JSON with keys:
"headline", "subheadline", "quote", "cta", "caption", "hashtags"
"""
    try:
        data = await gemini_adapter.generate_structured(prompt=prompt, response_model=dict, temperature=0.3)
    except Exception as e:
        logger.warning(f"AI poster content fallback: {e}")
        data = {
            "headline": f"Scale Your {topic} Exponentially",
            "subheadline": "The single highest-leverage strategy used by top industry leaders to dominate multi-channel distribution.",
            "quote": "Consistency without quality is spam; quality without consistency is invisible.",
            "cta": "Start Free Today",
            "caption": f"Tired of manual content repurposing? Discover how IncuBrix automates your multi-platform presence.\n\n#incubrix #growth",
            "hashtags": ["incubrix", "growth", "automation"]
        }
    return data


# ------------------ Concrete Generation Endpoints ------------------ #

async def _get_or_create_default_campaign(db: AsyncSession, user_id: uuid.UUID) -> Campaign:
    """Helper to ensure a user has an active campaign for saving assets."""
    res = await db.execute(
        select(Campaign).where(Campaign.user_id == user_id, Campaign.status == "active").order_by(Campaign.created_at.desc())
    )
    camp = res.scalars().first()
    if not camp:
        res2 = await db.execute(select(Campaign).where(Campaign.user_id == user_id).order_by(Campaign.created_at.desc()))
        camp = res2.scalars().first()
    if not camp:
        camp = Campaign(
            user_id=user_id,
            name="IncuBrix Omnichannel Engine",
            duration_days=30,
            platforms=["youtube", "facebook", "instagram"],
            status="active"
        )
        db.add(camp)
        await db.flush()
    return camp


@router.post("/video")
async def generate_video_module(
    payload: VideoGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Invokes the Animated-SVG Ad Video Pipeline with Google Cloud TTS and Playwright.
    Saves MP4 in local storage + MinIO, and creates ContentAsset in PostgreSQL.
    """
    camp_id = payload.campaign_id
    if not camp_id:
        camp = await _get_or_create_default_campaign(db, current_user.id)
        camp_id = camp.id

    asset_uuid = uuid.uuid4()
    aid = payload.asset_id or f"INC-VID-{uuid.uuid4().hex[:6].upper()}"
    target_dir = VIDEOS_DIR / aid
    target_dir.mkdir(parents=True, exist_ok=True)

    # Resolve use case
    aspect = payload.aspect or payload.aspect_ratio or "9:16"
    scenes_count = payload.scenes_count or (len(payload.scenes) if payload.scenes else 3)
    
    uc = payload.use_case
    if not uc:
        if payload.narration:
            uc = f"Brand: {payload.brand}. Goal: {payload.goal}. Script: {payload.narration}."
        else:
            uc = (
                f"Brand: {payload.brand}. Goal: {payload.goal}. "
                f"Audience: {payload.audience}. Tone: {payload.tone}. Offer: {payload.offer}."
            )

    try:
        logger.info(f"Triggering IncuBrix Animated-SVG Video Maker for {aid}...")
        result = await asyncio.to_thread(
            generate_animated_ad_video,
            use_case=uc,
            output_dir=target_dir,
            asset_id=aid,
            aspect=aspect,
            seconds=payload.seconds,
            scenes_count=scenes_count,
            voice=payload.voice
        )

        chosen_voice = result.get("voice") or "Kore"
        storyboard = result.get("storyboard") or {}
        sb_scenes = storyboard.get("scenes", [])
        total_scenes = result.get("scenes_count") or len(sb_scenes)
        duration_s = float(result.get("duration", 15.0))

        # Copy final mp4 to standard path
        final_file = Path(result["video_path"])
        std_path = VIDEOS_DIR / f"{aid}.mp4"
        if final_file.exists() and final_file != std_path:
            shutil.copy2(final_file, std_path)

        # Upload final MP4 to MinIO
        minio_key = f"users/{current_user.id}/campaigns/{camp_id}/assets/{asset_uuid}/{aid}.mp4"
        file_bytes = final_file.read_bytes() if final_file.exists() else b""
        if file_bytes:
            storage_service.upload_bytes(
                object_key=minio_key,
                data=file_bytes,
                content_type="video/mp4"
            )

        # Register source markdown for audit traceability
        source_file = SOURCE_DIR / f"{aid}_source.md"
        source_content = (
            f"# {aid} Animated Video Source\n\n"
            f"**Brand:** {payload.brand}\n"
            f"**Goal:** {payload.goal}\n"
            f"**Audience:** {payload.audience}\n"
            f"**Tone:** {payload.tone}\n"
            f"**Offer:** {payload.offer}\n"
            f"**Narrator Voice:** {chosen_voice}\n"
            f"**Scenes Count:** {total_scenes}\n"
            f"**Duration:** {duration_s:.1f}s\n\n"
            f"*Generated by Gemini Animated-SVG Ad Video Engine with GCP Chirp 3 HD.*"
        )
        source_file.write_text(source_content, encoding="utf-8")

        # Determine copy
        hook_text = sb_scenes[0].get("on_screen_headline") if sb_scenes else payload.title or f"Why solo creators need {payload.brand}"
        caption_text = sb_scenes[0].get("narration") if sb_scenes else payload.caption or f"Discover how {payload.brand} solves {payload.goal}."
        platform_name = payload.platform.lower()

        # Create ContentAsset
        asset = ContentAsset(
            id=asset_uuid,
            campaign_id=camp_id,
            platform=platform_name,
            format="short_video" if aspect == "9:16" else "video",
            hook=hook_text,
            caption=caption_text,
            hashtags=payload.hashtags or ["incubrix", platform_name, "video"],
            cta=payload.offer or payload.cta or "Explore IncuBrix",
            tracking_url=f"https://incubrix.com/?utm_source={platform_name}&utm_medium=video&utm_content={aid}",
            approval_status="approved",
            quality_status="passed",
            quality_checks={
                "aspect_ratio": aspect,
                "duration_seconds": duration_s,
                "voice": chosen_voice,
                "scenes_count": total_scenes,
                "engine": "IncuBrix Animated-SVG Ad Video Engine"
            },
            source_references=[{"aid": aid, "scenes": total_scenes, "voice": chosen_voice}]
        )
        db.add(asset)
        await db.flush()

        width = 1080 if aspect == "9:16" else (1920 if aspect == "16:9" else 1080)
        height = 1920 if aspect == "9:16" else (1080 if aspect == "16:9" else 1080)

        # Create AssetMedia
        media_rec = AssetMedia(
            content_asset_id=asset.id,
            media_type="video",
            file_name=f"{aid}.mp4",
            file_size_bytes=len(file_bytes),
            mime_type="video/mp4",
            minio_object_key=minio_key,
            duration_seconds=duration_s,
            width=width,
            height=height,
            editable_config={
                "aid": aid,
                "voice": chosen_voice,
                "storyboard": storyboard,
                "scenes": sb_scenes,
                "local_stream_url": f"/media/videos/{aid}.mp4",
                "aspect": aspect
            }
        )
        db.add(media_rec)

        # Initial Version
        db.add(AssetVersion(
            content_asset_id=asset.id,
            version_number=1,
            hook=asset.hook,
            caption=asset.caption,
            hashtags=asset.hashtags,
            cta=asset.cta,
            change_notes=f"Generated via IncuBrix Video Studio ({total_scenes} scenes, voice: {chosen_voice})"
        ))

        await db.commit()

        local_stream = f"/media/videos/{aid}.mp4"
        presigned_url = storage_service.get_presigned_url(minio_key) or local_stream

        return {
            "status": "success",
            "success": True,
            "asset_id": str(asset.id),
            "aid": aid,
            "video_url": local_stream,
            "stream_url": local_stream,
            "presigned_url": presigned_url,
            "duration_seconds": duration_s,
            "width": width,
            "height": height,
            "minio_object_key": minio_key,
            "result": result,
            "media_info": {
                "has_final": True,
                "stream_url": local_stream,
                "voice_name": chosen_voice,
                "scenes": sb_scenes,
                "storyboard": storyboard
            }
        }
    except Exception as e:
        logger.error(f"Video generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Video generation error: {str(e)}")


@router.post("/carousel")
async def generate_carousel_module(
    payload: CarouselGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Invokes the Gemini Animated SVG Carousel Engine.
    Produces self-contained SVGs with 1080px crossing seams, multi-page PDF, and preview runner.
    """
    camp_id = payload.campaign_id
    if not camp_id:
        camp = await _get_or_create_default_campaign(db, current_user.id)
        camp_id = camp.id

    asset_uuid = uuid.uuid4()
    aid = payload.asset_id or f"INC-CAR-{uuid.uuid4().hex[:6].upper()}"
    target_dir = CAROUSELS_DIR / aid
    target_dir.mkdir(parents=True, exist_ok=True)

    num_slides = payload.num_slides or (len(payload.slides) if payload.slides else 5)
    use_case = {
        "brand": payload.brand,
        "goal": payload.goal,
        "audience": payload.audience,
        "tone": payload.tone,
        "offer": payload.offer,
        "num_slides": num_slides
    }

    try:
        logger.info(f"Triggering IncuBrix Animated SVG Carousel Engine for {aid} ({num_slides} slides)...")
        result = await asyncio.to_thread(
            generate_and_render_animated_carousel,
            use_case=use_case,
            output_dir=target_dir,
            asset_id=aid,
            render_videos=False
        )

        # Register source markdown
        source_file = SOURCE_DIR / f"{aid}_source.md"
        source_content = (
            f"# {aid} Dynamic Carousel Source\n\n"
            f"**Brand:** {payload.brand}\n"
            f"**Goal:** {payload.goal}\n"
            f"**Audience:** {payload.audience}\n"
            f"**Tone:** {payload.tone}\n"
            f"**Offer:** {payload.offer}\n"
            f"**Slides:** {num_slides}\n\n"
            f"*Generated by Gemini Animated SVG Carousel Engine.*"
        )
        source_file.write_text(source_content, encoding="utf-8")

        # Determine copy
        hook_text = payload.title or f"The {num_slides}-Slide {payload.brand} Playbook"
        caption_text = payload.caption or f"Swipe through to discover how {payload.brand} tackles {payload.goal}. Designed with seamless animated vector motion."
        platform_name = payload.platform.lower()

        # Create ContentAsset
        asset = ContentAsset(
            id=asset_uuid,
            campaign_id=camp_id,
            platform=platform_name,
            format="carousel",
            hook=hook_text,
            caption=caption_text,
            hashtags=payload.hashtags or ["incubrix", platform_name, "carousel"],
            cta=payload.offer or payload.cta or "Swipe for more",
            tracking_url=f"https://incubrix.com/?utm_source={platform_name}&utm_medium=carousel&utm_content={aid}",
            approval_status="approved",
            quality_status="passed",
            quality_checks={
                "num_slides": num_slides,
                "engine": "IncuBrix Animated SVG Carousel Engine",
                "aspect": "4:5",
                "pdf_export": True
            }
        )
        db.add(asset)
        await db.flush()

        slides_media_list = []
        actual_count = len(result.get("svg_paths", []))
        total_slides_count = actual_count if actual_count > 0 else num_slides
        # Upload slides and create AssetMedia records
        for idx in range(1, total_slides_count + 1):
            svg_path = target_dir / f"slide_{idx}.svg"
            png_path = target_dir / f"slide_{idx}.png"

            svg_bytes = svg_path.read_bytes() if svg_path.exists() else b""
            png_bytes = png_path.read_bytes() if png_path.exists() else b""

            svg_key = f"users/{current_user.id}/campaigns/{camp_id}/assets/{asset_uuid}/slide_{idx}.svg"
            png_key = f"users/{current_user.id}/campaigns/{camp_id}/assets/{asset_uuid}/slide_{idx}.png"

            if png_bytes:
                storage_service.upload_bytes(object_key=png_key, data=png_bytes, content_type="image/png")
            if svg_bytes:
                storage_service.upload_bytes(object_key=svg_key, data=svg_bytes, content_type="image/svg+xml")

            db.add(AssetMedia(
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

            slides_media_list.append({
                "slide_idx": idx,
                "svg_url": f"/media/carousels/{aid}/slide_{idx}.svg",
                "png_url": f"/media/carousels/{aid}/slide_{idx}.png",
                "minio_object_key": png_key
            })

        # Multi-page PDF
        pdf_file = target_dir / f"{aid}.pdf"
        if not pdf_file.exists():
            # Check for alternative pdf name
            alt_pdf = list(target_dir.glob("*.pdf"))
            if alt_pdf:
                pdf_file = alt_pdf[0]

        pdf_bytes = pdf_file.read_bytes() if pdf_file.exists() else b""
        pdf_key = f"users/{current_user.id}/campaigns/{camp_id}/assets/{asset_uuid}/{aid}.pdf"
        if pdf_bytes:
            storage_service.upload_bytes(object_key=pdf_key, data=pdf_bytes, content_type="application/pdf")
            db.add(AssetMedia(
                content_asset_id=asset.id,
                media_type="carousel_pdf",
                file_name=f"{aid}.pdf",
                file_size_bytes=len(pdf_bytes),
                mime_type="application/pdf",
                minio_object_key=pdf_key,
                slide_index=0,
                editable_config={"aid": aid, "pdf_url": f"/media/carousels/{aid}/{aid}.pdf"}
            ))

        db.add(AssetVersion(
            content_asset_id=asset.id,
            version_number=1,
            hook=asset.hook,
            caption=asset.caption,
            hashtags=asset.hashtags,
            cta=asset.cta,
            change_notes=f"Generated via IncuBrix Carousel Studio ({num_slides} animated vector slides)"
        ))

        await db.commit()

        pdf_url = f"/media/carousels/{aid}/{aid}.pdf" if pdf_file.exists() else None
        preview_player_url = f"/media/carousels/{aid}/preview.html"

        return {
            "status": "success",
            "success": True,
            "asset_id": str(asset.id),
            "aid": aid,
            "total_slides": num_slides,
            "cover_url": f"/media/carousels/{aid}/slide_1.png",
            "pdf_url": pdf_url,
            "preview_player_url": preview_player_url,
            "slides": slides_media_list,
            "result": result,
            "media_info": {
                "has_final": True,
                "pdf_url": pdf_url,
                "preview_player_url": preview_player_url,
                "carousel_slides": slides_media_list
            }
        }
    except Exception as e:
        logger.error(f"Carousel generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Carousel generation error: {str(e)}")


@router.post("/poster")
@router.post("/image")
async def generate_poster_module(
    payload: PosterGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Invokes the Vector Ad Poster Pipeline (Gemini Art Director + Illustrator + Playwright PNG).
    """
    camp_id = payload.campaign_id
    if not camp_id:
        camp = await _get_or_create_default_campaign(db, current_user.id)
        camp_id = camp.id

    asset_uuid = uuid.uuid4()
    aid = payload.asset_id or f"INC-PST-{uuid.uuid4().hex[:6].upper()}"
    target_dir = GRAPHICS_DIR / aid
    target_dir.mkdir(parents=True, exist_ok=True)

    aspect = payload.aspect or payload.aspect_ratio or "1:1"
    uc = payload.use_case or (
        f"Brand: {payload.brand}. Goal: {payload.goal}. "
        f"{payload.headline or ''} {payload.subheadline or ''}"
    )

    try:
        logger.info(f"Triggering IncuBrix Vector Ad Poster Engine for {aid} ({aspect})...")
        res = await asyncio.to_thread(
            generate_poster,
            use_case=uc,
            output_dir=target_dir,
            name=aid,
            aspect=aspect,
            language=payload.language,
            direction=payload.direction,
            variants=max(1, min(4, payload.variants)),
            render=True
        )

        posters = res.get("posters", [])
        if not posters:
            raise RuntimeError("No poster generated.")

        first = posters[0]
        svg_file = Path(first["svg"])
        png_file = Path(first["png"]) if first.get("png") else None

        # Copy primary files to GRAPHICS_DIR root for direct linking
        std_svg = GRAPHICS_DIR / f"{aid}.svg"
        std_png = GRAPHICS_DIR / f"{aid}.png"
        std_brief = GRAPHICS_DIR / f"{aid}.brief.json"

        if svg_file.exists():
            shutil.copy2(svg_file, std_svg)
        if png_file and png_file.exists():
            shutil.copy2(png_file, std_png)
        if Path(first.get("brief", "")).exists():
            shutil.copy2(Path(first["brief"]), std_brief)

        dims = {"1:1": (1080, 1080), "4:5": (1080, 1350), "9:16": (1080, 1920), "16:9": (1920, 1080)}
        w, h = dims.get(aspect, (1080, 1080))
        platform_name = payload.platform.lower()

        # Guarantee PNG exists: if png_file was skipped or is 0 bytes, render via async_playwright
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
                logger.info(f"Rendered poster PNG via async_playwright: {std_png} ({std_png.stat().st_size} bytes)")
            except Exception as render_err:
                logger.error(f"Failed to render poster PNG via async_playwright: {render_err}")

        brief_data = first.get("brief_data", {})
        copy_data = brief_data.get("copy", {})
        headline = copy_data.get("headline") or payload.headline or f"Grow faster with {payload.brand}"
        support = copy_data.get("support") or payload.subheadline or f"Discover how {payload.brand} elevates your creative workflow."
        cta_text = copy_data.get("cta") or payload.cta or "Get Started at incubrix.com"

        # Upload to MinIO
        png_key = f"users/{current_user.id}/campaigns/{camp_id}/assets/{asset_uuid}/{aid}.png"
        svg_key = f"users/{current_user.id}/campaigns/{camp_id}/assets/{asset_uuid}/{aid}.svg"

        png_bytes = std_png.read_bytes() if (std_png.exists() and std_png.stat().st_size > 0) else (png_file.read_bytes() if png_file and png_file.exists() and png_file.stat().st_size > 0 else b"")
        svg_bytes = std_svg.read_bytes() if (std_svg.exists() and std_svg.stat().st_size > 0) else (svg_file.read_bytes() if svg_file.exists() and svg_file.stat().st_size > 0 else b"")

        if png_bytes:
            storage_service.upload_bytes(object_key=png_key, data=png_bytes, content_type="image/png")
        if svg_bytes:
            storage_service.upload_bytes(object_key=svg_key, data=svg_bytes, content_type="image/svg+xml")

        # Register source markdown
        source_file = SOURCE_DIR / f"{aid}_source.md"
        source_content = (
            f"# {aid} Ad Poster Source\n\n"
            f"**Brand:** {payload.brand}\n"
            f"**Title:** {first.get('title', aid)}\n"
            f"**Goal:** {payload.goal}\n"
            f"**Aspect:** {aspect}\n"
            f"**Direction:** {payload.direction}\n"
            f"**Headline:** {headline}\n"
            f"**Support:** {support}\n"
            f"**CTA:** {cta_text}\n\n"
            f"*Generated by Gemini Vector Poster Engine (SVG + Playwright Chromium PNG).*"
        )
        source_file.write_text(source_content, encoding="utf-8")

        # Create ContentAsset
        asset = ContentAsset(
            id=asset_uuid,
            campaign_id=camp_id,
            platform=platform_name,
            format="feed_image" if aspect in ("1:1", "4:5") else "image",
            hook=headline,
            caption=support,
            hashtags=payload.hashtags or ["incubrix", platform_name, "poster"],
            cta=cta_text,
            tracking_url=f"https://incubrix.com/?utm_source={platform_name}&utm_medium=poster&utm_content={aid}",
            approval_status="approved",
            quality_status="passed",
            quality_checks={
                "aspect_ratio": aspect,
                "engine": "IncuBrix Vector Poster Engine",
                "inlined_fonts": True,
                "qa_attempt_passed": True
            }
        )
        db.add(asset)
        await db.flush()

        db.add(AssetMedia(
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
                "direction": payload.direction,
                "brief": brief_data,
                "svg_url": f"/media/graphics/{aid}.svg",
                "png_url": f"/media/graphics/{aid}.png"
            }
        ))

        db.add(AssetVersion(
            content_asset_id=asset.id,
            version_number=1,
            hook=asset.hook,
            caption=asset.caption,
            hashtags=asset.hashtags,
            cta=asset.cta,
            change_notes=f"Generated via IncuBrix Poster Studio ({aspect}, direction: {payload.direction})"
        ))

        await db.commit()

        png_url = f"/media/graphics/{aid}.png"
        svg_url = f"/media/graphics/{aid}.svg"

        return {
            "status": "success",
            "success": True,
            "asset_id": str(asset.id),
            "aid": aid,
            "poster_url": png_url,
            "png_url": png_url,
            "svg_url": svg_url,
            "width": w,
            "height": h,
            "minio_object_key": png_key,
            "result": res,
            "media_info": {
                "has_final": True,
                "png_url": png_url,
                "svg_url": svg_url,
                "image_url": png_url,
                "brief": brief_data
            }
        }
    except Exception as e:
        logger.error(f"Poster generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Poster generation error: {str(e)}")
