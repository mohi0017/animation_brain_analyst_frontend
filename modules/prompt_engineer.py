"""
Prompt Engineer Agent - M4 dual-stage prompt builder.
"""

from __future__ import annotations

from typing import Optional, Tuple
import json
import re
from .utils import get_logger

logger = get_logger("prompt_engineer")


def generate_m4_cleanup_prompts() -> Tuple[str, str, str]:
    pos = (
        "(masterpiece), (ultra-clean lineart:1.5), (vector line art:1.3), "
        "high contrast, solid black lines, pure white background, sharp edges, "
        "flat 2d illustration, digital ink, perfect outlines"
    )
    neg = (
        "(color:1.6), shading, gradients, shadows, blurry, messy lines, "
        "rough sketch, pencil texture, gray scale, background noise, artifacts"
    )
    rationale = "M4 Stage 2 cleanup prompt focused on ink quality and line purity."
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


def _remove_exact_tags(prompt: str, tags_to_remove: list[str]) -> str:
    tags = [t.strip() for t in prompt.split(",") if t.strip()]
    remove_set = {t.lower().strip() for t in tags_to_remove}
    kept = [t for t in tags if t.lower().strip() not in remove_set]
    return ", ".join(kept)


def _drop_plain_when_weighted_exists(prompt: str, base_terms: list[str]) -> str:
    tags = [t.strip() for t in prompt.split(",") if t.strip()]
    lowered = [t.lower() for t in tags]
    weighted_present = {
        term.lower(): any((f"({term.lower()}:" in t) for t in lowered)
        for term in base_terms
    }
    kept = []
    for tag in tags:
        tag_l = tag.lower().strip()
        remove_plain = False
        for term in base_terms:
            term_l = term.lower()
            if weighted_present.get(term_l) and tag_l == term_l:
                remove_plain = True
                break
        if not remove_plain:
            kept.append(tag)
    return ", ".join(kept)


def _load_m4_prompt_templates(workflow_path: Optional[str]) -> Optional[dict]:
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


def _infer_subject_profile(report: dict, subject: str) -> str:
    entity_type = (report.get("entity_type") or "").lower().strip()
    text = " ".join(
        [
            subject or "",
            str(report.get("subject_details") or ""),
            str(report.get("entity_examples") or ""),
        ]
    ).lower()
    if any(k in text for k in ("circle", "ball", "sphere", "oval", "ring", "shape", "logo", "icon")):
        return "geometry"
    if any(k in text for k in ("car", "truck", "bus", "bike", "vehicle", "house", "building", "object", "prop")):
        return "object"
    if entity_type in ("single_complex", "multi_object") or any(k in text for k in ("character", "person", "woman", "man", "human")):
        return "character"
    if entity_type == "single_simple":
        return "geometry"
    return "generic"


def run_prompt_engineer_m4(
    report: dict,
    dest_phase: str,
    source_phase: str = "Roughs",
    pose_lock: bool = True,
    style_lock: bool = True,
    workflow_path: Optional[str] = None,
) -> Tuple[str, str, str, str, str]:
    templates = _load_m4_prompt_templates(workflow_path)
    if templates:
        pos1 = templates.get("pos1", "") or ""
        neg1 = templates.get("neg1", "") or ""
        pos2 = templates.get("pos2", "") or ""
        neg2 = templates.get("neg2", "") or ""
        rationale1 = "Stage 1 prompts from M4 workflow template."
        rationale2 = "Stage 2 prompts from M4 workflow template."
    else:
        pos1, neg1, rationale1 = "", "", "Stage 1 prompts missing template."
        pos2, neg2, rationale2 = generate_m4_cleanup_prompts()

    subject = _extract_subject_details(report)
    pose = _extract_pose(report)
    if subject:
        subject_tags = [t.strip() for t in subject.split(",") if t.strip()]
        if pos1:
            pos1 = _append_unique_tags(pos1, subject_tags)
        else:
            pos1 = ", ".join(subject_tags)
        if pos2:
            pos2 = _append_unique_tags(pos2, subject_tags)
        else:
            pos2 = ", ".join(subject_tags)
    if pose:
        if pos1:
            pos1 = _append_unique_tags(pos1, [pose])
        else:
            pos1 = pose

    line_quality = (report.get("line_quality") or "").lower().strip()
    construction_lines = (report.get("construction_lines") or "").lower().strip()
    broken_lines = (report.get("broken_lines") or "").lower().strip()
    entity_type = (report.get("entity_type") or "").lower().strip()
    subject_profile = _infer_subject_profile(report, subject)
    influence_scalar = report.get("_influence_scalar")
    try:
        influence_scalar = float(influence_scalar) if influence_scalar is not None else None
    except Exception:
        influence_scalar = None
    influence_scalar = None if influence_scalar is None else max(0.0, min(1.0, influence_scalar))
    try:
        conflict_penalty = float(report.get("reference_conflict_penalty") or 0.0)
    except Exception:
        conflict_penalty = 0.0
    conflict_penalty = max(0.0, min(1.0, conflict_penalty))
    reference_mode = (report.get("reference_mode") or "").lower().strip()
    reference_mode_ks2 = (report.get("reference_mode_ks2") or reference_mode).lower().strip()
    transition = f"{source_phase} -> {dest_phase}"
    ip_dual = report.get("ip_adapter_dual") or {}
    try:
        ip_ks1_w = float((ip_dual.get("ksampler1") or {}).get("weight", report.get("ip_weight") or 0.0))
    except Exception:
        ip_ks1_w = 0.0
    try:
        ip_ks2_w = float((ip_dual.get("ksampler2") or {}).get("weight", report.get("ip_weight") or 0.0))
    except Exception:
        ip_ks2_w = 0.0

    # Extra signal: construction/broken line intensity lets us scale the rescue negatives.
    def _construction_negatives(level: str) -> list[str]:
        if level == "high":
            return [
                "(construction lines:1.6)",
                "(guidelines:1.4)",
                "(graphite:1.3)",
                "(sketch artifacts:1.3)",
                "(smudge:1.2)",
            ]
        if level == "medium":
            return [
                "(construction lines:1.4)",
                "(guidelines:1.2)",
                "(graphite:1.2)",
                "(sketch artifacts:1.2)",
            ]
        if level == "low":
            return []
        return []

    def _broken_line_negatives(level: str) -> list[str]:
        if level == "high":
            return [
                "(broken lines:1.7)",
                "(dotted lines:1.6)",
                "(sketchy lines:1.4)",
                "(stippling:1.3)",
            ]
        if level == "medium":
            return [
                "(broken lines:1.5)",
                "(dotted lines:1.4)",
                "(sketchy lines:1.3)",
            ]
        if level == "low":
            return []
        return []

    extra_negatives = _construction_negatives(construction_lines) + _broken_line_negatives(broken_lines)
    if extra_negatives:
        neg1 = _append_unique_tags(neg1, extra_negatives)
        neg2 = _append_unique_tags(neg2, extra_negatives)

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
        
        # Inject Rescue Strategy negatives only when construction/broken levels are missing/unknown,
        # otherwise we may end up with conflicting duplicate weights (e.g. both 1.6 and 1.3).
        if not construction_lines and not broken_lines:
            rescue_negatives = [
                "(construction lines:1.3)",
                "(graphite:1.2)",
                "(sketch artifacts:1.2)",
                "(smudge:1.2)",
                "(guidelines:1.1)",
            ]
            neg1 = _append_unique_tags(neg1, rescue_negatives)
            neg2 = _append_unique_tags(neg2, rescue_negatives)
    artifact_risk = line_quality == "messy" or conflict_penalty >= 0.4
    if artifact_risk:
        artifact_negatives = [
            "(palette artifacts:1.6)",
            "(color banding:1.5)",
            "(jpeg artifacts:1.5)",
            "(green artifacts:1.8)",
            "(gif artifacts:1.5)",
        ]
        neg1 = _append_unique_tags(neg1, artifact_negatives)
        neg2 = _append_unique_tags(neg2, artifact_negatives)

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
        lineart_tags = [
            "solid black lines",
            "continuous and smooth lines",
            "unbroken linework",
            "single clean stroke",
            "bold line weight",
            "thick outline",
            "solid ink strokes",
            "pure white background",
        ]
        if pos1:
            pos1 = _append_unique_tags(pos1, lineart_tags)
        else:
            pos1 = ", ".join(lineart_tags)

    # For geometry/object cleanup, strictly lock canvas/background and only clean subject lines.
    if subject_profile in ("geometry", "object"):
        canvas_lock_pos = [
            "unchanged white canvas",
            "preserve original canvas",
            "no background alteration",
            "subject-only cleanup",
        ]
        canvas_lock_neg = [
            "(background change:1.6)",
            "(canvas texture:1.6)",
            "(paper grain:1.5)",
            "(background pattern:1.5)",
            "(frame border:1.6)",
            "(dirty background:1.5)",
            "(vignette:1.4)",
            "(lighting gradient:1.4)",
        ]
        pos1 = _append_unique_tags(pos1, canvas_lock_pos)
        pos2 = _append_unique_tags(pos2, canvas_lock_pos)
        neg1 = _append_unique_tags(neg1, canvas_lock_neg)
        neg2 = _append_unique_tags(neg2, canvas_lock_neg)

    # ---------- Stage-aware semantic layering (KS1 vs KS2 responsibilities) ----------
    # We keep templates as the base, then add *different* layers per stage.
    if subject_profile == "character":
        # KS1 = structure authority (conservative).
        ks1_structure_lock = [
            "preserve original pose exactly",
            "maintain original proportions",
            "retain original accessories",
            "do not redesign character",
        ]
        if conflict_penalty > 0.4:
            ks1_structure_lock.extend(
                [
                    "do not alter facial features",
                    "strictly follow input structure",
                ]
            )

        # If reference influence is low, avoid injecting any style/identity language into KS1.
        if (influence_scalar is not None and influence_scalar < 0.4) or ip_ks1_w < 0.6:
            ks1_style_hint: list[str] = []
        else:
            ks1_style_hint = ["subtle reference line influence"] if influence_scalar is not None else []

        pos1 = _append_unique_tags(pos1, ks1_structure_lock + ks1_style_hint)

        # KS2 = refinement authority (style/cleanup).
        ks2_refine = [
            "refine contours with confident strokes",
            "improve line consistency",
            "clean and unify line quality",
        ]
        # If KS2 IP is low, avoid strong reference identity language even if mode says identity.
        if ip_ks2_w < 0.35 and reference_mode_ks2 == "identity":
            reference_mode_ks2 = "style"
        if reference_mode_ks2 == "identity":
            ks2_refine.extend(
                [
                    "match reference line weight",
                    "follow reference stroke confidence",
                ]
            )
        elif reference_mode_ks2 == "style":
            ks2_refine.extend(
                [
                    "adopt reference stroke clarity",
                    "subtle reference influence",
                ]
            )
        elif reference_mode_ks2 == "style_lite":
            ks2_refine.extend(
                [
                    "focus on clean uniform lines",
                    "no identity transfer",
                ]
            )

        if conflict_penalty > 0.4:
            ks2_refine.extend(
                [
                    "avoid color tint shifts",
                    "no added background tones",
                    "no additional design elements",
                ]
            )

        pos2 = _append_unique_tags(pos2, ks2_refine)

        # Phase / transition semantics.
        if transition.lower() == "roughs -> tie down":
            pos1 = _append_unique_tags(pos1, ["resolve rough sketch into stable structure", "clarify construction", "remove sketch noise"])
            pos2 = _append_unique_tags(pos2, ["tighten anatomy", "convert rough strokes into clean tied-down lines"])
        elif transition.lower() == "roughs -> cleanup":
            pos1 = _append_unique_tags(pos1, ["resolve rough sketch into stable structure"])
            pos2 = _append_unique_tags(pos2, ["convert rough strokes into final clean lines"])
        elif transition.lower() == "tie down -> cleanup":
            pos1 = _append_unique_tags(pos1, ["preserve tied-down structure"])
            pos2 = _append_unique_tags(pos2, ["final clean ink", "uniform stroke width", "professional animation-ready line art"])

        # Negatives: add halo/fringe suppression when conflict is high.
        if conflict_penalty > 0.4:
            halo_negs = [
                "(chromatic aberration:1.6)",
                "(color fringe:1.6)",
                "(colored outlines:1.6)",
                "(edge halos:1.6)",
                "double lines",
            ]
            neg1 = _append_unique_tags(neg1, halo_negs)
            neg2 = _append_unique_tags(neg2, halo_negs)

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
        if subject_profile == "character":
            pos1 = _append_unique_tags(pos1, anatomy_focus)
            pos2 = _append_unique_tags(pos2, anatomy_focus)
            pos2 = _append_unique_tags(pos2, ["clean hand anatomy", "clear finger separation", "single decisive contour per limb"])
        if entity_type == "single_complex":
            pos2 = _append_unique_tags(
                pos2,
                [
                    "solid ink",
                    "deep black lines",
                    "high-contrast",
                    "clean-cut edges",
                    "monochrome line art",
                    "absolute black #000000",
                    "knife-sharp edges",
                ],
            )
            neg2 = _append_unique_tags(
                neg2,
                [
                    "(chromatic aberration:1.5)",
                    "(color fringe:1.5)",
                    "(yellow edges:1.5)",
                    "(blue edges:1.5)",
                    "(dotted lines:1.8)",
                    "(pixel jitter:1.4)",
                    "(multicolored edges:1.8)",
                    "(anti-aliasing artifacts:1.5)",
                    "(pixelated lines:1.5)",
                    "(halftone dots:1.6)",
                    "jittery lines",
                    "sketchy residue",
                ],
            )

    # Director-driven prompt modifiers (dynamic guardrails / style notes).
    # Some modifiers are KS2-only and must never pollute KS1.
    prompt_mods = report.get("prompt_modifiers") or []
    if isinstance(prompt_mods, list):
        prompt_mods = [str(x).strip() for x in prompt_mods if str(x).strip()]
    else:
        prompt_mods = []
    if prompt_mods:
        ks2_only = {
            "match reference line weight",
            "follow reference stroke confidence",
            "adopt reference stroke clarity",
            "subtle reference influence",
            "refine contours with confident strokes",
        }
        pos1 = _append_unique_tags(pos1, [m for m in prompt_mods if m.lower() not in ks2_only])
        pos2 = _append_unique_tags(pos2, prompt_mods)

    # Character cleanup quality: remove rigid geometric constraints that make lines stiff.
    if subject_profile == "character":
        rigid_terms = [
            "precise geometry",
            "stable silhouette",
            "single unbroken stroke",
            "uniform line thickness",
        ]
        pos1 = _remove_exact_tags(pos1, rigid_terms)
        pos2 = _remove_exact_tags(pos2, rigid_terms)
    elif subject_profile in ("geometry", "object"):
        # Remove character/anatomy-specific tags for non-character cleanup.
        simple_cleanup_removals = [
            "clear anatomy",
            "accurate anatomy",
            "well-defined facial features",
            "clean hands",
            "clean feet",
            "clean legs",
            "clean torso",
            "clean hips",
            "clean shoulders",
            "clean hand anatomy",
            "clear finger separation",
            "single decisive contour per limb",
        ]
        pos1 = _remove_exact_tags(pos1, simple_cleanup_removals)
        pos2 = _remove_exact_tags(pos2, simple_cleanup_removals)

    # Keep clean-line enforcement limited to Tie Down / CleanUp phases.
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
    # Drop sentence-like long tags that dilute prompt quality.
    pos1 = ", ".join([t for t in [x.strip() for x in pos1.split(",") if x.strip()] if not re.search(r"[.?!;:]", t)])
    pos2 = ", ".join([t for t in [x.strip() for x in pos2.split(",") if x.strip()] if not re.search(r"[.?!;:]", t)])
    pos1 = _dedupe_tags(pos1)
    pos1 = _cap_prompt_tokens(pos1, max_tokens=75)
    neg1 = _dedupe_tags(neg1)
    neg1 = _drop_plain_when_weighted_exists(
        neg1,
        ["broken lines", "dotted lines", "construction lines", "guidelines", "sketchy lines"],
    )
    neg1 = _cap_prompt_tokens(neg1, max_tokens=75)
    pos2 = _dedupe_tags(pos2)
    neg2 = _dedupe_tags(neg2)
    neg2 = _drop_plain_when_weighted_exists(
        neg2,
        ["broken lines", "dotted lines", "construction lines", "guidelines", "sketchy lines"],
    )

    rationale = f"Stage1: {rationale1} Stage2: {rationale2}"
    logger.info(f"M4 Prompts generated. Rationale: {rationale}")
    return pos1, neg1, pos2, neg2, rationale
