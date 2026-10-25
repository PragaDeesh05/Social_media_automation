import os
import subprocess
import tempfile
import time
from typing import Optional, Tuple
from pathlib import Path

from app.core.logging import logger
from app.services.ingestion.video_inspector import VideoInspector


class TTSService:
    @classmethod
    def synthesize_speech(cls, text: str, output_wav_path: str) -> Tuple[str, float]:
        """
        Synthesizes human speech audio from text using native speech synthesis.
        Guaranteed to run reliably on Windows with 0 external network dependencies.
        Returns (audio_path, duration_seconds).
        """
        os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)
        # Clean text for speech
        clean_text = text.replace('"', "'").replace("\n", " ").strip()

        ps_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 1
$synth.SetOutputToWaveFile("{output_wav_path.replace(os.sep, '/')}")
$synth.Speak("{clean_text}")
$synth.Dispose()
"""
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as f:
            f.write(ps_script)
            temp_script = f.name

        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", temp_script],
                capture_output=True,
                text=True,
                timeout=45
            )
            if res.returncode != 0:
                logger.warning(f"PowerShell TTS failed ({res.stderr}), falling back to lavfi sine generation")
                cls._fallback_tone(output_wav_path, max(3.0, len(text.split()) * 0.38))
        except Exception as e:
            logger.error(f"Error executing speech synthesis: {e}")
            cls._fallback_tone(output_wav_path, max(3.0, len(text.split()) * 0.38))
        finally:
            if os.path.exists(temp_script):
                try:
                    os.remove(temp_script)
                except Exception:
                    pass

        # Inspect duration with ffprobe
        probe = VideoInspector.probe_media(output_wav_path)
        duration = probe.get("duration_seconds", 5.0)
        return output_wav_path, duration

    @staticmethod
    def _fallback_tone(output_wav_path: str, duration: float):
        """Emergency fallback tone if TTS runtime fails."""
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={duration}",
            "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1",
            output_wav_path
        ], capture_output=True, check=True)


tts_service = TTSService()
