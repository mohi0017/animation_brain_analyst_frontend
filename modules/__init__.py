"""
AI Animation Studio - Modular Components
"""

from .config import (
    AnalysisConfig,
    SD_MODELS,
    DEFAULT_LINE_ART_MODEL,
    DEFAULT_M4_MODEL,
    DEFAULT_ANALYST_PROMPT_M3,
)
from .utils import (
    load_image_bytes,
    normalize_report,
    normalize_sequence_frames,
    extract_frames_from_video_bytes,
    extract_frames_from_zip_bytes,
    pick_keyframe_indices,
    load_sequence_from_folder,
)
from .gemini_client import get_genai_client, get_thinking_config, get_model_name
from .visual_analyst import run_visual_analyst_m4
from .prompt_engineer import run_prompt_engineer_m4, generate_m4_cleanup_prompts
from .workflows.registry import get_workflow_spec
from .animation_director import create_parameter_plan_m4
from .comfyui_client import call_comfyui

__all__ = [
    "AnalysisConfig",
    "SD_MODELS",
    "DEFAULT_LINE_ART_MODEL",
    "DEFAULT_M4_MODEL",
    "DEFAULT_ANALYST_PROMPT_M3",
    "load_image_bytes",
    "normalize_report",
    "normalize_sequence_frames",
    "extract_frames_from_video_bytes",
    "extract_frames_from_zip_bytes",
    "pick_keyframe_indices",
    "load_sequence_from_folder",
    "get_genai_client",
    "get_thinking_config",
    "get_model_name",
    "run_visual_analyst_m4",
    "run_prompt_engineer_m4",
    "generate_m4_cleanup_prompts",
    "get_workflow_spec",
    "create_parameter_plan_m4",
    "call_comfyui",
]
