import json
import os
import subprocess
from typing import Dict, Any, Optional
from pathlib import Path

from app.core.logging import logger
from app.core.exceptions import IncuBrixException


class VideoInspector:
    @staticmethod
    def probe_media(file_path: str) -> Dict[str, Any]:
        """Inspect media file metadata using ffprobe."""
        if not os.path.exists(file_path):
            raise IncuBrixException(status_code=404, detail="Media file not found for inspection")

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            data = json.loads(res.stdout)
            format_info = data.get("format", {})
            streams = data.get("streams", [])

            duration = float(format_info.get("duration", 0.0))
            size = int(format_info.get("size", 0))

            video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

            width = int(video_stream.get("width", 0)) if video_stream else None
            height = int(video_stream.get("height", 0)) if video_stream else None
            video_codec = video_stream.get("codec_name") if video_stream else None
            audio_codec = audio_stream.get("codec_name") if audio_stream else None

            # Calculate fps
            fps = None
            if video_stream and "r_frame_rate" in video_stream:
                try:
                    num, den = video_stream["r_frame_rate"].split("/")
                    fps = round(float(num) / float(den), 2)
                except Exception:
                    fps = 30.0

            return {
                "duration_seconds": duration,
                "file_size_bytes": size,
                "width": width,
                "height": height,
                "fps": fps,
                "video_codec": video_codec,
                "audio_codec": audio_codec,
                "has_video": video_stream is not None,
                "has_audio": audio_stream is not None,
                "streams_count": len(streams)
            }
        except subprocess.TimeoutExpired:
            raise IncuBrixException(status_code=400, detail="FFprobe inspection timed out")
        except Exception as e:
            logger.error(f"FFprobe error inspecting {file_path}: {e}")
            raise IncuBrixException(status_code=400, detail=f"Failed to inspect media file with FFprobe: {e}")

    @staticmethod
    def extract_audio(video_path: str, output_wav_path: str) -> str:
        """Extract a 16kHz mono WAV audio track for speech recognition."""
        os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_wav_path
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=120)
            return output_wav_path
        except Exception as e:
            logger.error(f"Failed to extract audio from {video_path}: {e}")
            raise IncuBrixException(status_code=400, detail=f"Audio extraction failed: {e}")

    @staticmethod
    def extract_frame(video_path: str, output_image_path: str, timestamp_sec: float = 1.0) -> str:
        """Extract a thumbnail image from video at specific timestamp."""
        os.makedirs(os.path.dirname(output_image_path), exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(timestamp_sec),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_image_path
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=30)
            return output_image_path
        except Exception as e:
            logger.error(f"Failed to extract frame from {video_path}: {e}")
            raise IncuBrixException(status_code=400, detail=f"Frame extraction failed: {e}")
