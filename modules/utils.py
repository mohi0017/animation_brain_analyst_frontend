"""
Utility functions for AI Animation Studio.
"""

from __future__ import annotations
import io
from typing import Tuple
from PIL import Image


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
    Parse JSON from a string, stripping code fences.
    
    Args:
        blob: String potentially containing JSON with markdown code fences
        
    Returns:
        Parsed dictionary or empty dict if parsing fails
    """
    if not blob:
        return {}
    text = blob.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].strip()
    if text.lower().startswith("json"):
        text = text[4:].strip()
    try:
        import json
        return json.loads(text)
    except Exception:
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
                    # do not keep the raw JSON blob in cleaned notes
                    continue
            cleaned_notes.append(n)

    return {
        "fixes": fixes,
        "removes": removes,
        "preserve": preserve,
        "notes": cleaned_notes,
    }

