"""
AI Animation Studio - Modular Components

This package contains the core modules for the AI Animation Studio:
- config: Configuration, constants, and data models
- utils: Helper functions
- gemini_client: Gemini API client initialization
- visual_analyst: Visual Analyst agent (multimodal image analysis)
- prompt_engineer: Prompt Engineer agent (SD prompt generation)
- comfyui_client: ComfyUI API client (workflow submission and image download)
"""

from .config import (
    AnalysisConfig,
    PHASE_PARAMS,
    DEFAULT_ANALYST_PROMPT,
    DEFAULT_PROMPT_ENGINEER,
)
from .utils import load_image_bytes, normalize_report
from .gemini_client import get_genai_client, get_thinking_config, get_model_name
from .visual_analyst import run_visual_analyst
from .prompt_engineer import run_prompt_engineer, generate_smart_fallback_prompts
from .comfyui_client import call_comfyui

__all__ = [
    # Config
    "AnalysisConfig",
    "PHASE_PARAMS",
    "DEFAULT_ANALYST_PROMPT",
    "DEFAULT_PROMPT_ENGINEER",
    # Utils
    "load_image_bytes",
    "normalize_report",
    # Gemini Client
    "get_genai_client",
    "get_thinking_config",
    "get_model_name",
    # Agents
    "run_visual_analyst",
    "run_prompt_engineer",
    "generate_smart_fallback_prompts",
    # ComfyUI
    "call_comfyui",
]

