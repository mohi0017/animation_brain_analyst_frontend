"""
AI Animation Studio - Modular Components
"""

from .config import (
    AnalysisConfig,
    SD_MODELS,
    DEFAULT_LINE_ART_MODEL,
    DEFAULT_ANALYST_PROMPT_M3,
)

# Backward-compatible config export (older deployments may not have DEFAULT_M4_MODEL yet).
try:
    from .config import DEFAULT_M4_MODEL
except ImportError:  # pragma: no cover - compatibility path
    from .config import DEFAULT_M3_MODEL as DEFAULT_M4_MODEL

from . import utils as _utils
from .gemini_client import get_genai_client, get_thinking_config, get_model_name

# Backward-compatible analyst export (older deployments may only provide M3 name).
try:
    from .visual_analyst import run_visual_analyst_m4
except ImportError:  # pragma: no cover - compatibility path
    from .visual_analyst import run_visual_analyst_m3 as run_visual_analyst_m4

# Backward-compatible prompt exports.
try:
    from .prompt_engineer import run_prompt_engineer_m4
except ImportError:  # pragma: no cover - compatibility path
    from .prompt_engineer import run_prompt_engineer_m3 as run_prompt_engineer_m4
from .prompt_engineer import generate_m4_cleanup_prompts

# Workflow registry path compatibility.
try:
    from .workflows.registry import get_workflow_spec
except ImportError:  # pragma: no cover - compatibility path
    from .workflow_registry import get_workflow_spec

# Backward-compatible parameter planner export.
try:
    from .animation_director import create_parameter_plan_m4
except ImportError:  # pragma: no cover - compatibility path
    from .animation_director import create_parameter_plan_m3 as create_parameter_plan_m4

from .comfyui_client import call_comfyui

load_image_bytes = _utils.load_image_bytes
normalize_report = _utils.normalize_report


def _missing_feature(name: str):
    def _raise(*_args, **_kwargs):
        raise NotImplementedError(
            f"`{name}` is not available in this deployment. Please update modules/utils.py."
        )
    return _raise


normalize_sequence_frames = getattr(_utils, "normalize_sequence_frames", _missing_feature("normalize_sequence_frames"))
extract_frames_from_video_bytes = getattr(_utils, "extract_frames_from_video_bytes", _missing_feature("extract_frames_from_video_bytes"))
extract_frames_from_zip_bytes = getattr(_utils, "extract_frames_from_zip_bytes", _missing_feature("extract_frames_from_zip_bytes"))
pick_keyframe_indices = getattr(_utils, "pick_keyframe_indices", _missing_feature("pick_keyframe_indices"))
load_sequence_from_folder = getattr(_utils, "load_sequence_from_folder", _missing_feature("load_sequence_from_folder"))

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
