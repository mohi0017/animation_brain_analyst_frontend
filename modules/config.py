"""
Configuration, constants, and data models for AI Animation Studio.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

# ---------- Data Models ----------
@dataclass
class AnalysisConfig:
    """Configuration for Visual Analyst agent."""
    source_phase: str
    dest_phase: str
    pose_lock: bool
    style_lock: bool
    anatomical_level: int


# ---------- Stable Diffusion Models ----------
SD_MODELS = {
    "animagine-xl-3.1.safetensors": {
        "name": "Animagine XL 3.1",
        "category": "Anime XL",
        "description": "High-quality SDXL anime model. Best default for M2 style transfer and motion lock.",
        "best_for": ["Tie Down", "CleanUp", "Colors"],
        "strengths": "Sharp anime linework, clean cel look, strong character rendering",
        "use_when": "You need strong anime-style output with clean structure",
        "keywords": ["anime", "character", "cel", "lineart", "xl"]
    }
}

# Default model for line art phases
DEFAULT_LINE_ART_MODEL = "animagine-xl-3.1.safetensors"

# Default model for Milestone 2 workflow (SDXL)
DEFAULT_M2_MODEL = "animagine-xl-3.1.safetensors"



DEFAULT_ANALYST_PROMPT_M2 = """You are a Multi-Modal Visual Analyst ("Brain") for Milestone 2.

You will receive ONE or TWO images.
1. The first image is the Input (User's sketch).
2. The second image (optional) is the Reference (Style guide).

Your job is to behave like an experienced animator: identify what to clean, what to preserve, and categorize the sketch for dynamic parameter control.

If a Reference image is provided, compare it to the Input only for reference analysis fields. Do NOT change subject_details or pose based on the reference image.

Required Output JSON keys:
{
  "fixes": [...],
  "removes": [...],
  "preserve": [...],
  "notes": [...],
  "issues": [...],
  "subject_details": "tag list like: character, wings, armor",
  "phase_goal": "Rough to Tie Down | Rough to CleanUp | Tie Down to CleanUp",
  "line_quality": "messy | structured | clean",
  "anatomy_risk": "low | medium | high",
  "complexity": "simple | detailed",
  "style_match": "true | false | null",
  "reference_quality": "high | medium | messy | none",
  "style_compatibility": "match | compatible | conflict | none",
  "reference_summary": "Brief analysis of the reference image (if present)"
}

Rules:
- subject_details must be short, SD-friendly tags (comma-separated).
- line_quality describes line cleanliness (messy roughs vs clean ink).
- anatomy_risk reflects how risky anatomy correction is.
- complexity is based on line density / detail amount.
- issues is optional; list problems like "pose drift", "over-processed", "thin lines".
- style_match is optional; true if reference style should be strongly matched.
- reference_quality: 'messy' if the reference itself is a scribbly sketch; 'high' if it's a finished production frame.
- style_compatibility: 'conflict' if input and reference have totally different proportions (e.g. chibi vs realistic).
- If the input clearly shows clothing or lack of clothing, include a concise, neutral tag (e.g., "swimsuit", "bare torso", "bare shoulders").
- If a prop is clearly visible (e.g., toothbrush), include it as a short tag.
"""
