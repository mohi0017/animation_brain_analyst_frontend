"""
Animation Director Agent (AD-Agent) - M3 Parameter Planner
"""

from __future__ import annotations

from .config import DEFAULT_LINE_ART_MODEL, DEFAULT_M3_MODEL
from .utils import get_logger

logger = get_logger("animation_director")


def create_parameter_plan_m3(
    report: dict,
    source_phase: str,
    dest_phase: str,
    pose_lock: bool = True,
    style_lock: bool = True,
) -> dict:
    """
    Compute M3 parameters based on analyst buckets and transition.
    Returns a dict with node-specific parameter values.
    """
    transition = f"{source_phase} -> {dest_phase}"
    line_quality = (report.get("line_quality") or "structured").lower()
    anatomy_risk = (report.get("anatomy_risk") or "medium").lower()
    complexity = (report.get("complexity") or "detailed").lower()
    entity_type = (report.get("entity_type") or "").lower().strip()
    entity_examples = (report.get("entity_examples") or "").lower().strip()
    construction_lines = (report.get("construction_lines") or "").lower().strip()
    low_construction_sublevel = (report.get("low_construction_sublevel") or "").lower().strip()
    broken_lines = (report.get("broken_lines") or "").lower().strip()
    notes = report.get("notes") or []
    issues = report.get("issues") or []
    subject_details = (report.get("subject_details") or "").lower()
    issue_text = " ".join(
        str(item) for item in (notes + issues) if isinstance(item, str)
    ).lower()
    simple_entity_text = f"{entity_examples} {subject_details}".lower()
    is_single_simple_geometric = entity_type == "single_simple" and any(
        key in simple_entity_text
        for key in ("circle", "ball", "football", "sphere", "oval", "shape", "ring")
    )

    def _apply_issue_overrides(plan: dict) -> dict:
        """
        Apply issue-driven tweaks even for early-return overrides.

        Plan shape:
          - ksampler1/2: {steps,cfg,denoise}
          - controlnet_union/openpose: {strength,end_percent}
          - ip_adapter: {weight,end_at}
        """
        if not issue_text:
            return plan

        cn_union = plan.get("controlnet_union", {})
        cn_openpose = plan.get("controlnet_openpose", {})
        ip = plan.get("ip_adapter", {})
        ks1 = plan.get("ksampler1", {})
        ks2 = plan.get("ksampler2", {})

        def _clampf(val, lo, hi):
            try:
                return max(lo, min(float(val), hi))
            except Exception:
                return lo

        # Over-processed output: slightly reduce refinement aggression + style.
        if "over-processed" in issue_text or "over processed" in issue_text:
            ks2["denoise"] = _clampf(ks2.get("denoise", 0.3) - 0.05, 0.1, 1.0)
            ks2["cfg"] = _clampf(ks2.get("cfg", 8.8) - 0.5, 5.0, 10.0)
            ip["weight"] = _clampf(ip.get("weight", 0.5) - 0.1, 0.0, 1.0)

        # Guidelines/construction lines being traced.
        if any(
            key in issue_text
            for key in (
                "double lines",
                "double-line",
                "double line",
                "kept guidelines",
                "kept guideline",
                "guidelines kept",
                "construction lines retained",
                "traced guidelines",
                "tracing guidelines",
            )
        ):
            cn_union["end_percent"] = _clampf(cn_union.get("end_percent", 0.6), 0.0, 0.50)
            cn_union["strength"] = _clampf(cn_union.get("strength", 0.6) - 0.10, 0.0, 1.0)
            ip["end_at"] = _clampf(ip.get("end_at", 0.4), 0.0, 0.30)
            ip["weight"] = _clampf(ip.get("weight", 0.5) - 0.15, 0.0, 1.0)
            ks1["denoise"] = _clampf(ks1.get("denoise", 0.7) + 0.05, 0.0, 1.0)

        # Pose drift.
        if "pose drift" in issue_text or "pose shift" in issue_text:
            cn_openpose["strength"] = 1.0
            cn_openpose["end_percent"] = _clampf(max(cn_openpose.get("end_percent", 0.9), 0.9), 0.0, 1.0)
            cn_union["strength"] = _clampf(cn_union.get("strength", 0.6) + 0.10, 0.0, 1.0)

        # Lines too thin/weak.
        if "thin lines" in issue_text or "weak lines" in issue_text:
            ks2["cfg"] = _clampf(ks2.get("cfg", 8.8) + 0.5, 5.0, 10.0)
            ks2["denoise"] = _clampf(ks2.get("denoise", 0.3) + 0.05, 0.1, 1.0)
            cn_union["strength"] = _clampf(cn_union.get("strength", 0.6) + 0.10, 0.0, 1.0)

        plan["controlnet_union"] = cn_union
        plan["controlnet_openpose"] = cn_openpose
        plan["ip_adapter"] = ip
        plan["ksampler1"] = ks1
        plan["ksampler2"] = ks2
        return plan

    def _low_construction_union_strength(default_strength: float) -> float:
        """
        Fine-grained mapping inside low-construction category:
        - none      -> 1.0
        - one_two   -> 0.9
        - two_three -> 0.8
        """
        if construction_lines != "low":
            return default_strength
        if low_construction_sublevel == "none":
            return 1.0
        if low_construction_sublevel == "one_two":
            return 0.9
        if low_construction_sublevel == "two_three":
            return 0.8
        return default_strength

    def _low_construction_ip_weight(default_weight: float) -> float:
        """
        Fine-grained IP weight mapping inside low-construction category.
        User rule: when Union maps to 0.9 (one_two), IP should be 0.7.
        """
        if construction_lines != "low":
            return default_weight
        if low_construction_sublevel == "one_two":
            return 0.7
        return default_weight

    # Special-case: single simple object + no construction lines.
    # In this scenario, we can fully trust the drawing signal and push the workflow toward a
    # near-deterministic "trace/ink" pass: max ControlNet, strong IP-Adapter, and aggressive denoise.
    if entity_type == "single_simple" and construction_lines == "low" and broken_lines not in ("medium", "high"):
        plan = {
            "transition": transition,
            "model_name": DEFAULT_M3_MODEL,
            "ksampler1": {"steps": 40, "cfg": 8.0, "denoise": 0.70},
            "ksampler2": {"steps": 50, "cfg": 7.0, "denoise": 0.50},
            "controlnet_union": {
                "strength": 0.9,
                "end_percent": 1.0,
            },
            "controlnet_openpose": {"strength": 1.0, "end_percent": 1.0},
            "ip_adapter": {
                "weight": 0.4,
                "end_at": 0.8,
            },
        }
        logger.info(f"Parameter plan created (single_simple+low_construction override): {plan}")
        return _apply_issue_overrides(plan)

    # Special-case: single simple object + low construction lines + broken lines.
    # Keep max guidance, but push the ink pass to reconnect linework.
    if entity_type == "single_simple" and construction_lines == "low" and broken_lines in ("medium", "high"):
        ks2_cfg = 9.6 if broken_lines == "high" else 9.2
        plan = {
            "transition": transition,
            "model_name": DEFAULT_M3_MODEL,
            "ksampler1": {"steps": 40, "cfg": 8.0, "denoise": 1.0},
            "ksampler2": {"steps": 40, "cfg": ks2_cfg, "denoise": 0.75 if broken_lines == "high" else 0.70},
            "controlnet_union": {
                "strength": _low_construction_union_strength(1.0),
                "end_percent": 1.0,
            },
            "controlnet_openpose": {"strength": 1.0, "end_percent": 1.0},
            "ip_adapter": {
                "weight": _low_construction_ip_weight(0.6),
                "end_at": 1.0,
            },
        }
        logger.info(
            "Parameter plan created (single_simple+low_construction+broken override): "
            f"broken_lines={broken_lines} plan={plan}"
        )
        return _apply_issue_overrides(plan)

    # Special-case: single simple object + construction lines present.
    # Reduce Union/IP so guidelines don't get traced; keep OpenPose max for consistency.
    # Use conservative denoise since guidance is weaker and we want to avoid hallucinated details.
    if entity_type == "single_simple" and construction_lines in ("medium", "high"):
        is_high = construction_lines == "high"
        plan = {
            "transition": transition,
            "model_name": DEFAULT_M3_MODEL,
            "ksampler1": {"steps": 40, "cfg": 8.0, "denoise": 0.70},
            "ksampler2": {
                "steps": 40,
                "cfg": 9.0 if broken_lines in ("medium", "high") else 8.8,
                "denoise": 0.60 if is_high else 0.65,
            },
            "controlnet_union": {"strength": 0.35 if is_high else 0.45, "end_percent": 0.45 if is_high else 0.55},
            "controlnet_openpose": {"strength": 1.0, "end_percent": 1.0},
            "ip_adapter": {"weight": 0.25 if is_high else 0.35, "end_at": 0.25 if is_high else 0.35},
        }
        logger.info(
            "Parameter plan created (single_simple+construction override): "
            f"construction_lines={construction_lines} broken_lines={broken_lines} plan={plan}"
        )
        return _apply_issue_overrides(plan)

    # Special-case: single complex object + low construction lines.
    # User requested: max ControlNet + max IP-Adapter, KS1 denoise=1, KS2 denoise=0.6.
    if entity_type == "single_complex" and construction_lines == "low":
        plan = {
            "transition": transition,
            "model_name": DEFAULT_M3_MODEL,
            "ksampler1": {"steps": 40, "cfg": 8.0, "denoise": 1.0},
            "ksampler2": {"steps": 40, "cfg": 8.8, "denoise": 0.60},
            "controlnet_union": {
                "strength": _low_construction_union_strength(1.0),
                "end_percent": 1.0,
            },
            "controlnet_openpose": {"strength": 1.0, "end_percent": 1.0},
            "ip_adapter": {"weight": 1.0, "end_at": 1.0},
        }
        logger.info(f"Parameter plan created (single_complex+low_construction override): {plan}")
        return _apply_issue_overrides(plan)

    # Special-case: single complex object + construction lines present.
    # Reduce Union/IP to avoid tracing guidelines and hallucinating details; keep OpenPose max.
    if entity_type == "single_complex" and construction_lines in ("medium", "high"):
        if construction_lines == "high" and broken_lines in ("medium", "high"):
            plan = {
                "transition": transition,
                "model_name": DEFAULT_M3_MODEL,
                # Emergency V2 preset: minimize segmentation/fringing under heavy roughness.
                "ksampler1": {"steps": 40, "cfg": 6.5, "denoise": 0.75},
                "ksampler2": {"steps": 50, "cfg": 6.5, "denoise": 0.30},
                "controlnet_union": {"strength": 0.90, "end_percent": 1.0},
                "controlnet_openpose": {"strength": 1.0, "end_percent": 1.0},
                "ip_adapter": {"weight": 0.0, "end_at": 0.0},
            }
            logger.info(
                "Parameter plan created (single_complex+construction high/medium_or_high override): "
                f"plan={plan}"
            )
            return _apply_issue_overrides(plan)

        is_high = construction_lines == "high"
        if not is_high and broken_lines in ("low", "medium"):
            plan = {
                "transition": transition,
                "model_name": DEFAULT_M3_MODEL,
                "ksampler1": {"steps": 40, "cfg": 8.0, "denoise": 0.70},
                "ksampler2": {"steps": 50, "cfg": 7.0, "denoise": 0.40},
                "controlnet_union": {"strength": 0.70, "end_percent": 0.8},
                "controlnet_openpose": {"strength": 1.0, "end_percent": 1.0},
                "ip_adapter": {"weight": 0.0, "end_at": 0.0},
            }
            logger.info(
                "Parameter plan created (single_complex+construction medium+broken low_or_medium override): "
                f"plan={plan}"
            )
            return _apply_issue_overrides(plan)

        plan = {
            "transition": transition,
            "model_name": DEFAULT_M3_MODEL,
            # Keep structure tighter and reduce stage-2 redraw to avoid dotted/pixelated contours.
            "ksampler1": {"steps": 40, "cfg": 9.0, "denoise": 0.70},
            "ksampler2": {"steps": 40, "cfg": 9.0, "denoise": 0.70 if is_high else 0.50},
            "controlnet_union": {"strength": 0.60 if is_high else 0.70, "end_percent": 0.60 if is_high else 1.0},
            "controlnet_openpose": {"strength": 1.0, "end_percent": 1.0},
            "ip_adapter": {"weight": 0.20 if is_high else 0.40, "end_at": 0.20 if is_high else 1.0},
        }
        logger.info(
            "Parameter plan created (single_complex+construction override): "
            f"construction_lines={construction_lines} broken_lines={broken_lines} plan={plan}"
        )
        return _apply_issue_overrides(plan)

    # Special-case: multi-object scene + low construction lines.
    # Keep structure stable (high OpenPose/Union), reduce style injection to avoid object hallucination.
    if entity_type == "multi_object" and construction_lines == "low":
        plan = {
            "transition": transition,
            "model_name": DEFAULT_M3_MODEL,
            "ksampler1": {"steps": 40, "cfg": 8.0, "denoise": 0.75},
            "ksampler2": {"steps": 50, "cfg": 9.0, "denoise": 0.60},
            "controlnet_union": {
                "strength": _low_construction_union_strength(0.7),
                "end_percent": 0.70,
            },
            "controlnet_openpose": {"strength": 1.0, "end_percent": 1.0},
            "ip_adapter": {"weight": 0.35, "end_at": 0.35},
        }
        logger.info(f"Parameter plan created (multi_object+low_construction override): {plan}")
        return _apply_issue_overrides(plan)

    # Special-case: multi-object scene + construction lines present.
    # Reduce Union/IP to avoid tracing guidelines and hallucinating extra objects; keep OpenPose max.
    if entity_type == "multi_object" and construction_lines in ("medium", "high"):
        is_high = construction_lines == "high"
        plan = {
            "transition": transition,
            "model_name": DEFAULT_M3_MODEL,
            "ksampler1": {"steps": 40, "cfg": 8.0, "denoise": 0.70},
            "ksampler2": {"steps": 50, "cfg": 9.2 if broken_lines in ("medium", "high") else 9.0, "denoise": 0.55 if is_high else 0.60},
            "controlnet_union": {"strength": 0.40 if is_high else 0.50, "end_percent": 0.45 if is_high else 0.55},
            "controlnet_openpose": {"strength": 1.0, "end_percent": 1.0},
            "ip_adapter": {"weight": 0.20 if is_high else 0.30, "end_at": 0.25 if is_high else 0.35},
        }
        logger.info(
            "Parameter plan created (multi_object+construction override): "
            f"construction_lines={construction_lines} broken_lines={broken_lines} plan={plan}"
        )
        return _apply_issue_overrides(plan)

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

    # Enforce openpose minimum requested by user (union clamp applied at end)
    openpose_strength = max(openpose_strength, 0.9)
    ks1_cfg = _clamp(ks1_cfg, 8.0, 10.0)
    ks2_cfg = _clamp(ks2_cfg, 8.0, 10.0)
    ks1_steps = 35
    ks2_steps = 35

    # Messy lines -> more structure lock, less style
    if line_quality == "messy":
        ks1_denoise = min(0.85, ks1_denoise + 0.1)
        cn_union_strength = _clamp(cn_union_strength + 0.1, 0.2, 1.0)
        cn_union_end = max(cn_union_end, 0.65)
        ip_weight = min(ip_weight, 0.4)
        ip_end = min(ip_end, 0.4)
        ks1_steps += 3

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
        ks1_steps += 2

    # Complexity rules
    if complexity == "simple":
        ks1_denoise = max(cfg["ks1_denoise"][0], ks1_denoise - 0.05)
        ip_weight = max(cfg["ip"][0], ip_weight - 0.1)
    elif complexity == "detailed":
        ks1_denoise = min(cfg["ks1_denoise"][1], ks1_denoise + 0.05)
        ip_weight = min(cfg["ip"][1], ip_weight + 0.1)
        ks1_steps += 2
        ks2_steps += 1

    # Entity-type rules (new analyst signal)
    # Rationale:
    # - multi_object scenes drift more; favor pose/structure lock and reduce style injection.
    # - single_simple objects should not be over-processed; reduce steps/strength slightly.
    if entity_type == "multi_object":
        cn_union_strength = _clamp(cn_union_strength + 0.05, 0.2, 1.0)
        cn_union_end = max(cn_union_end, 0.60)
        openpose_strength = max(openpose_strength, 0.95)
        openpose_end = max(openpose_end, 0.90)
        ip_weight = max(cfg["ip"][0], ip_weight - 0.15)
        ip_end = min(ip_end, 0.40)
        ks1_steps += 2
    elif entity_type == "single_simple":
        ks1_steps -= 2
        ks2_steps -= 2
        ks1_denoise = max(cfg["ks1_denoise"][0], ks1_denoise - 0.05)
        cn_union_strength = _clamp(cn_union_strength - 0.05, 0.2, 1.0)
        ip_weight = max(cfg["ip"][0], ip_weight - 0.05)

    # If it's not a character/person, OpenPose may be less reliable. Keep it high when pose_lock is on,
    # but avoid pushing it to the maximum unless it's clearly a character scene.
    if entity_examples and not any(k in entity_examples for k in ("person", "character", "human", "man", "woman", "boy", "girl")):
        if not pose_lock:
            openpose_strength = min(openpose_strength, 0.9)
        openpose_end = min(openpose_end, 0.9)

    # Construction/broken line rules (new analyst signal)
    # High construction lines: stop controlnets earlier so the model doesn't "trace" guidelines,
    # and increase denoise slightly to re-draw cleanly.
    if construction_lines == "high":
        ks1_denoise = min(0.90, ks1_denoise + 0.05)
        cn_union_end = min(cn_union_end, 0.55)
        cn_union_strength = _clamp(cn_union_strength - 0.05, 0.2, 1.0)
        ip_weight = max(cfg["ip"][0], ip_weight - 0.10)
        ip_end = min(ip_end, 0.35)
    elif construction_lines == "medium":
        cn_union_end = min(cn_union_end, 0.65)
        ip_weight = max(cfg["ip"][0], ip_weight - 0.05)

    # Broken lines: reinforce ink pass a bit.
    if broken_lines == "high":
        ks2_cfg = _clamp(ks2_cfg + 0.4, 5.0, 10.0)
        ks2_steps += 1
        cn_union_strength = _clamp(cn_union_strength + 0.05, 0.2, 1.0)
    elif broken_lines == "medium":
        ks2_cfg = _clamp(ks2_cfg + 0.2, 5.0, 10.0)

    # User override: when construction/broken lines are high, reduce Union + IP-Adapter to avoid
    # hallucinated objects and let the sampler correct lines; keep OpenPose at max for consistency.
    if construction_lines == "high" or broken_lines == "high":
        openpose_strength = 1.0
        openpose_end = max(openpose_end, 0.90)

        # Weaken structure guidance so guidelines don't get traced.
        cn_union_strength = _clamp(cn_union_strength - 0.15, 0.2, 1.0)
        cn_union_end = min(cn_union_end, 0.55)

        # Reduce style injection so the model doesn't invent details.
        ip_weight = max(0.2, ip_weight - 0.20)
        ip_end = min(ip_end, 0.35)

        # Denoise targets for this case.
        ks1_denoise = min(ks1_denoise, 0.70)
        ks2_denoise = _clamp(ks2_denoise, 0.50, 0.70)

        # Steps are locked later (KS1=40/KS2=40) for non-override paths; avoid step deltas here to
        # prevent dead logic. We tune denoise/strength/end_percent instead.

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

    # Guidelines/construction lines being traced -> end guidance earlier and redraw a bit more.
    if any(
        key in issue_text
        for key in (
            "double lines",
            "double-line",
            "double line",
            "kept guidelines",
            "kept guideline",
            "guidelines kept",
            "construction lines retained",
            "traced guidelines",
            "tracing guidelines",
        )
    ):
        cn_union_end = min(cn_union_end, 0.50)
        cn_union_strength = _clamp(cn_union_strength - 0.10, 0.2, 1.0)
        ip_end = min(ip_end, 0.30)
        ip_weight = max(0.2, ip_weight - 0.15)
        ks1_denoise = min(0.90, ks1_denoise + 0.05)

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

    # Core safe constraints
    # end_percent is expressed in [0.0, 1.0] for ComfyUI advanced controlnet nodes.
    openpose_end = _clamp(openpose_end, 0.0, 1.0)
    if openpose_end > 0.05:
        cn_union_end = min(cn_union_end, openpose_end - 0.15)
    cn_union_strength = _clamp(cn_union_strength, 0.3, 0.6)
    cn_union_end = _clamp(cn_union_end, 0.2, 0.9)
    # User request: lock both samplers to 40 steps for all non-override paths.
    ks1_steps = 40
    ks2_steps = 40
    if ip_end >= cn_union_end:
        ip_end = max(0.20, cn_union_end - 0.05)
    if ks2_denoise >= ks1_denoise:
        ks2_denoise = max(0.1, ks1_denoise - 0.1)

    # Low complexity + structured lines -> preserve detail
    if complexity == "simple" and line_quality == "structured":
        ks1_denoise = max(cfg["ks1_denoise"][0], ks1_denoise - 0.05)
        logger.info("Low complexity and structured lines detected: reducing KS1 denoise")

    model_name = DEFAULT_M3_MODEL

    plan = {
        "transition": transition,
        "model_name": model_name,
        "ksampler1": {
            "steps": ks1_steps,
            "cfg": round(ks1_cfg, 2),
            "denoise": round(ks1_denoise, 2),
        },
        "ksampler2": {
            "steps": ks2_steps,
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
