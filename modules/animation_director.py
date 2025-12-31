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
) -> dict:
    """
    Compute M2 parameters based on analyst buckets and transition.
    Returns a dict with node-specific parameter values.
    """
    transition = f"{source_phase} -> {dest_phase}"
    line_quality = (report.get("line_quality") or "structured").lower()
    anatomy_risk = (report.get("anatomy_risk") or "medium").lower()
    complexity = (report.get("complexity") or "detailed").lower()

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
    cn_union_strength = _mid(cfg["cn_union"][0], cfg["cn_union"][1])
    cn_union_end = cfg["cn_union"][2]
    openpose_strength = cfg["openpose"][0]
    openpose_end = cfg["openpose"][1]
    ip_weight = _mid(cfg["ip"][0], cfg["ip"][1])
    ip_end = cfg["ip"][2]

    # Rule C: messy lines increase KS1 denoise
    if line_quality == "messy":
        # Aggressive Rescue Strategy
        # Force high denoise to ignore construction lines
        ks1_denoise = 0.82 
        # Cut off ControlNet early to let model hallucinate clean lines
        cn_union_end = 0.55
        # Reduce style transfer for messy inputs to avoid color/style bleed
        ip_weight = min(ip_weight, 0.4)
        ip_end = min(ip_end, 0.4)

    # Rule A: high anatomy risk -> reduce style weight, force openpose strength
    if anatomy_risk == "high":
        ip_weight = max(cfg["ip"][0], ip_weight - 0.2)
        openpose_strength = 1.0

    # Complexity -> adjust IP weight
    if complexity == "simple":
        ip_weight = max(cfg["ip"][0], ip_weight - 0.1)
    elif complexity == "detailed":
        ip_weight = min(cfg["ip"][1], ip_weight + 0.1)

    # Rule B: openpose end must be >= 0.80 and union end 0.15 behind
    openpose_end = max(0.80, openpose_end)
    cn_union_end = min(cn_union_end, openpose_end - 0.15)

    # Rule D: low complexity + clean lines -> reduce denoise to preserve detail
    if complexity == "simple" and line_quality == "structured":
        ks1_denoise = max(cfg["ks1_denoise"][0], ks1_denoise - 0.05)
        logger.info("Low complexity and structured lines detected: reducing KS1 denoise")

    # Adapter ends before union
    if ip_end >= cn_union_end:
        ip_end = max(0.20, cn_union_end - 0.05)

    # CleanUp: enforce low style influence and lower KS2 denoise for pure lineart
    if dest_phase == "CleanUp":
        ip_weight = min(ip_weight, 0.25)
        ip_end = min(ip_end, 0.25)
        ks2_denoise = min(ks2_denoise, 0.25)

    # Tie Down: reduce style influence and soften KS1 denoise to avoid fill/shading
    if dest_phase == "Tie Down":
        ip_weight = min(ip_weight, 0.15)
        ip_end = min(ip_end, 0.20)
        ks1_denoise = min(ks1_denoise, 0.70)

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
            "cfg": 7.5,
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
