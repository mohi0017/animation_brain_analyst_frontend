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
    },
    "anything-v5-PrtRE.safetensors": {
        "name": "AnythingXL Ink Base",
        "category": "Line Art",
        "description": "Best for pure line art and ink drawings. Perfect for animation cleanup phases.",
        "best_for": ["Skeleton", "Roughs", "Tie Down", "CleanUp"],
        "strengths": "Clean lines, no unwanted shading, preserves ink color, transparent backgrounds",
        "use_when": "Input is sketches, line art, or needs clean outlines without fills",
        "keywords": ["line art", "sketch", "outline", "ink", "drawing", "clean lines"]
    },
    "Counterfeit-V3.0.safetensors": {
        "name": "Counterfeit V3",
        "category": "Anime",
        "description": "High-quality anime style. Great for character-focused work with vibrant colors.",
        "best_for": ["CleanUp", "Colors"],
        "strengths": "Anime aesthetics, vibrant colors, detailed characters, smooth gradients",
        "use_when": "Input has anime characters or needs anime-style coloring",
        "keywords": ["anime", "character", "girl", "boy", "manga", "face", "eyes"]
    },
    "GhostMix-v2.0.safetensors": {
        "name": "GhostMix V2",
        "category": "Anime/Fantasy",
        "description": "Ethereal anime style with soft lighting. Good for fantasy and atmospheric scenes.",
        "best_for": ["Colors"],
        "strengths": "Soft lighting, atmospheric effects, fantasy aesthetics, detailed backgrounds",
        "use_when": "Input has fantasy elements, magical scenes, or needs atmospheric coloring",
        "keywords": ["fantasy", "magic", "ethereal", "atmospheric", "ghost", "spirit"]
    },
    "Lyriel-v1.6.safetensors": {
        "name": "Lyriel V1.6",
        "category": "Illustration",
        "description": "Versatile illustration model. Works for both line art and coloring with artistic flair.",
        "best_for": ["Tie Down", "CleanUp", "Colors"],
        "strengths": "Artistic style, versatile, good for illustrations, balanced detail",
        "use_when": "Input needs artistic illustration style or book/concept art quality",
        "keywords": ["illustration", "art", "artistic", "book", "concept", "versatile"]
    },
    "Realistic_Vision_V5.1.safetensors": {
        "name": "Realistic Vision V5.1",
        "category": "Photorealistic",
        "description": "Photorealistic rendering. ⚠️ NOT recommended for line art (adds unwanted shading).",
        "best_for": ["Colors"],
        "strengths": "Photorealistic quality, 3D-like rendering, realistic lighting and shadows",
        "use_when": "Input is photo or needs realistic rendering (NOT for line art phases)",
        "keywords": ["photo", "realistic", "3d", "render", "real", "portrait"]
    }
}

# Default model for line art phases
DEFAULT_LINE_ART_MODEL = "anything-v5-PrtRE.safetensors"

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



