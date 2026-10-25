import io
import json
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont

from app.core.logging import logger
from app.services.storage.minio_service import storage_service


class CarouselService:
    @classmethod
    def render_slide(
        cls,
        slide_num: int,
        total_slides: int,
        headline: str,
        body: str,
        takeaway: str,
        brand_name: str = "IncuBrix",
        primary_color: str = "#4F46E5",
        width: int = 1080,
        height: int = 1350
    ) -> bytes:
        """Renders an individual 4:5 vertical carousel slide (1080x1350)."""
        img = Image.new("RGB", (width, height), color="#090D16")
        draw = ImageDraw.Draw(img)

        # Top progress bar
        bar_width = int((slide_num / total_slides) * width)
        draw.rectangle([(0, 0), (bar_width, 10)], fill=primary_color)
        draw.rectangle([(bar_width, 0), (width, 10)], fill="#1E293B")

        # Fonts
        try:
            head_font = ImageFont.truetype("arialbd.ttf", 54)
            body_font = ImageFont.truetype("arial.ttf", 34)
            takeaway_font = ImageFont.truetype("arial.ttf", 30)
            meta_font = ImageFont.truetype("arial.ttf", 24)
        except Exception:
            head_font = ImageFont.load_default()
            body_font = ImageFont.load_default()
            takeaway_font = ImageFont.load_default()
            meta_font = ImageFont.load_default()

        margin = 80
        top_y = 70

        # Top Meta: Brand and Slide Index
        draw.text((margin, top_y), brand_name.upper(), fill="#818CF8", font=meta_font)
        draw.rounded_rectangle([(width - margin - 90, top_y - 6), (width - margin, top_y + 36)], radius=12, fill="#1E293B")
        draw.text((width - margin - 75, top_y), f"{slide_num}/{total_slides}", fill="#FFFFFF", font=meta_font)

        # Main Headline
        y_cursor = top_y + 120
        head_lines = cls._wrap_text(headline, max_chars=28)
        for line in head_lines[:3]:
            draw.text((margin, y_cursor), line, fill="#FFFFFF", font=head_font)
            y_cursor += 68

        # Divider accent
        y_cursor += 30
        draw.line([(margin, y_cursor), (margin + 120, y_cursor)], fill=primary_color, width=4)
        y_cursor += 50

        # Body paragraph
        body_lines = cls._wrap_text(body, max_chars=40)
        for line in body_lines[:6]:
            draw.text((margin, y_cursor), line, fill="#CBD5E1", font=body_font)
            y_cursor += 48

        # Key Takeaway Card (Bottom)
        if takeaway:
            box_top = height - margin - 220
            box_rect = [(margin, box_top), (width - margin, box_top + 160)]
            draw.rounded_rectangle(box_rect, radius=20, fill="#131C31", outline="#312E81", width=2)
            draw.text((margin + 40, box_top + 25), "KEY TAKEAWAY", fill="#A5B4FC", font=meta_font)
            t_lines = cls._wrap_text(takeaway, max_chars=45)
            t_y = box_top + 65
            for tl in t_lines[:2]:
                draw.text((margin + 40, t_y), tl, fill="#F8FAFC", font=takeaway_font)
                t_y += 38

        # Bottom Swipe Hint
        bottom_y = height - margin + 20
        draw.text((margin, bottom_y), "Verified Source Grounding", fill="#64748B", font=meta_font)
        if slide_num < total_slides:
            draw.text((width - margin - 150, bottom_y), "Swipe →", fill="#818CF8", font=meta_font)
        else:
            draw.text((width - margin - 200, bottom_y), "incubrix.com", fill="#38BDF8", font=meta_font)

        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        return buf.getvalue()

    @classmethod
    def generate_and_store_carousel(
        cls,
        user_id: str,
        campaign_id: str,
        asset_id: str,
        topic: str,
        hook: str,
        source_ref: str,
        brand_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generates a full 5-slide carousel and stores all images + source config in MinIO."""
        brand_name = brand_profile.get("brand_name", "IncuBrix")
        primary_color = brand_profile.get("primary_color", "#4F46E5")

        slides_content = [
            {
                "slide_index": 1,
                "headline": f"The Blueprint for {topic[:28]}",
                "body": f"{hook}\n\nMost content creators lose hours trying to manually adapt their ideas across platforms.",
                "takeaway": "Work smarter: generate once, repurpose everywhere."
            },
            {
                "slide_index": 2,
                "headline": "The Hidden Repurposing Trap",
                "body": "Cross-posting plain links or identical copy fails because every social platform has distinct distribution algorithms and audience expectations.",
                "takeaway": "Native formats drive 3-5x higher organic engagement."
            },
            {
                "slide_index": 3,
                "headline": "Ground Every Asset in Truth",
                "body": f"AI models often hallucinate claims. Real growth content anchors every post in verified facts:\n\n\"{source_ref[:180]}\"",
                "takeaway": "Traceable citations protect brand authority."
            },
            {
                "slide_index": 4,
                "headline": "The 4-Platform Architecture",
                "body": "Distribute simultaneously across Instagram, Facebook, YouTube, and X without manual formatting overhead or delayed schedules.",
                "takeaway": "Autonomous engines maintain daily consistency."
            },
            {
                "slide_index": 5,
                "headline": "Start Automating Today",
                "body": "Turn your podcasts, blogs, recordings, and webinars into 30 days of high-converting social media assets in minutes.",
                "takeaway": "Test IncuBrix Free → incubrix.com/start"
            }
        ]

        rendered_slides = []
        for s in slides_content:
            idx = s["slide_index"]
            png_bytes = cls.render_slide(
                slide_num=idx,
                total_slides=5,
                headline=s["headline"],
                body=s["body"],
                takeaway=s["takeaway"],
                brand_name=brand_name,
                primary_color=primary_color
            )
            slide_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/slide_{idx}.png"
            storage_service.upload_bytes(
                object_key=slide_key,
                data=png_bytes,
                content_type="image/png",
                metadata={"asset_id": asset_id, "slide_index": str(idx)}
            )
            presigned = storage_service.get_presigned_url(slide_key)
            rendered_slides.append({
                "slide_index": idx,
                "minio_object_key": slide_key,
                "presigned_url": presigned,
                "size_bytes": len(png_bytes)
            })

        # Save editable source JSON
        editable_config = {
            "topic": topic,
            "hook": hook,
            "source_ref": source_ref,
            "brand_name": brand_name,
            "primary_color": primary_color,
            "total_slides": 5,
            "aspect_ratio": "4:5",
            "slides": slides_content
        }
        source_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/source.json"
        storage_service.upload_bytes(
            object_key=source_key,
            data=json.dumps(editable_config, indent=2).encode("utf-8"),
            content_type="application/json"
        )

        return {
            "slides": rendered_slides,
            "source_object_key": source_key,
            "total_slides": 5,
            "cover_url": rendered_slides[0]["presigned_url"] if rendered_slides else None,
            "editable_config": editable_config
        }

    @classmethod
    def generate_custom_carousel(
        cls,
        user_id: str,
        campaign_id: str,
        asset_id: str,
        title: str,
        slides_data: List[Dict[str, Any]],
        brand_name: str = "IncuBrix",
        primary_color: str = "#4F46E5",
        aspect_ratio: str = "4:5"
    ) -> Dict[str, Any]:
        """Renders and uploads a custom carousel with arbitrary slides and aspect ratio."""
        dim_map = {"4:5": (1080, 1350), "1:1": (1080, 1080)}
        width, height = dim_map.get(aspect_ratio, (1080, 1350))
        total_slides = len(slides_data)

        rendered_slides = []
        for s in slides_data:
            idx = s.get("slide_num", 1)
            headline = s.get("headline", f"Slide {idx}")
            body = s.get("body", "")
            takeaway = s.get("takeaway", "")

            png_bytes = cls.render_slide(
                slide_num=idx,
                total_slides=total_slides,
                headline=headline,
                body=body,
                takeaway=takeaway,
                brand_name=brand_name,
                primary_color=primary_color,
                width=width,
                height=height
            )

            slide_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/slide_{idx}.png"
            storage_service.upload_bytes(slide_key, png_bytes, content_type="image/png")
            presigned = storage_service.get_presigned_url(slide_key)

            rendered_slides.append({
                "slide_index": idx,
                "minio_object_key": slide_key,
                "presigned_url": presigned,
                "size_bytes": len(png_bytes),
                "width": width,
                "height": height
            })

        editable_config = {
            "title": title,
            "brand_name": brand_name,
            "primary_color": primary_color,
            "total_slides": total_slides,
            "aspect_ratio": aspect_ratio,
            "slides": slides_data
        }
        source_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/source.json"
        storage_service.upload_bytes(
            source_key,
            json.dumps(editable_config, indent=2).encode("utf-8"),
            content_type="application/json"
        )

        return {
            "slides": rendered_slides,
            "source_object_key": source_key,
            "total_slides": total_slides,
            "cover_url": rendered_slides[0]["presigned_url"] if rendered_slides else None,
            "editable_config": editable_config
        }

    @staticmethod
    def _wrap_text(text: str, max_chars: int = 35) -> list[str]:
        words = text.split()
        lines = []
        curr = []
        curr_len = 0
        for w in words:
            if curr_len + len(w) + 1 > max_chars:
                lines.append(" ".join(curr))
                curr = [w]
                curr_len = len(w)
            else:
                curr.append(w)
                curr_len += len(w) + 1
        if curr:
            lines.append(" ".join(curr))
        return lines


carousel_service = CarouselService()
