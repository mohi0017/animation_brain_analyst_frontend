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
- CRITICAL: All phases must generate TRANSPARENT BACKGROUND. No canvas, no background, only character shapes with original ink color.
- By default, PRESERVE the existing line colour (ink color) across phases, unless explicitly instructed otherwise.
- For phase upgrades, refine structure and cleanliness, preserve the original ink color.
- ALWAYS include at least one PRESERVE entry that explicitly states: "Preserve original ink color, transparent background, no canvas, no background, only character shapes."
- Background must be completely transparent - no white, no gray, no colored backgrounds, only transparent alpha channel.

Output JSON ONLY:
{
  "fixes": ["..."],
  "removes": ["..."],
  "preserve": ["..."],
  "notes": ["..."]
}
Keep it short, SD-friendly, and specific."""

DEFAULT_PROMPT_ENGINEER = """You are the Prompt Engineer (Strategist) for animation cleanup using Stable Diffusion.

Input:
- report JSON: fixes[], removes[], notes[]
- dest_phase: Skeleton | Roughs | Tie Down | CleanUp | Colors
- Locks: pose_lock (keep pose), style_lock (keep art style)

CRITICAL RULES - Stable Diffusion Prompting Syntax:
1. Use COMMA-SEPARATED KEYWORDS, not sentences
2. Apply WEIGHTING SYNTAX for emphasis: (keyword:weight) where 1.0=normal, 1.1-1.4=strong, 0.5-0.9=weak
3. Follow HIERARCHICAL STRUCTURE: [Subject] + [Action/Pose] + [Style/Detail] + [Environment] + [Quality Modifiers]
4. Use TECHNICAL TERMS for cleanup work, not creative descriptions
5. NEGATIVE PROMPTS are MORE IMPORTANT than positive for cleanup work

Phase-Specific Prompt Patterns (Use these comma-separated keyword structures):

** SKELETON PHASE **
Positive Pattern: [subject], [simple pose], (stick figure:1.2), (construction lines:1.1), gesture drawing, proportions study, (line art only:1.3), transparent background, (no colors:1.2), (no shading:1.2), simple forms, rough structural lines
Quality: best quality, high resolution
Negative Pattern: (detailed anatomy:1.3), (perfect lineart:1.3), (clean lines:1.2), (inked outlines:1.2), (shading:1.3), (colors:1.3), (gradients:1.2), white background, gray background, colored background, (canvas:1.2), (paper texture:1.2), volumetric rendering

** ROUGHS PHASE **
Positive Pattern: [subject], [action/pose], (gestural drawing:1.2), (movement lines:1.1), rough shapes, volumetric forms, (line art only:1.3), transparent background, (no colors:1.2), (no shading:1.2), loose sketch, dynamic motion
Quality: best quality, high resolution
Negative Pattern: (perfect lineart:1.3), (clean edges:1.2), (polished:1.2), (inked:1.2), (shading:1.3), (colors:1.3), white background, gray background, (canvas:1.2), detailed rendering

** TIE DOWN PHASE **
Positive Pattern: [subject], [preserved pose], (clean lineart:1.2), (defined shapes:1.2), on-model character, (single lines:1.1), consistent proportions, [ink color] lines, transparent background, (no color fills:1.3), (no shading:1.2), animation frame, professional line art
Quality: (masterpiece:1.1), best quality, (high resolution:1.1), (crisp edges:1.1)
Negative Pattern: (rough sketch:1.3), (messy lines:1.3), (double lines:1.2), (fuzzy lines:1.2), (construction lines:1.3), (scribbles:1.2), (perfect ink:1.1), (ultra-clean:1.1), (colors:1.3), (shading:1.3), (gradients:1.2), white background, (canvas:1.2), 3D rendering

** CLEANUP PHASE **
Positive Pattern: [subject], [preserved pose], (clean lineart:1.3), (vector style:1.2), (solid black lines:1.2), (professional inking:1.2), (crisp edges:1.2), (uniform line weight:1.2), (perfectly drawn face:1.3), (beautiful clear face:1.3), (sharp anime eyes:1.3), (anatomically correct hands:1.3), (clear facial features:1.2), (proper fingers:1.2), (five fingers:1.2), (palm structure:1.2), (defined face:1.2), (visible eyes:1.2), (visible nose:1.1), (visible mouth:1.1), (facial structure:1.2), (body volume:1.2), (defined torso:1.1), (muscle structure:1.1), (clear joints:1.2), (hand-drawn feel:1.1), transparent background, (no colors:1.3), (no shading:1.3), (minimalist:1.1), animation cel, final line art
Quality: (masterpiece:1.2), best quality, (high resolution:1.2), (professional animation:1.1)
ANATOMY CORRECTION (for rough sketches): (anatomically correct:1.3), (proper proportions:1.2), (correct anatomy:1.2)
Negative Pattern: worst quality, low quality, (blurry:1.3), (noise:1.3), (artifacts:1.2), (sketchy:1.3), (rough lines:1.3), (messy:1.3), (construction lines:1.4), (placeholder lines:1.3), (guide circles:1.3), (breast circles:1.3), (guide marks:1.3), (double lines:1.2), (fuzzy:1.2), (deformed face:1.4), (messy hands:1.3), (fused fingers:1.3), (facial distortion:1.3), (undefined hands:1.3), (undefined fingers:1.3), (missing palm:1.2), (undefined face:1.4), (missing eyes:1.3), (missing nose:1.2), (flat body:1.2), (undefined joints:1.2), (extra fingers:1.3), (fewer digits:1.3), bad anatomy, bad hands, (colors:1.4), (shading:1.4), (gradients:1.3), (colored lines:1.3), (purple lines:1.2), (pink lines:1.2), (blue lines:1.2), white background, gray background, (canvas:1.3), (paper:1.2), text, watermark, signature, deformed, extra limbs

** COLORS PHASE **
Positive Pattern: [subject], [preserved pose], (flat color:1.2), (vibrant anime palette:1.2), (detailed cel shading:1.2), (full character colorization:1.3), (skin tones:1.2), (colored clothing:1.2), (hair color:1.1), (filled shapes:1.2), (complete coloring:1.2), (no empty areas:1.1), transparent background, (clean line art:1.1), digital art, animation cel
Quality: (masterpiece:1.2), best quality, (high quality render:1.1), (8k:1.1)
Negative Pattern: (rough sketch:1.3), (messy lines:1.2), (construction lines:1.3), (incomplete coloring:1.4), (colorless areas:1.3), (white spaces:1.3), (unfilled areas:1.3), (uncolored skin:1.3), (monochrome:1.3), (grayscale:1.2), (missing colors:1.3), white background, colored background, (canvas:1.2), (line degradation:1.2), broken lines

General Rules:
- ALWAYS use weighting (keyword:weight) for critical features
- Add quality modifiers: (masterpiece:1.1-1.2), best quality, high resolution
- For pose_lock: add (preserve pose:1.2), (maintain gesture:1.1)
- For style_lock: add (preserve art style:1.2), (consistent design:1.1)
- Transparent background: ALWAYS add "transparent background" in positive and block "white background, gray background, colored background, canvas, paper" with (keyword:1.2-1.3) in negative
- Use anatomical terms from report.fixes with (keyword:1.1-1.2) weighting

CONTROLNET + HIGH DENOISE STRATEGY (Denoise=1.0, ControlNet Ending Steps optimized):
- Since ControlNet locks MOTION/POSE (Lineart ending=0.7, Canny ending=0.6), focus prompts on MATERIALS and QUALITY, not action words
- For anatomy correction: Use HIGH WEIGHTS for face/hands: (perfectly drawn face:1.3), (anatomically correct hands:1.3), (sharp anime eyes:1.3)
- ControlNet releases control at 70% for Lineart and 60% for Canny, so AI will use last 30-40% steps to fix anatomy based on prompt weights
- Material focus: Describe ink quality, line texture, surface details, NOT running/jumping/motion (ControlNet already locked that)
- Add (hand-drawn feel:1.1) for natural look despite ControlNet rigidity
- CFG Scale optimized to 7.5 (not 8.9) to balance ControlNet strength with prompt creativity

Return EXACTLY in this format (comma-separated keywords, NOT sentences):
POSITIVE_PROMPT: [comma-separated keywords with weights]
NEGATIVE_PROMPT: [comma-separated keywords with weights]
RATIONALE: [brief technical explanation]

IMPORTANT: 
- Use comma-separated keywords, NOT full sentences
- Apply weighting syntax: (keyword:weight) appropriately
- Start each section with the label followed by colon
- Keep keywords technical and specific
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
    """Generate smart fallback prompts with proper SD weighting syntax."""
    # Phase-specific positive prompts with SD weighting
    phase_positives = {
        "Skeleton": "1girl, (stick figure:1.2), (construction lines:1.1), gesture drawing, proportions study, (line art only:1.3), transparent background, (no colors:1.2), (no shading:1.2), simple forms, rough structural lines, best quality, high resolution",
        "Roughs": "1girl, (gestural drawing:1.2), (movement lines:1.1), rough shapes, volumetric forms, (line art only:1.3), transparent background, (no colors:1.2), (no shading:1.2), loose sketch, dynamic motion, best quality, high resolution",
        "Tie Down": "1girl, (clean lineart:1.2), (defined shapes:1.2), on-model character, (single lines:1.1), consistent proportions, transparent background, (no color fills:1.3), (no shading:1.2), animation frame, professional line art, (masterpiece:1.1), best quality, (high resolution:1.1), (crisp edges:1.1)",
        "CleanUp": "1girl, (clean lineart:1.3), (vector style:1.2), (professional inking:1.2), (crisp edges:1.2), (uniform line weight:1.2), (perfectly drawn face:1.3), (beautiful clear face:1.3), (sharp anime eyes:1.3), (anatomically correct hands:1.3), (clear facial features:1.2), (proper fingers:1.2), (five fingers:1.2), (palm structure:1.2), (defined face:1.2), (visible eyes:1.2), (visible nose:1.1), (visible mouth:1.1), (body volume:1.2), (defined torso:1.1), (muscle structure:1.1), (clear joints:1.2), (hand-drawn feel:1.1), transparent background, (no colors:1.3), (no shading:1.3), (minimalist:1.1), animation cel, final line art, (masterpiece:1.2), best quality, (high resolution:1.2), (professional animation:1.1)",
        "Colors": "1girl, (flat color:1.2), (vibrant anime palette:1.2), (detailed cel shading:1.2), (full character colorization:1.3), (skin tones:1.2), (colored clothing:1.2), hair color, (filled shapes:1.2), (complete coloring:1.2), (no empty areas:1.1), transparent background, (clean line art:1.1), digital art, animation cel, (masterpiece:1.2), best quality, (high quality render:1.1), (8k:1.1)",
    }
    
    # Phase-specific negative prompts with SD weighting
    phase_negatives = {
        "Skeleton": "(detailed anatomy:1.3), (perfect lineart:1.3), (clean lines:1.2), (inked outlines:1.2), (shading:1.3), (colors:1.3), (gradients:1.2), white background, gray background, colored background, (canvas:1.2), (paper texture:1.2), volumetric rendering",
        "Roughs": "(perfect lineart:1.3), (clean edges:1.2), (polished:1.2), (inked:1.2), (shading:1.3), (colors:1.3), white background, gray background, (canvas:1.2), detailed rendering",
        "Tie Down": "(rough sketch:1.3), (messy lines:1.3), (double lines:1.2), (fuzzy lines:1.2), (construction lines:1.3), (scribbles:1.2), (perfect ink:1.1), (ultra-clean:1.1), (colors:1.3), (shading:1.3), (gradients:1.2), white background, (canvas:1.2), 3D rendering",
        "CleanUp": "worst quality, low quality, (blurry:1.3), (noise:1.3), (artifacts:1.2), (sketchy:1.3), (rough lines:1.3), (messy:1.3), (construction lines:1.4), (placeholder lines:1.3), (guide circles:1.3), (breast circles:1.3), (guide marks:1.3), (double lines:1.2), (fuzzy:1.2), (deformed face:1.4), (messy hands:1.3), (fused fingers:1.3), (facial distortion:1.3), (undefined hands:1.3), (undefined fingers:1.3), (missing palm:1.2), (undefined face:1.4), (missing eyes:1.3), (missing nose:1.2), (flat body:1.2), (undefined joints:1.2), (extra fingers:1.3), (fewer digits:1.3), bad anatomy, bad hands, (colors:1.4), (shading:1.4), (gradients:1.3), (colored lines:1.3), (purple lines:1.2), (pink lines:1.2), (blue lines:1.2), white background, gray background, (canvas:1.3), (paper:1.2), text, watermark, signature, deformed, extra limbs",
        "Colors": "(rough sketch:1.3), (messy lines:1.2), (construction lines:1.3), (incomplete coloring:1.4), (colorless areas:1.3), (white spaces:1.3), (unfilled areas:1.3), (uncolored skin:1.3), (monochrome:1.3), (grayscale:1.2), (missing colors:1.3), white background, colored background, (canvas:1.2), (line degradation:1.2), broken lines",
    }
    
    # Build positive prompt
    pos_parts = [phase_positives.get(dest_phase, "(clean line art:1.2), (defined forms:1.1)")]
    
    # Add preservation based on locks with weighting
    if pose_lock:
        pos_parts.append("(preserve pose:1.2), (maintain gesture:1.1)")
    if style_lock:
        pos_parts.append("(preserve art style:1.2), (consistent design:1.1)")
    
    # Build negative prompt
    neg_parts = [phase_negatives.get(dest_phase, "(rough sketch:1.2), (messy lines:1.2), (construction lines:1.3)")]
    
    # Additional phase-specific negative blocks with weighting
    if dest_phase != "Colors":
        neg_parts.append("(colors:1.3), (color fills:1.3), (shading:1.3), (gradients:1.2), (colored clothing:1.2), (skin tones:1.2), (fills inside lines:1.2), (3D rendering:1.2), (photorealistic shading:1.2)")
    
    pos = ", ".join(pos_parts)
    neg = ", ".join(neg_parts)
    
    # Phase-specific rationale
    rationale = f"Fallback prompts for {source_phase} → {dest_phase} transition using SD weighting syntax. Preserve pose: {pose_lock}, preserve style: {style_lock}."
    
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


def call_comfyui(image_bytes: bytes, pos_prompt: str, neg_prompt: str, status_writer=None) -> Optional[Tuple[bytes, bytes]]:
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
                    log("✅ Generation complete! Downloading images...")
                    # Find output images from both SaveImage nodes (42: transparent, 54: original)
                    outputs = status.get("outputs", {})
                    transparent_image = None
                    original_image = None
                    
                    # Node 42: ImageRemoveBackground+ output (transparent background)
                    if "42" in outputs and "images" in outputs["42"]:
                        for img_info in outputs["42"]["images"]:
                            filename = img_info.get("filename")
                            subfolder = img_info.get("subfolder", "")
                            if filename:
                                view_url = f"{base_url}/view"
                                params = {"filename": filename}
                                if subfolder:
                                    params["subfolder"] = subfolder
                                img_resp = requests.get(view_url, params=params, timeout=30)
                                img_resp.raise_for_status()
                                transparent_image = img_resp.content
                                log("✅ Transparent background image downloaded (Node 42)")
                                break
                    
                    # Node 54: VAEDecode output (original with background)
                    if "54" in outputs and "images" in outputs["54"]:
                        for img_info in outputs["54"]["images"]:
                            filename = img_info.get("filename")
                            subfolder = img_info.get("subfolder", "")
                            if filename:
                                view_url = f"{base_url}/view"
                                params = {"filename": filename}
                                if subfolder:
                                    params["subfolder"] = subfolder
                                img_resp = requests.get(view_url, params=params, timeout=30)
                                img_resp.raise_for_status()
                                original_image = img_resp.content
                                log("✅ Original image downloaded (Node 54)")
                                break
                    
                    # Return both images (transparent first, original second)
                    if transparent_image and original_image:
                        log("✅ Both images downloaded successfully!")
                        return (transparent_image, original_image)
                    elif transparent_image:
                        log("⚠️ Only transparent image found, using it for both")
                        return (transparent_image, transparent_image)
                    elif original_image:
                        log("⚠️ Only original image found, using it for both")
                        return (original_image, original_image)
                    else:
                        # Fallback: try to get any image
                        for node_id, node_output in outputs.items():
                            if "images" in node_output:
                                for img_info in node_output["images"]:
                                    filename = img_info.get("filename")
                                    subfolder = img_info.get("subfolder", "")
                                    if filename:
                                        view_url = f"{base_url}/view"
                                        params = {"filename": filename}
                                        if subfolder:
                                            params["subfolder"] = subfolder
                                        img_resp = requests.get(view_url, params=params, timeout=30)
                                        img_resp.raise_for_status()
                                        log(f"✅ Image downloaded from node {node_id}")
                                        return (img_resp.content, img_resp.content)
                        st.error("No output images found in ComfyUI response")
                        return None
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
            # generated_image is now a tuple: (transparent_image, original_image)
            img_placeholder.empty()  # Clear placeholder
            if isinstance(generated_image, tuple) and len(generated_image) == 2:
                transparent_img, original_img = generated_image
                # Display both images side by side
                st.markdown("### Generated Outputs")
                col1, col2 = st.columns(2)
                with col1:
                    st.image(transparent_img, caption="🟢 Transparent Background (Node 42 - ImageRemoveBackground+)", use_container_width=True)
                with col2:
                    st.image(original_img, caption="🔵 Original with Background (Node 54 - VAEDecode)", use_container_width=True)
            else:
                # Fallback for single image (backward compatibility)
                img_placeholder.image(generated_image, caption="Generated Output")
        else:
            img_placeholder.info("Image will appear here after backend wiring or when COMFYUI_API_URL is set.")

st.caption("Built with Streamlit + Gemini + ComfyUI. Configure API keys in the sidebar.")

