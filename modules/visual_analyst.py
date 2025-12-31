"""
Visual Analyst Agent - Multi-modal image analysis using Gemini.
"""

from __future__ import annotations
from typing import Optional
import streamlit as st

try:
    from google.genai import types as genai_types
except Exception:
    genai_types = None

from .config import AnalysisConfig, DEFAULT_ANALYST_PROMPT_M2
from .gemini_client import get_genai_client, get_thinking_config, get_model_name
from .utils import get_logger, parse_report_blob

logger = get_logger("visual_analyst")


def run_visual_analyst_m2(
    image_bytes: bytes,
    mime: str,
    cfg: AnalysisConfig,
    reference_bytes: Optional[bytes] = None,
    reference_mime: Optional[str] = None,
) -> dict:
    """
    Run Visual Analyst for M2 using input + reference image.
    
    Returns:
        Analysis report dictionary with fixes/removes/preserve + style keywords.
    """
    client = get_genai_client()
    prompt = DEFAULT_ANALYST_PROMPT_M2.strip()

    if not client:
        # Fallback mock if no key
        return {
            "fixes": [],
            "removes": [],
            "preserve": [],
            "notes": ["Analysis unavailable: missing API key"],
            "subject_details": "",
            "phase_goal": f"{cfg.source_phase} to {cfg.dest_phase}",
            "line_quality": "",
            "anatomy_risk": "",
            "complexity": "",
            "reference_quality": "none",
        }

    model_name = get_model_name()
    image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=mime)
    
    contents = [image_part]
    
    # Add reference image if available
    if reference_bytes:
        ref_part = genai_types.Part.from_bytes(data=reference_bytes, mime_type=reference_mime or "image/png")
        contents.append(ref_part)
        prompt += "\n\n(Note: The second image provided is the REFERENCE image)"

    config_block = f"""
SOURCE_PHASE: {cfg.source_phase}
DEST_PHASE: {cfg.dest_phase}
POSE_LOCK: {cfg.pose_lock}
STYLE_LOCK: {cfg.style_lock}
ANATOMICAL_LEVEL: {cfg.anatomical_level}
"""
    full_prompt = f"{prompt}\n\n{config_block}"
    contents.append(full_prompt)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                temperature=0.2,
                thinking_config=get_thinking_config(),
            ),
        )
        text = response.text or ""
        logger.info(f"Visual analyst response received ({len(text)} chars)")
        
        parsed = parse_report_blob(text)
        if parsed:
            return parsed
        
        logger.warning("Failed to parse JSON from analyst response, returning raw notes")
        return {"fixes": [], "removes": [], "notes": [text.strip()]}

    except Exception as exc:
        logger.error(f"Gemini analyst fallback (error: {exc})")
        st.warning(f"Gemini analyst fallback (error: {exc})")
        return {
            "fixes": [],
            "removes": [],
            "preserve": [],
            "notes": [f"Analysis unavailable: {exc}"],
            "subject_details": "",
            "phase_goal": f"{cfg.source_phase} to {cfg.dest_phase}",
            "line_quality": "",
            "anatomy_risk": "",
            "complexity": "",
        }
