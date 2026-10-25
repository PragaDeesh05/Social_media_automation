#!/usr/bin/env python3
"""
ad_video_maker.py - Use Case / Script -> Animated-SVG Ad Video with AI Voice-over
==================================================================================

PIPELINE
  1. DIRECTOR  (Gemini)  use case -> storyboard JSON: story arc, ONE shared design system,
                          scenes (narration, on-screen text, visual beats, continuity notes),
                          transitions, and the narrator voice (picked from GCP Chirp 3 HD voices).
  2. VOICE     (GCP TTS)  one narration clip per scene -> exact scene durations.
  3. ANIMATOR  (Gemini)   one animated SVG per scene, written with the real narration timeline,
                          the shared design system, and the PREVIOUS scene's SVG as reference.
                          Every SVG is linted/auto-fixed, then (optionally) a vision QA pass
                          looks at a rendered frame and requests fixes.
  4. RENDER    (Chromium) each SVG is stepped frame-by-frame (deterministic, not screen-recorded),
                          burned-in subtitles are added, frames are piped into ffmpeg.
  5. ASSEMBLE  (ffmpeg)   scenes joined with xfade transitions (a "ribbon" element crosses every
                          seam), narration placed on the final timeline, loudness-normalised.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import wave
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------------------
DEFAULT_MODEL = os.getenv("GEMINI_VIDEO_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"))
FALLBACK_MODELS = [os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite"), "gemini-flash-lite-latest"]
MIN_CALL_INTERVAL_S = 3.0  # keeps us under requests/minute quota
TIMEOUT_MS = 600_000

FPS = 30
TRANSITION_S = 0.5      # xfade length between scenes
LEAD_S = 0.7            # silence at scene start (must be > TRANSITION_S)
TAIL_S = 0.8            # silence at scene end   (must be > TRANSITION_S)
FINAL_TAIL_S = 1.8      # hold on the CTA frame
SAMPLE_RATE = 24000

ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
TRANSITIONS = ["slideleft", "smoothleft", "wipeleft", "fade", "circleopen"]

# Chirp 3 HD voices (name -> (gender, character)); full name = "<lang>-Chirp3-HD-<Name>"
VOICES = {
    "Aoede": ("F", "warm, breezy, friendly storyteller"),
    "Kore": ("F", "confident, energetic, upbeat"),
    "Leda": ("F", "youthful, bright, approachable"),
    "Zephyr": ("F", "bright, cheerful, enthusiastic"),
    "Sulafat": ("F", "warm, welcoming, reassuring"),
    "Puck": ("M", "upbeat, playful, lively"),
    "Charon": ("M", "smooth, informative, trustworthy"),
    "Fenrir": ("M", "excitable, high-energy, punchy"),
    "Orus": ("M", "firm, authoritative, premium"),
    "Algenib": ("M", "strong, gravelly, bold"),
}

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def fill(template: str, **kw) -> str:
    """Replace <<TOKEN>> placeholders (safe with CSS/JSON braces)."""
    for k, v in kw.items():
        template = template.replace(f"<<{k}>>", str(v))
    return template


def sha(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def cached(path: Path, key: str) -> bool:
    meta = path.with_name(path.name + ".key")
    return path.exists() and meta.exists() and meta.read_text(encoding="utf-8") == key


def mark(path: Path, key: str) -> None:
    path.with_name(path.name + ".key").write_text(key, encoding="utf-8")


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd[:6])} ...\n{p.stderr[-2500:]}")
    return p


def slugify(text: str) -> str:
    words = re.sub(r"[^a-zA-Z0-9\s]", "", text).lower().split()[:6]
    return "-".join(words) or "ad-video"


def extract_json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        a, b = t.find("{"), t.rfind("}")
        if a >= 0 and b > a:
            return json.loads(t[a:b + 1])
        raise


def clean_spoken(text: str) -> str:
    text = re.sub(r"[*_#`~<>]", "", text)
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------------------
# Gemini Client Wrapper
# --------------------------------------------------------------------------------------
class Gemini:
    def __init__(self, model: Optional[str] = None):
        from dotenv import load_dotenv
        from google import genai
        from google.genai import types

        load_dotenv()
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        if not project:
            sys.exit("GOOGLE_CLOUD_PROJECT not found. Add it to a .env file next to this script (Vertex AI mode).")
        self.types = types
        self.client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
            http_options=types.HttpOptions(timeout=TIMEOUT_MS),
        )
        self.model = model or DEFAULT_MODEL

    def image_part(self, data: bytes, mime: str = "image/jpeg"):
        return self.types.Part.from_bytes(data=data, mime_type=mime)

    def generate(self, system: str, contents, json_mode: bool = False,
                 temperature: float = 0.9, retries: int = 4) -> str:
        cfg = self.types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json" if json_mode else None,
        )
        last = None
        models_to_try = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]
        
        for curr_model in models_to_try:
            for attempt in range(retries):
                gap = MIN_CALL_INTERVAL_S - (time.time() - getattr(self, "_last_call", 0.0))
                if gap > 0:
                    time.sleep(gap)
                self._last_call = time.time()
                try:
                    r = self.client.models.generate_content(model=curr_model, contents=contents, config=cfg)
                    if r.text:
                        self.model = curr_model
                        return r.text
                    last = RuntimeError("empty response")
                except Exception as e:
                    last = e
                
                # Check for quota errors
                err_str = str(last)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    log(f"  Gemini model {curr_model} quota exhausted, attempting fallback if available...")
                    break  # Break inner loop to try next model in fallback list
                
                wait = 3 * (2 ** attempt)
                log(f"  Gemini call failed ({type(last).__name__}: {str(last)[:160]}) - retry in {wait}s")
                time.sleep(wait)
        
        raise RuntimeError(f"Gemini failed across all models: {last}")


# --------------------------------------------------------------------------------------
# 1. DIRECTOR (Storyboard Generation)
# --------------------------------------------------------------------------------------
DIRECTOR_SYSTEM = """You are a senior advertising creative director, screenwriter and motion-design lead.
You turn a short brief (or a full script) into a storyboard for a short animated vector-illustration video ad
with a voice-over. Every scene will later be drawn as an animated SVG and joined with the others, so the film
must feel like ONE continuous piece, not a slideshow of unrelated posters.

PRINCIPLES
1. ONE WORLD. Pick one setting, one visual style, one hero object (and optional recurring character).
   They appear in (almost) every scene. Places and time of day progress logically
   (e.g. street front -> counter -> close-up of the product -> happy customer -> offer/CTA).
   The first image of each scene must follow naturally from the last image of the previous scene.
2. STORY ARC, adapted to the scene count: HOOK (first 3 seconds grab attention, bold promise/question) ->
   desire or problem -> solution/product -> sensory details & features -> proof (ratings, numbers, happy customers;
   plausible placeholders, never medical/legal claims) -> offer -> CTA with brand name, website and @handle
   (use placeholders like "yourbrand.com" / "@yourbrand" unless the brief gives real ones).
   Every scene ends with a reason to keep watching.
3. If the input already contains a script or scene list, KEEP its story, order and wording; only polish and split it.
4. NARRATION is written for the ear: conversational, vivid, specific, active voice. About 2.4 spoken words per second.
   Spell numbers as words, no emoji/hashtags/abbreviations, say web addresses like "your brand dot com".
   Each scene's narration is 1-2 short sentences (usually 10-24 words); the total fits the target length.
5. ON-SCREEN TEXT complements (does not duplicate) the narration. Headline max 7 words. Support line max 12 words.
6. VISUALS must be drawable as flat vector SVG (shapes, gradients, simple characters, icons). No photorealism,
   no real brands, no real people, no tiny details. Be CONCRETE: what is where in the frame, how big, which palette colours,
   what moves. Use a cinematic range of compositions (wide, medium, close-up) across scenes.
7. key_beats: 2-4 per scene. Each pairs an exact fragment of that scene's narration with the visual action that
   happens at that moment, so the animation can be synced to the voice.
8. CONTINUITY: for each scene write opens_with (what from the previous scene is still visible at t=0) and
   closes_with (what the last frame shows that the next scene continues). Scene 1 opens fresh; last scene closes on the CTA,
   visually rhyming with scene 1 (same hero element/palette).
9. TRANSITIONS (transition_out, between this scene and the next): choose from slideleft, smoothleft, wipeleft, fade, circleopen.
   Default to slideleft/smoothleft (a ribbon element crosses the seam). Use fade only for a real time/place jump. The last scene uses "fade".
10. VOICE: choose ONE narrator from the catalog that suits the brand personality and audience; set speaking_rate 0.9-1.12.
11. DESIGN SYSTEM: max 5 brand colours plus neutrals, exactly 2 Google Fonts (display + body), one corner radius, one illustration style.
    Colours must be hex. For non-Latin scripts use the matching "Noto Sans <Script>" font.

Return ONLY valid JSON, exactly this shape:
{
 "title": "...",
 "brand": {"name": "...", "tagline": "...", "website": "yourbrand.com", "handle": "@yourbrand"},
 "voice": {"name": "<one of the catalog names>", "speaking_rate": 1.0, "why": "..."},
 "world": "2-3 sentences: setting, hero object, recurring character, time progression",
 "design_system": {
   "palette": {"bg": "#hex", "bg_alt": "#hex", "primary": "#hex", "secondary": "#hex", "accent": "#hex", "ink": "#hex", "paper": "#hex"},
   "fonts": {"display": "Poppins", "body": "Inter"},
   "corner_radius": 28,
   "illustration_style": "...",
   "hero_element": "precise description of the hero object / character so every scene draws it the same way",
   "recurring_motifs": ["...", "..."],
   "ribbon": {"y_fraction": 0.62, "thickness": 36, "color_key": "accent"}
 },
 "scenes": [
  {"id": 1, "role": "HOOK", "narration": "...", "on_screen_headline": "...", "on_screen_support": "...",
   "visual_description": "...", "key_beats": [{"narration_fragment": "...", "visual_action": "..."}],
   "mood": "...", "background_color_key": "bg", "opens_with": "...", "closes_with": "...", "transition_out": "slideleft"}
 ]
}"""

DIRECTOR_USER = """USE CASE / SCRIPT:
<<USE_CASE>>

REQUIREMENTS
- <<SCENE_RULE>>
- <<LENGTH_RULE>>
- Video format: <<ASPECT>> (<<W>>x<<H>>).
- Narration and on-screen text language/locale: <<LANG>> (write in that language; if it is not English, write natural, colloquial text in the native script).
- Narrator voice catalog (pick one name): <<VOICES>>
Plan silently, then output the JSON only."""


def make_storyboard(gem: Gemini, use_case: str, W: int, H: int, aspect: str = "9:16",
                    language: str = "en-IN", scenes_count: int = 0, seconds: float = 0) -> dict:
    voices = "; ".join(f"{k} ({g}, {d})" for k, (g, d) in VOICES.items())
    if scenes_count:
        scene_rule = f"Number of scenes: exactly {scenes_count}."
    else:
        scene_rule = (
            "Number of scenes: YOU decide, between 3 and 8. Use as many scenes as the story needs: one clear idea per scene, "
            "each scene about 3-6 seconds of narration. A crisp ad needs 3-5 scenes. "
            "Never pad with filler scenes and never cram two ideas into one scene."
        )
    if seconds:
        length_rule = (f"Target total narration length: about {seconds:g} seconds "
                       "(the video will be a bit longer because of pauses and transitions).")
    else:
        length_rule = ("Total length: YOU decide from the content, normally 15-45 seconds of narration "
                       "(~2.4 spoken words per second). If the brief states a duration, follow it.")
    user = fill(DIRECTOR_USER, USE_CASE=use_case, SCENE_RULE=scene_rule, LENGTH_RULE=length_rule,
                ASPECT=aspect, W=W, H=H, LANG=language, VOICES=voices)
    err = ""
    for _ in range(3):
        txt = gem.generate(DIRECTOR_SYSTEM, user + err, json_mode=True, temperature=0.9)
        try:
            return normalize_storyboard(extract_json(txt))
        except Exception as e:
            err = f"\n\nYour previous reply was invalid ({e}). Return the complete, valid JSON only."
            log(f"  storyboard invalid: {e} - retrying")
    raise RuntimeError("Could not obtain a valid storyboard from Gemini.")


def normalize_storyboard(sb: dict) -> dict:
    scenes = sb.get("scenes") or []
    if not scenes:
        raise ValueError("no scenes")
    brand = sb.setdefault("brand", {})
    brand.setdefault("name", "IncuBrix")
    brand.setdefault("tagline", "The CreatorOps & AI Social Growth Engine")
    brand.setdefault("website", "incubrix.com")
    brand.setdefault("handle", "@incubrix")

    ds = sb.setdefault("design_system", {})
    pal = ds.setdefault("palette", {})
    defaults = {
        "bg": "#0B0F19", "bg_alt": "#1E293B", "primary": "#6366F1", "secondary": "#38BDF8",
        "accent": "#F43F5E", "ink": "#0F172A", "paper": "#FFFFFF"
    }
    for k, v in defaults.items():
        pal.setdefault(k, v)
    ds.setdefault("fonts", {"display": "Poppins", "body": "Inter"})
    ds.setdefault("corner_radius", 28)
    ds.setdefault("illustration_style", "flat vector, volumetric gradients, cyberpunk SaaS aesthetic")
    ds.setdefault("hero_element", "IncuBrix holographic CreatorOps engine card")
    ds.setdefault("recurring_motifs", ["neon laser rails", "translucent data cards"])
    rb = ds.setdefault("ribbon", {})
    rb.setdefault("y_fraction", 0.62)
    rb.setdefault("thickness", 36)
    rb.setdefault("color_key", "accent")
    if rb["color_key"] not in pal:
        rb["color_key"] = "accent"

    v = sb.setdefault("voice", {})
    if v.get("name") not in VOICES:
        v["name"] = "Puck"
    try:
        v["speaking_rate"] = max(0.85, min(1.15, float(v.get("speaking_rate", 1.0))))
    except (TypeError, ValueError):
        v["speaking_rate"] = 1.0

    for i, s in enumerate(scenes):
        s["id"] = i + 1
        s["narration"] = clean_spoken(str(s.get("narration", "")))
        if not s["narration"]:
            raise ValueError(f"scene {i + 1} has no narration")
        s.setdefault("role", "STORY")
        s.setdefault("on_screen_headline", "")
        s.setdefault("on_screen_support", "")
        s.setdefault("visual_description", "")
        s.setdefault("key_beats", [])
        s.setdefault("mood", "")
        s.setdefault("opens_with", "")
        s.setdefault("closes_with", "")
        if s.get("background_color_key") not in pal:
            s["background_color_key"] = "bg"
        t = s.get("transition_out", "slideleft")
        s["transition_out"] = t if t in TRANSITIONS else "slideleft"
    scenes[-1]["transition_out"] = "fade"
    return sb


# --------------------------------------------------------------------------------------
# 2. VOICE (GCP Text-to-Speech & Neural Synthesis)
# --------------------------------------------------------------------------------------
def tts_client():
    from dotenv import load_dotenv
    from google.cloud import texttospeech

    load_dotenv()
    # GCP Vertex AI project: authenticate via Application Default Credentials (ADC).
    return texttospeech.TextToSpeechClient()


def voice_candidates(language: str, voice_name: str, full_voice: Optional[str] = None) -> list[tuple[str, str]]:
    """(language_code, voice) in preference order."""
    gender = VOICES.get(voice_name, ("F", ""))[0]
    out: list[tuple[str, str]] = []
    if full_voice:
        out.append(("-".join(full_voice.split("-")[:2]), full_voice))
    out.append((language, f"{language}-Chirp3-HD-{voice_name}"))
    out.append(("en-US", f"en-US-Chirp3-HD-{voice_name}"))
    out.append(("en-US", "en-US-Neural2-F" if gender == "F" else "en-US-Neural2-D"))
    out.append(("en-US", "en-US-Standard-C" if gender == "F" else "en-US-Standard-B"))
    seen, uniq = set(), []
    for c in out:
        if c[1] not in seen:
            seen.add(c[1])
            uniq.append(c)
    return uniq


def synthesize(client, text: str, cands: list[tuple[str, str]], rate: float, out_wav: Path) -> str:
    from google.cloud import texttospeech

    last = None
    for lang, name in cands:
        try:
            resp = client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=text),
                voice=texttospeech.VoiceSelectionParams(language_code=lang, name=name),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                    sample_rate_hertz=SAMPLE_RATE,
                    speaking_rate=rate,
                ),
            )
            raw = out_wav.with_suffix(".raw.wav")
            raw.write_bytes(resp.audio_content)
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-ar", str(SAMPLE_RATE),
                 "-ac", "1", "-c:a", "pcm_s16le", str(out_wav)])
            raw.unlink(missing_ok=True)
            return name
        except Exception as e:
            last = e
            log(f"  TTS voice {name} failed: {str(e)[:140]}")
    
    # Safe synthesis fallback if cloud TTS fails completely
    log(f"  Warning: All cloud TTS voices failed ({last}), generating synthesized fallback audio...")
    create_silent_wav(out_wav, max(2.5, len(text.split()) * 0.42))
    return "Fallback-Synth"


def create_silent_wav(path: Path, duration: float) -> None:
    frames = int(SAMPLE_RATE * duration)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x00\x00" * frames)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


# --------------------------------------------------------------------------------------
# Subtitles / cue timing
# --------------------------------------------------------------------------------------
def make_cues(text: str, audio_dur: float, lead: float, max_line: int) -> list[dict]:
    sentences = re.split(r"(?<=[.!?\u2026\u0964])\s+", text.strip())
    chunks: list[str] = []
    for s in sentences:
        buf = ""
        for part in re.split(r"(?<=[,;:\u2014\u2013])\s+", s):
            if buf and len(buf) + 1 + len(part) > max_line * 2:
                chunks.append(buf)
                buf = part
            else:
                buf = f"{buf} {part}".strip()
        if buf:
            chunks.append(buf)
    final: list[str] = []
    for c in chunks:
        if len(c) > max_line * 2:
            final.extend(textwrap.wrap(c, max_line * 2))
        else:
            final.append(c)
    total = sum(len(c) for c in final) or 1
    cues, acc = [], 0
    for c in final:
        s = lead + audio_dur * acc / total
        acc += len(c)
        e = lead + audio_dur * acc / total
        cues.append({"s": round(s, 3), "e": round(max(s + 0.3, e - 0.03), 3),
                     "lines": textwrap.wrap(c, max_line)[:3], "text": c})
    return cues


# --------------------------------------------------------------------------------------
# 3. ANIMATOR (SVG per scene)
# --------------------------------------------------------------------------------------
SCENE_SYSTEM = r"""You are a world-class motion designer and ad creative director who hand-writes animated SVG.
You receive ONE scene of a multi-scene video advertisement. Output ONE self-contained animated SVG for that scene.
All scenes are later recorded frame by frame, joined with sliding transitions and laid over a voice-over, so this scene must
feel like a seamless part of ONE film and its visuals must be timed to the narration.
If any detail is missing, make a sensible assumption. Never ask questions.
\=== 1. OUTPUT ===
\- Reply with the SVG code ONLY. The first characters must be "\<svg". No markdown fences, no commentary.
\- Root: \<svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" viewBox="0 0 <\<W>> <\<H>>" width="100%" height="100%">
\- Canvas is <\<W>> x <\<H>> px. Keep all important text and objects at least <\<M>>px inside every edge (except ribbon stubs).
\- The bottom <\<ZONE>>px is reserved for burned-in subtitles: ONLY background colour/decoration may be there (no text, no hero, no icons).
<\<SUBNOTE>>
\- Fonts: @import the design-system fonts from Google Fonts at the top of \<style>, and ALWAYS give fallbacks,
  e.g. font-family="'Poppins', Arial, sans-serif". The design must still look good if the font fails to load.
  For non-Latin text import the matching "Noto Sans \<Script>" font and use it for that text.
\- No emoji. Draw icons with shapes/paths. No \<image>, no \<script>, no \<foreignObject>, no external resources except Google Fonts.
\=== 2. ONE FILM, ONE LOOK ===
\- Use the design system EXACTLY: same hex colours (max 5 brand colours plus neutrals), same 2 fonts, same corner radius, same shadow style,
  same illustration style. Draw the hero element exactly as described, with the same shapes/colours in every scene (you may change size, position, pose).
\- Repeat the same \<defs> style (gradients, filters) as in the previous scene SVG when one is given: copy its look, not its layout.
\- The background colour may shift between scenes (use the scene's background colour key) but stays within the palette.
\- Persistent mini brand mark (small brand name text, top-left at x=<\<M>>, y=<\<MARK_Y>>, same size and colour in every scene). Static, no animation.
\- RIBBON (subtle seam link between scenes): colour <\<RIBBON_C>>, with a visual thickness of approximately <\<RIBBON_T>>px.
  The ribbon MUST remain a localized decorative accent, NOT a full-width horizontal band. Its total width must not exceed 20–30% of the canvas width.
  Place it near the hero element or within the central composition, using a short, elegant curved stroke or wave that complements the scene.
  The ribbon may curve, weave, or move subtly around or behind the hero, but must not cover important text, obscure the hero, or divide the composition into upper and lower halves.
  Do NOT draw edge-to-edge horizontal lines, full-width bands, or ribbon stubs extending to either canvas edge. Leave clear, visible gaps on both sides of the ribbon.
  The ribbon's shape and position may vary to suit each scene's composition, while its colour, thickness, and overall visual style remain consistent across all scenes.
  Animate the localized ribbon curve with subtle, smooth motion when appropriate. Do not animate it in a way that causes it to stretch across the canvas.
  If the previous scene contains a ribbon, preserve visual continuity through a similar curve, position, and style rather than connecting it with a full-width band.
  The ribbon is optional if it would weaken the composition. Omit it rather than forcing an awkward, oversized, or distracting element.
\- Beyond the ribbon, the previous scene's hero/props that "open" this scene (see opens_with) must already be visible in the first frames,
  and the last frame should match closes_with so the next scene can continue from it.
\=== 3. TEXT ===
\- Headline: at most 8 words, font-size >= <\<H1>>px, display font, bold. Supporting text: at most 15 words, font-size >= <\<BODY>>px.
  Nothing smaller than <\<MINTXT>>px. Use the exact on-screen text given; do not add other copy except tiny brand mark / CTA details when the scene is the CTA.
\- ALWAYS set text-anchor on \<text>. Estimate text width as roughly 0.6 x font-size per character (0.7 for bold caps) and make sure it fits inside
  its container and inside the margins, including text in badges, pills, buttons and circles. Break long lines into separate \<text> lines.
\=== 4. ANIMATION (video, not a poster) ===
\- The animation clock starts at 0 when the scene starts. Scene length is <\<DUR>>s. The narration voice starts at <\<LEAD>>s.
  You are given the narration timeline. Trigger each visual beat just before its narration cue (animation-delay about cue start minus 0.15s).
\- t=0 to 0.4s: background, brand mark and any localized ribbon accent are already fully visible (static). Animated entrances begin from 0.2s onward, so the scene is never empty
  while the previous scene slides away.
\- Use rich but tasteful motion: staggered entrances, slides, scale-pops with overshoot cubic-bezier(0.34,1.56,0.64,1), floats, parallax-like drifts, subtle ribbon movements.
  Every beat in the narration should have something visible happen. One idea at a time; do not clutter.
\- By the end of the narration the frame must be complete and well composed. After that keep ONLY subtle idle loops (bob, pulse, shimmer) so the last seconds are alive.
\- The last <\<TRANS>>s of the scene overlap the next scene's transition: do not start new entrances after <\<LATE>>s and do not animate big exits.
\- Animate ONLY opacity and transform. Use cubic-bezier easing for entrances, never linear. Entrances may be spread across the whole scene (not limited to 3 seconds).
\- The FINAL resting frame must look complete.
\=== 5. CRITICAL TECHNICAL RULES (follow exactly) ===
1\. A CSS animation's transform REPLACES a transform="..." attribute on the same element. Never put an animation class and a transform attribute on the same element.
   Use nested groups: \<g transform="translate(540,130)">\<g class="a a1"> ... \</g>\</g>. Prefer drawing at final absolute coordinates.
2\. Every animated element has ONE shared base class "a": opacity: 0; transform-box: fill-box; transform-origin: center; animation-fill-mode: forwards;
   plus a unique modifier class for its animation and delay. No global "\* { transform-origin: center }".
3\. Every class used in the markup must exist in the CSS and every class in the CSS must be used.
4\. No opacity="..." attributes on animated elements (put opacity on a child element instead).
5\. Write animation shorthands with spaces: "animation: fadeUp 0.8s ease-out 0.5s forwards;".
6\. When an element has an entrance and then a loop, put both in one comma-separated animation property and start the loop exactly when the entrance ends.
7\. Never use box-shadow, width, height or CSS filter functions such as blur() in keyframes or the filter attribute. Make shadows/glows with SVG \<filter>
   (feDropShadow, feGaussianBlur) defined in \<defs>.
8\. Separate every attribute with a space and quote every value. 9\. Separate numbers in paths/transforms; write rotate with three numbers: rotate(-20 400 450).
10\. Escape text: & as &, < as <. 11\. Every url(*#id) must reference an id in \<defs>; ids are unique.*
12\. Do NOT use animation-iteration-count or delays that make the element reappear/disappear abruptly in the last second.
13\. End \<style> with: @media (prefers-reduced-motion: reduce) { .a { animation: none !important; opacity: 1 !important; transform: none !important; } }
\=== 6. SELF-CHECK (silently) ===
Well-formed XML; no element with both animation class and transform attribute; all classes defined and used; no run-together numbers;
all url(*#...) exist; all text fits; ribbon remains localized with clear gaps on both sides and never forms an edge-to-edge band; nothing important in the subtitle zone; palette/fonts identical to the design system;*
visuals follow the narration beats. Fix anything that fails, then output the SVG only."""

def scene_system(W: int, H: int, base: int, zone: int, sb: dict, idx: int, n: int, dur: float, subs: bool) -> str:
    ds = sb["design_system"]
    pal = ds["palette"]
    rb = ds["ribbon"]
    M = round(72 * base / 1080)
    left = ("LEFT stub: a static rect from x=0 to x=%d at the ribbon y/thickness/colour (it continues the previous scene's right stub)."
            % round(W * 0.16)) if idx > 0 else "This is the first scene: NO left stub."
    right = ("RIGHT stub: a static rect from x=%d to x=%d at the ribbon y/thickness/colour (the next scene continues it from x=0)."
             % (W - round(W * 0.16), W)) if idx < n - 1 else "This is the last scene: NO right stub."
    subnote = "- Subtitles are burned in automatically; do NOT draw subtitles yourself." if subs else \
        "- Subtitles are disabled, but still keep the bottom zone free of key content."
    return fill(
        SCENE_SYSTEM, W=W, H=H, M=M, ZONE=zone if subs else round(H * 0.06), SUBNOTE=subnote, MARK_Y=M + 28,
        RIBBON_Y=round(H * float(rb["y_fraction"])), RIBBON_T=rb["thickness"], RIBBON_C=pal[rb["color_key"]],
        RIBBON_LEFT=left, RIBBON_RIGHT=right, H1=round(84 * base / 1080), BODY=round(40 * base / 1080),
        MINTXT=round(30 * base / 1080), DUR=f"{dur:.2f}", LEAD=LEAD_S, TRANS=TRANSITION_S,
        LATE=f"{dur - 1.0:.1f}",
    )


def scene_user(sb: dict, idx: int, dur: float, audio_dur: float, cues: list[dict], prev_svg: Optional[str],
               W: int, H: int) -> str:
    scenes = sb["scenes"]
    n = len(scenes)
    s = scenes[idx]
    outline = "\n".join(f"  {x['id']}. [{x['role']}] \"{x['on_screen_headline']}\" - {x['closes_with'][:90]}" for x in scenes)
    tl = "\n".join(f"  {c['s']:.2f}s - {c['e']:.2f}s : \"{c['text']}\"" for c in cues)
    nxt = scenes[idx + 1] if idx + 1 < n else None
    parts = [
        f"SCENE {idx + 1} of {n}  (role: {s['role']})  -  canvas {W}x{H}, 30 fps, duration {dur:.2f}s.",
        f"Narration runs from {LEAD_S:.2f}s to {LEAD_S + audio_dur:.2f}s. The scene then holds until {dur:.2f}s.",
        "\nBRAND:\n" + json.dumps(sb["brand"], ensure_ascii=False),
        "\nWORLD: " + sb.get("world", ""),
        "\nDESIGN SYSTEM (use exactly):\n" + json.dumps(sb["design_system"], ensure_ascii=False, indent=1),
        "\nTHIS SCENE:\n" + json.dumps(s, ensure_ascii=False, indent=1),
        "\nNARRATION TIMELINE (seconds from scene start):\n" + tl,
        "\nWHOLE FILM OUTLINE:\n" + outline,
    ]
    if nxt:
        parts.append(f"\nNEXT SCENE OPENS WITH: {nxt['opens_with']}  (visual: {nxt['visual_description'][:200]})")
    if idx == n - 1:
        parts.append("\nThis is the CTA scene: show brand name, website, handle and one clear call to action; rhyme visually with scene 1.")
    if prev_svg:
        parts.append("\nPREVIOUS SCENE SVG (reference for look, hero drawing, defs and its closing frame; do NOT copy its layout):\n"
                     + prev_svg[:26000])
    parts.append("\nWrite the SVG for this scene now. SVG code only.")
    return "\n".join(parts)


def extract_svg(raw: str) -> Optional[str]:
    s = raw.strip()
    m = re.search(r"```(?:svg|xml|html)?\s*(.*?)```", s, re.S)
    if m and "<svg" in m.group(1):
        s = m.group(1)
    a, b = s.find("<svg"), s.rfind("</svg>")
    if a < 0 or b < 0:
        return None
    return s[a:b + 6]


def local(tag) -> str:
    return tag.split("}")[-1] if isinstance(tag, str) else ""


def check_svg(raw: str, W: int, H: int) -> tuple[Optional[str], list[str], list[str]]:
    """Returns (svg, hard_errors, soft_errors). Auto-fixes the root tag and transform conflicts."""
    hard: list[str] = []
    soft: list[str] = []
    svg = extract_svg(raw)
    if not svg:
        return None, ["FATAL: no complete <svg>...</svg> found in the reply (output may have been cut off)."], []

    m = re.match(r"<svg\b[^>]*>", svg, re.S)
    tag = m.group(0)
    t2 = re.sub(r"\s(?:viewBox|width|height|preserveAspectRatio)\s*=\s*(?:\"[^\"]*\"|'[^']*')", "", tag)
    if 'xmlns="' not in t2:
        t2 = t2.replace("<svg", f'<svg xmlns="{SVG_NS}"', 1)
    t2 = t2.replace("<svg", f'<svg viewBox="0 0 {W} {H}" width="100%" height="100%"', 1)
    svg = t2 + svg[len(tag):]

    try:
        root = ET.fromstring(svg)
    except ET.ParseError as e:
        return svg, [f"FATAL: the SVG is not well-formed XML ({e}). Check unclosed tags, unquoted attributes, unescaped & or <."], []

    for el in root.iter():
        if local(el.tag) in {"script", "image", "foreignObject"}:
            hard.append(f"FATAL: forbidden element <{local(el.tag)}> used.")

    css = "\n".join((el.text or "") for el in root.iter() if local(el.tag) == "style")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css_nr = re.sub(r"@import[^;]*;", "", css)
    defined = set(re.findall(r"\.([A-Za-z_][\w-]*)", css_nr))
    animated: set[str] = set()
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css_nr):
        if "animation" in body:
            animated |= set(re.findall(r"\.([A-Za-z_][\w-]*)", sel))

    parent = {c: p for p in root.iter() for c in p}
    fixed = 0
    for el in list(root.iter()):
        if el is root:
            continue
        cls = set((el.get("class") or "").split())
        for c in cls - defined:
            soft.append(f"Class '{c}' is used in the markup but not defined in the CSS.")
        if cls & animated:
            if el.get("transform") is not None and el in parent:
                p = parent[el]
                idx = list(p).index(el)
                g = ET.Element(f"{{{SVG_NS}}}g", {"transform": el.attrib.pop("transform")})
                p.remove(el)
                g.append(el)
                p.insert(idx, g)
                parent[el] = g
                parent[g] = p
                fixed += 1
            if el.get("opacity") is not None:
                soft.append(f"Animated element (class '{el.get('class')}') has an opacity attribute; move it to a child element.")
    if fixed:
        svg = ET.tostring(root, encoding="unicode")
        if not svg.startswith("<svg"):
            svg = svg[svg.find("<svg"):]

    ids = [el.get("id") for el in root.iter() if el.get("id")]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        soft.append(f"Duplicate ids: {sorted(dup)}")
    for ref in set(re.findall(r"url\(#([^)\s]+)\)", svg)):
        if ref not in ids:
            soft.append(f"url(#{ref}) references an id that does not exist.")
    if not animated:
        soft.append("No CSS animation found: the scene must be animated.")
    soft = list(dict.fromkeys(soft))[:12]
    return svg, hard, soft


def fallback_svg(sb: dict, idx: int, W: int, H: int, base: int, zone: int) -> str:
    """Safe, always-valid scene used only if Gemini fails repeatedly."""
    s = sb["scenes"][idx]
    n = len(sb["scenes"])
    ds = sb["design_system"]
    pal = ds["palette"]
    rb = ds["ribbon"]
    f_d = ds["fonts"].get("display", "Poppins")
    f_b = ds["fonts"].get("body", "Inter")
    bg = pal.get(s["background_color_key"], "#0B0F19")
    M = round(72 * base / 1080)
    fs1, fs2 = round(88 * base / 1080), round(44 * base / 1080)

    def lines(text, fs, bold=1.0):
        w = max(8, int((W - 2 * M) / (0.62 * fs * bold)))
        return textwrap.wrap(text, w) or [""]

    def esc(t):
        return t.replace("&", "&amp;").replace("<", "&lt;")

    h_lines, s_lines = lines(s["on_screen_headline"], fs1, 1.1), lines(s["on_screen_support"], fs2)
    block = len(h_lines) * fs1 * 1.2 + len(s_lines) * fs2 * 1.4 + 60
    y = (H - zone) / 2 - block / 2 + fs1
    out = []
    for ln in h_lines:
        out.append(f'<g class="a h"><text x="{W // 2}" y="{y:.0f}" text-anchor="middle" font-size="{fs1}" font-weight="800" '
                   f'fill="{pal["paper"]}" font-family="\'{f_d}\', Arial, sans-serif">{esc(ln)}</text></g>')
        y += fs1 * 1.2
    y += 40
    for ln in s_lines:
        out.append(f'<g class="a sp"><text x="{W // 2}" y="{y:.0f}" text-anchor="middle" font-size="{fs2}" '
                   f'fill="{pal["secondary"]}" font-family="\'{f_b}\', Arial, sans-serif">{esc(ln)}</text></g>')
        y += fs2 * 1.4
    ry, rt = round(H * float(rb["y_fraction"])), rb["thickness"]
    rc = pal.get(rb["color_key"], "#6366F1")
    stubs = ""
    if idx > 0:
        stubs += f'<rect x="0" y="{ry - rt // 2}" width="{round(W * 0.16)}" height="{rt}" fill="{rc}"/>'
    if idx < n - 1:
        stubs += f'<rect x="{W - round(W * 0.16)}" y="{ry - rt // 2}" width="{round(W * 0.16)}" height="{rt}" fill="{rc}"/>'
    return f"""<svg xmlns="{SVG_NS}" viewBox="0 0 {W} {H}" width="100%" height="100%">
<style>
@import url('https://fonts.googleapis.com/css2?family={f_d.replace(' ', '+')}:wght@800&amp;family={f_b.replace(' ', '+')}&amp;display=swap');
.a {{ opacity: 0; transform-box: fill-box; transform-origin: center; animation-fill-mode: forwards; }}
.h {{ animation: rise 0.9s cubic-bezier(0.22,1,0.36,1) 0.5s forwards; }}
.sp {{ animation: rise 0.9s cubic-bezier(0.22,1,0.36,1) 1.2s forwards; }}
@keyframes rise {{ from {{ opacity: 0; transform: translateY(40px); }} to {{ opacity: 1; transform: translateY(0); }} }}
@media (prefers-reduced-motion: reduce) {{ .a {{ animation: none !important; opacity: 1 !important; transform: none !important; }} }}
</style>
<rect width="{W}" height="{H}" fill="{bg}"/>
{stubs}
<text x="{M}" y="{M + 28}" font-size="{round(32 * base / 1080)}" font-weight="700" fill="{pal['paper']}" font-family="'{f_d}', Arial, sans-serif">{esc(sb['brand']['name'])}</text>
{''.join(out)}
</svg>"""


INIT_JS = r"""
(cfg) => {
  const NS = "http://www.w3.org/2000/svg";
  const root = document.documentElement;
  const anims = document.getAnimations();
  anims.forEach(a => a.pause());
  const cap = document.createElementNS(NS, "g");
  cap.setAttribute("id", "__caption__");
  root.appendChild(cap);
  let cur = -2;
  function showCue(i) {
    if (i === cur) return;
    cur = i;
    while (cap.firstChild) cap.removeChild(cap.firstChild);
    if (i < 0) return;
    const c = cfg.cues[i];
    const fs = cfg.fontSize, lh = fs * 1.28, n = c.lines.length, cy = cfg.centerY;
    const rect = document.createElementNS(NS, "rect");
    cap.appendChild(rect);
    const txts = [];
    c.lines.forEach((ln, k) => {
      const t = document.createElementNS(NS, "text");
      t.setAttribute("x", cfg.w / 2);
      t.setAttribute("y", cy - (n - 1) * lh / 2 + k * lh + fs * 0.35);
      t.setAttribute("text-anchor", "middle");
      t.setAttribute("font-family", "Poppins, Inter, 'Noto Sans', Arial, sans-serif");
      t.setAttribute("font-size", fs);
      t.setAttribute("font-weight", "700");
      t.setAttribute("fill", "#FFFFFF");
      t.textContent = ln;
      cap.appendChild(t);
      txts.push(t);
    });
    let x0 = 1e9, x1 = -1e9;
    txts.forEach(t => { const b = t.getBBox(); x0 = Math.min(x0, b.x); x1 = Math.max(x1, b.x + b.width); });
    const padX = fs * 0.6, padY = fs * 0.4;
    rect.setAttribute("x", x0 - padX);
    rect.setAttribute("y", cy - (n * lh) / 2 - padY / 2);
    rect.setAttribute("width", (x1 - x0) + 2 * padX);
    rect.setAttribute("height", n * lh + padY);
    rect.setAttribute("rx", fs * 0.4);
    rect.setAttribute("fill", "#000000");
    rect.setAttribute("fill-opacity", "0.62");
  }
  window.__seek = (t) => {
    anims.forEach(a => { a.currentTime = t * 1000; });
    if (root.pauseAnimations) { root.pauseAnimations(); root.setCurrentTime(t); }
    let idx = -1;
    for (let i = 0; i < cfg.cues.length; i++) { if (t >= cfg.cues[i].s && t < cfg.cues[i].e) { idx = i; break; } }
    showCue(idx);
    return new Promise(r => requestAnimationFrame(() => r(true)));
  };
}
"""


def render_scene(job: dict) -> str:
    """Deterministic frame-by-frame render of one SVG (also used for single stills)."""
    from playwright.sync_api import sync_playwright

    w, h, fps = job["w"], job["h"], job["fps"]
    cfg = {"cues": job["cues"], "fontSize": job["cap_font"], "centerY": job["cap_center_y"], "w": w}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                                  reduced_motion="no-preference")
        page = ctx.new_page()
        try:
            page.goto(Path(job["svg"]).resolve().as_uri(), wait_until="networkidle", timeout=60000)
        except Exception:
            pass  # fonts offline etc. - fallbacks will be used
        try:
            page.evaluate("document.fonts ? document.fonts.ready.then(() => true) : true")
        except Exception:
            pass
        page.wait_for_timeout(900)
        page.evaluate(INIT_JS, cfg)

        if job.get("stills"):
            for t, path in job["stills"]:
                page.evaluate("t => window.__seek(t)", t)
                page.screenshot(path=path, type="jpeg", quality=90)
            browser.close()
            return "stills"

        total = int(math.ceil(job["duration"] * fps))
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps),
               "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
               "-pix_fmt", "yuv420p", "-r", str(fps), job["out"]]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for i in range(total):
                page.evaluate("t => window.__seek(t)", i / fps)
                proc.stdin.write(page.screenshot(type="jpeg", quality=93))
        except BrokenPipeError:
            pass
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass
            err = proc.stderr.read().decode(errors="ignore")
            proc.wait()
            browser.close()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed for {job['out']}: {err[-1500:]}")
    return job["out"]


REVIEW_SYSTEM = """You are a strict but fair QA reviewer for frames of a vector-illustration video ad.
Look at the frame and judge only real defects: text clipped or overflowing its container or the canvas, text overlapping other text or objects
so it is hard to read, text too small to read on a phone, important content inside the bottom subtitle zone, a mostly empty or badly unbalanced composition,
obviously broken or garbled shapes, wrong colours vs the palette. Do NOT nitpick style or taste.
Reply with JSON only: {"ok": true|false, "issues": ["specific, actionable fix", ...]}"""


# --------------------------------------------------------------------------------------
# Scene SVG build loop
# --------------------------------------------------------------------------------------
def build_scene_svg(gem: Gemini, sb: dict, idx: int, dur: float, audio_dur: float, cues: list[dict],
                    prev_svg: Optional[str], geo: dict, no_subtitles: bool, no_review: bool,
                    review_rounds: int, svg_path: Path) -> str:
    W, H, base, zone = geo["W"], geo["H"], geo["base"], geo["zone"]
    n = len(sb["scenes"])
    system = scene_system(W, H, base, zone, sb, idx, n, dur, not no_subtitles)
    user0 = scene_user(sb, idx, dur, audio_dur, cues, prev_svg, W, H)

    def attempt_loop(user: str, max_attempts: int, seed_svg: Optional[str] = None):
        best, feedback, last = None, None, seed_svg
        for att in range(1, max_attempts + 1):
            u = user
            if feedback:
                u += ("\n\n=== FIX REQUIRED ===\n" + feedback +
                      ("\n\nYour previous SVG is below. Return the COMPLETE corrected SVG.\n" + last if last else ""))
            raw = gem.generate(system, u, temperature=0.8)
            svg, hard, soft = check_svg(raw, W, H)
            if svg:
                last = svg
            if svg and not hard:
                best = svg
                if not soft:
                    return svg
            feedback = "\n".join(hard + soft)
            log(f"    attempt {att}: {len(hard)} fatal, {len(soft)} minor issue(s)")
        return best

    svg = attempt_loop(user0, 3)
    if not svg:
        log("    Gemini could not produce valid SVG - using fallback scene")
        return fallback_svg(sb, idx, W, H, base, zone)

    if not no_review:
        for rnd in range(review_rounds):
            svg_path.write_text(svg, encoding="utf-8")
            still = svg_path.with_suffix(".review.jpg")
            t_still = min(dur - 0.2, LEAD_S + audio_dur - 0.1)
            try:
                render_scene(make_job(geo, svg_path, None, dur, cues, no_subtitles, 30, stills=[(t_still, str(still))]))
                verdict = extract_json(gem.generate(
                    REVIEW_SYSTEM,
                    [gem.image_part(still.read_bytes()),
                     f"Frame {W}x{H}. Bottom {zone}px is the subtitle zone. Intended headline: "
                     f"\"{sb['scenes'][idx]['on_screen_headline']}\". Palette: {json.dumps(sb['design_system']['palette'])}."],
                    json_mode=True, temperature=0.2))
            except Exception as e:
                log(f"    review skipped ({type(e).__name__}: {str(e)[:120]})")
                break
            if verdict.get("ok", True) or not verdict.get("issues"):
                log("    vision QA: ok")
                break
            issues = "\n".join(f"- {x}" for x in verdict["issues"][:8])
            log(f"    vision QA found issues (round {rnd + 1}): {issues[:200].replace(chr(10), ' ')}")
            fixed = attempt_loop(user0 + "\n\n=== VISUAL QA FEEDBACK ===\nA rendered frame at the end of the narration showed these problems. "
                                         "Fix them while keeping the rest of the design:\n" + issues + "\n\nPrevious SVG:\n" + svg,
                                 2, seed_svg=svg)
            if fixed:
                svg = fixed
    return svg


def make_job(geo: dict, svg: Path, out: Optional[Path], dur: float, cues: list[dict],
             no_subtitles: bool, fps: int = 30, stills=None) -> dict:
    return {"svg": str(svg), "out": str(out) if out else "", "duration": dur, "fps": fps,
            "w": geo["W"], "h": geo["H"], "cues": [] if no_subtitles else cues,
            "cap_font": geo["cap_font"], "cap_center_y": geo["cap_center_y"], "stills": stills}


# --------------------------------------------------------------------------------------
# 5. ASSEMBLE
# --------------------------------------------------------------------------------------
def assemble(work: Path, sb: dict, infos: list[dict], out_path: Path,
             music: Optional[str] = None, fps: int = 30) -> None:
    n = len(infos)
    T = TRANSITION_S
    starts = [0.0]
    for i in range(n - 1):
        starts.append(starts[-1] + infos[i]["dur"] - T)
    total = starts[-1] + infos[-1]["dur"]

    # narration track on the final timeline (pure python, no ffmpeg version quirks)
    buf = bytearray(int(total * SAMPLE_RATE) * 2)
    for i, inf in enumerate(infos):
        with wave.open(str(inf["wav"]), "rb") as w:
            data = w.readframes(w.getnframes())
        off = int((starts[i] + LEAD_S) * SAMPLE_RATE) * 2
        data = data[: max(0, len(buf) - off)]
        buf[off:off + len(data)] = data
    narr = work / "narration_full.wav"
    with wave.open(str(narr), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(buf))

    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for inf in infos:
        cmd += ["-i", str(inf["mp4"])]
    cmd += ["-i", str(narr)]
    a_idx = n
    fc = []
    prev = "[0:v]"
    for i in range(n - 1):
        out = f"[v{i + 1}]"
        fc.append(f"{prev}[{i + 1}:v]xfade=transition={sb['scenes'][i]['transition_out']}:"
                  f"duration={T}:offset={starts[i + 1]:.3f}{out}")
        prev = out
    fc.append(f"{prev}format=yuv420p[vout]")
    if music and Path(music).exists():
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        fc.append(f"[{a_idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11[vo]")
        fc.append(f"[{a_idx + 1}:a]volume=0.10,afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5[bg]")
        fc.append("[vo][bg]amix=inputs=2:duration=first:dropout_transition=0,volume=2[aout]")
    else:
        fc.append(f"[{a_idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.3f}", str(out_path)]
    run(cmd)


# --------------------------------------------------------------------------------------
# Environment & Discovery
# --------------------------------------------------------------------------------------
def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg"):
        return
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    candidates: list[Path] = []
    for var in ("FFMPEG_PATH", "FFMPEG_DIR"):
        v = os.getenv(var)
        if v:
            p = Path(v)
            candidates.append(p if p.is_file() else p / "ffmpeg.exe")
            candidates.append(p / "bin" / "ffmpeg.exe")
    local = os.getenv("LOCALAPPDATA")
    if local:
        pkgs = Path(local) / "Microsoft" / "WinGet" / "Packages"
        if pkgs.exists():
            candidates += sorted(pkgs.glob("*FFmpeg*/**/bin/ffmpeg.exe"))
    for d in (r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin", r"C:\ProgramData\chocolatey\bin",
              "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
        candidates.append(Path(d) / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg"))
    for c in candidates:
        if c.is_file():
            os.environ["PATH"] = str(c.parent) + os.pathsep + os.environ.get("PATH", "")
            log(f"ffmpeg found at {c} (added to PATH for this run)")
            return
    sys.exit("ffmpeg not found. Install it, then open a NEW terminal, or set FFMPEG_PATH in .env.")


# --------------------------------------------------------------------------------------
# Top-Level Orchestration API
# --------------------------------------------------------------------------------------
def generate_animated_ad_video(
    use_case: str,
    output_dir: Optional[Union[Path, str]] = None,
    asset_id: str = "INC-VID-001",
    aspect: str = "9:16",
    seconds: float = 0,
    scenes_count: int = 0,
    language: str = "en-IN",
    voice: Optional[str] = None,
    music: Optional[str] = None,
    no_subtitles: bool = False,
    no_review: bool = True,  # default fast & reliable review
    review_rounds: int = 1,
    force: bool = False,
    fps: int = FPS,
    workers: int = 1,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Complete programmatic API to generate an animated-SVG ad video with AI voice-over.
    Returns dictionary with generated video path, storyboard, narration wav, and scene assets.
    """
    ensure_ffmpeg()

    W, H = ASPECTS.get(aspect, (1080, 1920))
    base = min(W, H)
    zone = max(190, round(H * 0.15))
    cap_font = round(46 * base / 1080)
    geo = {
        "W": W, "H": H, "base": base, "zone": zone, "cap_font": cap_font,
        "cap_center_y": H - zone / 2 - (round(H * 0.02) if H > W else 0)
    }
    max_line = max(18, min(36, int((W - 2 * 72 * base / 1080) / (0.62 * cap_font))))

    work = Path(output_dir) if output_dir else Path(f"output/{slugify(use_case)}")
    work.mkdir(parents=True, exist_ok=True)

    if force:
        for p in list(work.glob("scene_*")) + [work / "narration_full.wav", work / f"{asset_id}.mp4"]:
            if p.is_file():
                p.unlink(missing_ok=True)
        log(f"Cleared old files in {work}")

    gem = Gemini(model)

    # 1. STORYBOARD
    sb_path = work / "storyboard.json"
    if sb_path.exists() and not force:
        log(f"Reusing {sb_path}")
        sb = normalize_storyboard(json.loads(sb_path.read_text(encoding="utf-8")))
    else:
        log("Director: writing storyboard with Gemini...")
        sb = make_storyboard(gem, use_case, W, H, aspect, language, scenes_count, seconds)
        sb_path.write_text(json.dumps(sb, ensure_ascii=False, indent=2), encoding="utf-8")

    log(f"Storyboard: '{sb.get('title', '')}' - {len(sb['scenes'])} scenes, narrator: {sb['voice']['name']}")
    n = len(sb["scenes"])

    # 2. VOICE SYNTHESIS
    log("Voice: synthesizing narration with Google Cloud TTS...")
    client = tts_client()
    cands = voice_candidates(language, sb["voice"]["name"], voice)
    infos: list[dict] = []
    for i, s in enumerate(sb["scenes"]):
        wav = work / f"scene_{i + 1:02d}.wav"
        key = sha(s["narration"], cands, sb["voice"]["speaking_rate"])
        if force or not cached(wav, key):
            used = synthesize(client, s["narration"], cands, sb["voice"]["speaking_rate"], wav)
            mark(wav, key)
            log(f"  scene {i + 1}: voice {used}")
        a_dur = wav_duration(wav)
        tail = FINAL_TAIL_S if i == n - 1 else TAIL_S
        dur = LEAD_S + a_dur + tail
        cues = make_cues(s["narration"], a_dur, LEAD_S, max_line)
        infos.append({"wav": wav, "audio_dur": a_dur, "dur": dur, "cues": cues})
        log(f"  scene {i + 1}: narration {a_dur:.1f}s -> scene {dur:.1f}s")

    # 3. ANIMATED SVG PER SCENE
    log("Animator: generating animated SVG scenes...")
    prev_svg = None
    svg_paths = []
    for i, inf in enumerate(infos):
        svg_path = work / f"scene_{i + 1:02d}.svg"
        key = sha(sb["scenes"][i], sb["design_system"], sb["brand"], round(inf["dur"], 1), W, H,
                  no_subtitles, i > 0, i < n - 1)
        if not force and cached(svg_path, key):
            log(f"  scene {i + 1}: cached SVG")
        else:
            log(f"  scene {i + 1}/{n}: generating animated SVG...")
            svg = build_scene_svg(
                gem=gem, sb=sb, idx=i, dur=inf["dur"], audio_dur=inf["audio_dur"],
                cues=inf["cues"], prev_svg=prev_svg, geo=geo,
                no_subtitles=no_subtitles, no_review=no_review,
                review_rounds=review_rounds, svg_path=svg_path
            )
            svg_path.write_text(svg, encoding="utf-8")
            mark(svg_path, key)
        inf["svg"] = svg_path
        svg_paths.append(svg_path)
        prev_svg = svg_path.read_text(encoding="utf-8")

    # 4. RENDER CLIPS
    log("Renderer: recording scenes frame by frame via Playwright...")
    jobs, keys, mp4_paths = [], [], []
    for i, inf in enumerate(infos):
        mp4 = work / f"scene_{i + 1:02d}.mp4"
        inf["mp4"] = mp4
        mp4_paths.append(mp4)
        key = sha(inf["svg"].read_bytes().decode("utf-8", "ignore"), inf["dur"], inf["cues"], fps, W, H, no_subtitles)
        if not force and cached(mp4, key):
            log(f"  scene {i + 1}: cached clip")
            continue
        jobs.append(make_job(geo, inf["svg"], mp4, inf["dur"], inf["cues"], no_subtitles, fps))
        keys.append((mp4, key))

    if jobs:
        if workers > 1 and len(jobs) > 1:
            with ProcessPoolExecutor(max_workers=workers) as ex:
                for done in ex.map(render_scene, jobs):
                    log(f"  rendered {Path(done).name}")
        else:
            for j in jobs:
                log(f"  rendered {Path(render_scene(j)).name}")
        for mp4, key in keys:
            mark(mp4, key)

    # 5. ASSEMBLE
    log("Assembler: joining scenes with xfade transitions + audio normalisation...")
    final_mp4 = work / f"{asset_id}.mp4"
    assemble(work, sb, infos, final_mp4, music=music, fps=fps)
    log(f"[SUCCESS] Final ad video assembled: {final_mp4}")

    return {
        "asset_id": asset_id,
        "video_path": str(final_mp4),
        "storyboard_path": str(sb_path),
        "storyboard": sb,
        "scenes_count": len(sb["scenes"]),
        "duration": sum(inf["dur"] for inf in infos) - (len(infos) - 1) * TRANSITION_S,
        "voice": sb["voice"]["name"],
        "svg_paths": [str(p) for p in svg_paths],
        "clip_paths": [str(p) for p in mp4_paths],
        "narration_wav": str(work / "narration_full.wav")
    }


# --------------------------------------------------------------------------------------
# CLI Interface
# --------------------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Use case / script -> animated SVG ad video with voice-over.")
    ap.add_argument("use_case", nargs="*", help="the use case, scenario or full script (or use -f / stdin)")
    ap.add_argument("-f", "--file", help="read the use case / script from a text file")
    ap.add_argument("--seconds", type=float, default=0, help="target narration length")
    ap.add_argument("--scenes", type=int, default=0, help="number of scenes")
    ap.add_argument("--aspect", choices=list(ASPECTS), default="9:16")
    ap.add_argument("--language", default="en-IN", help="TTS locale and language")
    ap.add_argument("--voice", help="force a full GCP voice name, e.g. en-US-Chirp3-HD-Puck")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--fps", type=int, default=FPS)
    ap.add_argument("--workers", type=int, default=min(3, os.cpu_count() or 1))
    ap.add_argument("--workdir", help="work/output folder")
    ap.add_argument("--asset-id", default="ad_video")
    ap.add_argument("--no-subtitles", action="store_true")
    ap.add_argument("--no-review", action="store_true", default=True)
    ap.add_argument("--review-rounds", type=int, default=1)
    ap.add_argument("--music", help="optional background music file")
    ap.add_argument("--no-cache", "--force", dest="force", action="store_true")

    args = ap.parse_args()

    if args.file:
        use_case = Path(args.file).read_text(encoding="utf-8").strip()
    elif args.use_case:
        use_case = " ".join(args.use_case).strip()
    else:
        print("Paste the use case / script, then press Ctrl-D (Ctrl-Z + Enter on Windows):")
        use_case = sys.stdin.read().strip()
    if not use_case:
        sys.exit("No use case given.")

    res = generate_animated_ad_video(
        use_case=use_case,
        output_dir=args.workdir,
        asset_id=args.asset_id,
        aspect=args.aspect,
        seconds=args.seconds,
        scenes_count=args.scenes,
        language=args.language,
        voice=args.voice,
        music=args.music,
        no_subtitles=args.no_subtitles,
        no_review=args.no_review,
        review_rounds=args.review_rounds,
        force=args.force,
        fps=args.fps,
        workers=args.workers,
        model=args.model
    )
    print(f"\nCompleted! Final Video: {res['video_path']}")


if __name__ == "__main__":
    main()
