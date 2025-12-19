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

# Lazy imports to avoid circular dependencies and hot-reload issues
__all__ = [
    # Config
    "AnalysisConfig",
    "PHASE_PARAMS",
    "SD_MODELS",
    "DEFAULT_LINE_ART_MODEL",
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
    # AD-Agent
    "ParameterPlan",
    "create_parameter_plan",
    # ComfyUI
    "call_comfyui",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies and streamlit hot-reload issues."""
    if name in __all__:
        # Import on-demand to avoid module initialization issues
        if name in ("AnalysisConfig", "PHASE_PARAMS", "SD_MODELS", "DEFAULT_LINE_ART_MODEL", "DEFAULT_ANALYST_PROMPT", "DEFAULT_PROMPT_ENGINEER"):
            from .config import AnalysisConfig, PHASE_PARAMS, SD_MODELS, DEFAULT_LINE_ART_MODEL, DEFAULT_ANALYST_PROMPT, DEFAULT_PROMPT_ENGINEER
            return locals()[name]
        elif name in ("load_image_bytes", "normalize_report"):
            from .utils import load_image_bytes, normalize_report
            return locals()[name]
        elif name in ("get_genai_client", "get_thinking_config", "get_model_name"):
            from .gemini_client import get_genai_client, get_thinking_config, get_model_name
            return locals()[name]
        elif name == "run_visual_analyst":
            from .visual_analyst import run_visual_analyst
            return run_visual_analyst
        elif name in ("run_prompt_engineer", "generate_smart_fallback_prompts"):
            from .prompt_engineer import run_prompt_engineer, generate_smart_fallback_prompts
            return locals()[name]
        elif name == "ParameterPlan":
            from .parameter_plan import ParameterPlan
            return ParameterPlan
        elif name == "create_parameter_plan":
            from .animation_director import create_parameter_plan
            return create_parameter_plan
        elif name == "call_comfyui":
            from .comfyui_client import call_comfyui
            return call_comfyui
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

