"""
Utility functions for AI Animation Studio.
"""

from __future__ import annotations
import io
import json
import logging
import os
import subprocess
import tempfile
import zipfile
import re
from pathlib import Path
from typing import List, Tuple
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


def sort_filenames_ascending(names: List[str]) -> List[str]:
    """
    Strictly sort sequence filenames by frame index.

    Accepted basename patterns:
    - <prefix><sep><digits>.<ext>   (e.g., shot_0001.png, frame-12.jpg)
    - <digits>.<ext>                (e.g., 0001.png)

    Validation:
    - every filename must contain a trailing numeric frame index
    - all files must share one naming family (same normalized prefix + extension)
    - frame indices must be unique
    """
    if not names:
        return []

    parsed: list[tuple[str, int, str, str]] = []
    # (original_name, frame_idx, normalized_prefix, ext)

    for raw_name in names:
        base = os.path.basename(str(raw_name or "")).strip()
        stem, ext = os.path.splitext(base)
        ext = ext.lower()
        if not stem or not ext:
            raise ValueError(
                f"Invalid sequence filename '{raw_name}'. Expected a file with extension, e.g. frame_0001.png."
            )

        # Require a trailing frame number in the stem.
        match = re.match(r"^(?P<prefix>.*?)(?:[_\-\s]?)(?P<idx>\d+)$", stem)
        if not match:
            raise ValueError(
                f"Invalid sequence filename '{raw_name}'. "
                "Expected trailing numeric frame index, e.g. shot_0001.png."
            )

        prefix = (match.group("prefix") or "").strip().lower()
        # Normalize separators so shot-a_ and shot a- are treated as same family.
        prefix = re.sub(r"[_\-\s]+", "_", prefix).strip("_")
        idx = int(match.group("idx"))
        parsed.append((raw_name, idx, prefix, ext))

    families = {(pfx, ext) for _, _, pfx, ext in parsed}
    if len(families) > 1:
        sample = ", ".join(sorted(f"{pfx or '<numeric-only>'}{ext}" for pfx, ext in families))
        raise ValueError(
            "Sequence contains mixed filename families/extensions. "
            f"Found: {sample}. Keep one consistent pattern (e.g., frame_0001.png ... frame_0120.png)."
        )

    seen: dict[int, str] = {}
    for original, idx, _, _ in parsed:
        if idx in seen:
            raise ValueError(
                f"Duplicate frame index detected in sequence: {seen[idx]} and {original}. "
                "Frame indices must be unique."
            )
        seen[idx] = original

    parsed.sort(key=lambda x: x[1])
    return [original for original, _, _, _ in parsed]


def normalize_sequence_frames(frames: List[Tuple[str, bytes]]) -> List[Tuple[str, bytes]]:
    """
    Normalize sequence names to frame_000001.png ... frame_N.png in ascending order.
    """
    by_name = {name: data for name, data in frames if isinstance(name, str) and data}
    ordered_names = sort_filenames_ascending(list(by_name.keys()))
    normalized: List[Tuple[str, bytes]] = []
    for idx, name in enumerate(ordered_names, start=1):
        normalized.append((f"frame_{idx:06d}.png", by_name[name]))
    return normalized


def extract_frames_from_video_bytes(video_bytes: bytes, suffix: str = ".mp4") -> List[Tuple[str, bytes]]:
    """
    Extract PNG frames from uploaded video bytes using ffmpeg.
    Requires ffmpeg binary available in PATH.
    """
    with tempfile.TemporaryDirectory(prefix="m4_video_") as tmpdir:
        in_path = Path(tmpdir) / f"input{suffix}"
        out_dir = Path(tmpdir) / "frames"
        out_dir.mkdir(parents=True, exist_ok=True)
        in_path.write_bytes(video_bytes)

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(in_path),
            "-vsync",
            "0",
            str(out_dir / "frame_%06d.png"),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                "Video frame extraction failed. Ensure ffmpeg is installed and video is valid."
            )

        frame_paths = sorted(out_dir.glob("frame_*.png"))
        frames: List[Tuple[str, bytes]] = []
        for p in frame_paths:
            frames.append((p.name, p.read_bytes()))
        if not frames:
            raise RuntimeError("No frames extracted from uploaded video.")
        return frames


def pick_keyframe_indices(num_frames: int) -> List[int]:
    """
    Pick keyframe indices for sequence analysis.
    - <= 3 frames: all
    - otherwise: first, middle, last
    """
    if num_frames <= 0:
        return []
    if num_frames <= 3:
        return list(range(num_frames))
    idx = {0, num_frames // 2, num_frames - 1}
    return sorted(idx)


def load_sequence_from_folder(folder_path: str) -> List[Tuple[str, bytes]]:
    """
    Load sequence images from a local folder path.
    Files are validated/sorted using strict filename parser and normalized.
    """
    folder = Path(folder_path).expanduser()
    if not folder.exists():
        raise ValueError(f"Folder not found: {folder}")
    if not folder.is_dir():
        raise ValueError(f"Path is not a folder: {folder}")

    allowed_exts = {".png", ".jpg", ".jpeg"}
    candidates = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in allowed_exts]
    if not candidates:
        raise ValueError("No sequence images found in folder. Supported: PNG, JPG, JPEG.")

    ordered_names = sort_filenames_ascending([p.name for p in candidates])
    by_name = {p.name: p for p in candidates}
    frames: List[Tuple[str, bytes]] = []
    for name in ordered_names:
        p = by_name[name]
        try:
            img = Image.open(p).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            frames.append((name, buf.getvalue()))
        except Exception as exc:
            raise ValueError(f"Failed to read image '{p}': {exc}") from exc

    return normalize_sequence_frames(frames)


def extract_frames_from_zip_bytes(zip_bytes: bytes) -> List[Tuple[str, bytes]]:
    """
    Extract sequence images from a ZIP archive.
    Accepts PNG/JPG/JPEG entries and returns normalized frame names.
    """
    allowed_exts = {".png", ".jpg", ".jpeg"}
    frames: List[Tuple[str, bytes]] = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        image_names = [
            n for n in names
            if Path(n).suffix.lower() in allowed_exts
            and not Path(n).name.startswith(".")
        ]
        if not image_names:
            raise ValueError("ZIP does not contain PNG/JPG/JPEG frames.")

        # Validate and sort by basename frame index.
        ordered = sort_filenames_ascending([Path(n).name for n in image_names])
        # For duplicate basenames in different subfolders, keep first occurrence.
        by_base = {}
        for n in image_names:
            by_base.setdefault(Path(n).name, n)

        for base_name in ordered:
            arc_name = by_base[base_name]
            data = zf.read(arc_name)
            try:
                img = Image.open(io.BytesIO(data)).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                frames.append((base_name, buf.getvalue()))
            except Exception as exc:
                raise ValueError(f"Invalid image in ZIP: {arc_name} ({exc})") from exc

    return normalize_sequence_frames(frames)
