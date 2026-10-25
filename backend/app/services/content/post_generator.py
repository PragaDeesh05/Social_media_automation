import json
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.core.logging import logger
from app.services.ai.gemini_adapter import gemini_adapter
from app.services.content.utm_service import utm_service

PLATFORM_LIMITS = {
    "x": {"max_chars": 280, "max_hashtags": 3},
    "facebook": {"max_chars": 2000, "max_hashtags": 5},
    "instagram": {"max_chars": 2200, "max_hashtags": 10},
    "youtube": {"max_title_chars": 100, "max_chars": 5000, "max_hashtags": 5}
}


class AssetCopyOutput(BaseModel):
    hook: str = Field(description="Attention-grabbing opening hook")
    caption: str = Field(description="Body caption tailored for the specific platform")
    hashtags: List[str] = Field(description="Relevant hashtags without # symbol")
    cta: str = Field(description="Call to action statement")


class PostGenerator:
    @classmethod
    async def generate_post_copy(
        cls,
        slot_brief: Dict[str, Any],
        brand_profile: Dict[str, Any],
        campaign_name: str,
        asset_id: str,
        destination_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates platform-adapted copy, hooks, and UTM links for a specific asset slot."""
        platform = slot_brief.get("platform", "x").lower()
        fmt = slot_brief.get("format", "text").lower()
        topic = slot_brief.get("topic", "Content Strategy")
        source_ref = slot_brief.get("source_reference", "")
        brand_name = brand_profile.get("brand_name", "IncuBrix")
        tone = brand_profile.get("tone_of_voice", "Educational, Action-Oriented")
        default_cta = brand_profile.get("default_cta", "Repurpose your content with IncuBrix → incubrix.com/start")
        base_url = destination_url or "https://incubrix.com/start"

        # Generate UTM URL
        utm_result = utm_service.generate_tracking_url(
            base_url=base_url,
            platform=platform,
            format_type=fmt,
            campaign_name=campaign_name,
            asset_id=asset_id
        )
        tracking_url = utm_result["final_url"]

        prompt = f"""
PLATFORM: {platform.upper()}
FORMAT: {fmt.upper()}
TOPIC: {topic}
SOURCE EVIDENCE: \"{source_ref}\"
BRAND NAME: {brand_name}
BRAND TONE: {tone}
CTA LINK: {tracking_url}

Write native social media copy adhering to {platform} best practices:
- For X: Under 260 characters total, punchy hook, crisp takeaway, link at end.
- For Instagram: Hook on line 1, short visual spacing, 5-8 niche hashtags, save/share CTA.
- For Facebook: Narrative-driven, value proof, question at end, clear CTA.
- For YouTube: Catchy title (for Shorts), short video description with timestamps and CTA.

Ground everything in the provided source evidence.
"""

        try:
            copy_data = await gemini_adapter.generate_structured(
                prompt=prompt,
                response_model=AssetCopyOutput,
                temperature=0.4
            )
            hook = copy_data["hook"].strip()
            caption = copy_data["caption"].strip()
            hashtags = [h.replace("#", "").strip() for h in copy_data.get("hashtags", []) if h]
            cta = copy_data.get("cta", default_cta).strip()

            # Enforce platform character limits strictly
            if platform == "x":
                total_len = len(hook) + len(caption) + len(tracking_url) + 10
                if total_len > 280:
                    available = 270 - len(tracking_url) - len(hook)
                    caption = caption[:max(50, available)] + "..."

            return {
                "hook": hook,
                "caption": caption,
                "hashtags": hashtags[:PLATFORM_LIMITS.get(platform, {}).get("max_hashtags", 5)],
                "cta": cta,
                "tracking_url": tracking_url,
                "utm_parameters": utm_result["utm_parameters"]
            }
        except Exception as e:
            logger.warning(f"AI copy generation failed for slot ({platform}, {fmt}): {e}. Using deterministic copy.")
            return cls._deterministic_copy(
                platform=platform,
                fmt=fmt,
                topic=topic,
                source_ref=source_ref,
                tracking_url=tracking_url,
                default_cta=default_cta,
                utm_params=utm_result["utm_parameters"]
            )

    @classmethod
    def _deterministic_copy(
        cls,
        platform: str,
        fmt: str,
        topic: str,
        source_ref: str,
        tracking_url: str,
        default_cta: str,
        utm_params: Dict[str, str]
    ) -> Dict[str, Any]:
        hooks = {
            "x": f"Most creators lose 10+ hours/week to manual repurposing. Here is the fix for {topic}:",
            "instagram": f"Stop rebuilding your social content from scratch. How to master {topic} in 3 steps:",
            "facebook": f"Why leading marketing teams never create content for just one platform:\n\nA deep dive into {topic}.",
            "youtube": f"The 60-Second Blueprint to Scale {topic} (Automated Repurposing)"
        }
        captions = {
            "x": f"{source_ref}\n\nAutomate your 30-day calendar without fluff.\n{tracking_url}",
            "instagram": f"{source_ref}\n\nKey takeaways:\n1. 1 long-form input = 30 days of assets\n2. Native format conversion\n3. Zero hallucination\n\nLink in bio to build yours.",
            "facebook": f"Creating consistent high-signal social content does not require 40 hours of manual work.\n\n\"{source_ref}\"\n\nTest our content engine free: {tracking_url}",
            "youtube": f"Here is how you turn 1 long-form input into a full 30-day social media campaign with verified source grounding.\n\nLearn more: {tracking_url}"
        }

        tags = ["IncuBrix", "ContentRepurposing", "GrowthEngineering", "SocialMediaAI"]
        return {
            "hook": hooks.get(platform, hooks["x"]),
            "caption": captions.get(platform, captions["x"]),
            "hashtags": tags,
            "cta": default_cta,
            "tracking_url": tracking_url,
            "utm_parameters": utm_params
        }


post_generator = PostGenerator()
