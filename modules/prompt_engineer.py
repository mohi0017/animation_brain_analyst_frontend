"""
Prompt Engineer Agent - M2 dual-stage prompt builder.
"""

from __future__ import annotations

from typing import Optional, Tuple
import json
import re
from .utils import get_logger

logger = get_logger("prompt_engineer")


def generate_m2_cleanup_prompts() -> Tuple[str, str, str]:
    pos = (
        "(masterpiece), (ultra-clean lineart:1.5), (vector line art:1.3), "
        "high contrast, solid black lines, pure white background, sharp edges, "
        "flat 2d illustration, digital ink, perfect outlines"
    )
    neg = (
        "(color:1.6), shading, gradients, shadows, blurry, messy lines, "
        "rough sketch, pencil texture, gray scale, background noise, artifacts"
    )
    rationale = "M2 Stage 2 cleanup prompt focused on ink quality and line purity."
    return pos, neg, rationale


def _sanitize_subject_details(details: str) -> str:
    cleaned = details.strip()
    cleaned = cleaned.replace("\n", " ").replace("\r", " ")
    cleaned = re.sub(r"[\[\]{}()\"']", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    # Split by commas and keep short tag-like tokens
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    safe_parts = []
    for part in parts:
        if len(part.split()) > 4:
            continue
        if re.search(r"[.?!;:]", part):
            continue
        if re.search(r"\b(the|this|that|these|those|with|and|for|to|from)\b", part, re.IGNORECASE):
            continue
        safe_parts.append(part)
    return ", ".join(safe_parts)


def _extract_subject_details(report: dict) -> str:
    details = report.get("subject_details")
    if isinstance(details, str) and details.strip():
        return _sanitize_subject_details(details)
    preserve = report.get("preserve") or []
    for item in preserve:
        if isinstance(item, str) and item.strip().lower().startswith("subject:"):
            return _sanitize_subject_details(item.split(":", 1)[-1].strip())
    return ""


def _extract_pose(report: dict) -> str:
    preserve = report.get("preserve") or []
    for item in preserve:
        if not isinstance(item, str):
            continue
        lower = item.strip().lower()
        if lower.startswith("preserve") and not any(
            key in lower for key in ["lines", "background", "colour", "color"]
        ):
            return item.split(" ", 1)[-1].strip()
    return ""


def _ensure_score_tags(pos_prompt: str) -> str:
    score_tags = "score_9, score_8_up, score_7_up, (masterpiece)"
    if pos_prompt.lower().startswith("score_9"):
        return pos_prompt
    return f"{score_tags}, {pos_prompt}"


def _cap_prompt_tokens(prompt: str, max_tokens: int = 75) -> str:
    """
    Cap prompt tags while prioritizing critical identifiers.
    """
    tags = [t.strip() for t in prompt.split(",") if t.strip()]
    if len(tags) <= max_tokens:
        return prompt
    
    # Priority tags: score tags, masterpiece, and bracketed emphasis
    priority_tags = []
    other_tags = []
    
    for tag in tags:
        lower_tag = tag.lower()
        if "score_" in lower_tag or "masterpiece" in lower_tag or "(" in tag:
            priority_tags.append(tag)
        else:
            other_tags.append(tag)
            
    # Reconstruct with priority first
    combined = priority_tags + other_tags
    logger.info(f"Capping prompt: {len(tags)} tags -> {max_tokens} tags (prioritized {len(priority_tags)} tags)")
    return ", ".join(combined[:max_tokens])


def _append_unique_tags(prompt: str, tags: list[str]) -> str:
    existing = {t.strip().lower() for t in prompt.split(",") if t.strip()}
    additions = [t for t in tags if t.strip().lower() not in existing]
    if not additions:
        return prompt
    return f"{prompt}, {', '.join(additions)}"


def _remove_conflicting_tags(prompt: str, conflicts: list[str]) -> str:
    tags = [t.strip() for t in prompt.split(",") if t.strip()]
    conflicts_lower = {c.lower() for c in conflicts}
    filtered = []
    for tag in tags:
        if tag.lower() in conflicts_lower:
            continue
        filtered.append(tag)
    return ", ".join(filtered)


def _dedupe_tags(prompt: str) -> str:
    tags = [t.strip() for t in prompt.split(",") if t.strip()]
    seen = set()
    deduped = []
    for tag in tags:
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(tag)
    return ", ".join(deduped)


def _load_m2_prompt_templates(workflow_path: Optional[str]) -> Optional[dict]:
    if not workflow_path:
        return None
    try:
        with open(workflow_path, "r") as f:
            data = json.load(f)
    except Exception:
        return None

    if "nodes" in data:
        nodes = data.get("nodes", [])
        node_map = {str(n.get("id")): n for n in nodes}
        def _node_text(node_id: str) -> str:
            node = node_map.get(node_id, {})
            widgets = node.get("widgets_values") or []
            return widgets[0] if widgets else ""
        return {
            "pos1": _node_text("2"),
            "neg1": _node_text("3"),
            "pos2": _node_text("77"),
            "neg2": _node_text("76"),
        }

    return {
        "pos1": data.get("2", {}).get("inputs", {}).get("text", ""),
        "neg1": data.get("3", {}).get("inputs", {}).get("text", ""),
        "pos2": data.get("77", {}).get("inputs", {}).get("text", ""),
        "neg2": data.get("76", {}).get("inputs", {}).get("text", ""),
    }


def run_prompt_engineer_m2(
    report: dict,
    dest_phase: str,
    source_phase: str = "Roughs",
    pose_lock: bool = True,
    style_lock: bool = True,
    workflow_path: Optional[str] = None,
) -> Tuple[str, str, str, str, str]:
    templates = _load_m2_prompt_templates(workflow_path)
    if templates:
        pos1 = templates.get("pos1", "") or ""
        neg1 = templates.get("neg1", "") or ""
        pos2 = templates.get("pos2", "") or ""
        neg2 = templates.get("neg2", "") or ""
        rationale1 = "Stage 1 prompts from M2 workflow template."
        rationale2 = "Stage 2 prompts from M2 workflow template."
    else:
        pos1, neg1, rationale1 = "", "", "Stage 1 prompts missing template."
        pos2, neg2, rationale2 = generate_m2_cleanup_prompts()

    subject = _extract_subject_details(report)
    pose = _extract_pose(report)
    if subject:
        # Prefer analyst-driven subject details over template text.
        pos1 = subject
    if pose:
        pos1 = f"{pos1}, {pose}".strip(", ")
    if subject:
        pos2 = f"{pos2}, {subject}".strip(", ")

    line_quality = (report.get("line_quality") or "").lower().strip()
    if line_quality == "messy":
        if "solid black lines" in pos2 and "solid black lines:1.5" not in pos2:
            pos2 = re.sub(
                r"\bsolid black lines\b",
                "(solid black lines:1.5)",
                pos2,
                flags=re.IGNORECASE,
            )
        elif "solid black lines" not in pos2.lower():
            pos2 = f"{pos2}, (solid black lines:1.5)"
        
        # Inject Rescue Strategy negatives
        rescue_negatives = [
            "(construction lines:1.3)",
            "(graphite:1.2)",
            "(sketch artifacts:1.2)",
            "(smudge:1.2)",
            "(guidelines:1.1)",
        ]
        neg1 = _append_unique_tags(neg1, rescue_negatives)
        neg2 = _append_unique_tags(neg2, rescue_negatives)

    # Color blocking: keep Stage 1 lighter, Stage 2 stronger (avoid noisy artifacts)
    color_block_negatives_stage1 = [
        "(color:1.2)",
        "(color fill:1.2)",
        "(flat colors:1.2)",
        "(cel shading:1.2)",
    ]
    color_block_negatives_stage2 = [
        "(color:1.6)",
        "(coloring:1.4)",
        "(color fill:1.4)",
        "(flat colors:1.4)",
        "(flat colour:1.4)",
        "(cel shading:1.4)",
        "(painted:1.3)",
        "(colored lines:1.3)",
        "(pastel:1.2)",
    ]
    tone_block_negatives_stage2 = [
        "(grayscale:1.4)",
        "(grey:1.4)",
        "(tones:1.3)",
        "(halftone:1.3)",
        "(screen tone:1.3)",
        "(paper texture:1.3)",
        "(crosshatching:1.3)",
        "(hatching:1.3)",
        "(noise texture:1.3)",
    ]
    neg1 = _append_unique_tags(neg1, color_block_negatives_stage1)
    neg2 = _append_unique_tags(neg2, color_block_negatives_stage2)
    neg2 = _append_unique_tags(neg2, tone_block_negatives_stage2)
    # Block dotted or broken lines
    line_break_negatives = [
        "(dotted lines:1.4)",
        "(broken lines:1.4)",
        "(sketchy lines:1.3)",
        "(stippling:1.2)",
    ]
    neg1 = _append_unique_tags(neg1, line_break_negatives)
    neg2 = _append_unique_tags(neg2, line_break_negatives)
    # Keep only colored background negatives; remove plain "background" tag.
    neg1 = _remove_conflicting_tags(neg1, ["background"])
    neg2 = _remove_conflicting_tags(neg2, ["background"])

    if dest_phase in ("Tie Down", "CleanUp"):
        pos2 = _append_unique_tags(
            pos2,
            [
                "solid black lines",
                "continuous and smooth lines",
                "unbroken linework",
                "single clean stroke",
                "bold line weight",
                "thick outline",
                "solid ink strokes",
                "pure white background",
            ],
        )
        pos2 = _remove_conflicting_tags(
            pos2,
            [
                "color",
                "colored background",
                "background",
                "fills",
                "gradients",
                "texture",
                "cel shaded",
                "flat color",
                "shading",
                "shadows",
            ],
        )
        neg1 = _append_unique_tags(
            neg1,
            [
                "color",
                "colored background",
                "fills",
                "gradients",
                "texture",
            ],
        )
        neg2 = _append_unique_tags(
            neg2,
            [
                "color",
                "colored background",
                "fills",
                "gradients",
                "texture",
            ],
        )

    if dest_phase == "CleanUp":
        anatomy_focus = [
            "clear anatomy",
            "accurate anatomy",
            "well-defined facial features",
            "clean hands",
            "clean feet",
            "clean legs",
            "clean torso",
            "clean hips",
            "clean shoulders",
        ]
        pos1 = _append_unique_tags(pos1, anatomy_focus)
        pos2 = _append_unique_tags(pos2, anatomy_focus)

    # Enforce clean black lines + white background across all stages
    pos1 = _append_unique_tags(
        pos1,
        [
            "solid black lines",
            "continuous and smooth lines",
            "unbroken linework",
            "single clean stroke",
            "bold line weight",
            "thick outline",
            "solid ink strokes",
            "pure white background",
        ],
    )
    pos2 = _append_unique_tags(
        pos2,
        [
            "solid black lines",
            "continuous and smooth lines",
            "unbroken linework",
            "single clean stroke",
            "bold line weight",
            "thick outline",
            "solid ink strokes",
            "pure white background",
        ],
    )
    # Remove "rough sketch" language when aiming for clean output
    if dest_phase in ("Tie Down", "CleanUp"):
        pos1 = re.sub(r"\brough sketch\b", "", pos1, flags=re.IGNORECASE)
        pos1 = re.sub(r"\(\s*\)", "", pos1)
    pos1 = _remove_conflicting_tags(
        pos1,
        [
            "color",
            "colored background",
            "fills",
            "gradients",
            "texture",
            "cel shaded",
            "flat color",
            "shading",
            "shadows",
        ],
    )
    pos2 = _remove_conflicting_tags(
        pos2,
        [
            "color",
            "colored background",
            "fills",
            "gradients",
            "texture",
            "cel shaded",
            "flat color",
            "shading",
            "shadows",
        ],
    )

    pos1 = _ensure_score_tags(pos1)
    pos1 = _dedupe_tags(pos1)
    pos1 = _cap_prompt_tokens(pos1, max_tokens=75)
    neg1 = _dedupe_tags(neg1)
    neg1 = _cap_prompt_tokens(neg1, max_tokens=75)
    pos2 = _dedupe_tags(pos2)
    neg2 = _dedupe_tags(neg2)

    rationale = f"Stage1: {rationale1} Stage2: {rationale2}"
    logger.info(f"M2 Prompts generated. Rationale: {rationale}")
    return pos1, neg1, pos2, neg2, rationale
