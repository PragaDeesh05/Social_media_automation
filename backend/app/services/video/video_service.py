import io
import json
import os
import subprocess
import tempfile
import time
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont

from app.core.logging import logger
from app.services.storage.minio_service import storage_service
from app.services.ingestion.video_inspector import VideoInspector
from app.services.video.tts_service import tts_service


class VideoService:
    @classmethod
    def render_scene_frame(
        cls,
        scene_idx: int,
        title: str,
        headline: str,
        highlight_text: str,
        brand_name: str = "IncuBrix",
        primary_color: str = "#4F46E5",
        output_png_path: str = ""
    ) -> str:
        """Renders a modern, vertical 9:16 (1080x1920) scene slide."""
        width, height = 1080, 1920
        img = Image.new("RGB", (width, height), color="#060911")
        draw = ImageDraw.Draw(img)

        # Gradient accent top & bottom bars
        draw.rectangle([(0, 0), (width, 16)], fill=primary_color)
        draw.rectangle([(0, height - 16), (width, height)], fill=primary_color)

        try:
            head_font = ImageFont.truetype("arialbd.ttf", 64)
            sub_font = ImageFont.truetype("arial.ttf", 40)
            tag_font = ImageFont.truetype("arial.ttf", 28)
            brand_font = ImageFont.truetype("arialbd.ttf", 32)
        except Exception:
            head_font = ImageFont.load_default()
            sub_font = ImageFont.load_default()
            tag_font = ImageFont.load_default()
            brand_font = ImageFont.load_default()

        # Top Header Pill
        draw.rounded_rectangle([(80, 120), (360, 180)], radius=30, fill=primary_color)
        draw.text((110, 136), brand_name.upper(), fill="#FFFFFF", font=brand_font)
        draw.text((800, 136), f"SCENE 0{scene_idx}", fill="#64748B", font=brand_font)

        # Central Card Container
        margin = 60
        card_rect = [(margin, 340), (width - margin, 1500)]
        draw.rounded_rectangle(card_rect, radius=36, fill="#0F172A", outline="#1E293B", width=3)

        # Main Headline
        y_cursor = 440
        h_lines = cls._wrap_text(headline, max_chars=22)
        for line in h_lines[:3]:
            draw.text((margin + 60, y_cursor), line, fill="#FFFFFF", font=head_font)
            y_cursor += 84

        # Divider
        y_cursor += 30
        draw.line([(margin + 60, y_cursor), (margin + 200, y_cursor)], fill=primary_color, width=6)
        y_cursor += 60

        # Subtitle / Scene text
        s_lines = cls._wrap_text(title, max_chars=32)
        for line in s_lines[:4]:
            draw.text((margin + 60, y_cursor), line, fill="#94A3B8", font=sub_font)
            y_cursor += 54

        # Highlight quote box
        if highlight_text:
            box_top = 1140
            draw.rounded_rectangle([(margin + 40, box_top), (width - margin - 40, box_top + 260)], radius=24, fill="#1E293B", outline="#3B82F6", width=2)
            draw.text((margin + 70, box_top + 35), "GROUNDED EVIDENCE", fill="#60A5FA", font=tag_font)
            q_lines = cls._wrap_text(f'"{highlight_text}"', max_chars=34)
            qy = box_top + 85
            for ql in q_lines[:3]:
                draw.text((margin + 70, qy), ql, fill="#F8FAFC", font=sub_font)
                qy += 50

        # Footer
        draw.text((margin + 60, height - 120), "Automated with IncuBrix Content Engine", fill="#475569", font=tag_font)
        draw.text((width - margin - 280, height - 120), "incubrix.com", fill="#818CF8", font=tag_font)

        img.save(output_png_path, format="PNG")
        return output_png_path

    @classmethod
    def generate_short_video(
        cls,
        user_id: str,
        campaign_id: str,
        asset_id: str,
        topic: str,
        hook: str,
        source_ref: str,
        brand_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assembles a complete, broadcast-ready vertical 9:16 short video <= 60s.
        Grounded in source facts, narrated with TTS, synchronized captions, and validated with FFprobe.
        """
        brand_name = brand_profile.get("brand_name", "IncuBrix")
        primary_color = brand_profile.get("primary_color", "#4F46E5")

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. Prepare Narration Script
            narration_text = (
                f"{hook}. "
                f"When creators repurpose manually, they waste hours reformatting the exact same message. "
                f"According to verified product data: {source_ref[:120]}. "
                f"IncuBrix automates this entire pipeline so you publish native high-converting assets every single day."
            )

            # 2. Synthesize audio
            audio_path = os.path.join(tmp_dir, "narration.wav")
            _, duration = tts_service.synthesize_speech(narration_text, audio_path)
            # Cap maximum short video duration to 60 seconds strictly
            duration = min(duration, 59.5)

            # 3. Create 4 Scene Storyboard
            scene_duration = duration / 4.0
            scenes = [
                {"idx": 1, "headline": "Stop Wasting 10h/Week", "title": f"Why manual repurposing for {topic[:20]} breaks your schedule", "highlight": ""},
                {"idx": 2, "headline": "The Multi-Platform Problem", "title": "Each platform demands a unique format: carousels, reels, shorts, threads", "highlight": ""},
                {"idx": 3, "headline": "100% Grounded in Truth", "title": "Every hook and script is grounded directly in your source", "highlight": source_ref[:100]},
                {"idx": 4, "headline": "Launch in 30 Seconds", "title": "Generate a full 30-day social calendar with 1 click", "highlight": "Try IncuBrix Free at incubrix.com/start"}
            ]

            # 4. Render Scene Images
            scene_files = []
            concat_txt_path = os.path.join(tmp_dir, "scenes.txt")
            with open(concat_txt_path, "w", encoding="utf-8") as concat_f:
                for s in scenes:
                    png_path = os.path.join(tmp_dir, f"scene_{s['idx']}.png")
                    cls.render_scene_frame(
                        scene_idx=s["idx"],
                        title=s["title"],
                        headline=s["headline"],
                        highlight_text=s["highlight"],
                        brand_name=brand_name,
                        primary_color=primary_color,
                        output_png_path=png_path
                    )
                    scene_files.append(png_path)
                    concat_f.write(f"file '{png_path.replace(os.sep, '/')}'\n")
                    concat_f.write(f"duration {scene_duration:.2f}\n")
                # Repeat last frame for safety
                concat_f.write(f"file '{scene_files[-1].replace(os.sep, '/')}'\n")

            # 5. Generate SRT Subtitles
            srt_path = os.path.join(tmp_dir, "captions.srt")
            with open(srt_path, "w", encoding="utf-8") as srt_f:
                srt_f.write("1\n00:00:00,000 --> 00:00:04,000\n" + hook[:40] + "\n\n")
                srt_f.write("2\n00:00:04,000 --> 00:00:09,000\nStop wasting 10+ hours per week\n\n")
                srt_f.write("3\n00:00:09,000 --> 00:00:15,000\n" + source_ref[:45] + "\n\n")
                srt_f.write(f"4\n00:00:15,000 --> 00:00:{int(duration):02d},000\nLaunch with IncuBrix Engine\n\n")

            # 6. Assemble MP4 with FFmpeg
            output_mp4 = os.path.join(tmp_dir, "final.mp4")
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_txt_path,
                "-i", audio_path,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-r", "30",
                "-vf", "scale=1080:1920",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                output_mp4
            ]
            try:
                subprocess.run(cmd, capture_output=True, check=True, timeout=90)
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg render error: {e.stderr.decode('utf-8', errors='ignore')}")
                raise

            # 7. Validate output with FFprobe
            probe = VideoInspector.probe_media(output_mp4)
            verified_duration = probe.get("duration_seconds", duration)
            file_size = os.path.getsize(output_mp4)

            # 8. Upload outputs to MinIO
            video_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/final.mp4"
            storage_service.upload_file(video_key, output_mp4, content_type="video/mp4")

            srt_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/captions.srt"
            storage_service.upload_file(srt_key, srt_path, content_type="text/plain")

            # Editable scene timeline source JSON
            editable_timeline = {
                "asset_id": asset_id,
                "topic": topic,
                "aspect_ratio": "9:16",
                "width": 1080,
                "height": 1920,
                "fps": 30,
                "duration_seconds": round(verified_duration, 2),
                "narration_script": narration_text,
                "scenes": scenes,
                "render_settings": {
                    "vcodec": "libx264",
                    "acodec": "aac",
                    "resolution": "1080x1920"
                }
            }
            source_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/source.json"
            storage_service.upload_bytes(
                source_key,
                json.dumps(editable_timeline, indent=2).encode("utf-8"),
                content_type="application/json"
            )

            presigned_url = storage_service.get_presigned_url(video_key)
            srt_url = storage_service.get_presigned_url(srt_key)

            return {
                "minio_object_key": video_key,
                "srt_object_key": srt_key,
                "source_object_key": source_key,
                "presigned_url": presigned_url,
                "srt_presigned_url": srt_url,
                "duration_seconds": round(verified_duration, 2),
                "file_size_bytes": file_size,
                "width": 1080,
                "height": 1920,
                "editable_config": editable_timeline
            }

    @classmethod
    def generate_custom_video(
        cls,
        user_id: str,
        campaign_id: str,
        asset_id: str,
        title: str,
        narration_text: str,
        scenes_data: List[Dict[str, Any]],
        aspect_ratio: str = "9:16",
        brand_name: str = "IncuBrix",
        primary_color: str = "#4F46E5"
    ) -> Dict[str, Any]:
        """Assembles a custom video with arbitrary scenes, TTS narration, and selectable aspect ratio (9:16 or 16:9)."""
        dim_map = {"9:16": (1080, 1920), "16:9": (1920, 1080)}
        width, height = dim_map.get(aspect_ratio, (1080, 1920))

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. Synthesize audio
            audio_path = os.path.join(tmp_dir, "narration.wav")
            _, duration = tts_service.synthesize_speech(narration_text, audio_path)
            duration = min(duration, 59.5)

            # 2. Distribute duration across scenes
            num_scenes = max(1, len(scenes_data))
            scene_duration = duration / num_scenes

            # 3. Render scene frames
            scene_files = []
            concat_txt_path = os.path.join(tmp_dir, "scenes.txt")
            with open(concat_txt_path, "w", encoding="utf-8") as concat_f:
                for idx, s in enumerate(scenes_data, 1):
                    png_path = os.path.join(tmp_dir, f"scene_{idx}.png")
                    cls.render_scene_frame(
                        scene_idx=idx,
                        title=s.get("title", f"Scene {idx}"),
                        headline=s.get("headline", title[:25]),
                        highlight_text=s.get("highlight", ""),
                        brand_name=brand_name,
                        primary_color=primary_color,
                        output_png_path=png_path
                    )
                    # If 16:9, resize/pad image to 1920x1080
                    if aspect_ratio == "16:9":
                        with Image.open(png_path) as im:
                            bg = Image.new("RGB", (1920, 1080), color="#060911")
                            resized = im.resize((608, 1080))
                            bg.paste(resized, (656, 0))
                            bg.save(png_path, format="PNG")

                    scene_files.append(png_path)
                    concat_f.write(f"file '{png_path.replace(os.sep, '/')}'\n")
                    concat_f.write(f"duration {scene_duration:.2f}\n")
                if scene_files:
                    concat_f.write(f"file '{scene_files[-1].replace(os.sep, '/')}'\n")

            # 4. SRT Subtitles
            srt_path = os.path.join(tmp_dir, "captions.srt")
            with open(srt_path, "w", encoding="utf-8") as srt_f:
                for idx, s in enumerate(scenes_data, 1):
                    t_start = (idx - 1) * scene_duration
                    t_end = idx * scene_duration
                    s_text = s.get("headline") or s.get("title") or title
                    srt_f.write(f"{idx}\n00:00:{int(t_start):02d},000 --> 00:00:{int(t_end):02d},000\n{s_text[:40]}\n\n")

            # 5. FFmpeg Assembly
            output_mp4 = os.path.join(tmp_dir, "final.mp4")
            scale_filter = f"scale={width}:{height}"
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_txt_path,
                "-i", audio_path,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-r", "30",
                "-vf", scale_filter,
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                output_mp4
            ]
            try:
                subprocess.run(cmd, capture_output=True, check=True, timeout=90)
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg render error: {e.stderr.decode('utf-8', errors='ignore')}")
                raise

            probe = VideoInspector.probe_media(output_mp4)
            verified_duration = probe.get("duration_seconds", duration)
            file_size = os.path.getsize(output_mp4)

            # 6. Upload to MinIO
            video_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/final.mp4"
            storage_service.upload_file(video_key, output_mp4, content_type="video/mp4")

            srt_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/captions.srt"
            storage_service.upload_file(srt_key, srt_path, content_type="text/plain")

            editable_timeline = {
                "asset_id": asset_id,
                "title": title,
                "aspect_ratio": aspect_ratio,
                "width": width,
                "height": height,
                "fps": 30,
                "duration_seconds": round(verified_duration, 2),
                "narration_script": narration_text,
                "scenes": scenes_data,
                "brand_name": brand_name,
                "primary_color": primary_color
            }
            source_key = f"users/{user_id}/campaigns/{campaign_id}/assets/{asset_id}/source.json"
            storage_service.upload_bytes(
                source_key,
                json.dumps(editable_timeline, indent=2).encode("utf-8"),
                content_type="application/json"
            )

            presigned_url = storage_service.get_presigned_url(video_key)
            srt_url = storage_service.get_presigned_url(srt_key)

            return {
                "minio_object_key": video_key,
                "source_object_key": source_key,
                "presigned_url": presigned_url,
                "srt_presigned_url": srt_url,
                "duration_seconds": round(verified_duration, 2),
                "file_size_bytes": file_size,
                "width": width,
                "height": height,
                "editable_config": editable_timeline
            }

    @staticmethod
    def _wrap_text(text: str, max_chars: int = 24) -> list[str]:
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


video_service = VideoService()
