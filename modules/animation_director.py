"""
Animation Director Agent (AD-Agent) - M4 Parameter Planner
"""

from __future__ import annotations

from .config import DEFAULT_LINE_ART_MODEL, DEFAULT_M4_MODEL
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
    Compute M4 parameters based on analyst buckets and transition.
    Returns a dict with node-specific parameter values.
    """
    transition = f"{source_phase} -> {dest_phase}"
    line_quality = (report.get("line_quality") or "structured").lower()
    anatomy_risk = (report.get("anatomy_risk") or "medium").lower()
    complexity = (report.get("complexity") or "complex").lower()
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

    def _apply_reference_correlation(plan: dict) -> dict:
        """
        Scale IP-Adapter + related parameters based on input-vs-reference similarity.

        We rely on a multi-layer similarity signal computed in the app:
          report['reference_final_score'] in [0,1] (higher = more similar).
          report['reference_conflict_penalty'] in [0,1] (higher = more conflict).

        When the reference conflicts with the sketch, strong IP often introduces
        chromatic fringing and background tint. When it matches, IP helps line quality.
        """
        sim = report.get("reference_final_score")
        if sim is None:
            return plan
        try:
            sim = float(sim)
        except Exception:
            return plan
        sim = max(0.0, min(1.0, sim))

        try:
            conflict_penalty = float(report.get("reference_conflict_penalty") or 0.0)
        except Exception:
            conflict_penalty = 0.0
        conflict_penalty = max(0.0, min(1.0, conflict_penalty))

        # Phase awareness: later phases can tolerate more reference influence.
        if dest_phase.lower() in ("roughs", "skeleton"):
            phase_factor = 0.6
        elif dest_phase.lower() in ("tie down", "tiedown"):
            phase_factor = 0.8
        else:
            phase_factor = 1.0

        I_final = sim * phase_factor * (1.0 - conflict_penalty)
        I_final = max(0.0, min(1.0, float(I_final)))

        ip = dict(plan.get("ip_adapter", {}) or {})
        cn_union = dict(plan.get("controlnet_union", {}) or {})
        ks1 = dict(plan.get("ksampler1", {}) or {})
        ks2 = dict(plan.get("ksampler2", {}) or {})

        # Continuous scaling (stable, no buckets).
        desired_ip_w = 0.15 + 0.65 * I_final
        desired_ip_end = 0.30 + 0.60 * I_final

        # Early-only influence for conflict cases (prevents late-stage tint bleeding).
        if conflict_penalty > 0.40:
            desired_ip_end = min(desired_ip_end, 0.50)

        desired_ip_w = max(0.15, min(0.80, desired_ip_w))
        desired_ip_end = max(0.30, min(0.95, desired_ip_end))

        ip["weight"] = round(desired_ip_w, 2)
        ip["end_at"] = round(desired_ip_end, 2)

        # "Dual IP" logical roles (KS1 vs KS2). Current ComfyUI graph has a single IPAdapter node,
        # so this is used for prompt intensity + logging today. If we later duplicate IPAdapter
        # nodes per sampler, these values can be applied directly.
        ip_ks1_w = max(0.15, min(0.8, float(ip["weight"]) * 1.0))
        ip_ks1_end = max(0.30, min(0.95, float(ip["end_at"]) * 0.9))
        ip_ks2_w = max(0.15, min(0.8, float(ip["weight"]) * 0.55))
        ip_ks2_end = max(0.30, min(0.95, float(ip["end_at"]) * 0.75))
        if conflict_penalty > 0.4:
            ip_ks2_end = min(ip_ks2_end, 0.50)
        plan["ip_adapter_dual"] = {
            "ksampler1": {"weight": round(ip_ks1_w, 2), "end_at": round(ip_ks1_end, 2)},
            "ksampler2": {"weight": round(ip_ks2_w, 2), "end_at": round(ip_ks2_end, 2)},
        }

        # Master influence scalar (single control variable).
        plan["_influence_scalar"] = round(I_final, 3)

        # Reference mode switching (used for later logic + debugging).
        if I_final >= 0.7:
            plan["reference_mode"] = "identity"
        elif I_final >= 0.4:
            plan["reference_mode"] = "style"
        else:
            plan["reference_mode"] = "style_lite"
        # KS2 is cleanup/refinement only; never allow identity-structure adoption in stage 2.
        plan["reference_mode_ks2"] = "style" if plan["reference_mode"] == "identity" else plan["reference_mode"]

        # Prompt modifiers (consumed by prompt_engineer).
        prompt_modifiers: list[str] = []
        if conflict_penalty > 0.4:
            prompt_modifiers.extend(
                [
                    "preserve original pose exactly",
                    "preserve original facial proportions",
                    "keep original accessories",
                ]
            )
        if I_final > 0.6:
            prompt_modifiers.extend(
                [
                    "match reference line weight",
                    "follow reference stroke confidence",
                ]
            )
        if prompt_modifiers:
            plan["prompt_modifiers"] = prompt_modifiers

        # Union coupling: lower influence -> stronger structure lock; higher influence -> allow style shaping.
        base_union = float(cn_union.get("strength", 0.7) or 0.7)
        union_strength = base_union * (0.7 + 0.6 * (1.0 - I_final))
        cn_union["strength"] = max(0.35, min(1.0, union_strength))

        # KSampler coupling:
        # KS1 (structure pass) should trust the sketch more when reference is unreliable.
        base_ks1_cfg = float(ks1.get("cfg", 8.0) or 8.0)
        base_ks1_den = float(ks1.get("denoise", 0.7) or 0.7)
        ks1["cfg"] = max(7.0, min(10.0, base_ks1_cfg - 0.6 * conflict_penalty))
        ks1["denoise"] = max(0.1, min(1.0, min(0.6, base_ks1_den + 0.2 * (1.0 - I_final))))

        # KS2 (refinement pass) takes full influence scalar but stays safe under conflicts.
        base_ks2_cfg = float(ks2.get("cfg", 8.0) or 8.0)
        base_ks2_den = float(ks2.get("denoise", 0.4) or 0.4)
        ks2["cfg"] = max(8.5, min(10.0, base_ks2_cfg + 0.5 * I_final - 0.5 * conflict_penalty))
        ks2["denoise"] = max(0.1, min(1.0, base_ks2_den - 0.15 * I_final))

        # Extra fringing protection: when conflict is high, reduce KS2 cfg slightly.
        if conflict_penalty > 0.5:
            ks2["cfg"] = max(8.5, float(ks2["cfg"]) - 0.5)

        plan["ip_adapter"] = ip
        plan["controlnet_union"] = cn_union
        plan["ksampler1"] = ks1
        plan["ksampler2"] = ks2
        return plan

    def _apply_issue_overrides(plan: dict) -> dict:
        """
        Apply issue-driven tweaks even for early-return overrides.

        Plan shape:
          - ksampler1/2: {steps,cfg,denoise}
          - controlnet_union/openpose: {strength,end_percent}
          - ip_adapter: {weight,end_at}
        """
        plan = _apply_reference_correlation(plan)
        # Apply full adaptive control system for complex cases even when there are no explicit issues.
        if entity_type == "single_complex":
            try:
                plan = _apply_adaptive_control(plan)
            except Exception:
                pass
        # Keep semantic controls aligned with the final numeric plan to avoid prompt/parameter drift.
        try:
            inf = float(plan.get("_influence_scalar") or 0.0)
        except Exception:
            inf = 0.0
        if inf >= 0.7:
            plan["reference_mode"] = "identity"
        elif inf >= 0.4:
            plan["reference_mode"] = "style"
        else:
            plan["reference_mode"] = "style_lite"
        # Keep KS2 refinement-only semantics aligned with numeric controller.
        plan["reference_mode_ks2"] = "style" if plan["reference_mode"] == "identity" else plan["reference_mode"]
        mods: list[str] = []
        if float(report.get("reference_conflict_penalty") or 0.0) > 0.4:
            mods.extend(
                [
                    "preserve original pose exactly",
                    "preserve original facial proportions",
                    "keep original accessories",
                ]
            )
        if plan.get("reference_mode_ks2") == "identity":
            mods.extend(["match reference line weight", "follow reference stroke confidence"])
        if mods:
            plan["prompt_modifiers"] = mods
        else:
            plan.pop("prompt_modifiers", None)
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
            ks2["cfg"] = _clampf(ks2.get("cfg", 8.8) - 0.5, 8.5, 10.0)
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
            ks2["cfg"] = _clampf(ks2.get("cfg", 8.8) + 0.5, 8.5, 10.0)
            ks2["denoise"] = _clampf(ks2.get("denoise", 0.3) + 0.05, 0.1, 1.0)
            cn_union["strength"] = _clampf(cn_union.get("strength", 0.6) + 0.10, 0.0, 1.0)

        plan["controlnet_union"] = cn_union
        plan["controlnet_openpose"] = cn_openpose
        plan["ip_adapter"] = ip
        plan["ksampler1"] = ks1
        plan["ksampler2"] = ks2
        # Final CFG safety envelope.
        try:
            ks1["cfg"] = _clampf(ks1.get("cfg", 7.0), 7.0, 10.0)
            ks2["cfg"] = _clampf(ks2.get("cfg", 8.5), 8.5, 10.0)
            ks2["cfg"] = min(ks2["cfg"], ks1["cfg"])
            plan["ksampler1"] = ks1
            plan["ksampler2"] = ks2
        except Exception:
            pass
        return plan

    def _apply_adaptive_control(plan: dict) -> dict:
        """
        Formal adaptive control system mapping image-aware signals -> node values.

        Signals:
          S: structure confidence (0..1)  (higher => trust sketch)
          R: reference reliability (0..1) (higher => trust reference)
          D: style distance (0..1)        (higher => rough vs ref mismatch)
          P: pose risk (0..1)             (higher => pose/anatomy unstable)
          H: hallucination risk (0..1)    (higher => likely extra objects/fringing)
        """
        # --- Compute signals ---
        c = construction_lines
        b = broken_lines
        lq = line_quality
        ar = anatomy_risk

        # Structure confidence S: penalize construction/broken lines; reward clean line quality.
        c_pen = {"low": 0.1, "medium": 0.45, "high": 0.8}.get(c, 0.45)
        b_pen = {"low": 0.1, "medium": 0.4, "high": 0.75}.get(b, 0.4)
        lq_bonus = {"clean": 0.25, "structured": 0.15, "messy": 0.0}.get(lq, 0.1)
        S = 1.0 - (0.55 * c_pen + 0.45 * b_pen)
        S = max(0.0, min(1.0, S + lq_bonus))

        # Pose risk P: driven by anatomy risk; simple proxy for now.
        P = {"low": 0.25, "medium": 0.55, "high": 0.85}.get(ar, 0.55)
        if pose_lock:
            P = min(1.0, P + 0.05)

        # Reference reliability R: final_score tempered by conflict.
        try:
            sim = float(report.get("reference_final_score") or 0.0)
        except Exception:
            sim = 0.0
        try:
            conflict = float(report.get("reference_conflict_penalty") or 0.0)
        except Exception:
            conflict = 0.0
        try:
            text_conflict = float(report.get("reference_text_conflict") or 0.0)
        except Exception:
            text_conflict = 0.0
        try:
            image_conflict = float(report.get("reference_image_conflict") or 0.0)
        except Exception:
            image_conflict = 0.0
        try:
            accessory_mismatch = float(report.get("reference_accessory_mismatch") or 0.0)
        except Exception:
            accessory_mismatch = 0.0
        reference_is_colored = bool(report.get("reference_is_colored") or False)
        sim = max(0.0, min(1.0, sim))
        conflict = max(0.0, min(1.0, conflict))
        text_conflict = max(0.0, min(1.0, text_conflict))
        image_conflict = max(0.0, min(1.0, image_conflict))
        accessory_mismatch = max(0.0, min(1.0, accessory_mismatch))
        R = max(0.0, min(1.0, sim * (1.0 - conflict)))

        # Style distance D from reference compare (0..1), default 0.0 when no reference.
        try:
            D = float(report.get("reference_style_distance") or 0.0)
        except Exception:
            D = 0.0
        D = max(0.0, min(1.0, D))

        # --- Map signals -> raw values ---
        ks1 = dict(plan.get("ksampler1", {}) or {})
        ks2 = dict(plan.get("ksampler2", {}) or {})
        cn_union = dict(plan.get("controlnet_union", {}) or {})
        cn_pose = dict(plan.get("controlnet_openpose", {}) or {})

        # Raw node values from signals (before bounds).
        union_strength = 0.5 + 0.4 * (1.0 - S)
        pose_strength = 0.6 + 0.4 * P
        ip1 = 0.4 + 0.5 * R - 0.4 * P
        ip2 = 0.2 + 0.3 * R - 0.5 * conflict
        cfg1 = 7.5 - 0.7 * conflict
        denoise1 = 0.6 + 0.3 * (1.0 - R)
        cfg2 = 7.5 + 0.5 * R - 0.6 * conflict
        denoise2 = 0.45 - 0.2 * R

        # Style gap: allow a little more KS2 cleanup pressure.
        if D > 0.5:
            denoise2 += 0.08
            ip2 += 0.05

        # Prompt strictness intent (text obedience), used for CFG only.
        strict_phrases = (
            "exactly",
            "unchanged",
            "preserve original",
            "no deviation",
            "strictly",
            "perfect",
        )
        strict_hits = sum(1 for p in strict_phrases if p in issue_text)
        intent_strength = max(0.0, min(1.0, strict_hits / 4.0))
        # Global policy: CFG is always allowed in [7, 10], while effective limits stay adaptive.
        base_cfg = 7.2 + (1.8 * intent_strength)
        cfg1 = max(cfg1, base_cfg)
        cfg2 = max(cfg2, base_cfg - 0.5)

        # --- Dynamic bound profiles by case ---
        # object_scale can be provided by analyst; fallback from case.
        object_scale = (report.get("object_scale") or "").lower().strip()
        if not object_scale:
            if entity_type == "single_simple":
                object_scale = "small"
            elif entity_type == "single_complex":
                object_scale = "large"
            else:
                object_scale = "medium"
        subject_text = f"{entity_examples} {subject_details}".lower()
        is_human_subject = any(
            k in subject_text
            for k in ("person", "character", "human", "woman", "women", "man", "men", "female", "male", "girl", "boy")
        )

        if entity_type == "single_simple":
            bounds = {
                "union": [0.75, 1.00],
                "openpose": [0.85, 1.00],
                "ip1": [0.35, 0.80],
                "ip2": [0.15, 0.45],
                "ks1_den": [0.55, 0.90],
                "ks2_den": [0.25, 0.60],
                "cfg1": [7.0, 10.0],
                "cfg2": [8.5, 10.0],
            }
            cfg1_eff_max = 9.6
            cfg2_eff_max = 8.6
        elif entity_type == "multi_object":
            bounds = {
                "union": [0.55, 0.90],
                "openpose": [0.85, 1.00],
                "ip1": [0.25, 0.60],
                "ip2": [0.15, 0.40],
                "ks1_den": [0.50, 0.80],
                "ks2_den": [0.20, 0.50],
                "cfg1": [7.0, 10.0],
                "cfg2": [8.5, 10.0],
            }
            cfg1_eff_max = 9.2
            cfg2_eff_max = 8.2
        else:  # single_complex default
            bounds = {
                "union": [0.40, 0.70],
                "openpose": [0.75, 0.95],
                "ip1": [0.30, 0.70],
                "ip2": [0.15, 0.50],
                "ks1_den": [0.55, 0.85],
                "ks2_den": [0.22, 0.55],
                "cfg1": [7.0, 10.0],
                "cfg2": [8.5, 10.0],
            }
            cfg1_eff_max = 9.2
            cfg2_eff_max = 8.4

        clamp_reasons: list[str] = []

        # --- Signal-based bound adjustments ---
        if conflict > 0.4:
            bounds["ip1"][1] = min(bounds["ip1"][1], 0.55)
            bounds["ip2"][1] = min(bounds["ip2"][1], 0.30)
            clamp_reasons.append("high_conflict_tightened_ip_bounds")
        if reference_is_colored:
            bounds["ip2"][1] = min(bounds["ip2"][1], 0.35)
            clamp_reasons.append("colored_reference_capped_ip2")
        if accessory_mismatch >= 0.35:
            bounds["ip2"][1] = min(bounds["ip2"][1], 0.30)
            clamp_reasons.append("accessory_mismatch_capped_ip2_max")
        if LQ := {"clean": 0.85, "structured": 0.6, "messy": 0.3}.get(line_quality, 0.5):
            if LQ < 0.4:
                bounds["ks1_den"][1] = min(1.0, bounds["ks1_den"][1] + 0.05)
                bounds["ip1"][1] = min(0.85, bounds["ip1"][1] + 0.05)
                clamp_reasons.append("low_line_quality_expanded_ks1_repair")
            elif LQ > 0.75:
                bounds["ip2"][1] = max(bounds["ip2"][0], bounds["ip2"][1] - 0.10)
                bounds["ks2_den"][1] = max(bounds["ks2_den"][0], bounds["ks2_den"][1] - 0.05)
                clamp_reasons.append("high_line_quality_reduced_ks2_interference")
        if P > 0.7:
            bounds["ip1"][1] = max(bounds["ip1"][0], bounds["ip1"][1] - 0.05)
            clamp_reasons.append("high_pose_risk_reduced_ip1")
        if object_scale == "large":
            bounds["union"][1] = min(bounds["union"][1], 0.80)
            bounds["union"][0] = max(bounds["union"][0], 0.70)
            clamp_reasons.append("large_object_capped_union")
            # User policy: for large human subjects, keep denoise floors higher
            # so KS1 stabilizes structure and KS2 has enough cleanup authority.
            if is_human_subject:
                bounds["ks1_den"][0] = max(bounds["ks1_den"][0], 0.75)
                bounds["ks1_den"][1] = min(0.90, max(bounds["ks1_den"][1], 0.90))
                bounds["ks2_den"][0] = max(bounds["ks2_den"][0], 0.30)
                bounds["ks2_den"][1] = min(bounds["ks2_den"][1], 0.55)
                clamp_reasons.append("large_human_min_denoise_enforced")
        elif object_scale == "small":
            bounds["union"][1] = 1.00

        def _clamp(v, lo, hi):
            return max(lo, min(hi, v))

        # --- Clamp inside dynamic bounds ---
        union_strength = _clamp(union_strength, bounds["union"][0], bounds["union"][1])
        pose_strength = _clamp(pose_strength, bounds["openpose"][0], bounds["openpose"][1])
        ip1 = _clamp(ip1, bounds["ip1"][0], bounds["ip1"][1])
        ip2 = _clamp(ip2, bounds["ip2"][0], bounds["ip2"][1])
        denoise1 = _clamp(denoise1, bounds["ks1_den"][0], bounds["ks1_den"][1])
        denoise2 = _clamp(denoise2, bounds["ks2_den"][0], bounds["ks2_den"][1])
        cfg1 = _clamp(cfg1, bounds["cfg1"][0], bounds["cfg1"][1])
        cfg2 = _clamp(cfg2, bounds["cfg2"][0], bounds["cfg2"][1])

        # Stage envelopes under global [7,10] allowance.
        cfg1 = min(cfg1, cfg1_eff_max)
        cfg2 = min(cfg2, cfg2_eff_max)

        # Strong structure locks already constrain geometry; relax CFG1 a bit.
        if union_strength > 0.75 or pose_strength > 0.90:
            cfg1 = _clamp(cfg1 - 0.4, bounds["cfg1"][0], min(bounds["cfg1"][1], cfg1_eff_max))
            clamp_reasons.append("strong_structure_lock_relaxed_cfg1")

        # --- Final hard rules ---
        noisy_or_conflicted = (
            line_quality == "messy"
            or conflict >= 0.40
            or D >= 0.35
            or text_conflict >= 0.35
            or image_conflict >= 0.35
        )
        if noisy_or_conflicted:
            pose_strength = max(pose_strength, 0.95)
            union_strength = _clamp(union_strength, 0.70, 0.80)
            denoise1 = _clamp(denoise1, 0.75, 0.90)
            denoise2 = _clamp(denoise2, 0.30, 0.55)
            ip1 = min(ip1, 0.45)
            ip2 = min(ip2, 0.35)
            clamp_reasons.append("noisy_or_conflicted_dynamic_caps")
        else:
            ip2 = max(ip2, 0.50)
        if ip1 < ip2 + 0.10:
            ip1 = min(0.85, ip2 + 0.10)
        ip2 = min(ip2, max(bounds["ip2"][0], ip1 - 0.10))  # asymmetric dual-IP
        cn_union["end_percent"] = min(float(cn_union.get("end_percent", 1.0)), 0.85)
        pose_strength = min(pose_strength, 1.0)
        cfg1 = min(cfg1, 10.0)
        cfg2 = min(cfg2, 10.0)
        if ip2 > 0.50:
            cfg2 = min(cfg2, 7.4)
            clamp_reasons.append("ip2_gt_0_50_capped_cfg2_7_4")
        elif ip2 > 0.40:
            cfg2 = min(cfg2, 7.8)
            clamp_reasons.append("ip2_gt_0_40_capped_cfg2_7_8")
        cfg2 = min(cfg2, cfg1)
        ip1 = min(ip1, 0.85)
        if noisy_or_conflicted:
            ip2 = max(0.15, min(ip2, 0.35))
        else:
            ip2 = max(0.50, min(ip2, 0.80))
        denoise2 = min(denoise2, 0.60)

        ks1["cfg"] = round(cfg1, 2)
        ks1["denoise"] = round(denoise1, 2)
        ks2["cfg"] = round(cfg2, 2)
        ks2["denoise"] = round(denoise2, 2)
        cn_union["strength"] = round(union_strength, 2)
        cn_pose["strength"] = round(pose_strength, 2)
        cn_pose["end_percent"] = round(max(float(cn_pose.get("end_percent", 1.0)), 0.9 if P > 0.6 else 0.75), 2)

        # Hallucination risk H: if too high, dampen KS2 cfg + IP2 and re-clamp.
        cfg2_n = (float(ks2["cfg"]) - 8.5) / max(1e-6, (10.0 - 8.5))
        den2_n = (float(ks2["denoise"]) - bounds["ks2_den"][0]) / max(1e-6, (bounds["ks2_den"][1] - bounds["ks2_den"][0]))
        H = max(0.0, min(1.0, 0.30 * cfg2_n + 0.30 * den2_n + 0.25 * ip2 + 0.15 * conflict))
        if H > 0.6:
            ks1["cfg"] = round(_clamp(float(ks1["cfg"]) - 0.3, bounds["cfg1"][0], min(bounds["cfg1"][1], cfg1_eff_max)), 2)
            ks2["cfg"] = round(_clamp(float(ks2["cfg"]) - 0.5, bounds["cfg2"][0], min(bounds["cfg2"][1], cfg2_eff_max)), 2)
            ip2 = _clamp(ip2 - 0.10, bounds["ip2"][0], bounds["ip2"][1])
            ip2 = min(ip2, max(bounds["ip2"][0], ip1 - 0.10))
            ks2["cfg"] = round(min(float(ks2["cfg"]), float(ks1["cfg"])), 2)
            clamp_reasons.append("high_H_dampened_cfg_and_ip2")

        # Store diagnostics for UI/debug.
        plan["diagnostics"] = {
            "S_structure_confidence": round(S, 3),
            "R_reference_reliability": round(R, 3),
            "D_style_distance": round(D, 3),
            "P_pose_risk": round(P, 3),
            "H_hallucination_risk": round(H, 3),
            "conflict_penalty": round(conflict, 3),
            "text_conflict": round(text_conflict, 3),
            "image_conflict": round(image_conflict, 3),
            "reference_accessory_mismatch": round(float(report.get("reference_accessory_mismatch") or 0.0), 3),
            "reference_final_score": round(sim, 3),
            "reference_is_colored": bool(reference_is_colored),
            "intent_strength": round(intent_strength, 3),
            "cfg1_effective_max": round(cfg1_eff_max, 2),
            "cfg2_effective_max": round(cfg2_eff_max, 2),
            "clamp_reasons": sorted(set(clamp_reasons)),
            "case": entity_type,
            "object_scale": object_scale,
        }

        plan["controlnet_union"] = cn_union
        plan["controlnet_openpose"] = cn_pose
        plan["ksampler1"] = ks1
        plan["ksampler2"] = ks2
        ip1_end = min(0.95, 0.30 + 0.60 * R)
        ip2_end = min(0.90, 0.25 + 0.65 * R)
        if conflict > 0.4:
            ip2_end = min(ip2_end, 0.50)
        if reference_is_colored:
            ip2_end = min(ip2_end, 0.60)
        if accessory_mismatch >= 0.35:
            ip2_end = min(ip2_end, 0.55)
            clamp_reasons.append("accessory_mismatch_capped_ip2_end_at")
        # Global KS2 safety: keep KS2 refinement-only and lower under artifact risk.
        if noisy_or_conflicted:
            ip2 = min(ip2, 0.35)
            ip2_end = min(ip2_end, 0.50)
            clamp_reasons.append("ks2_refinement_only_ip_damped")
        else:
            ip2 = max(ip2, 0.50)
            ip2_end = min(ip2_end, 0.60)
            clamp_reasons.append("ks2_refinement_only_ip_floor")
        # User cap profile for KS2 in problematic large-character cases.
        if entity_type == "single_complex" and object_scale == "large":
            ks2["steps"] = 50
            ks2["cfg"] = round(min(max(float(ks2.get("cfg", 8.5)), 8.5), 9.0), 2)
            ks2["denoise"] = round(min(float(ks2.get("denoise", 0.4)), 0.4), 2)
            ip2 = max(ip2, 0.50)
            ip2_end = min(ip2_end, 0.80)
            clamp_reasons.append("large_single_complex_ks2_user_caps")
        if plan.get("diagnostics"):
            plan["diagnostics"]["clamp_reasons"] = sorted(set(clamp_reasons))
        plan["ip_adapter_dual"] = {
            "ksampler1": {"weight": round(ip1, 2), "end_at": round(ip1_end, 2)},
            "ksampler2": {"weight": round(ip2, 2), "end_at": round(ip2_end, 2)},
        }
        # Keep single IP for backwards compatibility (use KS1 by default).
        plan["ip_adapter"] = dict(plan.get("ip_adapter", {}) or {})
        plan["ip_adapter"]["weight"] = plan["ip_adapter_dual"]["ksampler1"]["weight"]
        plan["ip_adapter"]["end_at"] = plan["ip_adapter_dual"]["ksampler1"]["end_at"]

        # LoRA strength (optional): keep disabled by default unless enabled in environment.
        # This is only a plan field; comfyui_client decides whether to apply.
        if D > 0.5:
            plan["lora_strength"] = 0.4
        else:
            plan["lora_strength"] = 0.15

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
            "model_name": DEFAULT_M4_MODEL,
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
            "model_name": DEFAULT_M4_MODEL,
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
            "model_name": DEFAULT_M4_MODEL,
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
            "model_name": DEFAULT_M4_MODEL,
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
                "model_name": DEFAULT_M4_MODEL,
                # High construction + medium/high broken lines: allow some redraw for cleanup,
                # but don't over-lock Union or it starts tracing construction marks.
                "ksampler1": {"steps": 40, "cfg": 8.0, "denoise": 1.00},
                "ksampler2": {"steps": 50, "cfg": 7.0, "denoise": 0.60},
                "controlnet_union": {"strength": 0.50, "end_percent": 0.80},
                "controlnet_openpose": {"strength": 1.0, "end_percent": 1.0},
                "ip_adapter": {"weight": 0.60, "end_at": 1.00},
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
                "model_name": DEFAULT_M4_MODEL,
                "ksampler1": {"steps": 40, "cfg": 8.0, "denoise": 0.70},
                "ksampler2": {"steps": 50, "cfg": 9.0, "denoise": 0.40},
                "controlnet_union": {"strength": 0.70, "end_percent": 0.8},
                "controlnet_openpose": {"strength": 1.0, "end_percent": 1.0},
                "ip_adapter": {"weight": 0.70, "end_at": 1.0},
            }
            logger.info(
                "Parameter plan created (single_complex+construction medium+broken low_or_medium override): "
                f"plan={plan}"
            )
            return _apply_issue_overrides(plan)

        plan = {
            "transition": transition,
            "model_name": DEFAULT_M4_MODEL,
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
            "model_name": DEFAULT_M4_MODEL,
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
            "model_name": DEFAULT_M4_MODEL,
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
    elif complexity == "complex":
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

    model_name = DEFAULT_M4_MODEL

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


def create_parameter_plan_m4(
    report: dict,
    source_phase: str,
    dest_phase: str,
    pose_lock: bool = True,
    style_lock: bool = True,
) -> dict:
    """M4 alias for parameter planner entrypoint."""
    return create_parameter_plan_m3(
        report=report,
        source_phase=source_phase,
        dest_phase=dest_phase,
        pose_lock=pose_lock,
        style_lock=style_lock,
    )
