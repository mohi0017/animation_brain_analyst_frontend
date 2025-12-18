"""
Prompt Engineer Agent - Generate SD prompts from analysis report.
"""

from __future__ import annotations
from typing import Tuple
import streamlit as st

try:
    from google.genai import types as genai_types
except Exception:
    genai_types = None

from .config import DEFAULT_PROMPT_ENGINEER
from .gemini_client import get_genai_client, get_thinking_config, get_model_name


def generate_smart_fallback_prompts(
    source_phase: str, dest_phase: str, pose_lock: bool, style_lock: bool
) -> Tuple[str, str, str]:
    """
    Generate smart fallback prompts with proper SD weighting syntax.
    
    Args:
        source_phase: Source animation phase
        dest_phase: Destination animation phase
        pose_lock: Whether to preserve pose
        style_lock: Whether to preserve style
        
    Returns:
        Tuple of (positive_prompt, negative_prompt, rationale)
    """
    # Phase-specific positive prompts with SD weighting
    phase_positives = {
        "Skeleton": "1girl, (stick figure:1.2), (construction lines:1.1), gesture drawing, proportions study, (line art only:1.4), (outline only:1.3), transparent background, (no colors:1.4), (no shading:1.4), (no fills:1.4), (no rendering:1.3), simple forms, rough structural lines, pure linework, best quality, high resolution",
        "Roughs": "1girl, (gestural drawing:1.2), (movement lines:1.1), rough shapes, volumetric forms, (line art only:1.4), (outline only:1.3), transparent background, (no colors:1.4), (no shading:1.4), (no fills:1.4), (no rendering:1.3), loose sketch, dynamic motion, pure linework, best quality, high resolution",
        "Tie Down": "1girl, (clean lineart:1.3), (defined shapes:1.2), on-model character, (single lines:1.2), consistent proportions, (line art only:1.4), (outline only:1.3), transparent background, (no color fills:1.4), (no shading:1.4), (no fills:1.4), (no rendering:1.3), animation frame, professional line art, pure linework, (masterpiece:1.1), best quality, (high resolution:1.1), (crisp edges:1.1)",
        "CleanUp": "1girl, (clean lineart:1.4), (vector style:1.2), (professional inking:1.2), (crisp edges:1.2), (uniform line weight:1.2), (line art only:1.4), (outline only:1.4), (pure linework:1.3), (perfectly drawn face:1.3), (beautiful clear face:1.3), (sharp anime eyes:1.3), (anatomically correct hands:1.3), (clear facial features:1.2), (proper fingers:1.2), (five fingers:1.2), (palm structure:1.2), (defined face:1.2), (visible eyes:1.2), (visible nose:1.1), (visible mouth:1.1), (body volume:1.2), (defined torso:1.1), (muscle structure:1.1), (clear joints:1.2), (hand-drawn feel:1.1), transparent background, (no colors:1.4), (no shading:1.4), (no fills:1.4), (no rendering:1.4), (no gradients:1.4), (minimalist:1.1), animation cel, final line art, black ink on transparent, (masterpiece:1.2), best quality, (high resolution:1.2), (professional animation:1.1)",
        "Colors": "1girl, (flat color:1.2), (vibrant anime palette:1.2), (detailed cel shading:1.2), (full character colorization:1.3), (skin tones:1.2), (colored clothing:1.2), hair color, (filled shapes:1.2), (complete coloring:1.2), (no empty areas:1.1), transparent background, (clean line art:1.1), digital art, animation cel, (masterpiece:1.2), best quality, (high quality render:1.1), (8k:1.1)",
    }
    
    # Phase-specific negative prompts with SD weighting
    phase_negatives = {
        "Skeleton": "(detailed anatomy:1.3), (perfect lineart:1.3), (clean lines:1.2), (inked outlines:1.2), (shading:1.4), (colors:1.4), (gradients:1.4), (filled shapes:1.4), (soft rendering:1.4), (tonal values:1.3), (cel shading:1.3), (volume rendering:1.3), white background, gray background, colored background, (canvas:1.2), (paper texture:1.2), 3D rendering",
        "Roughs": "(perfect lineart:1.3), (clean edges:1.2), (polished:1.2), (inked:1.2), (shading:1.4), (colors:1.4), (gradients:1.4), (filled shapes:1.4), (soft rendering:1.4), (tonal values:1.3), (cel shading:1.3), (rendered forms:1.3), white background, gray background, (canvas:1.2), 3D rendering",
        "Tie Down": "(rough sketch:1.3), (messy lines:1.3), (double lines:1.2), (fuzzy lines:1.2), (construction lines:1.3), (scribbles:1.2), (perfect ink:1.1), (ultra-clean:1.1), (colors:1.4), (shading:1.4), (gradients:1.4), (filled shapes:1.4), (soft rendering:1.4), (tonal values:1.3), (cel shading:1.3), (volume rendering:1.3), (shaded forms:1.3), white background, (canvas:1.2), 3D rendering",
        "CleanUp": "worst quality, low quality, (blurry:1.3), (noise:1.3), (artifacts:1.2), (sketchy:1.3), (rough lines:1.3), (messy:1.3), (construction lines:1.4), (placeholder lines:1.3), (guide circles:1.3), (breast circles:1.3), (guide marks:1.3), (double lines:1.2), (fuzzy:1.2), (deformed face:1.4), (messy hands:1.3), (fused fingers:1.3), (facial distortion:1.3), (undefined hands:1.3), (undefined fingers:1.3), (missing palm:1.2), (undefined face:1.4), (missing eyes:1.3), (missing nose:1.2), (flat body:1.2), (undefined joints:1.2), (extra fingers:1.3), (fewer digits:1.3), bad anatomy, bad hands, (colors:1.4), (shading:1.4), (gradients:1.4), (filled shapes:1.4), (soft rendering:1.4), (soft shading:1.4), (tonal values:1.4), (cel shading:1.4), (volume rendering:1.4), (rendered forms:1.4), (form shading:1.4), (airbrushed:1.3), (smooth gradients:1.4), (color fills:1.4), (painted:1.3), (colored lines:1.3), (purple lines:1.2), (pink lines:1.2), (blue lines:1.2), (gray tones:1.3), white background, gray background, (canvas:1.3), (paper:1.2), text, watermark, signature, deformed, extra limbs, 3D rendering, photorealistic",
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
        neg_parts.append("(colors:1.4), (color fills:1.4), (shading:1.4), (gradients:1.4), (filled shapes:1.4), (soft shading:1.4), (soft rendering:1.4), (tonal values:1.4), (cel shading:1.4), (volume rendering:1.4), (colored clothing:1.3), (skin tones:1.3), (fills inside lines:1.4), (painted:1.3), (airbrushed:1.3), (3D rendering:1.3), (photorealistic shading:1.3), (form shading:1.4)")
    
    pos = ", ".join(pos_parts)
    neg = ", ".join(neg_parts)
    
    # Phase-specific rationale
    rationale = f"Fallback prompts for {source_phase} → {dest_phase} transition using SD weighting syntax. Preserve pose: {pose_lock}, preserve style: {style_lock}."
    
    return pos, neg, rationale


def run_prompt_engineer(
    report: dict, 
    dest_phase: str, 
    override: str, 
    source_phase: str = "Roughs", 
    pose_lock: bool = True, 
    style_lock: bool = True
) -> Tuple[str, str, str]:
    """
    Run Prompt Engineer agent to generate SD prompts.
    
    Args:
        report: Analysis report from Visual Analyst
        dest_phase: Destination animation phase
        override: Custom prompt override (if any)
        source_phase: Source animation phase
        pose_lock: Whether to preserve pose
        style_lock: Whether to preserve style
        
    Returns:
        Tuple of (positive_prompt, negative_prompt, rationale)
    """
    client = get_genai_client()
    prompt = override.strip() or DEFAULT_PROMPT_ENGINEER
    
    if not client:
        # Use smart fallback
        return generate_smart_fallback_prompts(source_phase, dest_phase, pose_lock, style_lock)

    merged_prompt = f"""{prompt}

dest_phase: {dest_phase}
report: {report}
"""
    model_name = get_model_name()
    
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[merged_prompt],
            config=genai_types.GenerateContentConfig(
                temperature=0.3,
                thinking_config=get_thinking_config(),
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
        return generate_smart_fallback_prompts(source_phase, dest_phase, pose_lock, style_lock)

