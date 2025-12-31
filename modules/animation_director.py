"""
Animation Director Agent (AD-Agent) - M2 Parameter Planner
"""

from __future__ import annotations

from .config import DEFAULT_LINE_ART_MODEL, DEFAULT_M2_MODEL
from .utils import get_logger

logger = get_logger("animation_director")


def create_parameter_plan_m2(
    report: dict,
    source_phase: str,
    dest_phase: str,
    pose_lock: bool = True,
    style_lock: bool = True,
) -> dict:
    """
    Compute M2 parameters based on analyst buckets and transition.
    Returns a dict with node-specific parameter values.
    """
    transition = f"{source_phase} -> {dest_phase}"
    line_quality = (report.get("line_quality") or "structured").lower()
    anatomy_risk = (report.get("anatomy_risk") or "medium").lower()
    complexity = (report.get("complexity") or "detailed").lower()
    notes = report.get("notes") or []
    issues = report.get("issues") or []
    issue_text = " ".join(
        str(item) for item in (notes + issues) if isinstance(item, str)
    ).lower()

    matrix = {
        "Roughs->Tie Down": {
            "ks1_denoise": (0.55, 0.65),
            "ks1_cfg": (6.5, 7.5),
            "ks2_denoise": (0.20, 0.25),
            "cn_union": (0.55, 0.65, 0.50),
            "openpose": (0.9, 0.80),
            "ip": (0.4, 0.5, 0.40),
        },
        "Roughs->CleanUp": {
            "ks1_denoise": (0.70, 0.80),
            "ks1_cfg": (7.0, 8.0),
            "ks2_denoise": (0.30, 0.35),
            "cn_union": (0.7, 0.8, 0.50),
            "openpose": (1.0, 0.85),
            "ip": (0.6, 0.8, 0.60),
        },
        "Tie Down->CleanUp": {
            "ks1_denoise": (0.35, 0.45),
            "ks1_cfg": (7.0, 8.0),
            "ks2_denoise": (0.20, 0.30),
            "cn_union": (0.5, 0.6, 0.80),
            "openpose": (0.8, 0.90),
            "ip": (0.5, 0.7, 0.50),
        },
    }

    key = f"{source_phase}->{dest_phase}"
    if key not in matrix:
        key = "Roughs->CleanUp"
    cfg = matrix[key]

    def _mid(lo, hi):
        return (lo + hi) / 2

    ks1_denoise = _mid(*cfg["ks1_denoise"])
    ks1_cfg = _mid(*cfg["ks1_cfg"])
    ks2_denoise = _mid(*cfg["ks2_denoise"])
    ks2_cfg = 8.8
    cn_union_strength = _mid(cfg["cn_union"][0], cfg["cn_union"][1])
    cn_union_end = cfg["cn_union"][2]
    openpose_strength = cfg["openpose"][0]
    openpose_end = cfg["openpose"][1]
    ip_weight = _mid(cfg["ip"][0], cfg["ip"][1])
    ip_end = cfg["ip"][2]

    def _clamp(val, lo, hi):
        return max(lo, min(val, hi))

    # Enforce minimums requested by user
    cn_union_strength = max(cn_union_strength, 0.6)
    openpose_strength = max(openpose_strength, 0.9)
    openpose_end = 0.0

    # Messy lines -> more structure lock, less style
    if line_quality == "messy":
        ks1_denoise = min(0.85, ks1_denoise + 0.1)
        cn_union_strength = _clamp(cn_union_strength + 0.1, 0.2, 1.0)
        cn_union_end = max(cn_union_end, 0.65)
        ip_weight = min(ip_weight, 0.4)
        ip_end = min(ip_end, 0.4)

    # Clean lines -> relax structure, push cleanup
    if line_quality == "clean":
        ks1_denoise = max(cfg["ks1_denoise"][0], ks1_denoise - 0.1)
        cn_union_strength = _clamp(cn_union_strength - 0.1, 0.2, 1.0)
        cn_union_end = min(cn_union_end, 0.5)
        ks2_denoise = _clamp(ks2_denoise + 0.05, 0.1, 0.6)

    # High anatomy risk -> stronger pose lock, reduced style
    if anatomy_risk == "high":
        ip_weight = max(cfg["ip"][0], ip_weight - 0.2)
        openpose_strength = 1.0
        openpose_end = max(openpose_end, 0.9)

    # Complexity rules
    if complexity == "simple":
        ks1_denoise = max(cfg["ks1_denoise"][0], ks1_denoise - 0.05)
        ip_weight = max(cfg["ip"][0], ip_weight - 0.1)
    elif complexity == "detailed":
        ks1_denoise = min(cfg["ks1_denoise"][1], ks1_denoise + 0.05)
        ip_weight = min(cfg["ip"][1], ip_weight + 0.1)

    # Need strong pose lock
    if pose_lock:
        openpose_strength = max(openpose_strength, 0.9)
        openpose_end = max(openpose_end, 0.85)
        ks1_cfg = min(ks1_cfg, 8.0)

    # Need strong style match (explicit flag)
    if report.get("style_match") is True:
        ip_weight = min(1.0, ip_weight + 0.1)
        ip_end = min(0.8, ip_end + 0.05)
    elif style_lock:
        ip_weight = min(ip_weight, 0.6)

    # CleanUp: anatomy/structure priority on top
    if dest_phase == "CleanUp":
        openpose_strength = max(openpose_strength, 0.9)
        openpose_end = max(openpose_end, 0.85)
        cn_union_strength = max(cn_union_strength, 0.55)
        ip_weight = min(ip_weight, 0.5)

    # Tie Down: reduce style influence to keep lineart neutral
    if dest_phase == "Tie Down":
        ip_weight = min(ip_weight, 0.3)
        ip_end = min(ip_end, 0.3)
        ks1_denoise = min(ks1_denoise, 0.7)

    # Over-processed output
    if "over-processed" in issue_text or "over processed" in issue_text:
        ks2_denoise = _clamp(ks2_denoise - 0.05, 0.1, 0.6)
        ks2_cfg = max(5.0, ks2_cfg - 0.5)
        ip_weight = max(0.2, ip_weight - 0.1)

    # Pose drift
    if "pose drift" in issue_text or "pose shift" in issue_text:
        openpose_strength = 1.0
        openpose_end = max(openpose_end, 0.9)
        cn_union_strength = _clamp(cn_union_strength + 0.1, 0.2, 1.0)
        ks1_denoise = max(cfg["ks1_denoise"][0], ks1_denoise - 0.05)

    # Lines too thin/weak
    if "thin lines" in issue_text or "weak lines" in issue_text:
        ks2_cfg = min(10.0, ks2_cfg + 0.5)
        ks2_denoise = _clamp(ks2_denoise + 0.05, 0.1, 0.6)
        cn_union_strength = _clamp(cn_union_strength + 0.1, 0.2, 1.0)

    # Core safe constraints (skip gap rule when OpenPose end is 0.0)
    if openpose_end > 0:
        openpose_end = max(0.80, openpose_end)
        cn_union_end = min(cn_union_end, openpose_end - 0.15)
    cn_union_end = _clamp(cn_union_end, 0.2, 0.9)
    if ip_end >= cn_union_end:
        ip_end = max(0.20, cn_union_end - 0.05)
    if ks2_denoise >= ks1_denoise:
        ks2_denoise = max(0.1, ks1_denoise - 0.1)

    # Low complexity + structured lines -> preserve detail
    if complexity == "simple" and line_quality == "structured":
        ks1_denoise = max(cfg["ks1_denoise"][0], ks1_denoise - 0.05)
        logger.info("Low complexity and structured lines detected: reducing KS1 denoise")

    model_name = DEFAULT_M2_MODEL

    plan = {
        "transition": transition,
        "model_name": model_name,
        "ksampler1": {
            "steps": 30,
            "cfg": round(ks1_cfg, 2),
            "denoise": round(ks1_denoise, 2),
        },
        "ksampler2": {
            "steps": 30,
            "cfg": round(ks2_cfg, 2),
            "denoise": round(ks2_denoise, 2),
        },
        "controlnet_union": {
            "strength": round(cn_union_strength, 2),
            "end_percent": round(cn_union_end, 2),
        },
        "controlnet_openpose": {
            "strength": round(openpose_strength, 2),
            "end_percent": round(openpose_end, 2),
        },
        "ip_adapter": {
            "weight": round(ip_weight, 2),
            "end_at": round(ip_end, 2),
        },
    }
    logger.info(f"Parameter plan created: {plan}")
    return plan
