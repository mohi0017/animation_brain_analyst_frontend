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
        "description": "High-quality SDXL anime model. Best default for M4 style transfer and motion lock.",
        "best_for": ["Tie Down", "CleanUp", "Colors"],
        "strengths": "Sharp anime linework, clean cel look, strong character rendering",
        "use_when": "You need strong anime-style output with clean structure",
        "keywords": ["anime", "character", "cel", "lineart", "xl"]
    }
}

# Default model for line art phases
DEFAULT_LINE_ART_MODEL = "animagine-xl-3.1.safetensors"

# Default model for Milestone 4 workflow (SDXL)
DEFAULT_M4_MODEL = "animagine-xl-3.1.safetensors"
# Backward-compatible alias.
DEFAULT_M3_MODEL = DEFAULT_M4_MODEL



DEFAULT_ANALYST_PROMPT_M3 = """You are a Multi-Modal Visual Analyst ("Brain") for Milestone 3.

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
  "entity_type": "single_complex | single_simple | multi_object",
  "entity_examples": "short phrase like: person | car | truck | house | ball | crowd",
  "construction_lines": "low | medium | high",
  "low_construction_sublevel": "none | one_two | two_three",
  "broken_lines": "low | medium | high",
  "phase_goal": "Rough to Tie Down | Rough to CleanUp | Tie Down to CleanUp",
  "line_quality": "messy | structured | clean",
  "anatomy_risk": "low | medium | high",
  "complexity": "simple | complex",
  "style_match": "true | false | null",
  "reference_quality": "high | medium | messy | none",
  "style_compatibility": "match | compatible | conflict | none",
  "reference_summary": "Brief analysis of the reference image (if present)"
}

Rules:
- subject_details must be short, SD-friendly tags (comma-separated).
- entity_type: classify the input scene into one of:
  - single_complex: one main large entity (person/character, car/truck, house/building, etc.)
  - single_simple: one simple main object (ball/football/circle, simple prop) with minimal parts
  - multi_object: multiple distinct entities (e.g., two people, person + car, crowd, many props)
- entity_examples: 1-3 words naming the main entity/entities (used for downstream parameter tuning).
- construction_lines: how much construction/guideline/overdraw is present (helps decide cleanup aggression).
- low_construction_sublevel: required when construction_lines is 'low':
  - none: construction lines are almost not visible
  - one_two: a very small amount (about 1-2 guide strokes)
  - two_three: a small amount (about 2-3 guide strokes)
  - if construction_lines is not low, return "none"
- broken_lines: how much line breakup/dotted/broken strokes exist (helps decide line reinforcement).
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
