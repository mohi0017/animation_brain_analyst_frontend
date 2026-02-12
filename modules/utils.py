"""
Utility functions for AI Animation Studio.
"""

from __future__ import annotations
import io
import json
import logging
import re
from typing import Tuple
from PIL import Image

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)


def load_image_bytes(file) -> Tuple[bytes, str]:
    """
    Load and convert uploaded file to PNG bytes.
    
    Args:
        file: Streamlit UploadedFile object
        
    Returns:
        Tuple of (image_bytes, mime_type)
    """
    image = Image.open(file).convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue(), "image/png"


def parse_report_blob(blob: str) -> dict:
    """
    Parse JSON from a string, stripping code fences and robustly extracting JSON objects.
    
    Args:
        blob: String potentially containing JSON with markdown code fences
        
    Returns:
        Parsed dictionary or empty dict if parsing fails
    """
    if not blob:
        return {}
    
    text = blob.strip()
    
    # 1. Try to find JSON block in markdown code fences
    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        text = code_block_match.group(1).strip()
    else:
        # 2. Try to find anything that looks like a JSON object
        object_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if object_match:
            text = object_match.group(1).strip()
    
    try:
        return json.loads(text)
    except Exception as exc:
        get_logger("utils").debug(f"Failed to parse JSON blob: {exc}. Original: {blob[:100]}...")
        return {}


def normalize_report(report: dict) -> dict:
    """
    Normalize report structure, extracting JSON from notes if needed.
    
    Args:
        report: Raw report dictionary from Visual Analyst
        
    Returns:
        Normalized report with fixes, removes, preserve, notes fields
    """
    if not isinstance(report, dict):
        return {}
    
    fixes = report.get("fixes") or []
    removes = report.get("removes") or []
    preserve = report.get("preserve") or []
    raw_notes = report.get("notes") or []
    issues = report.get("issues") or []
    style_match = report.get("style_match")
    style_keywords = report.get("style_keywords") or []
    style_notes = report.get("style_notes") or []
    subject_details = report.get("subject_details")
    entity_type = report.get("entity_type")
    entity_examples = report.get("entity_examples")
    construction_lines = report.get("construction_lines")
    low_construction_sublevel = report.get("low_construction_sublevel")
    broken_lines = report.get("broken_lines")
    phase_goal = report.get("phase_goal")
    line_quality = report.get("line_quality")
    anatomy_risk = report.get("anatomy_risk")
    complexity = report.get("complexity")
    reference_quality = report.get("reference_quality")
    style_compatibility = report.get("style_compatibility")
    reference_summary = report.get("reference_summary")
    cleaned_notes = []

    if isinstance(raw_notes, list):
        for n in raw_notes:
            if isinstance(n, str):
                parsed = parse_report_blob(n)
                if parsed:
                    fixes = fixes or parsed.get("fixes", fixes)
                    removes = removes or parsed.get("removes", removes)
                    preserve = preserve or parsed.get("preserve", preserve)
                    extra_notes = parsed.get("notes")
                    if extra_notes:
                        if isinstance(extra_notes, list):
                            cleaned_notes.extend(extra_notes)
                        elif isinstance(extra_notes, str):
                            cleaned_notes.append(extra_notes)
                    style_keywords = style_keywords or parsed.get("style_keywords", style_keywords)
                    style_notes = style_notes or parsed.get("style_notes", style_notes)
                    subject_details = subject_details or parsed.get("subject_details", subject_details)
                    entity_type = entity_type or parsed.get("entity_type", entity_type)
                    entity_examples = entity_examples or parsed.get("entity_examples", entity_examples)
                    construction_lines = construction_lines or parsed.get("construction_lines", construction_lines)
                    low_construction_sublevel = low_construction_sublevel or parsed.get(
                        "low_construction_sublevel",
                        low_construction_sublevel,
                    )
                    broken_lines = broken_lines or parsed.get("broken_lines", broken_lines)
                    phase_goal = phase_goal or parsed.get("phase_goal", phase_goal)
                    line_quality = line_quality or parsed.get("line_quality", line_quality)
                    anatomy_risk = anatomy_risk or parsed.get("anatomy_risk", anatomy_risk)
                    complexity = complexity or parsed.get("complexity", complexity)
                    issues = issues or parsed.get("issues", issues)
                    style_match = style_match if style_match is not None else parsed.get("style_match")
                    reference_quality = reference_quality or parsed.get("reference_quality", reference_quality)
                    style_compatibility = style_compatibility or parsed.get("style_compatibility", style_compatibility)
                    reference_summary = reference_summary or parsed.get("reference_summary", reference_summary)
                    # do not keep the raw JSON blob in cleaned notes
                    continue
            cleaned_notes.append(n)

    if style_match is None and style_compatibility:
        if style_compatibility in ("match", "compatible"):
            style_match = True
        elif style_compatibility == "conflict":
            style_match = False

    return {
        "fixes": fixes,
        "removes": removes,
        "preserve": preserve,
        "notes": cleaned_notes,
        "issues": issues,
        "style_keywords": style_keywords,
        "style_notes": style_notes,
        "subject_details": subject_details,
        "entity_type": entity_type,
        "entity_examples": entity_examples,
        "construction_lines": construction_lines,
        "low_construction_sublevel": low_construction_sublevel,
        "broken_lines": broken_lines,
        "phase_goal": phase_goal,
        "line_quality": line_quality,
        "anatomy_risk": anatomy_risk,
        "complexity": complexity,
        "style_match": style_match,
        "reference_quality": reference_quality,
        "style_compatibility": style_compatibility,
        "reference_summary": reference_summary,
    }
