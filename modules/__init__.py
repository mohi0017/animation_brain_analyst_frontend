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
    "SD_MODELS",
    "DEFAULT_LINE_ART_MODEL",
    "DEFAULT_M3_MODEL",
    "DEFAULT_ANALYST_PROMPT_M3",
    
    # Utils
    "load_image_bytes",
    "normalize_report",
    # Gemini Client
    "get_genai_client",
    "get_thinking_config",
    "get_model_name",
    # Agents
    "run_visual_analyst_m3",
    "run_prompt_engineer_m3",
    "generate_m3_cleanup_prompts",
    # Workflow Registry
    "get_workflow_spec",
    # AD-Agent
    "create_parameter_plan_m3",
    # ComfyUI
    "call_comfyui",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies and streamlit hot-reload issues."""
    if name in __all__:
        # Import on-demand to avoid module initialization issues
        if name in ("AnalysisConfig", "SD_MODELS", "DEFAULT_LINE_ART_MODEL"):
            from .config import AnalysisConfig, SD_MODELS, DEFAULT_LINE_ART_MODEL
            return locals()[name]
        elif name == "DEFAULT_ANALYST_PROMPT_M3":
            from .config import DEFAULT_ANALYST_PROMPT_M3
            return DEFAULT_ANALYST_PROMPT_M3
        elif name == "DEFAULT_M3_MODEL":
            from .config import DEFAULT_M3_MODEL
            return DEFAULT_M3_MODEL
        elif name in ("load_image_bytes", "normalize_report"):
            from .utils import load_image_bytes, normalize_report
            return locals()[name]
        elif name in ("get_genai_client", "get_thinking_config", "get_model_name"):
            from .gemini_client import get_genai_client, get_thinking_config, get_model_name
            return locals()[name]
        elif name == "run_visual_analyst_m3":
            from .visual_analyst import run_visual_analyst_m3
            return run_visual_analyst_m3
        elif name in ("run_prompt_engineer_m3", "generate_m3_cleanup_prompts"):
            from .prompt_engineer import run_prompt_engineer_m3, generate_m3_cleanup_prompts
            return locals()[name]
        elif name == "create_parameter_plan_m3":
            try:
                from .animation_director import create_parameter_plan_m3
                return create_parameter_plan_m3
            except (ImportError, AttributeError) as e:
                raise ImportError(f"Failed to import create_parameter_plan_m3 from animation_director: {e}.")
        elif name == "call_comfyui":
            from .comfyui_client import call_comfyui
            return call_comfyui
        elif name == "get_workflow_spec":
            from .workflow_registry import get_workflow_spec
            return get_workflow_spec
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
