import io
import json
import os
import uuid
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

from app.core.logging import logger
from app.services.storage.minio_service import storage_service


class ImageService:
    @classmethod
    def render_brand_card(
        cls,
        title: str,
        hook: str,
        quote: str,
        brand_name: str = "IncuBrix",
        primary_color: str = "#4F46E5",
        secondary_color: str = "#0F172A",
        width: int = 1080,
        height: int = 1080
    ) -> bytes:
        """
        Renders a crisp, high-contrast, modern brand card graphic with typography.
        Uses clean geometric composition, brand pill badges, and high-readability layout.
        """
        img = Image.new("RGB", (width, height), color="#0B0F19")
        draw = ImageDraw.Draw(img)

        # Draw subtle gradient/accent top banner
        draw.rectangle([(0, 0), (width, 16)], fill=primary_color)

        # Draw card container
        margin = 60
        card_rect = [(margin, margin + 40), (width - margin, height - margin)]
        draw.rounded_rectangle(card_rect, radius=24, fill="#131B2E", outline="#1E293B", width=2)

        # Draw Brand pill
        pill_x, pill_y = margin + 40, margin + 80
        draw.rounded_rectangle([(pill_x, pill_y), (pill_x + 180, pill_y + 44)], radius=22, fill=primary_color)
        draw.text((pill_x + 24, pill_y + 12), brand_name.upper(), fill="#FFFFFF")

        # Fallback default fonts
        try:
            title_font = ImageFont.truetype("arial.ttf", 46)
            body_font = ImageFont.truetype("arial.ttf", 30)
            quote_font = ImageFont.truetype("ariali.ttf", 26)
            footer_font = ImageFont.truetype("arial.ttf", 22)
        except Exception:
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()
            quote_font = ImageFont.load_default()
            footer_font = ImageFont.load_default()

        # Draw Title
        y_cursor = pill_y + 80
        lines = cls._wrap_text(title, max_chars=34)
        for line in lines[:3]:
            draw.text((margin + 40, y_cursor), line, fill="#F8FAFC", font=title_font)
            y_cursor += 56

        # Draw Hook
        y_cursor += 30
        draw.line([(margin + 40, y_cursor), (width - margin - 40, y_cursor)], fill="#334155", width=1)
        y_cursor += 30

        hook_lines = cls._wrap_text(hook, max_chars=45)
        for line in hook_lines[:4]:
            draw.text((margin + 40, y_cursor), line, fill="#94A3B8", font=body_font)
            y_cursor += 42

        # Draw Quote Card if available
        if quote:
            y_cursor += 40
            quote_rect = [(margin + 40, y_cursor), (width - margin - 40, y_cursor + 160)]
            draw.rounded_rectangle(quote_rect, radius=16, fill="#1E293B", outline="#3B82F6", width=2)
            draw.text((margin + 65, y_cursor + 20), "SOURCE EVIDENCE:", fill="#60A5FA", font=footer_font)
            q_lines = cls._wrap_text(f'"{quote}"', max_chars=48)
            q_y = y_cursor + 54
            for ql in q_lines[:2]:
                draw.text((margin + 65, q_y), ql, fill="#E2E8F0", font=quote_font)
                q_y += 34

        # Footer
        footer_y = height - margin - 50
        draw.text((margin + 40, footer_y), f"Verified Content Engine | {brand_name}", fill="#64748B", font=footer_font)
        draw.text((width - margin - 260, footer_y), "incubrix.com/start", fill="#818CF8", font=footer_font)

        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        return buf.getvalue()

    @classmethod
    def generate_and_store_image(
        cls,
        user_id: str,
        campaign_id: str,
        asset_id: str,
        title: str,
        hook: str,
        quote: str,
        brand_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generates graphic and uploads both final PNG and source JSON to MinIO."""
        brand_name = brand_profile.get("brand_name", "IncuBrix")
        primary_color = brand_profile.get("primary_color", "#4F46E5")
        secondary_color = brand_profile.get("secondary_color", "#0F172A")

        png_bytes = cls.render_brand_card(
            title=title,
            hook=hook,
            quote=quote,
            brand_name=brand_name,
            primary_color=primary_color,
            secondary_color=secondary_color
        )

        final_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/final.png"
        storage_service.upload_bytes(
            object_key=final_key,
            data=png_bytes,
            content_type="image/png",
            metadata={"asset_id": asset_id, "title": title}
        )

        # Store editable source config JSON
        editable_config = {
            "title": title,
            "hook": hook,
            "quote": quote,
            "brand_name": brand_name,
            "primary_color": primary_color,
            "secondary_color": secondary_color,
            "dimensions": {"width": 1080, "height": 1080},
            "layout": "brand_card_v1"
        }
        source_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/source.json"
        storage_service.upload_bytes(
            object_key=source_key,
            data=json.dumps(editable_config, indent=2).encode("utf-8"),
            content_type="application/json"
        )

        presigned_url = storage_service.get_presigned_url(final_key)

        return {
            "minio_object_key": final_key,
            "source_object_key": source_key,
            "presigned_url": presigned_url,
            "file_size_bytes": len(png_bytes),
            "width": 1080,
            "height": 1080,
            "editable_config": editable_config
        }

    @classmethod
    def render_custom_poster(
        cls,
        headline: str,
        subheadline: str,
        quote: Optional[str] = None,
        cta: str = "Explore with IncuBrix",
        brand_name: str = "IncuBrix",
        primary_color: str = "#4F46E5",
        secondary_color: str = "#0F172A",
        aspect_ratio: str = "1:1"
    ) -> bytes:
        """Renders a poster graphic with customizable aspect ratio (1:1, 4:5, 9:16, 16:9)."""
        dim_map = {
            "1:1": (1080, 1080),
            "4:5": (1080, 1350),
            "9:16": (1080, 1920),
            "16:9": (1920, 1080)
        }
        width, height = dim_map.get(aspect_ratio, (1080, 1080))
        img = Image.new("RGB", (width, height), color="#080C16")
        draw = ImageDraw.Draw(img)

        # Top accent
        draw.rectangle([(0, 0), (width, 14)], fill=primary_color)

        margin = 60 if width <= 1080 else 100
        card_rect = [(margin, margin + 30), (width - margin, height - margin - 20)]
        draw.rounded_rectangle(card_rect, radius=24, fill="#111827", outline="#1F2937", width=2)

        # Brand Pill
        pill_x, pill_y = margin + 40, margin + 60
        draw.rounded_rectangle([(pill_x, pill_y), (pill_x + 190, pill_y + 42)], radius=21, fill=primary_color)
        draw.text((pill_x + 22, pill_y + 11), brand_name.upper(), fill="#FFFFFF")

        try:
            head_size = 52 if height >= 1350 else 44
            head_font = ImageFont.truetype("arialbd.ttf", head_size)
            sub_font = ImageFont.truetype("arial.ttf", 30)
            quote_font = ImageFont.truetype("ariali.ttf", 26)
            footer_font = ImageFont.truetype("arial.ttf", 22)
            cta_font = ImageFont.truetype("arialbd.ttf", 24)
        except Exception:
            head_font = ImageFont.load_default()
            sub_font = ImageFont.load_default()
            quote_font = ImageFont.load_default()
            footer_font = ImageFont.load_default()
            cta_font = ImageFont.load_default()

        # Headline
        y_cursor = pill_y + 80
        h_lines = cls._wrap_text(headline, max_chars=int(width / 32))
        for line in h_lines[:4]:
            draw.text((margin + 40, y_cursor), line, fill="#F9FAFB", font=head_font)
            y_cursor += head_size + 14

        # Divider
        y_cursor += 20
        draw.line([(margin + 40, y_cursor), (width - margin - 40, y_cursor)], fill="#374151", width=1)
        y_cursor += 30

        # Subheadline
        s_lines = cls._wrap_text(subheadline, max_chars=int(width / 26))
        for line in s_lines[:5]:
            draw.text((margin + 40, y_cursor), line, fill="#9CA3AF", font=sub_font)
            y_cursor += 42

        # Evidence / Quote box
        if quote:
            y_cursor += 25
            q_height = 140 if height >= 1350 else 110
            q_rect = [(margin + 40, y_cursor), (width - margin - 40, y_cursor + q_height)]
            draw.rounded_rectangle(q_rect, radius=16, fill="#1F2937", outline="#3B82F6", width=2)
            draw.text((margin + 60, y_cursor + 16), "KEY TAKEAWAY", fill="#60A5FA", font=footer_font)
            ql = cls._wrap_text(f'"{quote}"', max_chars=int(width / 24))
            for idx, line in enumerate(ql[:2]):
                draw.text((margin + 60, y_cursor + 48 + (idx * 30)), line, fill="#E5E7EB", font=quote_font)
            y_cursor += q_height + 30

        # CTA Box
        if cta:
            cta_y = height - margin - 120
            draw.rounded_rectangle([(margin + 40, cta_y), (margin + 340, cta_y + 48)], radius=14, fill=primary_color)
            draw.text((margin + 60, cta_y + 12), cta, fill="#FFFFFF", font=cta_font)

        # Footer
        footer_y = height - margin - 50
        draw.text((margin + 40, footer_y), f"IncuBrix Content Engine • Verified Media", fill="#4B5563", font=footer_font)
        draw.text((width - margin - 240, footer_y), "incubrix.com/start", fill="#818CF8", font=footer_font)

        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        return buf.getvalue()

    @classmethod
    def generate_custom_poster(
        cls,
        user_id: str,
        campaign_id: str,
        asset_id: str,
        headline: str,
        subheadline: str,
        quote: Optional[str] = None,
        cta: str = "Explore with IncuBrix",
        aspect_ratio: str = "1:1",
        brand_name: str = "IncuBrix",
        primary_color: str = "#4F46E5"
    ) -> Dict[str, Any]:
        """Generates a custom poster, uploads to MinIO, and returns object metadata."""
        png_bytes = cls.render_custom_poster(
            headline=headline,
            subheadline=subheadline,
            quote=quote,
            cta=cta,
            brand_name=brand_name,
            primary_color=primary_color,
            aspect_ratio=aspect_ratio
        )

        dim_map = {"1:1": (1080, 1080), "4:5": (1080, 1350), "9:16": (1080, 1920), "16:9": (1920, 1080)}
        width, height = dim_map.get(aspect_ratio, (1080, 1080))

        final_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/poster.png"
        storage_service.upload_bytes(final_key, png_bytes, content_type="image/png")

        editable_config = {
            "headline": headline,
            "subheadline": subheadline,
            "quote": quote,
            "cta": cta,
            "aspect_ratio": aspect_ratio,
            "width": width,
            "height": height,
            "brand_name": brand_name,
            "primary_color": primary_color
        }
        source_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/source.json"
        storage_service.upload_bytes(
            source_key,
            json.dumps(editable_config, indent=2).encode("utf-8"),
            content_type="application/json"
        )

        return {
            "minio_object_key": final_key,
            "source_object_key": source_key,
            "presigned_url": storage_service.get_presigned_url(final_key),
            "file_size_bytes": len(png_bytes),
            "width": width,
            "height": height,
            "editable_config": editable_config
        }

    @staticmethod
    def _wrap_text(text: str, max_chars: int = 40) -> list[str]:
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


image_service = ImageService()
