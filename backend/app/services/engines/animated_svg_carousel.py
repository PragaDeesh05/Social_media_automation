"""
IncuBrix Animated SVG Carousel Engine
Powered by Gemini 3.6 Flash & Playwright Chromium

Generates production-grade, seamless, multi-slide Instagram/LinkedIn carousels
as self-contained animated SVGs with CSS keyframe motion, seam-crossing swipe continuity,
interactive HTML preview runners, rendered animated MP4 clips, and resting-state PDFs.
"""

import os
import re
import sys
import time
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

# Exact general instruction prompt mandated for carousel generation
CAROUSEL_DIRECTOR_PROMPT = """You are an expert Instagram carousel creative director and SVG motion designer. Using the USE CASE at the bottom, design a carousel of N slides (N is stated in the use case; if it is missing, use 7). Output N separate, self-contained SVG files, one per slide. Together they must read as ONE connected story and the best possible ad / marketing piece for the use case.

If any detail is missing, make a sensible assumption and continue. Do not ask questions.

=== 1. STORY AND MARKETING STRATEGY ===
Plan the narrative silently before drawing. Give the carousel a clear arc, adapted to N:
- Slide 1 (HOOK): the strongest, most scroll-stopping slide. A bold promise, question, or surprising claim in at most 8 words, with a clear "swipe" cue.
- Middle slides (STORY): one idea per slide, building on the previous one. Use the structure that fits the use case: problem, then agitation, then solution, then how it works / features, then proof (numbers, testimonial, before/after), then offer. Each slide's headline should make the viewer want to see the next slide.
- Last slide (CTA): a single clear call to action, the offer or reason to act now, and brand details (placeholder website and @handle).
- Keep text minimal: headline of at most 8 words, supporting text of at most 15 words per slide. Headlines at least 80px, body text at least 36px, nothing smaller than 28px.
- Slide 1 and the last slide should visually rhyme (same hero element or palette) so the carousel feels complete when swiped back to the start.

=== 2. VISUAL CONTINUITY (this is what makes it a carousel, not N separate posters) ===
- Define ONE design system and reuse it identically on every slide: same palette (max 5 colors plus neutrals), same 2 fonts, same corner radius, same shadow style, same illustration style, same margins.
- Repeat the same <defs> (gradients, filters, fonts) in every SVG so each file works alone.
- SEAMLESS SWIPE FLOW: imagine one wide canvas of N x 1080 px wide and 1350 px tall, cut into N slides. At least some elements (a path, a ribbon, a hero object, a color band, a trail of dots, a character's arm or shadow) must cross the right edge of slide k and continue from the left edge of slide k+1 at the same height. Draw the crossing element in BOTH slides, offset by exactly 1080px, so the join is pixel-aligned when swiped.
- Keep a persistent mini UI on every slide: a progress indicator (for example "2 / 7" or N dots with the current one highlighted) in the same position, and a small brand mark in the same corner.
- Slides 1 to N-1 carry a subtle "swipe" arrow or edge-peek cue. The final slide does not.
- Use background color shifts, shape continuations and recurring motifs to link slides; do NOT make every slide look identical.

=== 3. CANVAS ===
- Every SVG: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1350" width="100%" height="100%"> (4:5 portrait).
- Keep all important text and objects at least 72px inside every edge, except the deliberate seam-crossing elements.
- The file must start with "<svg". No "xml" label, no text before it.
- Fonts: import from Google Fonts with @import at the top of <style>, and ALWAYS include fallbacks, for example font-family="'Poppins', Arial, sans-serif". The design must still look good if the font fails to load.
- No emoji. Draw icons with shapes or paths.
- No <image>, no <script>, no <foreignObject>, no external resources except Google Fonts.
- Use placeholder brand text (e.g. "yourbrand.com", "@yourbrand") unless the use case provides real ones.

=== 4. ANIMATION ===
- If the use case asks for static images, output static SVGs (no <style> animation block).
- Otherwise make every slide animated. Each slide plays on its own when opened, with this timing: background 0s, main shapes 0.3-1.0s, headline 1.0-1.6s, supporting text 1.6-2.2s, accent elements 2.2-3.0s. The entrance must finish within 3 seconds. Then add a very subtle idle loop (gentle bob, shimmer or pulse).
- The FINAL resting frame of every animated slide must look complete and well composed, because it may be screenshotted.
- Use cubic-bezier easing for entrances, never linear.
- Animate ONLY opacity and transform.

=== 5. CRITICAL TECHNICAL RULES (follow exactly) ===
1. TRANSFORM CONFLICT: a CSS animation's transform REPLACES a transform="..." attribute on the same element. Never put an animation class and a transform attribute on the same element. Use nested groups:
   <g transform="translate(540,130)"><g class="a a1"> ... </g></g>
   Prefer drawing at final absolute coordinates so animated groups need no transform attribute.
2. Give every animated element ONE shared base class "a" with: opacity: 0; transform-box: fill-box; transform-origin: center; animation-fill-mode: forwards; then a unique modifier class per element for its animation and delay. Do NOT use a global "* { transform-origin: center }" rule.
3. CLASS CONSISTENCY: every class used in the markup must exist in the CSS, and every class in the CSS must be used. Do not list one class name in the base rule and a different one (like "steam-1") in the markup.
4. Do not put opacity="..." attributes on animated elements (it conflicts with the animation). Put opacity on a child element instead.
5. Write every animation shorthand with spaces: "animation: fadeUp 0.8s ease-out 0.5s forwards;" (never "0.5sforwards", never ")2.2s").
6. When an element has an entrance and then a loop, put both in one comma-separated animation property, and start the loop exactly when the entrance ends.
7. Never use box-shadow, width, height, or CSS filter functions such as blur() in keyframes or in the filter attribute. Make shadows and glows with SVG <filter> (feDropShadow, feGaussianBlur) defined in <defs>.
8. Separate every attribute with a space and quote every value: font-size="76" fill="red" (never font-size="76"fill="red").
9. Separate numbers in paths and transforms: "C 700,785 800,795 800,850" (never "795800,850"). Write rotate with three numbers: rotate(-20 400 450).
10. Escape text: & as &amp;, < as &lt;.
11. Every url(#id) must reference an id defined in <defs>. IDs are unique within a file.
12. Always set text-anchor on <text>. Center text blocks around x=540 unless the layout deliberately differs. Estimate text width as roughly 0.6 x font-size per character (0.7 for bold caps) and make sure it fits its container, including text inside badges, pills, buttons and circles. Break long lines into separate <text> lines.
13. Accessibility: add this at the end of <style>, and nothing else touches opacity globally:
    @media (prefers-reduced-motion: reduce) { .a { animation: none !important; opacity: 1 !important; transform: none !important; } }

=== 6. SELF-CHECK BEFORE ANSWERING ===
For EACH of the N SVGs, silently verify:
- Well-formed XML: all tags closed and nested, all attributes quoted and spaced.
- No element has both an animation class and a transform attribute.
- Every CSS class is used and every used class exists in the CSS.
- No run-together numbers, no missing spaces in animation shorthands.
- All url(#...) references exist.
- All text fits inside its container and inside the canvas.
- Seam-crossing elements match exactly between slide k and slide k+1 (same y, same shape, x offset of 1080).
- The design system (palette, fonts, progress indicator, brand mark) is identical across slides.
- The story flows: hook, then build, then proof, then CTA.
Fix anything that fails, then output.

=== 7. OUTPUT FORMAT ===
Output exactly N sections, in order, with no other text before, between or after them:

### Slide 1 of N - <role in the story>
```svg
<svg ...> ... </svg>
```
### Slide 2 of N - <role in the story>
```svg
...
```
(and so on up to slide N)

=== USE CASE ===
"""

_env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
load_dotenv(_env_path if _env_path.exists() else None)
load_dotenv()
MODEL_NAME = os.getenv("GEMINI_CAROUSEL_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"))
FALLBACK_MODEL_NAME = os.getenv("GEMINI_CAROUSEL_FALLBACK_MODEL", os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite"))
TIMEOUT_MS = 600_000


def format_use_case(use_case: Union[Dict[str, Any], str]) -> str:
    """Formats dynamic use case dictionary or string for injection into the prompt."""
    if isinstance(use_case, str):
        return use_case.strip()

    parts = []
    if "brand" in use_case:
        parts.append(f"Brand: {use_case['brand']}.")
    if "goal" in use_case:
        parts.append(f"Goal: {use_case['goal']}.")
    if "audience" in use_case:
        parts.append(f"Audience: {use_case['audience']}.")
    if "tone" in use_case:
        parts.append(f"Tone: {use_case['tone']}.")
    if "offer" in use_case:
        parts.append(f"Offer: {use_case['offer']}.")
    if "num_slides" in use_case:
        parts.append(f"Number of slides: {use_case['num_slides']}.")
    elif "slides" in use_case and isinstance(use_case["slides"], list):
        parts.append(f"Number of slides: {len(use_case['slides'])}.")

    # Additional contextual hints if provided
    if "context" in use_case:
        parts.append(f"Context: {use_case['context']}.")
    if "key_points" in use_case:
        parts.append(f"Key Points: {use_case['key_points']}.")

    return " ".join(parts)


def parse_expected_slide_count(use_case_str: str) -> int:
    """Extracts expected number of slides from the use case string, defaulting to 7."""
    match = re.search(r"Number of slides:\s*(\d+)", use_case_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 7


def extract_svg_slides(response_text: str, expected_n: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Parses the response into N separate, self-contained animated SVG slides.
    Extracts slide headers and SVG blocks, validating XML structure.
    """
    slides = []

    # Pattern matching: ### Slide X of N - <role>
    header_pattern = re.compile(
        r"###\s*Slide\s*(\d+)\s*(?:of\s*(\d+))?\s*(?:-\s*([^\n]+))?",
        re.IGNORECASE
    )

    # Search for all <svg ... </svg> in the response text (works fenced or unfenced)
    svg_matches = list(re.finditer(r"(<svg[\s\S]*?</svg>)", response_text, re.IGNORECASE))

    for idx, match in enumerate(svg_matches, start=1):
        clean_svg = match.group(1).strip()
        start_pos = match.start()

        # Extract nearest header in preceding text
        preceding = response_text[max(0, start_pos - 400):start_pos]
        headers = list(header_pattern.finditer(preceding))

        role = f"Slide {idx}"
        total = expected_n or len(svg_matches)
        if headers:
            last_h = headers[-1]
            if last_h.group(3):
                role = last_h.group(3).strip()
            if last_h.group(2):
                try:
                    total = int(last_h.group(2))
                except ValueError:
                    pass

        # Sanitize unescaped & in font URLs or attributes before XML parsing
        sanitized_svg = re.sub(r"&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", clean_svg)

        try:
            ET.fromstring(sanitized_svg)
            is_valid = True
            xml_error = None
        except ET.ParseError:
            try:
                ET.fromstring(clean_svg)
                sanitized_svg = clean_svg
                is_valid = True
                xml_error = None
            except ET.ParseError as err2:
                is_valid = False
                xml_error = str(err2)

        slides.append({
            "slide_index": idx,
            "total_slides": total,
            "role": role,
            "svg_code": sanitized_svg,
            "is_valid": is_valid,
            "xml_error": xml_error
        })

    print(f"[Extraction] Extracted {len(slides)} SVG slides.")
    if expected_n and len(slides) != expected_n:
        print(f"[Warning] Expected {expected_n} slides but extracted {len(slides)}.")

    return slides


def call_gemini_carousel(
    full_prompt: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    expected_n: Optional[int] = None,
    timeout_ms: int = TIMEOUT_MS,
    max_retries: int = 2
) -> str:
    """
    Calls Gemini using the google-genai SDK.
    Primary: gemini-3.5-flash-lite
    Secondary / Fallback: gemini-3.1-flash-lite
    Includes multi-turn continuation if fewer than expected_n slides are returned.
    """
    load_dotenv(_env_path if _env_path.exists() else None)
    load_dotenv()
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY not found. Please set it in .env or pass it explicitly.")

    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(timeout=timeout_ms),
    )

    primary = model or os.getenv("GEMINI_CAROUSEL_MODEL", "gemini-3.5-flash-lite")
    fallback = os.getenv("GEMINI_CAROUSEL_FALLBACK_MODEL", "gemini-3.1-flash-lite")

    models_to_try = [primary]
    if fallback and fallback not in models_to_try:
        models_to_try.append(fallback)

    cfg = types.GenerateContentConfig(max_output_tokens=32768, temperature=0.7)
    last_error = None

    for current_model in models_to_try:
        for attempt in range(1, max_retries + 1):
            try:
                print(f"[{current_model}] Generating animated carousel (attempt {attempt}/{max_retries})...")
                start = time.time()
                chat = client.chats.create(model=current_model, config=cfg)
                response = chat.send_message(full_prompt, config=cfg)
                duration = time.time() - start

                if not response or not response.text:
                    raise ValueError(f"Empty or null response received from {current_model}.")

                response_text = response.text
                print(f"[{current_model}] Initial generation completed in {duration:.1f}s ({len(response_text)} chars).")

                # Multi-turn continuation if slides are missing
                if expected_n:
                    extracted = extract_svg_slides(response_text, expected_n=expected_n)
                    continuation_count = 0
                    while len(extracted) < expected_n and continuation_count < 2:
                        continuation_count += 1
                        missing_from = len(extracted) + 1
                        print(f"[{current_model}] Continuation {continuation_count}: generated {len(extracted)}/{expected_n} slides. Requesting Slide {missing_from} to Slide {expected_n}...")
                        cont_prompt = (
                            f"CRITICAL: You have generated {len(extracted)} of {expected_n} required slides.\n"
                            f"Now immediately generate Slide {missing_from} to Slide {expected_n}.\n"
                            f"Each slide must start with '### Slide X of {expected_n} - <role>' and be a complete self-contained SVG wrapped in ```svg <svg...>...</svg> ```.\n"
                            f"Maintain the exact same design system, color palette, typography, and seam continuity."
                        )
                        cont_resp = chat.send_message(cont_prompt, config=cfg)
                        if cont_resp and cont_resp.text:
                            response_text += "\n\n" + cont_resp.text
                            extracted = extract_svg_slides(response_text, expected_n=expected_n)

                    if len(extracted) < expected_n and attempt < max_retries:
                        print(f"[{current_model}] Only {len(extracted)}/{expected_n} slides extracted after continuation. Retrying attempt {attempt + 1}...")
                        continue

                return response_text

            except Exception as e:
                last_error = e
                err_str = str(e)
                print(f"[Gemini Error on {current_model}] Attempt {attempt} failed: {type(e).__name__}: {e}")
                if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                    print(f"[Notice] Quota limit reached on {current_model}. Attempting fallback...")
                    break
                if attempt < max_retries:
                    time.sleep(3)

    raise RuntimeError(f"Failed to generate carousel after attempting models {models_to_try}: {last_error}")


def build_interactive_preview_player(slides: List[Dict[str, Any]], asset_id: str, title: str) -> str:
    """
    Builds a standalone interactive HTML preview runner that plays the animated SVGs
    with live 60fps CSS animations, interactive swipe controls, replay triggers,
    and a panoramic seamless swipe view showing the pixel-aligned crossing elements.
    """
    total = len(slides)
    slides_json = []
    for s in slides:
        # Escape for JS string template
        safe_svg = s["svg_code"].replace("`", "\\`").replace("${", "\\${")
        slides_json.append({
            "index": s["slide_index"],
            "role": s["role"],
            "svg": safe_svg
        })

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IncuBrix Animated Carousel — {asset_id}</title>
<style>
  :root {{
    --bg-dark: #090D16;
    --card-bg: #111827;
    --border: #1F2937;
    --accent: #6366F1;
    --accent-glow: rgba(99, 102, 241, 0.35);
    --text-primary: #F3F4F6;
    --text-secondary: #9CA3AF;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  body {{
    background: var(--bg-dark);
    color: var(--text-primary);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 16px;
  }}
  header {{
    width: 100%;
    max-width: 900px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }}
  .brand-badge {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 600;
    color: #A5B4FC;
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.4);
    padding: 6px 14px;
    border-radius: 9999px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }}
  .controls-bar {{
    display: flex;
    gap: 12px;
  }}
  button {{
    background: var(--card-bg);
    color: var(--text-primary);
    border: 1px solid var(--border);
    padding: 8px 16px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }}
  button:hover {{
    background: #1F2937;
    border-color: var(--accent);
    box-shadow: 0 0 12px var(--accent-glow);
  }}
  button.active {{
    background: var(--accent);
    color: white;
    border-color: var(--accent);
  }}
  /* Main Stage - Unclipped Full Frame Display */
  .stage-container {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    width: 100%;
    max-width: 100%;
    overflow: visible;
  }}
  .viewport-card {{
    width: 100%;
    max-width: 540px;
    aspect-ratio: 4 / 5;
    background: transparent;
    border-radius: 0;
    overflow: visible;
    position: relative;
    box-shadow: 0 10px 40px rgba(0,0,0,0.7);
    transition: max-width 0.25s ease;
  }}
  .viewport-card.native-size {{
    max-width: 1080px;
    width: 1080px;
    height: 1350px;
  }}
  .slide-stage {{
    width: 100%;
    height: 100%;
    position: relative;
    overflow: visible;
  }}
  .slide-stage svg {{
    width: 100%;
    height: 100%;
    display: block;
    overflow: visible !important;
  }}
  /* Panoramic Seamless Mode - Unclipped */
  .panoramic-mode {{
    display: none;
    width: 100%;
    max-width: 100%;
    overflow-x: auto;
    overflow-y: visible;
    padding: 20px 0;
  }}
  .panoramic-strip {{
    display: flex;
    gap: 0;
    width: max-content;
    box-shadow: 0 20px 50px rgba(0,0,0,0.9);
    border-radius: 0;
    overflow: visible;
  }}
  .panoramic-strip .pano-slide {{
    width: 480px;
    height: 600px;
    flex-shrink: 0;
    overflow: visible;
    border-right: 1px dashed rgba(255,255,255,0.25);
  }}
  .panoramic-strip .pano-slide svg {{
    width: 100%;
    height: 100%;
    display: block;
    overflow: visible !important;
  }}
  /* Bottom Navigation */
  .nav-bar {{
    display: flex;
    align-items: center;
    gap: 16px;
    margin-top: 8px;
  }}
  .dots-container {{
    display: flex;
    gap: 8px;
  }}
  .dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #374151;
    cursor: pointer;
    transition: all 0.2s ease;
  }}
  .dot.active {{
    background: var(--accent);
    transform: scale(1.3);
    box-shadow: 0 0 8px var(--accent-glow);
  }}
  .slide-role-label {{
    font-size: 14px;
    color: var(--text-secondary);
    font-weight: 500;
  }}
</style>
</head>
<body>

<header>
  <div>
    <h2 style="font-size:18px; font-weight:700;">IncuBrix Live Carousel Viewer</h2>
    <p style="font-size:13px; color:var(--text-secondary); margin-top:2px;">Asset ID: {asset_id} • {total} Seamless Animated Slides</p>
  </div>
  <div class="controls-bar">
    <button id="toggleNativeBtn" onclick="toggleNativeScale()">&#x2921; 100% Native (1080&times;1350)</button>
    <button id="replayBtn" onclick="replayCurrentSlide()">&#x21bb; Replay Motion</button>
    <button id="togglePanoBtn" onclick="togglePanoramicView()">&#x2922; Seamless Seam View</button>
  </div>
</header>

<div class="stage-container" id="singleStageView">
  <div class="viewport-card">
    <div class="slide-stage" id="slideStage"></div>
  </div>

  <div class="slide-role-label" id="roleLabel">Slide 1 of {total}</div>

  <div class="nav-bar">
    <button onclick="prevSlide()" id="prevBtn">&larr; Previous</button>
    <div class="dots-container" id="dotsContainer"></div>
    <button onclick="nextSlide()" id="nextBtn">Next &rarr;</button>
  </div>
</div>

<div class="panoramic-mode" id="panoramicView">
  <div style="margin-bottom:12px; font-size:14px; color:var(--text-secondary);">
    &#x2728; <strong>Seamless Swipe Verification:</strong> Notice how crossing elements continue across slide edges at the exact same height.
  </div>
  <div class="panoramic-strip" id="panoStrip"></div>
</div>

<script>
  const slidesData = [
"""
    # Inject each slide code
    for s in slides:
        clean = s["svg_code"].replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        html_content += f"""    {{
      index: {s["slide_index"]},
      role: "{s["role"]}",
      svg: `{clean}`
    }},\n"""

    html_content += f"""  ];

  let currentIndex = 0;
  const stage = document.getElementById("slideStage");
  const roleLabel = document.getElementById("roleLabel");
  const dotsContainer = document.getElementById("dotsContainer");

  function init() {{
    // Render dots
    dotsContainer.innerHTML = "";
    slidesData.forEach((_, i) => {{
      const d = document.createElement("div");
      d.className = "dot" + (i === 0 ? " active" : "");
      d.onclick = () => goToSlide(i);
      dotsContainer.appendChild(d);
    }});

    // Populate panoramic strip
    const panoStrip = document.getElementById("panoStrip");
    panoStrip.innerHTML = "";
    slidesData.forEach((s) => {{
      const container = document.createElement("div");
      container.className = "pano-slide";
      container.innerHTML = s.svg;
      panoStrip.appendChild(container);
    }});

    renderSlide(0);
  }}

  function renderSlide(index) {{
    currentIndex = index;
    const slide = slidesData[index];
    // Re-inject HTML to re-trigger CSS keyframe animations fresh
    stage.innerHTML = slide.svg;
    roleLabel.textContent = `Slide ${{slide.index}} of ${{slidesData.length}} - ${{slide.role}}`;

    document.querySelectorAll(".dot").forEach((d, i) => {{
      d.className = "dot" + (i === index ? " active" : "");
    }});

    document.getElementById("prevBtn").disabled = index === 0;
    document.getElementById("nextBtn").disabled = index === slidesData.length - 1;
  }}

  function nextSlide() {{
    if (currentIndex < slidesData.length - 1) {{
      renderSlide(currentIndex + 1);
    }}
  }}

  function prevSlide() {{
    if (currentIndex > 0) {{
      renderSlide(currentIndex - 1);
    }}
  }}

  function goToSlide(index) {{
    renderSlide(index);
  }}

  function replayCurrentSlide() {{
    renderSlide(currentIndex);
  }}

  let panoActive = false;
  function togglePanoramicView() {{
    panoActive = !panoActive;
    const single = document.getElementById("singleStageView");
    const pano = document.getElementById("panoramicView");
    const btn = document.getElementById("togglePanoBtn");

    if (panoActive) {{
      single.style.display = "none";
      pano.style.display = "block";
      btn.classList.add("active");
    }} else {{
      single.style.display = "flex";
      pano.style.display = "none";
      btn.classList.remove("active");
    }}
  }}

  let isNative = false;
  function toggleNativeScale() {{
    isNative = !isNative;
    const card = document.querySelector(".viewport-card");
    const btn = document.getElementById("toggleNativeBtn");
    if (isNative) {{
      card.classList.add("native-size");
      btn.classList.add("active");
      btn.innerHTML = "&#x2922; Fit Scale";
    }} else {{
      card.classList.remove("native-size");
      btn.classList.remove("active");
      btn.innerHTML = "&#x2921; 100% Native (1080&times;1350)";
    }}
  }}

  // Keyboard navigation
  window.addEventListener("keydown", (e) => {{
    if (e.key === "ArrowRight") nextSlide();
    if (e.key === "ArrowLeft") prevSlide();
    if (e.key === "r" || e.key === "R") replayCurrentSlide();
  }});

  init();
</script>
</body>
</html>
"""
    return html_content


def render_live_animated_media(
    slides: List[Dict[str, Any]],
    output_dir: Path,
    asset_id: str,
    render_videos: bool = True
) -> Dict[str, Any]:
    """
    Renders and stores the carousel assets:
    1. Saves self-contained animated .svg files (slide_1.svg ... slide_N.svg).
    2. Builds interactive preview.html runner with 60fps CSS animations & seam viewer.
    3. Uses headless Chrome via Playwright to:
       - Record live animated MP4 video clips (entrance + idle motion).
       - Snapshot high-res resting-state PNGs at t=3.2s.
    4. Compiles multi-page PDF for LinkedIn and cover PNG.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    video_dir = output_dir / "video_clips"
    if render_videos:
        video_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save all raw animated SVG files
    svg_paths = []
    for s in slides:
        idx = s["slide_index"]
        svg_file = output_dir / f"slide_{idx}.svg"
        svg_file.write_text(s["svg_code"], encoding="utf-8")
        svg_paths.append(svg_file)

    # 2. Build interactive HTML preview runner
    preview_file = output_dir / "preview.html"
    preview_html = build_interactive_preview_player(slides, asset_id, title=f"IncuBrix {asset_id}")
    preview_file.write_text(preview_html, encoding="utf-8")

    # 3. Headless Chrome rendering via Playwright
    png_paths = []
    mp4_paths = []

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception:
                browser = p.chromium.launch(channel="chrome", headless=True)

            for idx, svg_path in enumerate(svg_paths, start=1):
                temp_video_dir = output_dir / f"_temp_vid_{idx}"
                temp_video_dir.mkdir(parents=True, exist_ok=True)

                context_kwargs = {
                    "viewport": {"width": 1080, "height": 1350},
                }
                if render_videos:
                    context_kwargs["record_video_dir"] = str(temp_video_dir)
                    context_kwargs["record_video_size"] = {"width": 1080, "height": 1350}

                context = browser.new_context(**context_kwargs)
                page = context.new_page()

                # Load SVG
                page.goto(svg_path.resolve().as_uri())

                # Wait for 3.2s for entrance animation to finish & resting frame to stabilize
                page.wait_for_timeout(3200)

                # Capture resting-state high-res PNG
                png_file = output_dir / f"slide_{idx}.png"
                page.screenshot(path=str(png_file))
                png_paths.append(png_file)

                # Close context to finalize video recording
                context.close()

                # Convert WebM to MP4 if video rendering enabled
                if render_videos:
                    webm_files = list(temp_video_dir.glob("*.webm"))
                    if webm_files:
                        mp4_file = video_dir / f"slide_{idx}.mp4"
                        convert_cmd = [
                            "ffmpeg", "-y", "-i", str(webm_files[0]),
                            "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            str(mp4_file)
                        ]
                        subprocess.run(convert_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if mp4_file.exists():
                            mp4_paths.append(mp4_file)

                    # Clean temp recording dir
                    shutil.rmtree(temp_video_dir, ignore_errors=True)

            browser.close()

    except Exception as e:
        print(f"[Warning] Headless browser rendering encountered an error: {e}")

    # 4. Compile multi-page LinkedIn PDF from resting-state PNGs
    pdf_path = output_dir / f"{asset_id}.pdf"
    cover_path = output_dir / f"{asset_id}_cover.png"

    if png_paths:
        try:
            pil_images = [Image.open(p).convert("RGB") for p in png_paths]
            if pil_images:
                pil_images[0].save(pdf_path, "PDF", save_all=True, append_images=pil_images[1:])
                pil_images[0].save(cover_path, "PNG")
        except Exception as e:
            print(f"[Warning] PDF compilation error: {e}")

    # Also save parent-level copies for pipeline compatibility
    parent_dir = output_dir.parent
    if parent_dir and parent_dir.name == "carousels":
        if pdf_path.exists():
            shutil.copy2(pdf_path, parent_dir / f"{asset_id}.pdf")
        if cover_path.exists():
            shutil.copy2(cover_path, parent_dir / f"{asset_id}_cover.png")
        for idx, png_p in enumerate(png_paths, start=1):
            shutil.copy2(png_p, parent_dir / f"{asset_id}_slide_{idx}.png")

    return {
        "asset_id": asset_id,
        "svg_paths": [str(p) for p in svg_paths],
        "preview_html": str(preview_file),
        "png_paths": [str(p) for p in png_paths],
        "mp4_paths": [str(p) for p in mp4_paths],
        "pdf_path": str(pdf_path) if pdf_path.exists() else None,
        "cover_path": str(cover_path) if cover_path.exists() else None
    }


def generate_and_render_animated_carousel(
    use_case: Union[Dict[str, Any], str],
    output_dir: Optional[Path] = None,
    asset_id: str = "INC-CAR-001",
    api_key: Optional[str] = None,
    render_videos: bool = True
) -> Dict[str, Any]:
    """
    End-to-End Orchestrator:
    1. Formats the dynamic use case.
    2. Builds the complete prompt with CAROUSEL_DIRECTOR_PROMPT + USE CASE.
    3. Queries Gemini (Primary: gemini-3.5-flash-lite, Fallback: gemini-3.1-flash-lite) via google-genai.
    4. Validates and extracts N self-contained animated SVGs.
    5. Renders and stores live animated media, interactive preview player, and resting PDF.
    """
    use_case_str = format_use_case(use_case)
    expected_n = parse_expected_slide_count(use_case_str)

    # Specialize prompt with exact slide count
    prompt_base = CAROUSEL_DIRECTOR_PROMPT
    prompt_base = prompt_base.replace("N slides (N is stated in the use case; if it is missing, use 7)", f"EXACTLY {expected_n} slides (Slide 1 to Slide {expected_n})")
    prompt_base = prompt_base.replace("N slides", f"{expected_n} slides")
    prompt_base = prompt_base.replace("of N", f"of {expected_n}")
    prompt_base = prompt_base.replace("exactly N", f"exactly {expected_n}")
    prompt_base = prompt_base.replace("to slide N", f"to slide {expected_n}")

    completeness_clause = (
        f"\n=== MANDATORY COMPLETENESS REQUIREMENT ===\n"
        f"You MUST generate all {expected_n} slides in full: Slide 1 of {expected_n}, Slide 2 of {expected_n}, "
        f"up to Slide {expected_n} of {expected_n}. Do NOT stop after 1 slide.\n"
    )

    full_prompt = f"{prompt_base}\n{completeness_clause}\n=== USE CASE ===\n{use_case_str}"

    print(f"\n{'='*70}")
    print(f"Generating Animated SVG Carousel: {asset_id} ({expected_n} slides)")
    print(f"Use Case: {use_case_str}")
    print(f"{'='*70}")

    response_text = call_gemini_carousel(full_prompt=full_prompt, api_key=api_key, expected_n=expected_n)
    slides = extract_svg_slides(response_text, expected_n=expected_n)

    if not slides:
        raise ValueError("Failed to extract any valid SVG slides from Gemini response.")

    target_dir = output_dir or (Path("assets/final/carousels") / asset_id)
    result = render_live_animated_media(
        slides=slides,
        output_dir=target_dir,
        asset_id=asset_id,
        render_videos=render_videos
    )

    print(f"[Success] Rendered {len(result['svg_paths'])} animated SVGs into {target_dir}")
    print(f"[Success] Interactive Player: {result['preview_html']}")
    if result["pdf_path"]:
        print(f"[Success] Multi-page PDF: {result['pdf_path']}")
    if result["mp4_paths"]:
        print(f"[Success] Rendered {len(result['mp4_paths'])} animated MP4 video clips.")

    return result


if __name__ == "__main__":
    # Test execution with the exact Dosa House example given in prompt
    test_use_case = {
        "brand": "a South Indian restaurant called “Dosa House”",
        "goal": "drive weekend orders on Instagram",
        "audience": "young professionals",
        "tone": "warm, bold, appetizing",
        "offer": "dosa plus 3 chutneys for $8.99, free delivery over $20",
        "num_slides": 7
    }

    test_output = Path("assets/final/carousels/TEST-CAR-DOSA")
    generate_and_render_animated_carousel(
        use_case=test_use_case,
        output_dir=test_output,
        asset_id="TEST-CAR-DOSA",
        render_videos=True
    )
