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

from .config import AnalysisConfig, DEFAULT_ANALYST_PROMPT
from .gemini_client import get_genai_client, get_thinking_config, get_model_name


def run_visual_analyst(image_bytes: bytes, mime: str, cfg: AnalysisConfig) -> dict:
    """
    Run Visual Analyst agent on uploaded image.
    
    Args:
        image_bytes: Image data as bytes
        mime: MIME type (e.g., "image/png")
        cfg: Analysis configuration
        
    Returns:
        Analysis report dictionary with fixes, removes, preserve, notes
    """
    client = get_genai_client()
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
    model_name = get_model_name()
    image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=mime)
    
    # Inject run-time config so the model knows the transition and constraints
    config_block = f"""
SOURCE_PHASE: {cfg.source_phase}
DEST_PHASE: {cfg.dest_phase}
POSE_LOCK: {cfg.pose_lock}
STYLE_LOCK: {cfg.style_lock}
ANATOMICAL_LEVEL: {cfg.anatomical_level}
"""
    full_prompt = f"{prompt}\n\n{config_block}"
    
    # Follow Gemini docs: contents can be a mix of Parts and plain text strings
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[image_part, full_prompt],
            config=genai_types.GenerateContentConfig(
                temperature=0.2,
                thinking_config=get_thinking_config(),
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

