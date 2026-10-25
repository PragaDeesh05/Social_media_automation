#!/usr/bin/env python3
"""
ad_image.py - Use Case -> high-quality static SVG poster (+ PNG export)
=======================================================================

PIPELINE
  1. ART DIRECTOR (Gemini)  use case -> creative brief JSON: copy, ONE design system (palette, 2 fonts),
                            layout choice, precise hero-illustration description.
  2. LAYOUT (python)        exact zones in px, colour roles with guaranteed contrast, and PRE-FITTED text
                            (font sizes, line breaks, baselines, real font weights, badge/CTA geometry).
                            The model does not have to guess any text size or position.
  3. ILLUSTRATOR (Gemini)   writes ONE static SVG poster that follows the brief and the layout plan.
  4. LINT / AUTO-FIX        XML repair ladder, forbidden elements, SMIL stripping, path / transform syntax,
                            run-together numbers, ids and url() refs, classes, fonts @import forced to a
                            verified one, required text present (and no extra text), richness check.
  5. RENDER + QA (Chromium) renders the PNG, measures the REAL text boxes in the browser (outside canvas,
                            too close to the edge, too small, overlapping) and optionally asks Gemini to
                            review the rendered image. Issues go back to the model for a fix. The attempt
                            with the FEWEST issues wins.
     INFO BAND              briefs that describe a platform / company get a python-fitted band of step chips and
                            stat cards (real facts only) so the content is actually readable on the poster.
  6. FONT EMBEDDING         Google fonts are downloaded and inlined (base64) so the SVG looks identical in
                            <img> tags, e-mail, Figma, offline, etc. (skipped automatically if offline).
  7. FALLBACK               if the model keeps failing, a clean typographic poster is built in pure python,
                            so you always get a valid file.
"""
from __future__ import annotations

import argparse
import hashlib
import html.entities
import json
import math
import os
import re
import sys
import textwrap
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------------------
DEFAULT_MODEL = os.getenv("GEMINI_IMAGE_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"))
FALLBACK_MODELS = [os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite"), "gemini-flash-lite-latest"]
MIN_CALL_INTERVAL_S = 3.0
TIMEOUT_MS = 600_000
MAX_OUTPUT_TOKENS = 32768

ASPECTS = {"4:5": (1080, 1350), "1:1": (1080, 1080), "9:16": (1080, 1920), "16:9": (1920, 1080)}

VARIANT_DIRECTIONS = [
    "bold, high-contrast and punchy",
    "warm, premium and elegant",
    "playful, colourful and energetic",
    "clean, modern and airy",
]

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

# name -> (google css2 family spec, css fallback stack, average glyph width in em for bold text)
FONT_CATALOG: Dict[str, Tuple[str, str, float]] = {
    "Poppins": ("Poppins:wght@400;600;700;800;900", "Arial, Helvetica, sans-serif", 0.62),
    "Montserrat": ("Montserrat:wght@400;600;700;800;900", "Arial, Helvetica, sans-serif", 0.65),
    "Inter": ("Inter:wght@400;500;600;700;800", "Arial, Helvetica, sans-serif", 0.58),
    "DM Sans": ("DM+Sans:wght@400;500;700", "Arial, Helvetica, sans-serif", 0.57),
    "Nunito": ("Nunito:wght@400;600;800;900", "Arial, Helvetica, sans-serif", 0.57),
    "Work Sans": ("Work+Sans:wght@400;600;700;800", "Arial, Helvetica, sans-serif", 0.59),
    "Raleway": ("Raleway:wght@400;600;700;800;900", "Arial, Helvetica, sans-serif", 0.60),
    "Lato": ("Lato:wght@400;700;900", "Arial, Helvetica, sans-serif", 0.56),
    "Open Sans": ("Open+Sans:wght@400;600;700;800", "Arial, Helvetica, sans-serif", 0.58),
    "Bebas Neue": ("Bebas+Neue", "Impact, 'Arial Narrow', sans-serif", 0.43),
    "Anton": ("Anton", "Impact, 'Arial Narrow', sans-serif", 0.48),
    "Oswald": ("Oswald:wght@500;700", "Impact, 'Arial Narrow', sans-serif", 0.50),
    "Archivo Black": ("Archivo+Black", "Arial Black, Arial, sans-serif", 0.70),
    "Righteous": ("Righteous", "Arial, Helvetica, sans-serif", 0.60),
    "Fredoka": ("Fredoka:wght@500;600;700", "Arial Rounded MT Bold, Arial, sans-serif", 0.58),
    "Baloo 2": ("Baloo+2:wght@600;700;800", "Arial Rounded MT Bold, Arial, sans-serif", 0.58),
    "Playfair Display": ("Playfair+Display:wght@600;800;900", "Georgia, 'Times New Roman', serif", 0.60),
    "DM Serif Display": ("DM+Serif+Display", "Georgia, 'Times New Roman', serif", 0.56),
    "Abril Fatface": ("Abril+Fatface", "Georgia, 'Times New Roman', serif", 0.62),
    "Rozha One": ("Rozha+One", "Georgia, 'Times New Roman', serif", 0.60),
    "Lobster": ("Lobster", "'Brush Script MT', cursive", 0.54),
    "Pacifico": ("Pacifico", "'Brush Script MT', cursive", 0.60),
}

# Non-Latin scripts: (first code point, last code point, Noto family, average glyph width in em)
SCRIPT_RANGES: List[Tuple[int, int, str, float]] = [
    (0x0900, 0x097F, "Noto Sans Devanagari", 0.78),
    (0x0980, 0x09FF, "Noto Sans Bengali", 0.78),
    (0x0A00, 0x0A7F, "Noto Sans Gurmukhi", 0.78),
    (0x0A80, 0x0AFF, "Noto Sans Gujarati", 0.78),
    (0x0B80, 0x0BFF, "Noto Sans Tamil", 0.85),
    (0x0C00, 0x0C7F, "Noto Sans Telugu", 0.85),
    (0x0C80, 0x0CFF, "Noto Sans Kannada", 0.85),
    (0x0D00, 0x0D7F, "Noto Sans Malayalam", 0.90),
    (0x0600, 0x06FF, "Noto Sans Arabic", 0.62),
    (0x0590, 0x05FF, "Noto Sans Hebrew", 0.60),
    (0x0E00, 0x0E7F, "Noto Sans Thai", 0.62),
    (0x3040, 0x30FF, "Noto Sans JP", 1.00),
    (0xAC00, 0xD7AF, "Noto Sans KR", 1.00),
    (0x4E00, 0x9FFF, "Noto Sans SC", 1.00),
]
CJK_FAMILIES = {"Noto Sans JP", "Noto Sans KR", "Noto Sans SC"}

# Palette defaults
DEFAULT_PALETTE = {
    "bg": "#1A0C06", "bg_alt": "#3A1A0C", "primary": "#FF6B1A", "secondary": "#FFC93C",
    "accent": "#E63946", "ink": "#1A0C06", "paper": "#FFF8E7",
}


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


def slugify(text: str) -> str:
    words = re.sub(r"[^a-zA-Z0-9\s]", "", text).lower().split()[:6]
    return "-".join(words) or "poster"


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


def clean_text(text: Any, max_words: int = 0, max_chars: int = 0) -> str:
    t = re.sub(r"[*_#`~<>]", "", str(text or ""))
    t = re.sub(r"\s+", " ", t).strip()
    if max_words:
        t = " ".join(t.split()[:max_words])
    if max_chars and len(t) > max_chars:
        cut = t[:max_chars]
        if " " in cut and t[max_chars] != " ":
            cut = cut.rsplit(" ", 1)[0]
        t = cut.rstrip(" ,;:-")
    return t


def esc(t: str) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------------------
# Gemini client wrapper
# --------------------------------------------------------------------------------------
class Gemini:
    def __init__(self, model: Optional[str] = None):
        from dotenv import load_dotenv
        from google import genai
        from google.genai import types

        load_dotenv()
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            sys.exit("GEMINI_API_KEY not found. Add it to a .env file next to this script.")
        self.types = types
        self.client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=TIMEOUT_MS))
        self.model = model or DEFAULT_MODEL
        self._last_call = 0.0
        tb = os.getenv("GEMINI_THINKING_BUDGET", "").strip()
        self.thinking_budget: Optional[int] = int(tb) if tb.lstrip("-").isdigit() else None

    def image_part(self, data: bytes, mime: str = "image/png"):
        return self.types.Part.from_bytes(data=data, mime_type=mime)

    def generate(self, system: str, contents, json_mode: bool = False, temperature: float = 0.9,
                 retries: int = 4, max_tokens: int = MAX_OUTPUT_TOKENS) -> str:
        kw: Dict[str, Any] = dict(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json" if json_mode else None,
            max_output_tokens=max_tokens,
        )
        if self.thinking_budget is not None and hasattr(self.types, "ThinkingConfig"):
            kw["thinking_config"] = self.types.ThinkingConfig(thinking_budget=self.thinking_budget)
        cfg = self.types.GenerateContentConfig(**kw)

        last: Any = None
        for curr in [self.model] + [m for m in FALLBACK_MODELS if m != self.model]:
            rate_hits = 0
            for attempt in range(retries):
                gap = MIN_CALL_INTERVAL_S - (time.time() - self._last_call)
                if gap > 0:
                    time.sleep(gap)
                self._last_call = time.time()
                try:
                    r = self.client.models.generate_content(model=curr, contents=contents, config=cfg)
                    if r.text:
                        self.model = curr
                        return r.text
                    last = RuntimeError("empty response")
                except Exception as e:
                    last = e
                err = str(last)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    rate_hits += 1
                    if rate_hits >= 2:
                        log(f"  Gemini model {curr} quota exhausted - trying the next model if available")
                        break
                    log(f"  Gemini model {curr} rate limited - waiting 20s")
                    time.sleep(20)
                    continue
                if any(k in err for k in ("404", "NOT_FOUND", "INVALID_ARGUMENT", "PERMISSION_DENIED")):
                    log(f"  Gemini model {curr} not usable ({err[:140]}) - trying the next model if available")
                    break
                wait = 3 * (2 ** attempt)
                log(f"  Gemini call failed ({type(last).__name__}: {err[:160]}) - retry in {wait}s")
                time.sleep(wait)
        raise RuntimeError(f"Gemini failed across all models: {last}")


# --------------------------------------------------------------------------------------
# Colour maths (guaranteed readable colour roles)
# --------------------------------------------------------------------------------------
def hex_ok(c: Any) -> bool:
    return isinstance(c, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", c.strip()) is not None


def _rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def lum(h: str) -> float:
    r, g, b = _rgb(h)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def mix(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return "#%02X%02X%02X" % tuple(round(ra[i] * (1 - t) + rb[i] * t) for i in range(3))


def best_text_on(fill_c: str) -> str:
    return "#FFFFFF" if contrast("#FFFFFF", fill_c) >= contrast("#111111", fill_c) else "#111111"


def color_roles(p: Dict[str, str]) -> Dict[str, Any]:
    bg, bg2 = p["bg"], p["bg_alt"]
    dark = (lum(bg) + lum(bg2)) / 2 < 0.30
    base = p["paper"] if dark else p["ink"]
    if min(contrast(base, bg), contrast(base, bg2)) < 7:
        base = "#FFFFFF" if dark else "#111111"
    muted = mix(base, bg, 0.28)
    if min(contrast(muted, bg), contrast(muted, bg2)) < 4.5:
        muted = base
    emph = next((c for c in (p["accent"], p["primary"], p["secondary"])
                 if min(contrast(c, bg), contrast(c, bg2)) >= 3.0), base)
    cta_fill = p["accent"] if contrast(p["accent"], bg) >= 1.6 else p["primary"]
    badge_fill = p["primary"] if p["primary"].lower() != cta_fill.lower() else p["secondary"]
    support = mix(base, bg, 0.12)
    if min(contrast(support, bg), contrast(support, bg2)) < 7:
        support = base
    chip_fill = mix(bg2, base, 0.10)
    if contrast(base, chip_fill) < 7:
        chip_fill = bg2
    return {
        "background_gradient_from": bg, "background_gradient_to": bg2, "dark_background": dark,
        "text_main": base, "text_support": support, "text_muted": muted, "emphasis": emph,
        "chip_fill": chip_fill, "chip_stroke": emph, "chip_text": base,
        "cta_fill": cta_fill, "cta_text": best_text_on(cta_fill),
        "badge_fill": badge_fill, "badge_text": best_text_on(badge_fill),
    }


# --------------------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------------------
def detect_script(text: str) -> Optional[Tuple[str, float]]:
    counts: Dict[str, int] = {}
    for ch in text:
        o = ord(ch)
        for lo, hi, fam, _f in SCRIPT_RANGES:
            if lo <= o <= hi:
                counts[fam] = counts.get(fam, 0) + 1
                break
    if not counts:
        return None
    fam = "Noto Sans JP" if "Noto Sans JP" in counts else max(counts, key=lambda k: counts[k])
    return fam, next(f for _a, _b, n, f in SCRIPT_RANGES if n == fam)


def font_stack(name: str, script: Optional[str] = None) -> str:
    spec = FONT_CATALOG.get(name, FONT_CATALOG["Poppins"])
    base = f"'{name}', {spec[1]}"
    return f"'{script}', {base}" if script else base


def font_import(names: List[str], script: Optional[str] = None) -> str:
    specs = ["family=" + FONT_CATALOG.get(n, FONT_CATALOG["Poppins"])[0] for n in dict.fromkeys(names)]
    if script:
        specs.append("family=" + script.replace(" ", "+") + ":wght@400;600;700;800")
    return "@import url('https://fonts.googleapis.com/css2?" + "&amp;".join(specs) + "&amp;display=swap');"


def font_weights(name: str) -> List[int]:
    spec = FONT_CATALOG.get(name)
    if not spec:
        return [400, 500, 600, 700, 800]
    m = re.search(r"wght@([\d;]+)", spec[0])
    return [int(x) for x in m.group(1).split(";")] if m else [400]


def snap_weight(name: str, want: int) -> int:
    return min(font_weights(name), key=lambda w: (abs(w - want), -w))


_IMPORT_RE = re.compile(r"@import\s+url\([^)]*\)[^;]*;", re.I)


def inline_fonts(svg: str, script: Optional[str]) -> str:
    import base64
    import urllib.request

    if script in CJK_FAMILIES:
        return svg
    m = re.search(r"@import\s+url\(\s*['\"]?([^'\")]+)", svg)
    if not m:
        return svg
    url = m.group(1).replace("&amp;", "&")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

    def get(u: str) -> bytes:
        with urllib.request.urlopen(urllib.request.Request(u, headers=headers), timeout=25) as r:
            return r.read()

    wanted = {"latin"}
    if script:
        wanted.add(script.split()[-1].lower())
    try:
        css = get(url).decode("utf-8")
        blocks = re.findall(r"/\*\s*([^*]+?)\s*\*/\s*(@font-face\s*\{[^}]*\})", css)
        keep = [b for name, b in blocks if name.strip() in wanted]
        if not keep or len(keep) > 16 or (script and not any(n.strip() == script.split()[-1].lower() for n, _ in blocks)):
            return svg

        def to_data(mm: "re.Match[str]") -> str:
            return "url(data:font/woff2;base64," + base64.b64encode(get(mm.group(1))).decode("ascii") + ")"

        rules = "\n".join(re.sub(r"url\((https://[^)]+)\)", to_data, b) for b in keep)
    except Exception as e:
        log(f"  font embedding skipped ({type(e).__name__}: {str(e)[:100]}) - keeping Google Fonts @import")
        return svg
    out = _IMPORT_RE.sub("", svg)
    s = re.search(r"<style\b[^>]*>", out)
    if not s:
        return svg
    log(f"  fonts embedded ({len(rules) // 1024} KB)")
    return out[:s.end()] + "\n" + rules + out[s.end():]


# --------------------------------------------------------------------------------------
# Layouts
# --------------------------------------------------------------------------------------
def _L(eyebrow, headline, support, hero, cta, footer, badge, align):
    return {"eyebrow": eyebrow, "headline": headline, "support": support, "hero": hero,
            "cta": cta, "footer": footer, "badge": badge, "align": align}


_WIDE_STACK = _L((0.06, 0.08, 0.50, 0.14), (0.06, 0.15, 0.52, 0.50), (0.06, 0.515, 0.50, 0.66),
                 (0.50, 0.08, 0.97, 0.92), (0.06, 0.70, 0.34, 0.825), (0.06, 0.90, 0.46, 0.95),
                 (0.90, 0.22, 0.125), "left")

LAYOUTS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "stack": {
        "tall": _L((0.10, 0.062, 0.90, 0.098), (0.07, 0.104, 0.93, 0.272), (0.10, 0.282, 0.90, 0.372),
                   (0.05, 0.388, 0.95, 0.768), (0.19, 0.800, 0.81, 0.880), (0.07, 0.915, 0.93, 0.955),
                   (0.80, 0.45, 0.125), "center"),
        "square": _L((0.10, 0.056, 0.90, 0.094), (0.07, 0.100, 0.93, 0.292), (0.10, 0.302, 0.90, 0.392),
                     (0.06, 0.404, 0.94, 0.790), (0.20, 0.822, 0.80, 0.908), (0.07, 0.935, 0.93, 0.975),
                     (0.81, 0.52, 0.125), "center"),
        "wide": _WIDE_STACK,
    },
    "hero-top": {
        "tall": _L((0.10, 0.495, 0.90, 0.530), (0.07, 0.540, 0.93, 0.700), (0.10, 0.708, 0.90, 0.792),
                   (0.04, 0.045, 0.96, 0.465), (0.19, 0.806, 0.81, 0.884), (0.07, 0.915, 0.93, 0.955),
                   (0.81, 0.13, 0.125), "center"),
        "square": _L((0.10, 0.520, 0.90, 0.560), (0.07, 0.568, 0.93, 0.725), (0.10, 0.732, 0.90, 0.815),
                     (0.05, 0.040, 0.95, 0.500), (0.20, 0.826, 0.80, 0.910), (0.07, 0.935, 0.93, 0.975),
                     (0.81, 0.15, 0.125), "center"),
        "wide": _L((0.55, 0.08, 0.95, 0.14), (0.55, 0.15, 0.95, 0.50), (0.55, 0.515, 0.95, 0.66),
                   (0.04, 0.08, 0.50, 0.92), (0.55, 0.70, 0.81, 0.825), (0.55, 0.90, 0.95, 0.95),
                   (0.44, 0.20, 0.125), "left"),
    },
    "left": {
        "tall": _L((0.07, 0.065, 0.66, 0.100), (0.07, 0.110, 0.66, 0.330), (0.07, 0.338, 0.93, 0.418),
                   (0.04, 0.435, 0.96, 0.790), (0.07, 0.825, 0.60, 0.905), (0.07, 0.930, 0.93, 0.965),
                   (0.82, 0.16, 0.125), "left"),
        "square": _L((0.07, 0.060, 0.66, 0.098), (0.07, 0.106, 0.66, 0.330), (0.07, 0.338, 0.93, 0.418),
                     (0.05, 0.435, 0.95, 0.800), (0.07, 0.832, 0.60, 0.915), (0.07, 0.938, 0.93, 0.975),
                     (0.82, 0.18, 0.125), "left"),
        "wide": _WIDE_STACK,
    },
}


def aspect_class(W: int, H: int) -> str:
    r = H / W
    if r >= 1.25:
        return "tall"
    if r > 0.85:
        return "square"
    return "wide"


# --------------------------------------------------------------------------------------
# 1. ART DIRECTOR
# --------------------------------------------------------------------------------------
DIRECTOR_SYSTEM = """You are a senior advertising art director and copywriter. You turn a short brief (a business name, a product,
an offer, or a full description) into the creative brief for ONE social-media poster: a single, static, vector-illustrated image.
Another designer will draw it as SVG, so every decision must be concrete and drawable with shapes and gradients.

PRINCIPLES
1. ONE BIG IDEA: one hero object or scene that is instantly recognisable, desirable and drawable in rich vector style (layered shapes,
   gradients, highlights, soft shadows). No photorealism, no real people, no real brands or logos, no tiny fiddly details.
2. COPY is short, punchy and specific. Headline max 6 words (a concrete promise, craving or hook: never a vague slogan such as "build the future").
   Supporting line max 12 words, plain and specific about WHAT the offer actually does. When a company or product is described,
   the eyebrow carries its brand name or category (e.g. "IncuBrix CreatorOps").
   CTA max 3 words, verb first. Use placeholders "yourbrand.com" and "@yourbrand" unless real ones are given.
   If the brief already contains copy, keep its wording. Never make medical or legal claims.
   Offer: only if the brief mentions a price/discount/offer, or if it clearly helps conversion; keep any invented price realistic, use the currency
   implied by the brief or language (default "$"), and keep it short. Otherwise set "offer" to null.
3. DESIGN SYSTEM: max 5 brand colours (hex) plus neutrals, chosen for emotion, appetite and contrast with the product.
   Exactly 2 fonts taken from the catalog: a display font (headline, price, CTA) and a body font (everything else).
   headline_caps = true for punchy uppercase display fonts, false for elegant or script fonts.
4. LAYOUT: choose ONE of "stack" (headline on top, hero in the middle, CTA at the bottom), "hero-top" (hero at the top, headline below it),
   "left" (left-aligned text on top, hero below or to the right). Pick what suits the hero's shape.
5. HERO must be described precisely enough to draw without guessing: 6-12 components (shape, colour from the palette, relative size, position inside
   the hero zone as fractions, rotation), the light direction (top-left), surface details (highlights, texture, shadows, steam, drips, gloss) and 4-8 small
   props (garnish, ingredients, sparkles, splashes) with where they float.
6. BACKGROUND: gradient direction and colours, a soft glow behind the hero, 2-4 big faint decorative shapes, optional very subtle grain.
7. INFORMATION-RICH BRIEFS (a company profile, a platform, a multi-feature product): the poster must communicate the REAL offering at a glance.
   - "steps": 3-5 items, 1-2 words each (max 10 characters per item), in order, taken from the stages / features the brief names. Otherwise [].
   - "stats": up to 3 REAL numbers stated in the brief (team size, locations, years, ratings...), value max 6 characters, label max 14 characters
     in capitals. NEVER invent numbers. Otherwise [].
   - The hero is then a simple, BOLD visual metaphor of the offering (hub-and-orbit, loop, pipeline) drawn large with icon-like nodes that match the
     steps, and no text inside it. The chips and stat cards carry the words, so the hero must stay uncluttered.
8. Write all poster text in the requested language. For non-Latin scripts keep the catalog font names anyway (the layout engine adds the matching Noto font).

Return ONLY valid JSON, exactly this shape:
{
 "title": "...",
 "brand": {"name": "...", "tagline": "...", "website": "yourbrand.com", "handle": "@yourbrand"},
 "copy": {"eyebrow": "max 4 words or empty string", "headline": "max 6 words", "headline_emphasis": "one word of the headline to accent",
          "support": "max 12 words", "cta": "max 3 words",
          "steps": ["Discover", "Create", "Publish"], "stats": [{"value": "20", "label": "TEAM MEMBERS"}],
          "offer": {"kicker": "ONLY", "main": "$8.99", "sub": "DOSA + 3 CHUTNEYS"}},
 "concept": "2-3 sentences: the big idea and the mood",
 "design_system": {
   "palette": {"bg": "#hex", "bg_alt": "#hex", "primary": "#hex", "secondary": "#hex", "accent": "#hex", "ink": "#hex", "paper": "#hex"},
   "fonts": {"display": "<catalog name>", "body": "<catalog name>"},
   "headline_caps": true, "corner_radius": 28,
   "style": "illustration style in one sentence", "lighting": "light direction and mood"},
 "composition": {"layout": "stack|hero-top|left",
   "hero": "precise description of the hero illustration",
   "props": ["small floating props and where"],
   "background": "background description", "decor": ["big faint decorative shapes"]}
}"""

DIRECTOR_USER = """USE CASE / BRIEF:
<<USE_CASE>>

REQUIREMENTS
- Poster format: <<ASPECT>> (<<W>> x <<H>> px).
- Language of all poster text: <<LANG>>.
- Style direction: <<DIRECTION>>
- Font catalog (use exactly these names): <<FONTS>>
Plan silently, then output the JSON only."""


def make_brief(gem: Gemini, use_case: str, aspect: str, W: int, H: int, language: str, direction: str) -> dict:
    user = fill(DIRECTOR_USER, USE_CASE=use_case, ASPECT=aspect, W=W, H=H, LANG=language,
                DIRECTION=direction or "choose what fits the product best",
                FONTS=", ".join(FONT_CATALOG.keys()))
    err = ""
    for _ in range(3):
        txt = gem.generate(DIRECTOR_SYSTEM, user + err, json_mode=True, temperature=0.9)
        try:
            return normalize_brief(extract_json(txt))
        except Exception as e:
            err = f"\n\nYour previous reply was invalid ({e}). Return the complete, valid JSON only."
            log(f"  brief invalid: {e} - retrying")
    raise RuntimeError("Could not obtain a valid creative brief from Gemini.")


def normalize_brief(b: dict) -> dict:
    if not isinstance(b, dict):
        raise ValueError("brief is not an object")
    brand = b.get("brand") if isinstance(b.get("brand"), dict) else {}
    b["brand"] = brand
    brand["name"] = clean_text(brand.get("name"), max_chars=32) or "IncuBrix"
    brand["tagline"] = clean_text(brand.get("tagline"), max_chars=60)
    brand["website"] = clean_text(brand.get("website"), max_chars=40).replace(" ", "") or "incubrix.com"
    h = clean_text(brand.get("handle"), max_chars=30).replace(" ", "") or "@incubrix"
    brand["handle"] = h if h.startswith("@") else "@" + h

    cp = b.get("copy") if isinstance(b.get("copy"), dict) else {}
    b["copy"] = cp
    cp["eyebrow"] = clean_text(cp.get("eyebrow"), max_words=4, max_chars=28)
    cp["headline"] = clean_text(cp.get("headline"), max_words=7, max_chars=48) or brand["name"]
    emph = clean_text(cp.get("headline_emphasis"), max_words=2)
    cp["headline_emphasis"] = emph if emph and emph.lower() in cp["headline"].lower() else ""
    cp["support"] = clean_text(cp.get("support"), max_words=14, max_chars=100)
    cp["cta"] = clean_text(cp.get("cta"), max_words=3, max_chars=22) or "Get Started"
    steps = [clean_text(x, max_words=2, max_chars=10) for x in (cp.get("steps") or [])[:5] if isinstance(x, str)]
    steps = [x for x in steps if x]
    cp["steps"] = steps if len(steps) >= 3 else []
    stats = []
    for st in (cp.get("stats") or [])[:3]:
        if isinstance(st, dict) and clean_text(st.get("value")) and clean_text(st.get("label")):
            stats.append({"value": clean_text(st["value"], max_chars=6), "label": clean_text(st["label"], max_chars=14)})
    cp["stats"] = stats
    off = cp.get("offer")
    if isinstance(off, dict) and clean_text(off.get("main")):
        cp["offer"] = {"kicker": clean_text(off.get("kicker"), max_chars=10),
                       "main": clean_text(off.get("main"), max_chars=12),
                       "sub": clean_text(off.get("sub"), max_chars=22)}
    else:
        cp["offer"] = None

    b["concept"] = clean_text(b.get("concept"), max_chars=500)
    b["title"] = clean_text(b.get("title"), max_chars=80) or brand["name"]

    ds = b.get("design_system") if isinstance(b.get("design_system"), dict) else {}
    b["design_system"] = ds
    pal = ds.get("palette") if isinstance(ds.get("palette"), dict) else {}
    ds["palette"] = {k: (pal[k].strip().upper() if hex_ok(pal.get(k)) else v) for k, v in DEFAULT_PALETTE.items()}
    fonts = ds.get("fonts") if isinstance(ds.get("fonts"), dict) else {}
    ds["fonts"] = {"display": fonts.get("display") if fonts.get("display") in FONT_CATALOG else "Poppins",
                   "body": fonts.get("body") if fonts.get("body") in FONT_CATALOG else "Inter"}
    ds["headline_caps"] = bool(ds.get("headline_caps", True))
    try:
        ds["corner_radius"] = max(8, min(60, int(ds.get("corner_radius", 28))))
    except (TypeError, ValueError):
        ds["corner_radius"] = 28
    ds["style"] = clean_text(ds.get("style"), max_chars=200) or "rich layered vector illustration with soft gradients"
    ds["lighting"] = clean_text(ds.get("lighting"), max_chars=160) or "soft light from the top-left, warm glow"

    comp = b.get("composition") if isinstance(b.get("composition"), dict) else {}
    b["composition"] = comp
    if comp.get("layout") not in LAYOUTS:
        comp["layout"] = "stack"
    comp["hero"] = clean_text(comp.get("hero"), max_chars=1400) or "the main product, large and centred, with soft highlights and a contact shadow"
    comp["props"] = [clean_text(x, max_chars=140) for x in (comp.get("props") or [])[:8] if clean_text(x)]
    comp["background"] = clean_text(comp.get("background"), max_chars=300) or "dark gradient with a warm glow behind the hero"
    comp["decor"] = [clean_text(x, max_chars=140) for x in (comp.get("decor") or [])[:6] if clean_text(x)]
    return b


# --------------------------------------------------------------------------------------
# 2. LAYOUT PLAN
# --------------------------------------------------------------------------------------
def text_w(text: str, fs: float, factor: float, caps: bool = False, ls_em: float = 0.0) -> float:
    return len(text) * fs * (factor * (1.12 if caps else 1.0) + ls_em)


def wrap_balanced(text: str, per_line: int) -> List[str]:
    kw = dict(break_long_words=False, break_on_hyphens=False)
    lines = textwrap.wrap(text, max(3, per_line), **kw) or [text]
    n = len(lines)
    for p in range(per_line - 1, 3, -1):
        alt = textwrap.wrap(text, p, **kw) or [text]
        if len(alt) != n:
            break
        lines = alt
    return lines


def fit_text(text: str, box_w: float, box_h: float, factor: float, caps: bool, max_lines: int,
             max_fs: float, min_fs: float, lh: float = 1.12, ls_em: float = 0.0) -> Tuple[int, List[str]]:
    text = " ".join(str(text).split())
    fs = int(max_fs)
    floor = max(16, int(min_fs * 0.7))
    while fs >= floor:
        cw = fs * (factor * (1.12 if caps else 1.0) + ls_em)
        lines = wrap_balanced(text, int(box_w / cw))
        w_ok = max(text_w(ln, fs, factor, caps, ls_em) for ln in lines) <= box_w
        h_ok = fs * (0.95 + (len(lines) - 1) * lh) <= box_h
        if len(lines) <= max_lines and w_ok and h_ok:
            return fs, lines
        fs -= 2
    cw = floor * (factor * (1.12 if caps else 1.0) + ls_em)
    return floor, wrap_balanced(text, int(box_w / cw))


def place(lines: List[str], fs: float, zone: Tuple[float, float, float, float], align: str, lh: float) -> List[dict]:
    x0, y0, x1, y1 = zone
    n = len(lines)
    cap = 0.72 * fs
    block = cap + (n - 1) * fs * lh
    top = y0 + ((y1 - y0) - block) / 2
    x = (x0 + x1) / 2 if align == "center" else x0
    anchor = "middle" if align == "center" else "start"
    return [{"text": t, "x": round(x, 1), "y": round(top + cap + i * fs * lh, 1),
             "font_size": int(fs), "anchor": anchor} for i, t in enumerate(lines)]


def badge_plan(offer: dict, cx: float, cy: float, r: float, f_disp: float, f_body: float,
               W: int, margin: float, min_px: float, avoid: Optional[List[Tuple[float, float, float, float]]] = None) -> dict:
    ri = 0.82 * r

    def width_at(dy: float, fs: float) -> float:
        d = abs(dy) + 0.45 * fs
        return 2 * math.sqrt(max(ri * ri - d * d, (0.25 * ri) ** 2)) * 0.94

    has_k = bool(" ".join(str(offer.get("kicker", "")).split()))
    spec = [("kicker", offer.get("kicker", ""), -0.50, 0.19, 0.12, True, f_body, 0.10, "body", 800),
            ("main", offer.get("main", ""), 0.10 if has_k else 0.0, 0.60, 0.25, False, f_disp, 0.0, "display", 900)]
    lines = []
    for role, text, dy, mx, mn, caps, factor, ls, fam, weight in spec:
        text = " ".join(str(text).split())
        if not text:
            continue
        if caps:
            text = text.upper()
        fs = mx * r
        while fs > mn * r and text_w(text, fs, factor, caps, ls) > width_at(dy * r, fs):
            fs -= 1
        fs = int(fs)
        lines.append({"role": role, "text": text, "x": round(cx, 1), "y": round(cy + dy * r + 0.36 * fs, 1),
                      "font_size": fs, "anchor": "middle", "font": fam, "weight": weight,
                      "letter_spacing": round(ls * fs, 1)})
    pill = None
    sub = " ".join(str(offer.get("sub", "")).split()).upper()
    if sub:
        pcy = cy + 0.96 * r
        fs = min(max(int(round(0.17 * r)), int(min_px)), int(0.2 * r))
        h = fs * 1.9
        lo, hi = margin, W - margin
        for (zx0, zy0, zx1, zy1) in (avoid or []):
            if zy0 < pcy + h / 2 + 8 and zy1 > pcy - h / 2 - 8:
                if (zx0 + zx1) / 2 >= cx:
                    hi = min(hi, zx0 - 14)
                else:
                    lo = max(lo, zx1 + 14)
        if hi - lo < 120:
            lo, hi = margin, W - margin
        max_w = max(60.0, min(3.0 * r, hi - lo))
        while fs > 18 and text_w(sub, fs, f_body, True, 0.06) + 1.4 * fs > max_w:
            fs -= 1
        h = fs * 1.9
        w = min(max_w, text_w(sub, fs, f_body, True, 0.06) + 1.4 * fs)
        pcx = min(max(cx, lo + w / 2), hi - w / 2)
        pill = {"x": round(pcx - w / 2, 1), "y": round(pcy - h / 2, 1), "w": round(w, 1), "h": round(h, 1), "rx": round(h / 2, 1),
                "text": {"text": sub, "x": round(pcx, 1), "y": round(pcy + 0.36 * fs, 1), "font_size": fs,
                         "anchor": "middle", "font": "body", "weight": 800, "letter_spacing": round(0.06 * fs, 1)}}
    return {"cx": round(cx, 1), "cy": round(cy, 1), "r": round(r, 1), "ring_r": round(ri, 1), "lines": lines, "pill": pill}


def build_band(cp: dict, hero: Tuple[float, float, float, float], W: int, H: int, m: float, cls: str,
               f_disp: float, f_body: float, caps: bool, up, sw_d, sw_b) -> Tuple[Optional[dict], Tuple[float, float, float, float]]:
    steps, stats = list(cp.get("steps") or []), list(cp.get("stats") or [])
    if not steps and not stats:
        return None, hero
    hx0, hy0, hx1, hy1 = hero
    st_k, sp_k = {"tall": (0.090, 0.056), "square": (0.070, 0.048), "wide": (0.090, 0.056)}[cls]
    stats_h, steps_h, gap = st_k * m, sp_k * m, 0.014 * m
    use_stats, use_steps = bool(stats), bool(steps)
    if use_stats and use_steps:
        total = stats_h + steps_h + 2 * gap
        if (hy1 - hy0 - total) < 0.5 * (hy1 - hy0):
            use_stats = False
    bx0, bx1 = max(hx0, 0.07 * W), min(hx1, 0.93 * W)
    bw = bx1 - bx0
    band: Dict[str, Any] = {"steps": None, "stats": None}
    y = hy1
    if use_steps:
        y -= steps_h
        n = len(steps)
        cg = 0.010 * bw
        cw = (bw - (n - 1) * cg) / n
        labels = [up(x) for x in steps]
        fs = min(fit_text(l, cw - 0.3 * steps_h, 0.7 * steps_h, f_body, caps, 1, 0.032 * m, 0.020 * m, ls_em=0.04)[0]
                 for l in labels)
        chips = []
        for i, l in enumerate(labels):
            x = bx0 + i * (cw + cg)
            chips.append({"x": round(x, 1), "y": round(y, 1), "w": round(cw, 1), "h": round(steps_h, 1),
                          "rx": round(steps_h / 2, 1),
                          "text": {"text": l, "x": round(x + cw / 2, 1), "y": round(y + steps_h / 2 + 0.36 * fs, 1),
                                   "font_size": int(fs), "anchor": "middle", "weight": sw_b(700),
                                   "letter_spacing": round(0.04 * fs, 1)}})
        band["steps"] = {"chips": chips}
    if use_stats:
        if use_steps:
            y -= gap
        y -= stats_h
        k = len(stats)
        sg = 0.02 * bw
        cw = (bw - (k - 1) * sg) / k
        vfs = min(fit_text(st["value"], cw - 0.3 * stats_h, 0.6 * stats_h, f_disp, False, 1, 0.52 * stats_h, 0.30 * stats_h)[0]
                  for st in stats)
        lfs = min(fit_text(up(st["label"]), cw - 0.3 * stats_h, 0.36 * stats_h, f_body, caps, 1, 0.028 * m, 0.020 * m, ls_em=0.06)[0]
                  for st in stats)
        content = 0.72 * vfs + 0.12 * stats_h + 0.72 * lfs
        top = y + (stats_h - content) / 2
        vbase = top + 0.72 * vfs
        lbase = vbase + 0.12 * stats_h + 0.72 * lfs
        cards = []
        for i, st in enumerate(stats):
            x = bx0 + i * (cw + sg)
            cards.append({"x": round(x, 1), "y": round(y, 1), "w": round(cw, 1), "h": round(stats_h, 1),
                          "rx": round(0.25 * stats_h, 1),
                          "value": {"text": st["value"], "x": round(x + cw / 2, 1), "y": round(vbase, 1), "font_size": int(vfs),
                                    "anchor": "middle", "weight": sw_d(900)},
                          "label": {"text": up(st["label"]), "x": round(x + cw / 2, 1), "y": round(lbase, 1),
                                    "font_size": int(lfs), "anchor": "middle", "weight": sw_b(700),
                                    "letter_spacing": round(0.06 * lfs, 1)}})
        band["stats"] = {"cards": cards}
    band["top"] = round(y, 1)
    return band, (hx0, hy0, hx1, y - gap)


def build_plan(brief: dict, W: int, H: int) -> dict:
    cls = aspect_class(W, H)
    cp, ds, comp = brief["copy"], brief["design_system"], brief["composition"]
    spec = LAYOUTS[comp["layout"]][cls]
    m = min(W, H)
    align = spec["align"]

    offer = cp["offer"] or {}
    sample = " ".join([cp["eyebrow"], cp["headline"], cp["support"], cp["cta"], brief["brand"]["name"],
                       offer.get("kicker", ""), offer.get("main", ""), offer.get("sub", "")]
                      + list(cp.get("steps") or []) + [x["label"] for x in cp.get("stats") or []])
    script = detect_script(sample)
    s_name, s_factor = script if script else (None, None)
    disp_name, body_name = ds["fonts"]["display"], ds["fonts"]["body"]
    f_disp = s_factor or FONT_CATALOG[disp_name][2]
    f_body = s_factor or FONT_CATALOG[body_name][2]
    f_body_latin = FONT_CATALOG[body_name][2]
    up = (lambda s: s) if script else (lambda s: s.upper())

    def sw_d(w: int) -> int:
        return snap_weight(s_name or disp_name, w)

    def sw_b(w: int) -> int:
        return snap_weight(s_name or body_name, w)

    zones = {k: (spec[k][0] * W, spec[k][1] * H, spec[k][2] * W, spec[k][3] * H)
             for k in ("eyebrow", "headline", "support", "hero", "cta", "footer")}
    band, zones["hero"] = build_band(cp, zones["hero"], W, H, m, cls, f_disp, f_body, not script, up, sw_d, sw_b)
    text: Dict[str, List[dict]] = {}

    if cp["eyebrow"]:
        z = zones["eyebrow"]
        fs, lines = fit_text(up(cp["eyebrow"]), z[2] - z[0], z[3] - z[1], f_body, not script, 1, 0.034 * m, 0.026 * m, ls_em=0.14)
        text["eyebrow"] = place(lines, fs, z, align, 1.2)
        for ln in text["eyebrow"]:
            ln["letter_spacing"] = round(0.14 * fs, 1)
            ln["weight"] = sw_b(700)

    z = zones["headline"]
    caps = bool(ds["headline_caps"]) and not script
    t = cp["headline"].upper() if caps else cp["headline"]
    fs, lines = fit_text(t, z[2] - z[0], z[3] - z[1], f_disp, caps, 4 if cls == "wide" else 3, 0.125 * m, 0.05 * m, lh=1.06)
    text["headline"] = place(lines, fs, z, align, 1.06)
    for ln in text["headline"]:
        ln["weight"] = sw_d(800)

    if cp["support"]:
        z = zones["support"]
        fs, lines = fit_text(cp["support"], z[2] - z[0], z[3] - z[1], f_body, False, 3,
                             0.042 * m, 0.030 * m, lh=1.25)
        text["support"] = place(lines, fs, z, align, 1.25)
        for ln in text["support"]:
            ln["weight"] = sw_b(500)

    cz = zones["cta"]
    cw, ch = cz[2] - cz[0], cz[3] - cz[1]
    arrow_r = 0.27 * ch
    arrow_cx = cz[2] - 0.5 * ch
    arrow_cy = (cz[1] + cz[3]) / 2
    tx0, tx1 = cz[0] + 0.06 * cw, arrow_cx - arrow_r - 0.30 * ch
    fs, lines = fit_text(up(cp["cta"]), tx1 - tx0, 0.6 * ch, f_disp, not script, 1, min(0.46 * ch, 0.05 * m), 0.026 * m, ls_em=0.04)
    cta_text = [{"text": lines[0], "x": round((tx0 + tx1) / 2, 1), "y": round(arrow_cy + 0.36 * fs, 1),
                 "font_size": int(fs), "anchor": "middle", "weight": sw_d(800), "letter_spacing": round(0.04 * fs, 1)}]
    cta = {"x": round(cz[0], 1), "y": round(cz[1], 1), "w": round(cw, 1), "h": round(ch, 1), "rx": round(ch / 2, 1),
           "arrow": {"cx": round(arrow_cx, 1), "cy": round(arrow_cy, 1), "r": round(arrow_r, 1)}}

    z = zones["footer"]
    foot = f"{brief['brand']['website']}\u00a0\u00a0\u2022\u00a0\u00a0{brief['brand']['handle']}"
    fs, lines = fit_text(foot, z[2] - z[0], z[3] - z[1], f_body_latin, False, 1, 0.030 * m, 0.025 * m)
    text["footer"] = place(lines, fs, z, align, 1.2)
    for ln in text["footer"]:
        ln["weight"] = snap_weight(body_name, 600)

    badge = None
    if cp["offer"]:
        bx, by, br = spec["badge"]
        r_px = br * m
        cy_px = by * H
        if band:
            cy_px = min(cy_px, band["top"] - 1.12 * r_px - 12)
        avoid = [zones[k] for k in ("eyebrow", "headline", "support", "cta", "footer")]
        badge = badge_plan(cp["offer"], bx * W, cy_px, r_px, f_disp, f_body_latin if not script else f_body,
                           W, round(0.067 * m), round(0.022 * m), avoid)
        for ln in badge["lines"]:
            ln["weight"] = (sw_d if ln["font"] == "display" else sw_b)(ln["weight"])
        if badge["pill"]:
            badge["pill"]["text"]["weight"] = sw_b(badge["pill"]["text"]["weight"])

    roles = color_roles(ds["palette"])
    roles["pill_fill"], roles["pill_text"] = roles["badge_text"], roles["badge_fill"]
    fonts = {"display": font_stack(disp_name, s_name), "body": font_stack(body_name, s_name),
             "import": font_import([disp_name, body_name], s_name)}
    required = [ln["text"] for k in ("eyebrow", "headline", "support", "footer") for ln in text.get(k, [])]
    required += [ln["text"] for ln in cta_text]
    if badge:
        required += [ln["text"] for ln in badge["lines"]]
        if badge["pill"]:
            required.append(badge["pill"]["text"]["text"])
    if band:
        if band["steps"]:
            required += [c["text"]["text"] for c in band["steps"]["chips"]]
        if band["stats"]:
            for c in band["stats"]["cards"]:
                required += [c["value"]["text"], c["label"]["text"]]
    return {
        "W": W, "H": H, "class": cls, "layout": comp["layout"], "align": align, "script": s_name,
        "margin": round(0.067 * m), "min_text_px": round(0.022 * m),
        "zones": {k: {"x0": round(v[0]), "y0": round(v[1]), "x1": round(v[2]), "y1": round(v[3])} for k, v in zones.items()},
        "colors": roles, "fonts": fonts, "text": text, "band": band,
        "cta": cta, "cta_text": cta_text, "badge": badge, "required_text": required,
        "headline_emphasis": cp["headline_emphasis"], "corner_radius": ds["corner_radius"],
    }


# --------------------------------------------------------------------------------------
# 3. ILLUSTRATOR
# --------------------------------------------------------------------------------------
POSTER_SYSTEM = r"""You are a world-class poster designer and SVG illustrator.
You receive a finished creative brief and an exact layout plan. Output ONE self-contained, STATIC SVG poster that looks like a professionally
designed, high-end social-media advertisement. If any detail is missing, make a sensible assumption. Never ask questions.

=== 1. OUTPUT ===
- Reply with the SVG code ONLY. The first characters must be "<svg". No markdown fences, no commentary.
- Root: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 <<W>> <<H>>" width="100%" height="100%">. The canvas is <<W>> x <<H>>.
- STATIC image: no animation of any kind (no @keyframes, no animation or transition properties, no <animate>, <animateTransform>, <set>).
- No <image>, <script>, <foreignObject>, no external resources, no emoji (draw icons with shapes and paths).
- Fonts: the plan gives one exact @import line; paste it as the FIRST line inside <style> and use the exact font-family stacks given (they include fallbacks).

=== 2. QUALITY BAR (this is what makes it look professional, not like clip-art) ===
- Build in layers, back to front: (1) background: rich linear/radial gradient from the colour roles, a soft glow or vignette behind the hero, big faint
  decorative shapes, optionally ONE subtle grain overlay (feTurbulence, opacity at most 0.07); (2) far decor: soft, low-opacity or gently blurred shapes and particles;
  (3) the hero illustration; (4) foreground accents (garnish, splashes, sparkles, steam); (5) typography, offer badge, CTA, footer.
- HERO: it is the star and must fill its zone (at least 70% of the zone's width or height). Build it from 25-60 shapes with real form: every major object has a base
  gradient (highlight -> base -> shade), an inner shade shape, a soft specular highlight (white, opacity 0.15-0.45), an edge/rim light and a contact shadow
  (blurred dark ellipse under it). Add surface detail (texture dots, grill marks, veins, folds, glossy drips, bubbles, steam wisps as soft strokes, crumbs).
  It must be recognisable at thumbnail size: strong silhouette, simplified but rich.
  When the hero is a diagram or metaphor of a platform (hub, orbit, loop, pipeline) draw it BIG with bold shapes, strokes of at least 4px and
  icon-like node shapes at least 90px wide, with no text inside it.
- LIGHT: one light source at the top-left, used consistently for every highlight and shadow.
- COLOUR: only the palette (tints and shades allowed), max 5 brand colours plus neutrals. Use the given colour roles for text, CTA and badge exactly.
- COMPOSITION: hero > headline > offer badge > CTA > the rest. Generous breathing room; no clutter near text; never put busy detail behind text unless a scrim keeps contrast >= 4.5:1.
- POLISH: one corner radius (given) for all rounded shapes, one shadow style from at most 6 reusable filters, consistent stroke widths, no stray shapes, nothing cut off by accident.
- RICHNESS: use at least 120 drawing elements (path, circle, ellipse, rect, polygon...). Use <use> for repeated items (seeds, sparkles, leaves) to keep the code compact.

=== 3. LAYOUT AND TEXT (exact, produced by a layout engine: do not change) ===
- Keep ALL text, badge, CTA and footer exactly at the given coordinates and font sizes. The hero stays inside the hero zone (decor may bleed into the background only).
- The text plan lists every line with x, y (baseline), font_size, weight and anchor. Create ONE <text> element per planned line with those exact values, the given text
  (do not rewrite, translate, re-wrap or re-case it), the given font stack, the given weight as font-weight (it is the heaviest weight that font really has: never ask for a heavier one)
  and fill. Set text-anchor, font-size, font-family, font-weight and fill as attributes.
  Letter-spacing where given. Emphasise the "headline_emphasis" word with <tspan fill="emphasis colour">; everything else uses the colour roles.
- CTA: draw a rounded rect pill at the given x, y, w, h, rx in cta_fill; the CTA text in cta_text colour; a circular arrow icon (circle + chevron path) at the given arrow position, in cta_text colour on a circle of the opposite tone.
- Badge (if given): draw a circle at (cx, cy) with radius r in badge_fill and a dashed ring at ring_r (stroke badge_text, opacity 0.6), then the kicker and main lines inside it in badge_text colour.
  The "pill" (if given) is a rounded rect at pill.x, pill.y, pill.w, pill.h, pill.rx filled with pill_fill that overlaps the lower edge of the circle, containing pill.text in pill_text colour.
  The badge may overlap the hero's edge on purpose.
- Footer is one text line (it contains non-breaking spaces around the bullet: keep them). Nothing else may contain text, except <title>/<desc>.
- INFO BAND (if the plan has "band"): "steps.chips" are rounded rects at the given x, y, w, h, rx filled with chip_fill and a 2px stroke in chip_stroke, each
  with its text (given position, size, weight) in chip_text colour. "stats.cards" are rounded rects filled with chip_fill; the value text in the emphasis colour
  and the label text in text_support colour, at the given positions. Add nothing else to the band except tiny decorative connectors (thin line or chevron in the gaps)
  that never touch the text. The hero zone already excludes the band.
- TEXT COLOURS: headline = text_main (emphasis word = emphasis), support lines = text_support, eyebrow = emphasis, footer = text_muted.
- LEGIBILITY IS THE TOP PRIORITY: everything must be readable on a phone at a glance. Keep the area behind every text zone calm (plain gradient, or a soft scrim of
  0.35-0.6 opacity); never let hero parts, props, decor, grain or glow cross into a text zone or the band.
- Corner radius for any other rounded rect: <<CORNER>>.

=== 4. TECHNICAL RULES (follow exactly) ===
1. Well-formed XML: every tag closed, every attribute value quoted, attributes separated by a space (width="76" fill="red", never width="76"fill="red").
2. Escape & as &amp; and < as &lt; in text.
3. Numbers: separate numbers in path data, points and transforms with a space or comma. Never run numbers together (wrong: "795800,850"). Path commands need the right count
   of numbers (M/L/T 2, H/V 1, C 6, S/Q 4, A 7). Use rotate(angle) or rotate(angle cx cy) only. No coordinate beyond +/- <<LIM>>.
4. IDs unique. Every url(#id) and href="#id" must exist in the file. Define gradients, filters, clipPaths in <defs>. Use href, not xlink:href.
5. A gradient with the default objectBoundingBox units disappears on perfectly horizontal/vertical lines and zero-size shapes: use gradientUnits="userSpaceOnUse" there or a solid colour.
6. Shadows and glows ONLY with SVG <filter> (feDropShadow, feGaussianBlur, feOffset+feMerge) defined in <defs>: at most 6 filters, each with x="-30%" y="-30%" width="160%" height="160%"
   so nothing is clipped. Never use CSS filter functions (blur(), drop-shadow()), mix-blend-mode or backdrop-filter anywhere.
7. Do not use text-transform, textLength, dx/dy on text, or opacity on <text> (use a fill colour). No pattern fills for large areas, no data URIs, file size under 350 KB.
8. Every class used in the markup must be defined in the CSS. Prefer plain attributes over classes.
9. Group logically with descriptive ids (background, decor, hero, props, headline, badge, cta, footer). Add <title> (poster title) and <desc> (one sentence).

=== 5. SELF-CHECK (silently, then output) ===
Well-formed XML; no run-together numbers; correct path argument counts; every url(#...) and href exists; no animation; every planned text line present once with the exact
coordinates and size; no extra text; band chips and cards present exactly as planned; text colours match the roles; calm areas behind text; hero fills its zone and has gradients, highlights and a contact shadow; at least 120 drawing elements; nothing important outside the safe margin
(<<MARGIN>> px); no emoji. Fix anything that fails, then output the SVG only."""


def poster_system(plan: dict) -> str:
    W, H = plan["W"], plan["H"]
    return fill(POSTER_SYSTEM, W=W, H=H, CORNER=plan["corner_radius"], LIM=3 * max(W, H), MARGIN=plan["margin"])


def poster_user(use_case: str, brief: dict, plan: dict) -> str:
    comp, ds = brief["composition"], brief["design_system"]
    pal = ds["palette"]
    layout_json = {
        "canvas": {"width": plan["W"], "height": plan["H"], "safe_margin": plan["margin"]},
        "layout": plan["layout"], "text_align": plan["align"], "zones_px": plan["zones"],
        "colour_roles": plan["colors"], "palette": pal,
        "fonts": plan["fonts"], "text_plan": plan["text"],
        "cta": plan["cta"], "cta_text_plan": plan["cta_text"], "badge": plan["badge"],
        "headline_emphasis": plan["headline_emphasis"],
    }
    parts = [
        "USE CASE: " + use_case,
        "\nPOSTER TITLE: " + brief["title"],
        "BRAND: " + json.dumps(brief["brand"], ensure_ascii=False),
        "\nCONCEPT: " + brief["concept"],
        "\nDESIGN SYSTEM: style: " + ds["style"] + " | lighting: " + ds["lighting"] + " | corner radius: " + str(ds["corner_radius"]),
        "\nHERO ILLUSTRATION (draw this inside the hero zone):\n" + comp["hero"],
        "\nFLOATING PROPS:\n" + "\n".join("- " + x for x in comp["props"]),
        "\nBACKGROUND: " + comp["background"],
        "\nBIG FAINT DECOR:\n" + "\n".join("- " + x for x in comp["decor"]),
        "\nLAYOUT PLAN (exact, final):\n" + json.dumps(layout_json, ensure_ascii=False, indent=1),
        "\nWrite the SVG poster now. SVG code only.",
    ]
    return "\n".join(parts)


# --------------------------------------------------------------------------------------
# 4. LINT / AUTO-FIX
# --------------------------------------------------------------------------------------
def extract_svg(raw: str) -> Optional[str]:
    s = raw.strip().lstrip("\ufeff")
    m = re.search(r"```(?:svg|xml|html)?\s*(.*?)```", s, re.S)
    if m and "<svg" in m.group(1):
        s = m.group(1)
    a, b = s.find("<svg"), s.rfind("</svg>")
    if a < 0 or b < 0:
        return None
    return s[a:b + 6]


def local(tag: Any) -> str:
    return tag.split("}")[-1] if isinstance(tag, str) else ""


def force_fonts(svg: str, import_line: str) -> str:
    svg = _IMPORT_RE.sub("", svg)
    m = re.search(r"<style\b[^>]*>", svg)
    if m:
        return svg[:m.end()] + "\n" + import_line + svg[m.end():]
    r = re.match(r"<svg\b[^>]*>", svg, re.S)
    if not r:
        return svg
    return svg[:r.end()] + "<defs><style>\n" + import_line + "\n</style></defs>" + svg[r.end():]


def strip_smil(svg: str) -> str:
    svg = re.sub(r"<(?:animate|animateTransform|animateMotion|set)\b[^>]*?/>", "", svg)
    return re.sub(r"<(animate|animateTransform|animateMotion|set)\b[^>]*>.*?</\1>", "", svg, flags=re.S)


def normalize_root(svg: str, W: int, H: int) -> str:
    m = re.match(r"<svg\b[^>]*>", svg, re.S)
    if not m:
        return svg
    tag = m.group(0)
    t2 = re.sub(r"\s(?:viewBox|width|height|preserveAspectRatio)\s*=\s*(?:\"[^\"]*\"|'[^']*')", "", tag)
    if 'xmlns="' not in t2 and "xmlns='" not in t2:
        t2 = t2.replace("<svg", f'<svg xmlns="{SVG_NS}"', 1)
    t2 = t2.replace("<svg", f'<svg viewBox="0 0 {W} {H}" width="100%" height="100%"', 1)
    return t2 + svg[len(tag):]


_XML_ENT = {"amp", "lt", "gt", "quot", "apos"}


def _fix_entities(s: str) -> str:
    def rep(m):
        name = m.group(1)
        if name in _XML_ENT:
            return m.group(0)
        cp = html.entities.name2codepoint.get(name)
        return chr(cp) if cp else "&amp;" + name + ";"
    s = re.sub(r"&([A-Za-z][A-Za-z0-9]*);", rep, s)
    return re.sub(r"&(?!(?:[A-Za-z][A-Za-z0-9]*|#[0-9]+|#x[0-9A-Fa-f]+);)", "&amp;", s)


def parse_with_repair(svg: str) -> Tuple[Optional[ET.Element], str, Optional[str]]:
    try:
        return ET.fromstring(svg), svg, None
    except ET.ParseError:
        pass
    s = _fix_entities(svg)
    s = re.sub(r'(=\s*"[^"<>]*")(?=[A-Za-z_:])', r"\1 ", s)
    s = re.sub(r"(=\s*'[^'<>]*')(?=[A-Za-z_:])", r"\1 ", s)
    if "xlink:" in s and "xmlns:xlink" not in s:
        s = s.replace("<svg", '<svg xmlns:xlink="http://www.w3.org/1999/xlink"', 1)
    try:
        return ET.fromstring(s), s, None
    except ET.ParseError as e:
        line, _col = getattr(e, "position", (0, 0))
        lines = s.splitlines()
        ctx = lines[line - 1].strip()[:220] if 0 < line <= len(lines) else ""
        return None, s, (f"FATAL: the SVG is not well-formed XML ({e}). Near: {ctx}")


_PATH_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
_ARITY = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def check_path(d: str, limit: float) -> List[str]:
    problems: List[str] = []
    rest = re.sub(r"[\s,]", "", _PATH_TOKEN.sub("", d))
    if rest:
        problems.append(f"invalid characters '{rest[:12]}'")
        return problems
    toks = _PATH_TOKEN.findall(d)
    if not toks:
        return ["empty path data"]
    if toks[0] not in ("M", "m"):
        problems.append("path data must start with M")
    cmd: Optional[str] = None
    count = 0

    def flush():
        if cmd is None:
            return
        ar = _ARITY[cmd.upper()]
        if ar == 0:
            if count:
                problems.append(f"'{cmd}' takes no numbers")
        elif cmd.upper() != "A" and (count == 0 or count % ar):
            problems.append(f"'{cmd}' has {count} numbers (needs a multiple of {ar})")
        elif cmd.upper() == "A" and count < 7:
            problems.append(f"'{cmd}' has only {count} numbers (needs 7)")

    for tk in toks:
        if tk.isalpha():
            flush()
            cmd, count = tk, 0
        else:
            count += 1
            try:
                if abs(float(tk)) > limit:
                    problems.append(f"suspicious number {tk}")
                    break
            except ValueError:
                pass
    flush()
    return problems[:3]


_TR_ARITY = {"translate": (1, 2), "scale": (1, 2), "rotate": (1, 3), "skewX": (1,), "skewY": (1,), "matrix": (6,)}


def check_transform(t: str, limit: float) -> List[str]:
    problems = []
    leftover = re.sub(r"[\s,]", "", re.sub(r"\w+\s*\([^)]*\)", "", t))
    if leftover:
        problems.append(f"invalid transform syntax '{t[:50]}'")
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", t):
        nums = [a for a in re.split(r"[\s,]+", args.strip()) if a]
        if name not in _TR_ARITY:
            problems.append(f"unknown transform '{name}'")
        elif len(nums) not in _TR_ARITY[name]:
            problems.append(f"{name}({args.strip()[:30]}) has {len(nums)} arguments")
        for n in nums:
            try:
                if abs(float(n)) > limit and name != "matrix":
                    problems.append(f"suspicious number {n} in {name}()")
                    break
            except ValueError:
                problems.append(f"non-numeric argument '{n}' in {name}()")
                break
    return problems[:3]


_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2B55\uFE0F]")
_DRAW_TAGS = {"path", "circle", "ellipse", "rect", "polygon", "polyline", "line"}


def _norm(t: str) -> str:
    return " ".join(t.split()).casefold()


def check_svg(raw: str, plan: dict) -> Tuple[Optional[str], List[str], List[str]]:
    W, H = plan["W"], plan["H"]
    limit = 3.0 * max(W, H)
    hard: List[str] = []
    soft: List[str] = []
    svg = extract_svg(raw)
    if not svg:
        return None, ["FATAL: no complete <svg>...</svg> found in the reply."], []
    svg = strip_smil(svg)
    svg = force_fonts(svg, plan["fonts"]["import"])
    svg = normalize_root(svg, W, H)
    root, svg, err = parse_with_repair(svg)
    if root is None:
        return svg, [err or "FATAL: invalid XML"], []

    css_parts: List[str] = []
    ids: List[str] = []
    drawn = 0
    grads = 0
    used_classes: set = set()
    for el in root.iter():
        tag = local(el.tag)
        if tag in {"script", "image", "foreignObject"}:
            hard.append(f"FATAL: forbidden element <{tag}> (poster must be static, self-contained SVG).")
        if tag == "style":
            css_parts.append(el.text or "")
        if el.get("id"):
            ids.append(el.get("id"))
        if tag in _DRAW_TAGS:
            drawn += 1
        if tag in {"linearGradient", "radialGradient"}:
            grads += 1
        if tag == "use":
            h = el.get("href") or el.get("{http://www.w3.org/1999/xlink}href") or ""
            if h and not h.startswith("#"):
                hard.append("FATAL: <use> must reference an internal id, not an external file.")
        for c in (el.get("class") or "").split():
            used_classes.add(c)
        if tag == "path" and el.get("d"):
            for p in check_path(el.get("d"), limit):
                soft.append(f"Invalid path data ({p}) in {el.get('d')[:60]}...")
        if el.get("transform"):
            for p in check_transform(el.get("transform"), limit):
                soft.append(f"Invalid transform: {p}")
        if tag in {"polygon", "polyline"} and el.get("points"):
            nums = [x for x in re.split(r"[\s,]+", el.get("points").strip()) if x]
            if len(nums) % 2:
                soft.append("polygon/polyline points has an odd number of values.")
        if tag in {"text", "tspan"}:
            for a in ("dx", "dy", "textLength", "opacity"):
                if el.get(a) is not None:
                    soft.append(f"<{tag}> uses the forbidden attribute '{a}'.")
                    break

    css = re.sub(r"/\*.*?\*/", "", "\n".join(css_parts), flags=re.S)
    css_nr = _IMPORT_RE.sub("", css)
    defined = set(re.findall(r"\.([A-Za-z_][\w-]*)", css_nr))
    for c in sorted(used_classes - defined):
        soft.append(f"Class '{c}' is used in the markup but not defined in the CSS.")
    if re.search(r"@keyframes|animation\s*:|animation-name|transition\s*:", svg):
        soft.append("Animation found: the poster must be completely static.")
    if re.search(r"filter\s*[:=]\s*[\"']?\s*(?:blur|drop-shadow|brightness|contrast|grayscale|saturate|hue-rotate|invert|sepia)\(", svg):
        soft.append("CSS filter functions are not allowed: use SVG <filter> elements.")
    if re.search(r"mix-blend-mode|backdrop-filter", svg):
        soft.append("mix-blend-mode / backdrop-filter are not allowed.")
    if "text-transform" in svg:
        soft.append("text-transform is not allowed.")
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        soft.append(f"Duplicate ids: {dup[:6]}")
    refs = set(re.findall(r"url\(\s*['\"]?#([^)'\"\s]+)", svg)) | set(re.findall(r"href\s*=\s*[\"']#([^\"']+)", svg))
    for ref in sorted(refs):
        if ref not in ids:
            soft.append(f"url(#{ref}) / href=\"#{ref}\" references an id that does not exist.")
    if _EMOJI_RE.search(svg):
        soft.append("Emoji / pictograph characters found.")

    texts = [_norm("".join(t.itertext())) for t in root.iter() if local(t.tag) == "text"]
    blob = " ".join(texts)
    missing = [t for t in plan["required_text"] if _norm(t) not in blob]
    if missing:
        soft.append("Required text missing: " + "; ".join(f'"{m}"' for m in missing[:6]))
    req = {_norm(t) for t in plan["required_text"]}
    extra = [t for t in texts if t and t not in req]
    if extra:
        soft.append("Extra or altered text: " + "; ".join(f'"{e[:40]}"' for e in extra[:5]))
    if drawn < 90:
        soft.append(f"Illustration too sparse ({drawn} drawing elements): add more detail.")
    if grads < 4:
        soft.append("Too few gradients: use gradients for depth.")
    if len(svg) > 380_000:
        soft.append("SVG is larger than 350 KB.")
    soft = list(dict.fromkeys(soft))[:14]
    return svg, list(dict.fromkeys(hard)), soft


# --------------------------------------------------------------------------------------
# 5. RENDER + BROWSER LAYOUT QA
# --------------------------------------------------------------------------------------
MEASURE_JS = r"""
() => {
  const nodes = Array.from(document.querySelectorAll('text'));
  return nodes.map((el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const m = el.getScreenCTM();
    const sc = m ? Math.sqrt(m.a * m.a + m.b * m.b) : 1;
    let op = 1;
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const o = parseFloat(getComputedStyle(n).opacity);
      if (!isNaN(o)) op *= o;
    }
    const fo = parseFloat(cs.fillOpacity);
    if (!isNaN(fo)) op *= fo;
    return {text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 48),
            l: r.left, t: r.top, r: r.right, b: r.bottom, fs: parseFloat(cs.fontSize) * sc, op: op};
  });
}
"""


def analyze_layout(items: List[dict], W: int, H: int, margin: float, min_px: float) -> List[str]:
    issues: List[str] = []
    boxes = []
    for it in items:
        if it["op"] < 0.45 or not it["text"]:
            continue
        cy, hh = (it["t"] + it["b"]) / 2, 0.35 * it["fs"]
        boxes.append((it, (it["l"], cy - hh, it["r"], cy + hh)))
    for it, core in boxes:
        label = f'"{it["text"]}"'
        if it["l"] < -1 or it["r"] > W + 1 or core[1] < -1 or core[3] > H + 1:
            issues.append(f"Text {label} extends outside canvas.")
        elif it["l"] < margin * 0.7 or it["r"] > W - margin * 0.7:
            issues.append(f"Text {label} is closer than {margin * 0.7:.0f}px to edge.")
        if it["fs"] < min_px * 0.9:
            issues.append(f"Text {label} renders at only {it['fs']:.0f}px.")
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (a, ca), (b, cb) = boxes[i], boxes[j]
            ix = min(ca[2], cb[2]) - max(ca[0], cb[0])
            iy = min(ca[3], cb[3]) - max(ca[1], cb[1])
            if ix > 0 and iy > 0:
                ar = min((ca[2] - ca[0]) * (ca[3] - ca[1]), (cb[2] - cb[0]) * (cb[3] - cb[1]))
                if ar > 0 and ix * iy / ar > 0.30:
                    issues.append(f'Texts "{a["text"]}" and "{b["text"]}" overlap.')
    return list(dict.fromkeys(issues))[:10]


def render_png(svg_path: Path, png_path: Path, plan: dict, scale: float = 1.0, measure: bool = True) -> List[str]:
    from playwright.sync_api import sync_playwright

    W, H = plan["W"], plan["H"]
    issues: List[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=scale)
            page = ctx.new_page()
            try:
                page.goto(Path(svg_path).resolve().as_uri(), wait_until="networkidle", timeout=60000)
            except Exception:
                pass
            try:
                page.evaluate("document.fonts ? document.fonts.ready.then(() => true) : true")
            except Exception:
                pass
            page.wait_for_timeout(700)
            if measure:
                items = page.evaluate(MEASURE_JS)
                issues = analyze_layout(items, W, H, plan["margin"], plan["min_text_px"])
            page.screenshot(path=str(png_path), type="png")
        finally:
            browser.close()
    return issues


REVIEW_SYSTEM = """You are a strict but fair QA reviewer for finished social-media poster images (vector illustrations).
Judge only real defects: text clipped, overflowing its container or the canvas, text overlapping other text or objects so it is hard to read,
poor contrast between text and the background behind it, text smaller than about 2.4% of the canvas height (too small for a phone), a hero that fills much less than its zone, a hero illustration that looks broken, garbled, flat, empty or unrecognisable,
a badly unbalanced composition (large empty areas, hero tiny or cut off), clutter near the text, or colours that clash with the stated palette.
Do NOT nitpick taste. Reply with JSON only: {"ok": true|false, "issues": ["specific, actionable fix", ...]}"""


def review_png(gem: Gemini, png_path: Path, brief: dict, plan: dict) -> List[str]:
    try:
        verdict = extract_json(gem.generate(
            REVIEW_SYSTEM,
            [gem.image_part(png_path.read_bytes()),
             f"Poster {plan['W']}x{plan['H']}. Hero zone px: {json.dumps(plan['zones']['hero'])}. Headline: \"{brief['copy']['headline']}\". "
             f"Palette: {json.dumps(brief['design_system']['palette'])}. Hero should be: {brief['composition']['hero'][:300]}"],
            json_mode=True, temperature=0.2, max_tokens=4096))
    except Exception as e:
        log(f"    vision QA skipped ({type(e).__name__}: {str(e)[:120]})")
        return []
    if verdict.get("ok", True) or not verdict.get("issues"):
        log("    vision QA: ok")
        return []
    return [f"[visual review] {x}" for x in verdict["issues"][:6]]


# --------------------------------------------------------------------------------------
# Build loop
# --------------------------------------------------------------------------------------
def build_poster_svg(gem: Gemini, use_case: str, brief: dict, plan: dict, svg_path: Path, png_path: Path,
                     attempts: int, review: bool, render: bool) -> Optional[str]:
    system = poster_system(plan)
    base_user = poster_user(use_case, brief, plan)
    feedback = ""
    prev: Optional[str] = None
    best: Optional[str] = None
    best_n = 10 ** 9
    render_ok = render
    for att in range(1, attempts + 1):
        user = base_user
        if feedback:
            user += ("\n\n=== FIX REQUIRED ===\n" + feedback +
                     (("\n\nYour previous SVG is below. Return the COMPLETE corrected SVG only.\n" + prev[:120000]) if prev else ""))
        raw = gem.generate(system, user, temperature=0.75 if att == 1 else 0.45)
        svg, hard, soft = check_svg(raw, plan)
        if svg:
            prev = svg
        if svg and not hard:
            issues = list(soft)
            if render_ok:
                try:
                    svg_path.write_text(svg, encoding="utf-8")
                    issues += render_png(svg_path, png_path, plan, 1.0, measure=True)
                    if review:
                        issues += review_png(gem, png_path, brief, plan)
                except Exception as e:
                    log(f"    render unavailable ({type(e).__name__}: {str(e)[:140]}) - continuing with static checks only")
                    render_ok = False
            log(f"    attempt {att}: {len(issues)} issue(s)")
            if len(issues) < best_n:
                best, best_n = svg, len(issues)
            if not issues:
                return svg
            feedback = "\n".join(f"- {x}" for x in issues[:14])
        else:
            log(f"    attempt {att}: {len(hard)} fatal, {len(soft)} minor issue(s)")
            feedback = "\n".join(f"- {x}" for x in (hard + soft)[:14])
    if best:
        log(f"  using the best attempt ({best_n} remaining issue(s))")
    return best


# --------------------------------------------------------------------------------------
# 6. FALLBACK (pure python, always valid)
# --------------------------------------------------------------------------------------
def fallback_svg(brief: dict, plan: dict) -> str:
    W, H = plan["W"], plan["H"]
    pal = brief["design_system"]["palette"]
    r = plan["colors"]
    fd, fb = plan["fonts"]["display"], plan["fonts"]["body"]
    z = plan["zones"]["hero"]
    hx, hy = (z["x0"] + z["x1"]) / 2, (z["y0"] + z["y1"]) / 2
    hr = 0.44 * min(z["x1"] - z["x0"], z["y1"] - z["y0"])
    initials = "".join(w[0] for w in brief["brand"]["name"].split()[:2]).upper() or "IB"
    parts: List[str] = []

    def t(item: dict, fam: str, fill_c: str, weight: Optional[int] = None, extra: str = "") -> str:
        w = weight or item.get("weight", 700)
        ls = f' letter-spacing="{item["letter_spacing"]}"' if item.get("letter_spacing") else ""
        return (f'<text x="{item["x"]}" y="{item["y"]}" text-anchor="{item["anchor"]}" font-size="{item["font_size"]}" '
                f'font-family="{fam}" font-weight="{w}" fill="{fill_c}"{ls}{extra}>{esc(item["text"])}</text>')

    deco = "".join(
        f'<circle cx="{round(hx + hr * 1.18 * math.cos(a), 1)}" cy="{round(hy + hr * 1.18 * math.sin(a), 1)}" '
        f'r="{round(hr * (0.035 + 0.02 * (i % 3)), 1)}" fill="{pal["secondary"] if i % 2 else pal["primary"]}" opacity="0.75"/>'
        for i, a in enumerate([k * math.pi / 5 for k in range(10)]))
    rays = "".join(
        f'<line x1="{round(hx + hr * 0.2 * math.cos(a), 1)}" y1="{round(hy + hr * 0.2 * math.sin(a), 1)}" '
        f'x2="{round(hx + hr * 1.5 * math.cos(a), 1)}" y2="{round(hy + hr * 1.5 * math.sin(a), 1)}" '
        f'stroke="{pal["secondary"]}" stroke-width="3" opacity="0.10"/>'
        for a in [k * math.pi / 8 for k in range(16)])
    parts.append(f"""<svg xmlns="{SVG_NS}" viewBox="0 0 {W} {H}" width="100%" height="100%">
<title>{esc(brief['title'])}</title><desc>Typographic poster for {esc(brief['brand']['name'])}</desc>
<defs>
<style>
{plan['fonts']['import']}
</style>
<linearGradient id="bgG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{r['background_gradient_from']}"/><stop offset="1" stop-color="{r['background_gradient_to']}"/></linearGradient>
<radialGradient id="glowG" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{pal['primary']}" stop-opacity="0.55"/><stop offset="1" stop-color="{pal['primary']}" stop-opacity="0"/></radialGradient>
<radialGradient id="plateG" cx="0.35" cy="0.3" r="0.8"><stop offset="0" stop-color="{mix(pal['paper'], pal['secondary'], 0.15)}"/><stop offset="0.6" stop-color="{pal['secondary']}"/><stop offset="1" stop-color="{mix(pal['secondary'], pal['bg'], 0.45)}"/></radialGradient>
<radialGradient id="coreG" cx="0.35" cy="0.3" r="0.9"><stop offset="0" stop-color="{pal['primary']}"/><stop offset="1" stop-color="{mix(pal['primary'], pal['bg'], 0.5)}"/></radialGradient>
<filter id="shG" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="14" stdDeviation="16" flood-color="#000000" flood-opacity="0.5"/></filter>
</defs>
<rect width="{W}" height="{H}" fill="url(#bgG)"/>
<circle cx="{hx}" cy="{hy}" r="{round(hr * 1.7)}" fill="url(#glowG)"/>
<g id="decor">{rays}{deco}</g>
<g id="hero" filter="url(#shG)">
<circle cx="{hx}" cy="{hy}" r="{round(hr)}" fill="url(#plateG)"/>
<circle cx="{hx}" cy="{hy}" r="{round(hr * 0.80)}" fill="url(#coreG)"/>
<circle cx="{hx}" cy="{hy}" r="{round(hr * 0.80)}" fill="none" stroke="{r['text_main']}" stroke-opacity="0.35" stroke-width="3" stroke-dasharray="10 12"/>
<ellipse cx="{round(hx - hr * 0.3)}" cy="{round(hy - hr * 0.45)}" rx="{round(hr * 0.35)}" ry="{round(hr * 0.12)}" fill="#FFFFFF" opacity="0.28" transform="rotate(-25 {round(hx - hr * 0.3)} {round(hy - hr * 0.45)})"/>
<text x="{hx}" y="{round(hy + hr * 0.2)}" text-anchor="middle" font-size="{round(hr * 0.62)}" font-family="{fd}" font-weight="{snap_weight(brief['design_system']['fonts']['display'], 900)}" fill="{pal['paper']}">{esc(initials)}</text>
</g>""")
    for it in plan["text"].get("eyebrow", []):
        parts.append(t(it, fb, r["emphasis"]))
    emph = plan["headline_emphasis"].casefold()
    for it in plan["text"]["headline"]:
        parts.append(t(it, fd, r["emphasis"] if emph and emph in it["text"].casefold() else r["text_main"]))
    for it in plan["text"].get("support", []):
        parts.append(t(it, fb, r["text_support"]))
    c = plan["cta"]
    a = c["arrow"]
    parts.append(f'<rect x="{c["x"]}" y="{c["y"]}" width="{c["w"]}" height="{c["h"]}" rx="{c["rx"]}" fill="{r["cta_fill"]}" filter="url(#shG)"/>')
    parts.append(t(plan["cta_text"][0], fd, r["cta_text"]))
    parts.append(f'<circle cx="{a["cx"]}" cy="{a["cy"]}" r="{a["r"]}" fill="{r["cta_text"]}"/>'
                 f'<path d="M {round(a["cx"] - a["r"] * 0.3, 1)} {round(a["cy"] - a["r"] * 0.45, 1)} L {round(a["cx"] + a["r"] * 0.3, 1)} {a["cy"]} '
                 f'L {round(a["cx"] - a["r"] * 0.3, 1)} {round(a["cy"] + a["r"] * 0.45, 1)}" fill="none" stroke="{r["cta_fill"]}" '
                 f'stroke-width="{max(3, round(a["r"] * 0.16))}" stroke-linecap="round" stroke-linejoin="round"/>')
    bd = plan.get("band")
    if bd and bd.get("steps"):
        for ch in bd["steps"]["chips"]:
            parts.append(f'<rect x="{ch["x"]}" y="{ch["y"]}" width="{ch["w"]}" height="{ch["h"]}" rx="{ch["rx"]}" '
                         f'fill="{r["chip_fill"]}" stroke="{r["chip_stroke"]}" stroke-width="2"/>')
            parts.append(t(ch["text"], fb, r["chip_text"]))
    if bd and bd.get("stats"):
        for cd in bd["stats"]["cards"]:
            parts.append(f'<rect x="{cd["x"]}" y="{cd["y"]}" width="{cd["w"]}" height="{cd["h"]}" rx="{cd["rx"]}" '
                         f'fill="{r["chip_fill"]}" stroke="{r["chip_stroke"]}" stroke-opacity="0.5" stroke-width="2"/>')
            parts.append(t(cd["value"], fd, r["emphasis"]))
            parts.append(t(cd["label"], fb, r["text_support"]))
    for it in plan["text"].get("footer", []):
        parts.append(t(it, fb, r["text_muted"]))
    b = plan["badge"]
    if b:
        parts.append(f'<circle cx="{b["cx"]}" cy="{b["cy"]}" r="{b["r"]}" fill="{r["badge_fill"]}" filter="url(#shG)"/>'
                     f'<circle cx="{b["cx"]}" cy="{b["cy"]}" r="{b["ring_r"]}" fill="none" stroke="{r["badge_text"]}" stroke-opacity="0.6" stroke-width="3" stroke-dasharray="8 8"/>')
        for it in b["lines"]:
            parts.append(t(it, fd if it["font"] == "display" else fb, r["badge_text"], it["weight"]))
        pl = b.get("pill")
        if pl:
            parts.append(f'<rect x="{pl["x"]}" y="{pl["y"]}" width="{pl["w"]}" height="{pl["h"]}" rx="{pl["rx"]}" fill="{r["pill_fill"]}" filter="url(#shG)"/>')
            parts.append(t(pl["text"], fb, r["pill_text"], pl["text"]["weight"]))
    parts.append("</svg>")
    return "\n".join(parts)


# --------------------------------------------------------------------------------------
# Orchestration API
# --------------------------------------------------------------------------------------
def generate_poster(
    use_case: str,
    output_dir: Optional[Union[Path, str]] = None,
    name: str = "poster",
    aspect: str = "4:5",
    language: str = "English",
    direction: str = "",
    variants: int = 1,
    attempts: int = 3,
    review: bool = True,
    render: bool = True,
    scale: float = 1.0,
    force: bool = False,
    model: Optional[str] = None,
    gem: Any = None,
    embed_fonts: bool = True,
    brief_override: Optional[dict] = None
) -> Dict[str, Any]:
    """
    Complete programmatic API to generate high-authority static SVG advertisement posters + PNG exports.
    """
    W, H = ASPECTS.get(aspect, ASPECTS["4:5"])
    work = Path(output_dir) if output_dir else Path("output") / slugify(use_case)
    work.mkdir(parents=True, exist_ok=True)
    gem = gem or Gemini(model)
    if brief_override is not None:
        brief_override = normalize_brief(json.loads(json.dumps(brief_override)))
    results = []
    for v in range(1, max(1, variants) + 1):
        tag = f"{name}_v{v}" if variants > 1 else name
        if variants > 1:
            if direction:
                dirn = (f"{direction}. This is variant {v} of {variants}: make it clearly different from the others "
                        "in composition, hero pose and colour mood.")
            else:
                dirn = VARIANT_DIRECTIONS[(v - 1) % len(VARIANT_DIRECTIONS)]
        else:
            dirn = direction
        log(f"=== Variant {v}/{variants}  ({dirn or 'free direction'}) ===")

        bpath = work / f"{tag}.brief.json"
        bkey = sha(use_case, aspect, language, dirn, v, "brief-3")
        if brief_override is not None:
            log("Art director: using the hand-written brief")
            brief = json.loads(json.dumps(brief_override))
            bpath.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
            mark(bpath, sha("override", brief))
        elif not force and cached(bpath, bkey):
            log("Art director: reusing cached brief")
            brief = normalize_brief(json.loads(bpath.read_text(encoding="utf-8")))
        else:
            log("Art director: writing the creative brief...")
            brief = make_brief(gem, use_case, aspect, W, H, language, dirn)
            bpath.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
            mark(bpath, bkey)
        plan = build_plan(brief, W, H)
        log(f"  '{brief['title']}'  layout={plan['layout']}/{plan['class']}  fonts={brief['design_system']['fonts']}"
            + (f"  script={plan['script']}" if plan["script"] else ""))

        svg_path, png_path = work / f"{tag}.svg", work / f"{tag}.png"
        skey = sha(brief, W, H, embed_fonts, "svg-3")
        regenerated = False
        if not force and cached(svg_path, skey):
            log("Illustrator: reusing cached SVG")
        else:
            log("Illustrator: drawing the poster...")
            try:
                svg = build_poster_svg(gem, use_case, brief, plan, svg_path, png_path, attempts, review, render)
            except Exception as e:
                log(f"  illustrator failed ({type(e).__name__}: {str(e)[:160]})")
                svg = None
            if not svg:
                log("  Gemini could not produce a valid SVG - using the fallback poster")
                svg = fallback_svg(brief, plan)
            if embed_fonts:
                svg = inline_fonts(svg, plan["script"])
            svg_path.write_text(svg, encoding="utf-8")
            mark(svg_path, skey)
            regenerated = True

        png_ok = False
        if render and (regenerated or not png_path.exists() or force or scale != 1.0):
            try:
                render_png(svg_path, png_path, plan, scale=scale, measure=False)
                png_ok = True
                log(f"  PNG: {png_path}")
            except Exception as e:
                log(f"  PNG export skipped ({type(e).__name__}: {str(e)[:140]}).")
        elif png_path.exists():
            png_ok = True
        log(f"  SVG: {svg_path}")
        results.append({
            "variant": v,
            "svg": str(svg_path),
            "png": str(png_path) if png_ok else None,
            "brief": str(bpath),
            "brief_data": brief,
            "plan_data": plan,
            "title": brief["title"]
        })
    return {"output_dir": str(work), "posters": results}


def main() -> None:
    ap = argparse.ArgumentParser(description="Use case -> high-quality static SVG poster (+ PNG).")
    ap.add_argument("use_case", nargs="*", help='the use case, e.g. "Dosa Corner: crispy dosa and tasty chutneys" (or use -f / stdin)')
    ap.add_argument("-f", "--file", help="read the use case from a text file")
    ap.add_argument("--brief", help="JSON creative brief to use instead of asking the art director")
    ap.add_argument("--aspect", choices=list(ASPECTS), default="4:5", help="4:5 (Instagram feed), 1:1, 9:16, 16:9")
    ap.add_argument("--language", default="English", help="language of the poster text (e.g. Tamil, Hindi)")
    ap.add_argument("--direction", default="", help='style direction, e.g. "premium and elegant"')
    ap.add_argument("--variants", type=int, default=1, help="number of different poster designs to generate (1-4)")
    ap.add_argument("--attempts", type=int, default=3, help="max illustrator attempts")
    ap.add_argument("--no-review", action="store_true", help="skip the Gemini vision review of the rendered PNG")
    ap.add_argument("--no-render", action="store_true", help="skip Chromium (no PNG, static checks only)")
    ap.add_argument("--no-embed-fonts", action="store_true", help="keep the Google Fonts @import instead of inlining the fonts")
    ap.add_argument("--scale", type=float, default=1.0, help="PNG device scale factor")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--workdir", help="output folder")
    ap.add_argument("--name", default="poster", help="base file name")
    ap.add_argument("--no-cache", "--force", dest="force", action="store_true")
    args = ap.parse_args()

    if args.file:
        use_case = Path(args.file).read_text(encoding="utf-8").strip()
    elif args.use_case:
        use_case = " ".join(args.use_case).strip()
    elif args.brief:
        use_case = ""
    else:
        print("Paste the use case, then press Ctrl-D (Ctrl-Z + Enter on Windows):")
        use_case = sys.stdin.read().strip()
    brief_override = None
    if args.brief:
        brief_override = json.loads(Path(args.brief).read_text(encoding="utf-8"))
        use_case = use_case or str(brief_override.get("title") or brief_override.get("concept") or "poster")
    if not use_case:
        sys.exit("No use case given.")

    res = generate_poster(
        use_case=use_case, output_dir=args.workdir, name=args.name, aspect=args.aspect,
        language=args.language, direction=args.direction,
        variants=max(1, min(4, args.variants)), attempts=max(1, args.attempts),
        review=not args.no_review, render=not args.no_render, scale=args.scale,
        force=args.force, model=args.model, embed_fonts=not args.no_embed_fonts,
        brief_override=brief_override
    )
    print("\nCompleted!")
    for p in res["posters"]:
        print(f"  v{p['variant']}: {p['svg']}" + (f"   {p['png']}" if p["png"] else ""))


if __name__ == "__main__":
    main()
