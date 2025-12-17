"""
Streamlit frontend for the AI Animation Studio.
Controls the Roughs -> Tie Down / CleanUp / Colors pipeline by:
1) Taking user image + phase settings.
2) Calling Gemini (multimodal) for analysis.
3) Calling Gemini (text) for prompt engineering.
4) Sending prompts + image to ComfyUI (RunPod) for generation.

Environment:
- GOOGLE_GENAI_API_KEY: required for Gemini calls.
- COMFYUI_API_URL: base URL to your ComfyUI HTTP API (e.g., http://host:port).
- COMFYUI_AUTH_TOKEN: optional bearer token if your API is protected.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import requests
import streamlit as st
from PIL import Image
from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None
    genai_types = None

load_dotenv()


# ---------- Default Master Prompts ----------
DEFAULT_ANALYST_PROMPT = """You are a Multi-Modal Visual Analyst (“Brain”) for animation cleanup.

Phases (authoritative dictionary):
0) Skeleton: posing/proportion; stick figure joints; sometimes before/after Roughs.
1) Roughs: gestural scribbles capturing movement; can be volumetric; construction/building-block lines.
2) Tie Down: puts subject on-model (shapes/proportions); cleaner lines; non-essential elements removed; adds definition.
3) Cleanup: perfect, smooth, uniform line work on top of tie-down shapes.
4) Colors: fills between clean lines (some styles colorize the lines).

Inputs:
- Image (user rough/skeleton).
- SOURCE_PHASE (default Roughs).
- DEST_PHASE (default Tie Down/CleanUp/Colors).

Required analysis steps:
A) Recognition: identify characters/objects (hands, sunglasses, steering wheel, etc.).
B) Pose/Action analysis: find anatomical/pose issues (e.g., “left hand anatomically incorrect”).
C) Phase comparison (SOURCE -> DEST):
   - Moving EARLIER in the pipeline (e.g., Tie Down -> Roughs, Roughs -> Skeleton, Cleanup -> Roughs/Skeleton, Colors -> Roughs/Skeleton):
       * Simplify detail; REMOVE non-essential volume and cleanup-quality lines.
       * Preserve pose, timing, and overall composition.
       * Skeleton DEST: reduce to posing/proportion lines and stick-figure / simple construction.
       * Roughs DEST: keep gestural scribbles and movement, with some volumetric hints but not on-model shapes.
   - Moving FORWARD in the pipeline (e.g., Skeleton -> Roughs/Tie Down/Cleanup/Colors, Roughs -> Tie Down/Cleanup/Colors, Tie Down -> Cleanup/Colors, Cleanup -> Colors):
       * Increase clarity and fidelity appropriate to DEST_PHASE.
       * Skeleton/Roughs -> Tie Down: remove scribbles and clutter; fix shapes/proportions; make the subject on-model, but do not produce ink-perfect lineart.
       * Roughs -> Cleanup: CRITICAL - This is a major upgrade. Must: (1) Define proper anatomical shapes for all body parts (hands with clear fingers, proper palm structure, defined joints), (2) Add proper face definition (eyes, nose, mouth placement, facial structure), (3) Add proper body volume (torso volume, limb thickness, muscle definition where appropriate), (4) Make all body parts precise and anatomically correct (shoulders, elbows, knees, ankles, wrists), (5) Remove all construction lines, scribbles, and rough marks, (6) Create smooth, uniform, final line art quality.
       * Tie Down -> Cleanup: focus on line quality; refine shapes to be more precise; add missing anatomical details (hands, face features, body volume); keep shapes as-is but make them more defined; avoid changing pose/composition.
       * Any -> Colors: conceptually perform cleanup first (as if -> Tie Down/Cleanup) and THEN apply colours while preserving existing line/background colours.
   - Lateral moves at same “level” (e.g., Skeleton <-> Roughs, Tie Down <-> Cleanup when explicitly requested):
       * Adjust cleanliness and structural emphasis to match DEST_PHASE definitions, keeping the same character, pose, and timing.
D) Output a concise report: 3-4 critical FIXES and 3-4 REMOVES, plus NOTES if needed.
   - For Cleanup phase (especially from Roughs): CRITICALLY analyze and report:
     * Missing anatomical details: Are hands properly defined with clear fingers and palm? Is face properly defined with eyes, nose, mouth? Are body parts precise with clear joints?
     * Missing body volume: Is torso showing proper volume? Are limbs showing proper thickness and muscle structure? Are shoulders, hips, joints properly defined?
     * Construction elements to remove: Are there construction lines, guide circles, scribbles, rough marks that need removal?
     * Line quality issues: Are lines rough, inconsistent, or need refinement to final quality?
E) PRESERVE: list 2-3 items/gestures/styles that must be kept (e.g., “preserve right-hand gesture”, “keep sunglasses angle”).
F) Colour & background analysis: describe dominant line colour(s) and background (e.g., “blue line art on white background”) and whether they should be preserved.

Locks/levels:
- Pose lock: if true, keep pose/action; only fix anatomy.
- Style lock: if true, keep art style.
- Anatomical level (0-100): how strictly to correct anatomy.

Colour & background rules:
- Detect dominant line colour(s) and background colour. Be precise: distinguish pure white from light gray, pure black from dark gray.
- CRITICAL DISTINCTION: Background = canvas/paper area OUTSIDE the character boundaries. Character internal colors (clothing, skin, shading inside character) are NOT background.
- If the image has a white/light canvas area around the character, that is the BACKGROUND. Character's internal colors (crop top, shorts, skin tones, shading) are separate and should be preserved as-is if they exist.
- By default, PRESERVE the existing colour scheme (line colours + background) across phases, unless explicitly instructed otherwise.
- For phase upgrades, refine structure and cleanliness, not the colour scheme.
- For Roughs -> Colors, assume the same line/background colours in the final result unless notes clearly say otherwise.
- ALWAYS include at least one PRESERVE entry that explicitly states the colour scheme, e.g. “Preserve black line art on a pure white background (canvas area outside character, not character internal colors).”
- If background is pure white, explicitly note “pure white background (canvas/paper area), solid white, no gray tones, no shading in background area” to prevent SD from generating grayscale/shaded backgrounds.

Output JSON ONLY:
{
  "fixes": ["..."],
  "removes": ["..."],
  "preserve": ["..."],
  "notes": ["..."]
}
Keep it short, SD-friendly, and specific."""

DEFAULT_PROMPT_ENGINEER = """You are the Prompt Engineer (Strategist) for animation cleanup.

Input:
- report JSON: fixes[], removes[], notes[]
- dest_phase: Skeleton | Roughs | Tie Down | CleanUp | Colors
- Locks: pose_lock (keep pose), style_lock (keep art style)

Strategy:
- Positive Prompt: turn fixes into high-weight, specific SD-friendly terms targeted to dest_phase fidelity.
  * Skeleton: focus on posing and proportion; reduce volumes to simple construction and stick-figure lines; keep gesture and timing; DO NOT produce clean final shapes or perfect circles—embrace slightly rough structural lines. CRITICAL: explicitly add "line art only, no colors, no shading, no fills."
  * Roughs: gestural movement capture with some volumetric cues; looser than Skeleton but not fully on-model shapes. CRITICAL: explicitly add "line art only, no colors, no shading, no fills."
  * Tie Down: on-model shapes, defined forms, clean single lines (not ink-perfect), preserve intended gesture. CRITICAL: explicitly add "black line art only, no colors, no color fills, no shading, no gradients, line art style."
  * Cleanup: perfect smooth uniform linework on existing tie-down shapes. CRITICAL REQUIREMENTS: (1) Define proper anatomical shapes for all body parts - hands must have clear finger definition with proper palm structure, defined joints, and anatomically correct proportions; (2) Add proper face definition - clearly defined eyes, nose, mouth placement, facial structure, head shape, and facial features; (3) Add proper body volume - torso volume with defined chest and waist, limb thickness showing proper muscle structure, shoulders, hips, and joints properly defined; (4) Make all body parts precise - shoulders, elbows, wrists, knees, ankles, all joints clearly defined with proper anatomical structure; (5) Remove all construction lines, placeholder lines, guide circles, breast circles, anatomical guide marks, scribbles, rough marks, and all non-final lines; (6) Create smooth, uniform, final line art quality with consistent line weight. Explicitly add "pure black line art only, monochrome black lines, no colors whatsoever, no color fills, no shading, no gradients, no tints, no hues, no colored lines, line art style, black ink only, grayscale line art forbidden, defined hands with clear fingers and palm structure, proper face definition with eyes nose mouth, proper body volume with defined torso and limbs, precise anatomical body parts with clear joints, smooth uniform final line art quality."
  * Colors: fill character with colors inside all shapes, colorize entire character including skin tones on all visible skin areas, hair colors, clothing colors, accessory colors, fill all enclosed areas with appropriate colors, add vibrant colors to character body, fill skin areas with natural skin tones, colorize all skin regions including arms, legs, face, torso, fill background with colors, colorize background area, complete colorization of character and background, ensure all areas are filled with colors including skin, no empty white spaces inside character, no uncolored skin areas, full color fill for entire character, preserve line art integrity.
- Negative Prompt: removes + anything that would overshoot the phase.
  * Skeleton: block fully on-model final shapes, detailed volumetric rendering, perfect lineart, inked outlines, shading, colours, gradients, color fills, colored clothing, skin tones.
  * Tie Down: block rough sketch, messy/double/fuzzy lines, construction lines, dense scribbles, off-model anatomy, warped proportions, colored backgrounds if not wanted, "perfect crisp ink lines", "ultra-clean lineart". CRITICAL: also block "colors, color fills, shading, gradients, colored clothing, skin tones, fills inside lines, any colors except line art, 3D rendering, photorealistic shading."
  * Cleanup: block sketchiness, noise, color bleed, undefined body parts, missing anatomical details. CRITICAL: MUST aggressively block "construction lines, placeholder lines, guide circles, breast circles, anatomical guide marks, guide lines, reference lines, building block lines, volumetric guide lines, non-final lines, temporary lines, rough sketch quality, undefined hands, undefined fingers, missing palm structure, undefined face, missing facial features, undefined eyes, missing nose, missing mouth, undefined body volume, flat body parts, undefined joints, missing anatomical structure, undefined shoulders, undefined elbows, undefined wrists, undefined knees, undefined ankles, any colors, color fills, shading, gradients, colored clothing, skin tones, fills inside lines, colored lines, purple lines, pink lines, blue lines, red lines, any colored line art, grayscale lines, tinted lines, 3D rendering, photorealistic shading, realistic colors, colorized lines, non-black lines, any line color except pure black, scribbles, messy lines, rough lines, incomplete line art, unfinished drawing."
  * Colors: block rough sketch quality, messy lines, construction lines, off-model anatomy, warped proportions, line art degradation, broken lines, missing colors, colorless areas, empty white spaces inside character, unfilled areas, incomplete colorization, white spaces within character, transparent areas, uncolored regions, uncolored skin areas, white skin areas, uncolored body parts, uncolored arms, uncolored legs, uncolored face, uncolored torso, monochrome fill, grayscale fill.
- Respect locks: if pose_lock, do not change pose/action except minimal anatomical correction; if style_lock, preserve art style.
- Colour scheme:
  * Read from report.preserve/notes any mention of line colour and background colour.
  * CRITICAL: Background = canvas/paper area OUTSIDE character boundaries. Character internal colors (clothing, skin, shading inside character) are NOT background and should be preserved separately if they exist.
  * You MUST add an explicit phrase like “preserve blue line art on a white background (canvas area outside character)” in POSITIVE_PROMPT when a colour scheme is present.
  * For WHITE backgrounds: explicitly say “pure white background (canvas/paper area outside character), solid white background, no shading in background area, no grayscale in background, no gray tones in background” to prevent SD from confusing character internal colors with background.
  * For BLACK line art: explicitly say "pure black lines, solid black line art, monochrome black lines, no grayscale lines, no gray tones in lines, no colored lines, no purple lines, no pink lines, no blue lines, black ink only" to prevent SD from generating any colored or tinted lines.
  * CRITICAL: If dest_phase is NOT "Colors", then character internal colors (clothing, skin tones, shading) should be BLOCKED, not preserved. Only preserve line art color and background color. For non-Color phases, add to NEGATIVE_PROMPT: "colors, color fills, shading, gradients, colored clothing, skin tones, fills inside lines, 3D rendering, photorealistic shading."
  * If dest_phase IS "Colors", then fill character with colors AND colorize background: "fill character with colors inside all shapes, colorize entire character including skin tones on all visible skin areas, hair colors, clothing colors, accessory colors, fill all enclosed areas with appropriate colors, fill skin areas with natural skin tones, colorize all skin regions including arms, legs, face, torso, fill background with colors, colorize background area, complete colorization of character and background, ensure all areas are filled with colors including skin, no empty white spaces inside character, no uncolored skin areas, full color fill for entire character."
  * Do NOT recolour line art or background unless the notes clearly request a style/colour change.
  * In NEGATIVE_PROMPT, block unwanted recolouring such as “black ink lines, dark background” if they would change the original scheme.
  * ALWAYS block in NEGATIVE_PROMPT: "grayscale background, gray background, shaded background, monochrome background, light gray background, gray tones in background, gray shading in background area, purple lines, pink lines, blue lines, red lines, colored lines, tinted lines, any non-black line color" when the original background is pure white/black and line art is black. But DO NOT block character internal shading/colors if they exist in the original (only for Colors phase).
- Roughs -> Colors behaviour:
  * Treat this as a two-step process in one generation: first cleanup/define lines (as if doing Tie Down/Cleanup), then apply colours.
  * Encode this in the prompts: describe both the cleanup and the final coloured look, while preserving existing line/background colours.
- Rationale: briefly explain the intended edits so the diffusion model “knows what to fix” (e.g., “edit left hand to read as on-model animated character anatomy”).

Return EXACTLY in this format (one section per line, no extra prefixes):
POSITIVE_PROMPT: [your positive prompt text here, can be multiple lines]
NEGATIVE_PROMPT: [your negative prompt text here, can be multiple lines]
RATIONALE: [your rationale text here]

IMPORTANT: 
- Start each section with "POSITIVE_PROMPT:", "NEGATIVE_PROMPT:", or "RATIONALE:" followed by a colon and space
- The text after the colon is the actual prompt/rationale (can span multiple lines)
- Do NOT include "POSITIVE_PROMPT:" or "NEGATIVE_PROMPT:" prefix in the actual prompt text sent to ComfyUI
- Keep the structure consistent regardless of source/destination phase transition
"""


# ---------- Data Models ----------
@dataclass
class AnalysisConfig:
    source_phase: str
    dest_phase: str
    pose_lock: bool
    style_lock: bool
    anatomical_level: int
    master_instruction: str


# ---------- Helpers ----------
def _load_image_bytes(file) -> Tuple[bytes, str]:
    image = Image.open(file).convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue(), "image/png"


def _get_genai_client() -> Optional["genai.Client"]:
    # Prefer official GEMINI_API_KEY; fallback to GOOGLE_GENAI_API_KEY for compatibility.
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
    if not api_key or genai is None:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def _thinking_config():
    """Optional thinking budget from env (in tokens)."""
    try:
        budget = os.getenv("GEMINI_THINK_BUDGET")
        if budget is None:
            return None
        budget_val = int(budget)
        return genai_types.ThinkingConfig(thinking_budget=budget_val)
    except Exception:
        return None


def _parse_report_blob(blob: str) -> dict:
    """Try to parse JSON from a string, stripping code fences."""
    if not blob:
        return {}
    text = blob.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].strip()
    if text.lower().startswith("json"):
        text = text[4:].strip()
    try:
        import json

        return json.loads(text)
    except Exception:
        return {}


def normalize_report(report: dict) -> dict:
    """If structured fields are missing, but notes contain JSON, extract them."""
    if not isinstance(report, dict):
        return {}
    fixes = report.get("fixes") or []
    removes = report.get("removes") or []
    preserve = report.get("preserve") or []
    raw_notes = report.get("notes") or []
    cleaned_notes = []

    if isinstance(raw_notes, list):
        for n in raw_notes:
            if isinstance(n, str):
                parsed = _parse_report_blob(n)
                if parsed:
                    fixes = fixes or parsed.get("fixes", fixes)
                    removes = removes or parsed.get("removes", removes)
                    preserve = preserve or parsed.get("preserve", preserve)
                    extra_notes = parsed.get("notes")
                    if extra_notes:
                        if isinstance(extra_notes, list):
                            cleaned_notes.extend(extra_notes)
                        elif isinstance(extra_notes, str):
                            cleaned_notes.append(extra_notes)
                    # do not keep the raw JSON blob in cleaned notes
                    continue
            cleaned_notes.append(n)

    return {
        "fixes": fixes,
        "removes": removes,
        "preserve": preserve,
        "notes": cleaned_notes,
    }


def _generate_smart_fallback_prompts(
    source_phase: str, dest_phase: str, pose_lock: bool, style_lock: bool
) -> Tuple[str, str, str]:
    """Generate smart fallback prompts based on phase transition and locks."""
    # Phase-specific positive prompts
    phase_positives = {
        "Skeleton": "simple construction lines, stick-figure structure, posing and proportion focus, line art only, no colors, no shading",
        "Roughs": "gestural movement capture, loose volumetric shapes, building blocks, line art only, no colors, no shading",
        "Tie Down": "on-model shapes, defined forms, clean single lines, preserve intended gesture, black line art only, no colors, no shading, line art style",
        "CleanUp": "perfect smooth uniform linework, clean precise outlines, uniform line weight, defined hands with clear fingers and proper palm structure, proper face definition with eyes nose mouth and facial structure, proper body volume with defined torso and limb thickness showing muscle structure, precise anatomical body parts with clear joints including shoulders elbows wrists knees ankles, remove all construction lines, remove all placeholder lines, remove guide circles, remove breast circles, remove anatomical guide marks, remove all non-final lines, keep only final clean line art, pure black line art only, monochrome black lines, no colors whatsoever, no shading, line art style",
        "Colors": "fill character with colors inside all shapes, colorize entire character including skin tones on all visible skin areas, hair colors, clothing colors, accessory colors, fill all enclosed areas with appropriate colors, add vibrant colors to character body, fill skin areas with natural skin tones, colorize all skin regions including arms, legs, face, torso, fill background with colors, colorize background area, complete colorization of character and background, ensure all areas are filled with colors including skin, no empty white spaces inside character, no uncolored skin areas, full color fill for entire character",
    }
    
    # Phase-specific negative prompts
    phase_negatives = {
        "Skeleton": "fully on-model final shapes, detailed volumetric rendering, perfect lineart, inked outlines, shading, colours, gradients, color fills",
        "Roughs": "perfect lineart, inked outlines, shading, colours, gradients, color fills",
        "Tie Down": "rough sketch, messy lines, double lines, fuzzy lines, construction lines, dense scribbles, perfect crisp ink lines, ultra-clean lineart, colors, color fills, shading, gradients, colored clothing, skin tones, 3D rendering, photorealistic shading",
        "CleanUp": "sketchy lines, wobbly lines, rough lines, fuzzy lines, construction lines, placeholder lines, guide circles, breast circles, anatomical guide marks, guide lines, reference lines, building block lines, volumetric guide lines, overlapping strokes, inconsistent line weight, non-final lines, temporary lines, undefined hands, undefined fingers, missing palm structure, undefined face, missing facial features, undefined eyes, missing nose, missing mouth, undefined body volume, flat body parts, undefined joints, missing anatomical structure, undefined shoulders, undefined elbows, undefined wrists, undefined knees, undefined ankles, incomplete line art, unfinished drawing, colors, color fills, shading, gradients, colored clothing, skin tones, purple lines, pink lines, blue lines, any colored line art, non-black lines, 3D rendering, photorealistic shading",
        "Colors": "rough sketch, messy lines, construction lines, off-model anatomy, warped proportions, line art degradation, broken lines, missing colors, colorless areas, empty white spaces inside character, unfilled areas, monochrome fill, grayscale fill, incomplete colorization, white spaces within character, transparent areas, uncolored regions",
    }
    
    # Build positive prompt
    pos_parts = [phase_positives.get(dest_phase, "clean line art, defined forms")]
    
    # Add preservation based on locks
    if pose_lock:
        pos_parts.append("preserve character pose and motion, maintain gesture")
    if style_lock:
        pos_parts.append("preserve art style and proportions")
    
    # Preserve color scheme based on destination phase
    if dest_phase == "Colors":
        # Colors phase: preserve line art integrity, allow color fills for character AND background
        pos_parts.append("preserve existing line art, maintain line integrity, fill character with colors inside all shapes including skin tones on all visible skin areas, fill all skin regions with natural skin colors, fill background with colors, colorize entire image including character and background, ensure complete colorization of all areas including skin, no empty white spaces, no uncolored skin areas")
    else:
        # Non-Color phases: enforce black lines, white background, no colors
        pos_parts.append("pure black line art only, pure white background (canvas area outside character), no colors, no shading, no fills")
    
    # Build negative prompt
    neg_parts = [phase_negatives.get(dest_phase, "rough sketch, messy lines, construction lines")]
    
    # Block colors for non-Color phases only
    if dest_phase != "Colors":
        neg_parts.append("colors, color fills, shading, gradients, colored clothing, skin tones, fills inside lines, any colors except line art, 3D rendering, photorealistic shading, purple lines, pink lines, blue lines, any colored line art")
    else:
        # Colors phase: block rough sketch quality, empty spaces, incomplete colorization, uncolored skin
        neg_parts.append("rough sketch quality, messy lines, construction lines, off-model anatomy, warped proportions, line art degradation, broken lines, missing colors, colorless areas, empty white spaces inside character, unfilled areas, incomplete colorization, white spaces within character, transparent areas, uncolored regions, uncolored skin areas, white skin areas, uncolored body parts, uncolored arms, uncolored legs, uncolored face, uncolored torso")
    
    # Background handling: for Colors phase, allow colored backgrounds; for others, block grayscale
    if dest_phase == "Colors":
        # Colors phase: allow colored backgrounds, but block grayscale/monochrome backgrounds
        neg_parts.append("grayscale background, monochrome background, colorless background, empty background")
    else:
        # Non-Color phases: always block grayscale backgrounds
        neg_parts.append("grayscale background, gray background, shaded background, monochrome background, light gray background, gray tones in background")
    
    pos = ", ".join(pos_parts)
    neg = ", ".join(neg_parts)
    
    # Phase-specific rationale
    if dest_phase == "Colors":
        rationale = f"Fallback prompts for {source_phase} → {dest_phase} transition. Preserve pose: {pose_lock}, preserve style: {style_lock}. Add accurate color fills behind existing line art while maintaining line integrity and character structure."
    else:
        rationale = f"Fallback prompts for {source_phase} → {dest_phase} transition. Preserve pose: {pose_lock}, preserve style: {style_lock}. Focus on phase-appropriate cleanup while maintaining character structure."
    
    return pos, neg, rationale


def run_visual_analyst(image_bytes: bytes, mime: str, cfg: AnalysisConfig) -> dict:
    client = _get_genai_client()
    prompt = cfg.master_instruction.strip() or DEFAULT_ANALYST_PROMPT
    if not client:
        # Fallback mock if no key
        return {
            "fixes": [
                "anatomically correct left hand on steering wheel",
                "clear volumetric forearm and wrist",
                "on-model torso proportions",
                "defined facial plane"
            ],
            "removes": [
                "rough sketch",
                "messy lines",
                "construction lines",
                "dense scribbles"
            ],
            "preserve": [
                "preserve overall steering gesture",
                "maintain sunglasses angle"
            ],
            "notes": ["Mock output (no GOOGLE_GENAI_API_KEY set)"],
        }

    # Build multimodal content
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=mime)
    # Inject run-time config so the model knows the transition and constraints.
    config_block = f"""
SOURCE_PHASE: {cfg.source_phase}
DEST_PHASE: {cfg.dest_phase}
POSE_LOCK: {cfg.pose_lock}
STYLE_LOCK: {cfg.style_lock}
ANATOMICAL_LEVEL: {cfg.anatomical_level}
"""
    full_prompt = f"{prompt}\n\n{config_block}"
    # Follow Gemini docs: contents can be a mix of Parts and plain text strings.
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[image_part, full_prompt],
            config=genai_types.GenerateContentConfig(
                temperature=0.2,
                thinking_config=_thinking_config(),
            ),
        )
        text = response.text or ""
        # Naive extraction; expect the model to return JSON
        try:
            import json

            return json.loads(text)
        except Exception:
            return {"fixes": [], "removes": [], "notes": [text.strip()]}
    except Exception as exc:
        # Graceful degradation on overload/404/etc.
        st.warning(f"Gemini analyst fallback (error: {exc})")
        # Generate phase-appropriate fallback based on config
        phase_fixes = {
            "Skeleton": ["simplify to construction lines", "focus on posing and proportion"],
            "Roughs": ["capture gestural movement", "add volumetric building blocks"],
            "Tie Down": ["define on-model shapes", "clean up lines", "remove construction marks"],
            "CleanUp": ["smooth all lines to uniform weight", "remove sketchiness", "refine line quality", "remove construction lines", "remove placeholder lines", "remove guide circles"],
            "Colors": ["add accurate color fills", "preserve line integrity"],
        }
        phase_removes = {
            "Skeleton": ["detailed volumetric rendering", "perfect lineart", "shading", "colours"],
            "Roughs": ["perfect lineart", "shading", "colours"],
            "Tie Down": ["rough sketch", "messy lines", "construction lines", "dense scribbles", "colors", "shading"],
            "CleanUp": ["sketchy lines", "wobbly lines", "construction lines", "placeholder lines", "guide circles", "breast circles", "anatomical guide marks", "colors", "colored lines", "shading"],
            "Colors": ["rough sketch", "messy lines", "construction lines"],
        }
        return {
            "fixes": phase_fixes.get(cfg.dest_phase, ["refine shapes", "clean up lines"]),
            "removes": phase_removes.get(cfg.dest_phase, ["rough sketch", "messy lines"]),
            "preserve": [
                "preserve black line art on pure white background" if cfg.dest_phase != "Colors" else "preserve line art integrity",
                "preserve character pose and motion" if cfg.pose_lock else "preserve overall composition",
                "preserve art style and proportions" if cfg.style_lock else "preserve character design",
            ],
            "notes": [f"Fallback due to Gemini error: {exc}"],
        }


def run_prompt_engineer(report: dict, dest_phase: str, override: str, source_phase: str = "Roughs", pose_lock: bool = True, style_lock: bool = True) -> Tuple[str, str, str]:
    client = _get_genai_client()
    prompt = override.strip() or DEFAULT_PROMPT_ENGINEER
    if not client:
        # Use smart fallback
        pos, neg, rationale = _generate_smart_fallback_prompts(source_phase, dest_phase, pose_lock, style_lock)
        return pos, neg, rationale

    merged_prompt = f"""{prompt}

dest_phase: {dest_phase}
report: {report}
"""
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[merged_prompt],
            config=genai_types.GenerateContentConfig(
                temperature=0.3,
                thinking_config=_thinking_config(),
            ),
        )
        text = response.text or ""
        # Parse prompts with better handling for multi-line and consistent format
        pos, neg, rationale = "", "", ""
        lines = text.splitlines()
        current_section = None
        current_content = []
        
        for line in lines:
            line_lower = line.lower().strip()
            # Check for section headers
            if line_lower.startswith("positive_prompt"):
                # Save previous section if any
                if current_section == "pos" and current_content:
                    pos = "\n".join(current_content).strip()
                elif current_section == "neg" and current_content:
                    neg = "\n".join(current_content).strip()
                elif current_section == "rationale" and current_content:
                    rationale = "\n".join(current_content).strip()
                # Start new section
                current_section = "pos"
                current_content = []
                # Extract text after colon if present
                if ":" in line:
                    after_colon = line.split(":", 1)[-1].strip()
                    if after_colon:
                        current_content.append(after_colon)
            elif line_lower.startswith("negative_prompt"):
                # Save previous section
                if current_section == "pos" and current_content:
                    pos = "\n".join(current_content).strip()
                elif current_section == "neg" and current_content:
                    neg = "\n".join(current_content).strip()
                elif current_section == "rationale" and current_content:
                    rationale = "\n".join(current_content).strip()
                # Start new section
                current_section = "neg"
                current_content = []
                # Extract text after colon if present
                if ":" in line:
                    after_colon = line.split(":", 1)[-1].strip()
                    if after_colon:
                        current_content.append(after_colon)
            elif line_lower.startswith("rationale"):
                # Save previous section
                if current_section == "pos" and current_content:
                    pos = "\n".join(current_content).strip()
                elif current_section == "neg" and current_content:
                    neg = "\n".join(current_content).strip()
                elif current_section == "rationale" and current_content:
                    rationale = "\n".join(current_content).strip()
                # Start new section
                current_section = "rationale"
                current_content = []
                # Extract text after colon if present
                if ":" in line:
                    after_colon = line.split(":", 1)[-1].strip()
                    if after_colon:
                        current_content.append(after_colon)
            elif current_section and line.strip():
                # Continue current section (multi-line content)
                current_content.append(line.strip())
        
        # Save last section
        if current_section == "pos" and current_content:
            pos = "\n".join(current_content).strip()
        elif current_section == "neg" and current_content:
            neg = "\n".join(current_content).strip()
        elif current_section == "rationale" and current_content:
            rationale = "\n".join(current_content).strip()
        
        # Fallback: if no structured format found, try simple extraction
        if not pos and not neg:
            # Try old format as fallback
            for line in lines:
                if line.lower().startswith("positive_prompt"):
                    pos = line.split(":", 1)[-1].strip() if ":" in line else ""
                elif line.lower().startswith("negative_prompt"):
                    neg = line.split(":", 1)[-1].strip() if ":" in line else ""
                elif line.lower().startswith("rationale"):
                    rationale = line.split(":", 1)[-1].strip() if ":" in line else ""
        
        # Ensure we return clean prompts (no prefixes)
        pos = pos.strip() if pos else ""
        neg = neg.strip() if neg else ""
        rationale = rationale.strip() if rationale else ""
        
        return pos or text.strip(), neg, rationale
    except Exception as exc:
        st.warning(f"Gemini prompt-engineer fallback (error: {exc})")
        # Use smart fallback based on phase transition
        pos, neg, rationale = _generate_smart_fallback_prompts(source_phase, dest_phase, pose_lock, style_lock)
        return pos, neg, rationale


def call_comfyui(image_bytes: bytes, pos_prompt: str, neg_prompt: str, status_writer=None) -> Optional[bytes]:
    """
    Submit workflow to ComfyUI API (RunPod) and retrieve generated image.
    Uses workflow template from ANIMATION_M1_api_version.json (preferred, API format) or ANIMATION_M1.json (v11 format).
    """
    base_url = os.getenv("COMFYUI_API_URL", "").rstrip("/")
    if not base_url:
        if status_writer:
            status_writer.write("⚠️ COMFYUI_API_URL not set in environment")
        return None

    import json
    import time
    import uuid

    def log(msg):
        if status_writer:
            status_writer.write(msg)
        else:
            st.info(msg)

    try:
        # Step 1: Upload image to ComfyUI
        log("📤 Uploading image to ComfyUI...")
        upload_resp = requests.post(
            f"{base_url}/upload/image",
            files={"image": ("input.png", image_bytes, "image/png")},
            timeout=30,
        )
        upload_resp.raise_for_status()
        upload_data = upload_resp.json()
        uploaded_filename = upload_data.get("name")  # e.g., "input_abc123.png"
        if not uploaded_filename:
            st.error("ComfyUI upload failed: no filename returned")
            return None
        log(f"✅ Image uploaded: {uploaded_filename}")

        # Step 2: Load workflow template
        # Priority: 1) Server workflow URL, 2) Local files
        log("📋 Loading workflow template...")
        workflow = None
        workflow_source = None
        
        # Option 1: Try to fetch from server URL if provided
        workflow_url = os.getenv("COMFYUI_WORKFLOW_URL", "").strip()
        if workflow_url:
            log(f"🔍 Fetching workflow from URL: {workflow_url}")
            try:
                resp = requests.get(workflow_url, timeout=15)
                resp.raise_for_status()
                workflow = resp.json()
                workflow_source = f"Server URL: {workflow_url}"
                log(f"✅ Loaded workflow from server URL")
            except Exception as e:
                log(f"⚠️ Could not fetch from URL: {e}")
                log("📁 Falling back to local files...")
        
        # Option 2: Try to fetch from server file path (if server allows file access)
        if workflow is None:
            workflow_path_server = os.getenv("COMFYUI_WORKFLOW_PATH", "").strip()
            if workflow_path_server:
                log(f"🔍 Trying to fetch workflow from server path: {workflow_path_server}")
                try:
                    # Try common ComfyUI workflow endpoints
                    endpoints_to_try = [
                        f"{base_url}/view?filename={workflow_path_server}&type=workflow",
                        f"{base_url}/workflows/{workflow_path_server}",
                        f"{base_url}/api/workflow?filename={workflow_path_server}",
                    ]
                    
                    for endpoint in endpoints_to_try:
                        try:
                            resp = requests.get(endpoint, timeout=10)
                            if resp.status_code == 200:
                                content_type = resp.headers.get("content-type", "")
                                if "application/json" in content_type:
                                    workflow = resp.json()
                                    workflow_source = f"Server Path: {workflow_path_server}"
                                    log(f"✅ Loaded workflow from server path")
                                    break
                        except requests.exceptions.RequestException:
                            continue
                except Exception as e:
                    log(f"⚠️ Could not fetch from server path: {e}")
        
        # Option 3: Load from local files
        if workflow is None:
            workflow_path = None
            # Priority: API version (v10 format) first, then v11 format
            for path in ["ANIMATION_M1_api_version.json", "ANIMATION_M1.json"]:
                if os.path.exists(path):
                    workflow_path = path
                    break
            
            if workflow_path:
                log(f"📁 Loading from local file: {workflow_path}")
                with open(workflow_path, "r") as f:
                    workflow = json.load(f)
                workflow_source = f"Local: {workflow_path}"
            else:
                error_msg = (
                    "❌ ComfyUI workflow template not found.\n\n"
                    "**Options to fix:**\n"
                    "1. **Use server workflow URL**: Set `COMFYUI_WORKFLOW_URL` in .env\n"
                    "   Example: `COMFYUI_WORKFLOW_URL=https://your-server.com/workflow.json`\n\n"
                    "2. **Use server workflow path**: Set `COMFYUI_WORKFLOW_PATH` in .env\n"
                    "   Example: `COMFYUI_WORKFLOW_PATH=ANIMATION_M1.json`\n\n"
                    "3. **Use local file**: Place `ANIMATION_M1_api_version.json` or `ANIMATION_M1.json` in project root"
                )
                st.error(error_msg)
                return None
        
        if workflow_source:
            log(f"✅ Using template: {workflow_source}")

        # Step 3: Update workflow with prompts and image
        is_v11_format = "nodes" in workflow
        
        if is_v11_format:
            # v11 format - update nodes directly by ID
            log("📝 Updating v11 format workflow...")
            node_2_found = False
            node_3_found = False
            node_4_found = False
            
            for node in workflow["nodes"]:
                node_id = node.get("id")
                node_type = node.get("type")
                
                # Node 2: Positive prompt (CLIPTextEncode)
                if node_id == 2 and node_type == "CLIPTextEncode":
                    if "widgets_values" in node and len(node["widgets_values"]) > 0:
                        old_pos = node["widgets_values"][0][:50] if isinstance(node["widgets_values"][0], str) else ""
                        node["widgets_values"][0] = pos_prompt
                        log(f"✅ Updated positive prompt (was: {old_pos}...)")
                        node_2_found = True
                
                # Node 3: Negative prompt (CLIPTextEncode)
                elif node_id == 3 and node_type == "CLIPTextEncode":
                    if "widgets_values" in node and len(node["widgets_values"]) > 0:
                        old_neg = node["widgets_values"][0][:50] if isinstance(node["widgets_values"][0], str) else ""
                        node["widgets_values"][0] = neg_prompt
                        log(f"✅ Updated negative prompt (was: {old_neg}...)")
                        node_3_found = True
                
                # Node 4: LoadImage
                elif node_id == 4 and node_type == "LoadImage":
                    if "widgets_values" in node and len(node["widgets_values"]) > 0:
                        node["widgets_values"][0] = uploaded_filename
                        log(f"✅ Updated image filename: {uploaded_filename}")
                        node_4_found = True
            
            if not node_2_found:
                log("⚠️ Node 2 (positive prompt) not found in workflow")
            if not node_3_found:
                log("⚠️ Node 3 (negative prompt) not found in workflow")
            if not node_4_found:
                log("⚠️ Node 4 (LoadImage) not found in workflow")
            
            # For v11 format, we need to convert to v10 for API submission
            # ComfyUI API expects v10 format (flat dictionary)
            log("🔄 Converting v11 to v10 format for API submission...")
            v10_workflow = {}
            
            # Create a map of node_id -> node for quick lookup
            node_map = {str(node.get("id")): node for node in workflow["nodes"]}
            
            # Step 1: Create all nodes in v10 format (even if empty)
            for node in workflow["nodes"]:
                node_id = str(node.get("id"))
                node_type = node.get("type")
                v10_node = {
                    "class_type": node_type,
                    "inputs": {}
                }
                v10_workflow[node_id] = v10_node
            
            # Step 2: Process widgets_values to set static inputs
            for node in workflow["nodes"]:
                node_id = str(node.get("id"))
                node_type = node.get("type")
                v10_node = v10_workflow[node_id]
                
                if "widgets_values" in node:
                    widgets = node["widgets_values"]
                    
                    # CLIPTextEncode: text is first widget
                    if node_type == "CLIPTextEncode" and len(widgets) > 0:
                        v10_node["inputs"]["text"] = widgets[0]
                    
                    # LoadImage: image filename is first widget
                    elif node_type == "LoadImage" and len(widgets) > 0:
                        v10_node["inputs"]["image"] = widgets[0]
                    
                    # CheckpointLoaderSimple: ckpt_name is first widget
                    elif node_type == "CheckpointLoaderSimple" and len(widgets) > 0:
                        v10_node["inputs"]["ckpt_name"] = widgets[0]
                    
                    # KSampler: multiple inputs
                    elif node_type == "KSampler" and len(widgets) >= 7:
                        ksampler_inputs = ["seed", "control_after_generate", "steps", "cfg", "sampler_name", "scheduler", "denoise"]
                        for i, widget_val in enumerate(widgets[:7]):
                            if i < len(ksampler_inputs):
                                v10_node["inputs"][ksampler_inputs[i]] = widget_val
                    
                    # LineArtPreprocessor: mode and resolution
                    elif node_type == "LineArtPreprocessor" and len(widgets) >= 2:
                        v10_node["inputs"]["mode"] = widgets[0]
                        v10_node["inputs"]["resolution"] = widgets[1]
                    
                    # Canny: low_threshold and high_threshold
                    elif node_type == "Canny" and len(widgets) >= 2:
                        v10_node["inputs"]["low_threshold"] = widgets[0]
                        v10_node["inputs"]["high_threshold"] = widgets[1]
                    
                    # RemBGSession+: model and device
                    elif node_type == "RemBGSession+" and len(widgets) >= 2:
                        v10_node["inputs"]["model"] = widgets[0]
                        v10_node["inputs"]["device_mode"] = widgets[1]
                    
                    # SaveImage: filename_prefix
                    elif node_type == "SaveImage" and len(widgets) > 0:
                        v10_node["inputs"]["filename_prefix"] = widgets[0]
                    
                    # CR Multi-ControlNet Stack: complex widget handling
                    elif node_type == "CR Multi-ControlNet Stack" and len(widgets) > 0:
                        # This node has complex structure, handle basic case
                        pass  # Will be handled by links
            
            # Step 3: Process links array to set up all connections
            # Links format: [link_id, source_node_id, source_output, target_node_id, target_input, type]
            if "links" in workflow:
                for link in workflow["links"]:
                    if len(link) >= 6:
                        link_id = link[0]
                        source_id = str(link[1])
                        source_output = link[2]
                        target_id = str(link[3])
                        target_input_index = link[4]
                        link_type = link[5] if len(link) > 5 else None
                        
                        # Ensure both nodes exist
                        if source_id not in v10_workflow:
                            log(f"⚠️ Source node {source_id} not found in workflow")
                            continue
                        if target_id not in v10_workflow:
                            log(f"⚠️ Target node {target_id} not found in workflow")
                            continue
                        
                        # Find the target node's input name from the original v11 structure
                        target_node = node_map.get(target_id)
                        if target_node and "inputs" in target_node:
                            # Find which input corresponds to this link
                            # In v11, the "link" field in inputs is the link ID (link[0]), not source node ID
                            for inp in target_node["inputs"]:
                                if inp.get("link") == link_id:  # Match link ID (first element of link array)
                                    inp_name = inp.get("name")
                                    if inp_name:
                                        v10_workflow[target_id]["inputs"][inp_name] = [source_id, source_output]
                                        break
                        else:
                            # Fallback: try to infer input name from common patterns
                            target_node_type = v10_workflow[target_id]["class_type"]
                            # Try to get input name from the target node's structure
                            target_node = node_map.get(target_id)
                            if target_node and "inputs" in target_node:
                                # Try to match by input index
                                inputs_list = target_node["inputs"]
                                if target_input_index < len(inputs_list):
                                    inp = inputs_list[target_input_index]
                                    inp_name = inp.get("name")
                                    if inp_name:
                                        v10_workflow[target_id]["inputs"][inp_name] = [source_id, source_output]
                                        continue
                            
                            # Final fallback: common input names by node type and index
                            input_name_maps = {
                                "VAEEncode": {0: "pixels", 1: "vae"},
                                "VAEDecode": {0: "samples", 1: "vae"},
                                "KSampler": {0: "model", 1: "positive", 2: "negative", 3: "latent_image"},
                                "CLIPTextEncode": {0: "clip"},
                                "ImageRemoveBackground+": {0: "rembg_session", 1: "image"},
                                "SaveImage": {0: "images"},
                                "CR Apply Multi-ControlNet": {0: "base_positive", 1: "base_negative", 2: "controlnet_stack"},
                                "CR Multi-ControlNet Stack": {0: "image_1", 1: "image_2", 2: "image_3", 3: "controlnet_stack"},
                            }
                            if target_node_type in input_name_maps:
                                input_map = input_name_maps[target_node_type]
                                if target_input_index in input_map:
                                    v10_workflow[target_id]["inputs"][input_map[target_input_index]] = [source_id, source_output]
            
            # Step 4: Validate that all referenced nodes exist
            all_node_ids = set(v10_workflow.keys())
            referenced_node_ids = set()
            if "links" in workflow:
                for link in workflow["links"]:
                    if len(link) >= 4:
                        referenced_node_ids.add(str(link[1]))  # source
                        referenced_node_ids.add(str(link[3]))  # target
            
            missing_nodes = referenced_node_ids - all_node_ids
            if missing_nodes:
                log(f"⚠️ Warning: Links reference missing nodes: {missing_nodes}")
                # These might be link IDs, not node IDs - log for debugging
                log(f"   All converted node IDs: {sorted([int(n) for n in all_node_ids if n.isdigit()])}")
            
            workflow = v10_workflow
            log(f"✅ Converted v11 to v10 format ({len(v10_workflow)} nodes)")
        
        else:
            # v10 format - update directly
            log("📝 Updating v10 format workflow...")
            if "2" in workflow and workflow["2"].get("class_type") == "CLIPTextEncode":
                old_pos = workflow["2"]["inputs"].get("text", "")[:50]
                workflow["2"]["inputs"]["text"] = pos_prompt
                log(f"✅ Updated positive prompt (was: {old_pos}...)")
            else:
                log("⚠️ Node 2 (positive prompt) not found in workflow")
            
            if "3" in workflow and workflow["3"].get("class_type") == "CLIPTextEncode":
                old_neg = workflow["3"]["inputs"].get("text", "")[:50]
                workflow["3"]["inputs"]["text"] = neg_prompt
                log(f"✅ Updated negative prompt (was: {old_neg}...)")
            else:
                log("⚠️ Node 3 (negative prompt) not found in workflow")
            
            if "4" in workflow and workflow["4"].get("class_type") == "LoadImage":
                workflow["4"]["inputs"]["image"] = uploaded_filename
                log(f"✅ Updated image filename: {uploaded_filename}")
            else:
                log("⚠️ Node 4 (LoadImage) not found in workflow")
        
        log("✅ Workflow updated with prompts and image")

        # Step 4: Submit workflow
        log("🚀 Submitting workflow to ComfyUI...")
        prompt_id = str(uuid.uuid4())
        try:
            submit_resp = requests.post(
                f"{base_url}/prompt",
                json={"prompt": workflow, "client_id": prompt_id},
                timeout=30,
            )
            submit_resp.raise_for_status()
            submit_data = submit_resp.json()
            actual_prompt_id = submit_data.get("prompt_id")
            if not actual_prompt_id:
                st.error("ComfyUI submission failed: no prompt_id returned")
                st.json(submit_data)  # Debug output
                return None
            log(f"✅ Workflow submitted (ID: {actual_prompt_id[:8]}...)")
        except requests.exceptions.HTTPError as e:
            error_detail = "Unknown error"
            try:
                error_detail = submit_resp.json() if 'submit_resp' in locals() else str(e.response.text) if hasattr(e, 'response') else str(e)
            except:
                error_detail = str(e)
            st.error(f"ComfyUI API error (400 Bad Request): {error_detail}")
            st.json({"workflow_keys": list(workflow.keys())[:10]})  # Show first 10 node IDs
            return None

        # Step 5: Poll for completion (max 2 minutes)
        log("⏳ Waiting for generation (this may take 30-60 seconds)...")
        max_wait = 120
        poll_interval = 2
        elapsed = 0
        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval
            history_resp = requests.get(f"{base_url}/history/{actual_prompt_id}", timeout=10)
            history_resp.raise_for_status()
            history = history_resp.json()
            if actual_prompt_id in history:
                status = history[actual_prompt_id]
                if status.get("status", {}).get("completed", False):
                    log("✅ Generation complete! Downloading image...")
                    # Find output image filename
                    outputs = status.get("outputs", {})
                    for node_id, node_output in outputs.items():
                        if "images" in node_output:
                            for img_info in node_output["images"]:
                                filename = img_info.get("filename")
                                subfolder = img_info.get("subfolder", "")
                                if filename:
                                    # Step 6: Download generated image
                                    view_url = f"{base_url}/view"
                                    params = {"filename": filename}
                                    if subfolder:
                                        params["subfolder"] = subfolder
                                    img_resp = requests.get(view_url, params=params, timeout=30)
                                    img_resp.raise_for_status()
                                    log("✅ Image downloaded successfully!")
                                    return img_resp.content
                elif status.get("status", {}).get("error"):
                    error_msg = status.get("status", {}).get("error", "Unknown error")
                    st.error(f"ComfyUI generation error: {error_msg}")
                    return None
            if elapsed % 10 == 0:  # Update every 10 seconds
                log(f"⏳ Still processing... ({elapsed}s/{max_wait}s)")

        st.error("ComfyUI generation timeout (exceeded 2 minutes)")
        return None

    except requests.exceptions.RequestException as exc:
        error_msg = f"ComfyUI API error: {exc}"
        st.error(error_msg)
        if status_writer:
            status_writer.write(f"❌ {error_msg}")
        return None
    except Exception as exc:
        error_msg = f"ComfyUI call failed: {exc}"
        st.error(error_msg)
        if status_writer:
            status_writer.write(f"❌ {error_msg}")
        import traceback
        st.code(traceback.format_exc())  # Debug traceback
        return None


# ---------- Streamlit UI ----------
st.set_page_config(page_title="AI Animation Studio", page_icon="🎬", layout="wide")
st.title("AI Animation Studio Control Panel")

with st.sidebar:
    st.markdown("**Environment**")
    st.text_input("GOOGLE_GENAI_API_KEY", type="password", value=os.getenv("GOOGLE_GENAI_API_KEY", ""))
    comfy_url = st.text_input("COMFYUI_API_URL", value=os.getenv("COMFYUI_API_URL", "https://j9z3h3awdbe4rf-8188.proxy.runpod.net"))
    if comfy_url:
        st.caption(f"Using: {comfy_url}")
    st.markdown("**Workflow Template**")
    
    # Server workflow options
    with st.expander("🔧 Server Workflow (Optional)", expanded=False):
        st.caption("Use workflow saved on ComfyUI server")
        workflow_url_input = st.text_input(
            "Workflow URL (COMFYUI_WORKFLOW_URL)",
            value=os.getenv("COMFYUI_WORKFLOW_URL", ""),
            help="Full URL to workflow JSON file on server"
        )
        workflow_path_input = st.text_input(
            "Workflow Path (COMFYUI_WORKFLOW_PATH)",
            value=os.getenv("COMFYUI_WORKFLOW_PATH", ""),
            help="Filename/path of workflow on server (e.g., ANIMATION_M1.json)"
        )
        if workflow_url_input:
            os.environ["COMFYUI_WORKFLOW_URL"] = workflow_url_input
        if workflow_path_input:
            os.environ["COMFYUI_WORKFLOW_PATH"] = workflow_path_input
    
    # Local workflow files
    workflow_files = [f for f in os.listdir(".") if f.startswith("ANIMATION_M1") and f.endswith(".json")]
    if workflow_files:
        # Show priority order (API version first, then v11 format)
        priority_order = ["ANIMATION_M1_api_version.json", "ANIMATION_M1.json"]
        found_priority = [f for f in priority_order if f in workflow_files]
        if found_priority:
            st.caption(f"✅ Local: {found_priority[0]}")
            if len(found_priority) > 1:
                st.caption(f"Also: {found_priority[1]}")
        else:
            st.caption(f"Local files: {', '.join(workflow_files[:2])}")
    else:
        if not os.getenv("COMFYUI_WORKFLOW_URL") and not os.getenv("COMFYUI_WORKFLOW_PATH"):
            st.warning("No local workflow found. Use server workflow options above or place ANIMATION_M1_api_version.json in project root.")

# 1) Input & Upload
st.header("Input & Upload")
uploaded = st.file_uploader("Upload Rough Image", type=["png", "jpg", "jpeg"])
if uploaded:
    st.image(uploaded, caption="Preview")

col_src, col_dst = st.columns(2)
with col_src:
    source_phase = st.selectbox(
        "Source Phase",
        ["Skeleton", "Roughs", "Tie Down", "CleanUp", "Colors"],
        index=1,
    )
with col_dst:
    dest_phase = st.selectbox(
        "Destination Phase",
        ["Skeleton", "Roughs", "Tie Down", "CleanUp", "Colors"],
        index=2,
    )

# 2) Phase Configuration
st.header("Phase Configuration (LLM Analyst Control)")
col_lock1, col_lock2 = st.columns(2)
with col_lock1:
    pose_lock = st.checkbox("Motion / Pose Lock", value=True)
with col_lock2:
    style_lock = st.checkbox("Style / Artistic Lock", value=True)

anat_level = st.slider("Anatomical Correction Level", 0, 100, 70)
master_instruction = st.text_area(
    "LLM Master Instruction (advanced override)",
    value="",
    placeholder="Leave blank to use the default Master Prompt.",
)

# 3) Generation Control & Output
st.header("Generation")
generate = st.button("Generate Phase")
status_placeholder = st.empty()
img_placeholder = st.empty()

with st.expander("View Generated Prompts"):
    pos_box = st.empty()
    neg_box = st.empty()

if generate:
    if not uploaded:
        st.warning("Please upload an image first.")
    else:
        image_bytes, mime = _load_image_bytes(uploaded)
        cfg = AnalysisConfig(
            source_phase=source_phase,
            dest_phase=dest_phase,
            pose_lock=pose_lock,
            style_lock=style_lock,
            anatomical_level=anat_level,
            master_instruction=master_instruction,
        )

        with st.status("Processing...", expanded=True) as status:
            status.write("1) Running Visual Analyst (Gemini multimodal)...")
            raw_report = run_visual_analyst(image_bytes, mime, cfg)
            report = normalize_report(raw_report)

            status.write("2) Running Prompt Engineer (Gemini text)...")
            pos_prompt, neg_prompt, rationale = run_prompt_engineer(
                report, dest_phase, master_instruction, 
                source_phase=source_phase, 
                pose_lock=pose_lock, 
                style_lock=style_lock
            )

            status.write("3) Calling ComfyUI / KSampler...")
            generated_image = call_comfyui(image_bytes, pos_prompt, neg_prompt, status)

            status.update(label="Done", state="complete")

        with st.expander("Visual Analyst Report"):
            st.write("**Fixes**")
            st.code("\n".join(report.get("fixes", [])) or "N/A")
            st.write("**Removes**")
            st.code("\n".join(report.get("removes", [])) or "N/A")
            st.write("**Preserve**")
            st.code("\n".join(report.get("preserve", [])) or "N/A")
            # Highlight colour scheme if present in preserve/notes
            colour_lines = []
            for section in (report.get("preserve", []), report.get("notes", [])):
                for line in section:
                    if isinstance(line, str) and any(
                        key in line.lower()
                        for key in ["line art", "background", "colour", "color"]
                    ):
                        colour_lines.append(line)
            st.write("**Colour Scheme**")
            st.code("\n".join(colour_lines) or "N/A")
            st.write("**Notes**")
            st.code("\n".join(report.get("notes", [])) or "N/A")

        pos_box.code(pos_prompt or "N/A")
        neg_box.code(neg_prompt or "N/A")
        st.markdown("**Prompt Engineer Rationale**")
        st.info(rationale or "N/A")

        if generated_image:
            img_placeholder.image(generated_image, caption="Generated Output")
        else:
            img_placeholder.info("Image will appear here after backend wiring or when COMFYUI_API_URL is set.")

st.caption("Built with Streamlit + Gemini + ComfyUI. Configure API keys in the sidebar.")

