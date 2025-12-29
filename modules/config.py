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
    master_instruction: str


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

You will receive ONE image (the user's rough/line sketch). Your job is to behave
like an experienced animator: identify what to clean, what to preserve, and
categorize the sketch for dynamic parameter control.

Required Output JSON keys:
{
  "fixes": [...],
  "removes": [...],
  "preserve": [...],
  "notes": [...],
  "subject_details": "tag list like: 1girl, sunglasses, crop top",
  "phase_goal": "Rough to Tie Down | Rough to CleanUp | Tie Down to CleanUp",
  "line_quality": "messy | structured | clean",
  "anatomy_risk": "low | medium | high",
  "complexity": "simple | detailed"
}

Rules:
- subject_details must be short, SD-friendly tags (comma-separated).
- line_quality describes line cleanliness (messy roughs vs clean ink).
- anatomy_risk reflects how risky anatomy correction is.
- complexity is based on line density / detail amount.
"""
