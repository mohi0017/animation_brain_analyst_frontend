"""
Gemini API client initialization and configuration.
"""

from __future__ import annotations
import os
from typing import Optional

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None
    genai_types = None


def get_genai_client() -> Optional["genai.Client"]:
    """
    Initialize and return Gemini API client.
    
    Returns:
        genai.Client instance or None if API key not available
    """
    # Prefer official GEMINI_API_KEY; fallback to GOOGLE_GENAI_API_KEY for compatibility.
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
    if not api_key or genai is None:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def get_thinking_config():
    """
    Get thinking configuration from environment variable.
    
    Returns:
        ThinkingConfig instance or None if not configured
    """
    try:
        budget = os.getenv("GEMINI_THINK_BUDGET")
        if budget is None:
            return None
        budget_val = int(budget)
        return genai_types.ThinkingConfig(thinking_budget=budget_val)
    except Exception:
        return None


def get_model_name() -> str:
    """
    Get Gemini model name from environment or return default.
    
    Returns:
        Model name string
    """
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

