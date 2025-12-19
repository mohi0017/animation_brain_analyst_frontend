"""
Animation Director Agent (AD-Agent) - Intelligent Parameter Optimization

This module implements the AD-Agent that analyzes animation cleanup goals
and computes optimal parameters for Stable Diffusion generation, including
model selection, CFG, Denoise, ControlNet settings, and conflict resolution.
"""

from typing import Dict, Optional, Tuple
from .parameter_plan import ParameterPlan
from .config import SD_MODELS, DEFAULT_LINE_ART_MODEL


def create_parameter_plan(
    report: dict,
    source_phase: str,
    dest_phase: str,
    pose_lock: bool = True,
    style_lock: bool = True,
    anatomy_level: int = 70,
    user_model_override: Optional[str] = None,
) -> ParameterPlan:
    """
    Main entry point: Create complete parameter plan for generation.
    
    Args:
        report: Visual Analyst report with fixes, removes, preserve, notes
        source_phase: Current animation phase (Skeleton, Roughs, etc.)
        dest_phase: Target animation phase
        pose_lock: Whether to preserve pose
        style_lock: Whether to preserve style
        anatomy_level: Anatomy fix level (0-100)
        user_model_override: Optional manual model selection
    
    Returns:
        ParameterPlan object with all computed parameters
    """
    # Step 0: Sanity check
    _sanity_check_phases(source_phase, dest_phase)
    
    # Step 1: Goal understanding
    goal_info = determine_goal_type(
        source_phase, dest_phase, report.get("fixes", []), anatomy_level
    )
    goal_info["pose_lock"] = pose_lock
    goal_info["style_lock"] = style_lock
    
    # Step 2: Model selection
    preserve_subject = _extract_subject(report.get("preserve", []))
    analyst_recommendation = report.get("recommended_model")
    model_name, model_warning = select_model(
        goal_info, preserve_subject, analyst_recommendation, user_model_override
    )
    
    # Step 3: Parameter design
    cfg = compute_cfg(goal_info, goal_info["damage_level"])
    denoise = compute_denoise(goal_info, anatomy_level)
    steps = compute_steps(goal_info, goal_info["damage_level"])
    controlnet_params = compute_controlnet_params(
        goal_info, goal_info["damage_level"], pose_lock
    )
    
    # Create initial plan
    plan = ParameterPlan(
        model_name=model_name,
        cfg=cfg,
        denoise=denoise,
        steps=steps,
        sampler="euler",
        scheduler="simple",
        lineart_strength=controlnet_params["lineart_strength"],
        lineart_end=controlnet_params["lineart_end"],
        canny_strength=controlnet_params["canny_strength"],
        canny_end=controlnet_params["canny_end"],
    )
    
    # Add model warning if any
    if model_warning:
        plan.warnings.append(model_warning)
    
    # Step 4: Conflict resolution
    conflicts_fixed = resolve_conflicts(plan, goal_info)
    plan.conflicts_fixed = conflicts_fixed
    
    # Step 5: Validation & safety check
    validation_warnings = validate_plan(plan, goal_info)
    plan.warnings.extend(validation_warnings)
    
    # Step 6: Generate reasoning
    plan.reasoning = generate_reasoning(plan, goal_info, conflicts_fixed)
    
    return plan


def _sanity_check_phases(source_phase: str, dest_phase: str) -> None:
    """Step 0: Validate phase combination."""
    if dest_phase == "Colors" and source_phase in ["Skeleton", "Roughs"]:
        # This is allowed but user should know it's better to go through CleanUp first
        pass  # We'll add warning in reasoning instead of blocking


def determine_goal_type(
    source_phase: str, dest_phase: str, fixes: list, anatomy_level: int
) -> Dict:
    """
    Step 1: Determine goal type and damage level.
    
    Returns:
        dict with goal_type, damage_level, transition
    """
    # Transition type
    if source_phase in ["Skeleton", "Roughs"] and dest_phase in ["Skeleton", "Roughs"]:
        goal_type = "REBUILD"  # Major structural change
    elif source_phase == "Roughs" and dest_phase == "Tie Down":
        goal_type = "REFINE"  # Cleanup + anatomy fix
    elif source_phase == "Tie Down" and dest_phase == "CleanUp":
        goal_type = "INK_ONLY"  # Pure inking, minimal change
    elif dest_phase == "Colors":
        goal_type = "COLOR_ONLY"  # Add fills, lock structure
    else:
        # Default: Refine
        goal_type = "REFINE"
    
    # Damage assessment
    damage_keywords = ["hands", "face", "torso", "broken", "messy", "fused", "fingers"]
    damage_count = sum(
        1 for fix in fixes if any(kw in fix.lower() for kw in damage_keywords)
    )
    
    if damage_count >= 3 or anatomy_level >= 80:
        damage_level = "HIGH"
    elif damage_count >= 1 or anatomy_level >= 50:
        damage_level = "MEDIUM"
    else:
        damage_level = "LOW"
    
    return {
        "goal_type": goal_type,
        "damage_level": damage_level,
        "transition": f"{source_phase} → {dest_phase}",
    }


def select_model(
    goal_info: Dict,
    preserve_subject: str,
    analyst_recommendation: Optional[str],
    user_override: Optional[str],
) -> Tuple[str, Optional[str]]:
    """
    Step 2: Select best model for generation.
    
    Returns:
        (model_name, warning_message_or_none)
    """
    dest_phase = goal_info["transition"].split("→")[1].strip()
    
    # User override takes priority (but warn if mismatch)
    if user_override:
        model = user_override
        warning = None
        if dest_phase in ["Skeleton", "Roughs", "Tie Down", "CleanUp"]:
            if model == "Realistic_Vision_V5.1.safetensors":
                warning = "Realistic Vision adds shading to line art. Consider AnythingXL Ink Base."
        return model, warning
    
    # Use analyst recommendation (already smart)
    if analyst_recommendation:
        return analyst_recommendation, None
    
    # Fallback: Phase-based selection
    if dest_phase in ["Skeleton", "Roughs", "Tie Down", "CleanUp"]:
        return DEFAULT_LINE_ART_MODEL, None
    elif dest_phase == "Colors":
        # Subject-based selection for Colors
        subject_lower = preserve_subject.lower() if preserve_subject else ""
        if any(kw in subject_lower for kw in ["anime", "character", "girl", "boy"]):
            return "Counterfeit-V3.0.safetensors", None
        elif any(kw in subject_lower for kw in ["fantasy", "magic"]):
            return "GhostMix-v2.0.safetensors", None
        else:
            return "Counterfeit-V3.0.safetensors", None  # Default
    
    return DEFAULT_LINE_ART_MODEL, None


def compute_cfg(goal_info: Dict, damage_level: str) -> float:
    """
    Step 3.1: Compute CFG scale.
    
    Returns:
        CFG value in safe range [6.5, 8.0]
    """
    goal_type = goal_info["goal_type"]
    
    if goal_type == "INK_ONLY":
        # Cleanup: Moderate CFG, don't overbake
        base_cfg = 7.0
    elif goal_type == "REFINE":
        # Tie Down: Slightly higher for anatomy fixes
        base_cfg = 7.5
    elif goal_type == "REBUILD":
        # Major changes: Higher CFG
        base_cfg = 7.8
    elif goal_type == "COLOR_ONLY":
        # Colors: Balanced
        base_cfg = 7.5
    else:
        base_cfg = 7.5
    
    # Adjust for damage
    if damage_level == "HIGH":
        base_cfg += 0.3
    elif damage_level == "LOW":
        base_cfg -= 0.2
    
    # Clamp to safe range
    return max(6.5, min(8.0, base_cfg))


def compute_denoise(goal_info: Dict, anatomy_level: int) -> float:
    """
    Step 3.2: Compute Denoise value.
    
    Returns:
        Denoise value in safe range [0.4, 0.9]
    """
    dest_phase = goal_info["transition"].split("→")[1].strip()
    
    # Base denoise by phase
    phase_denoise = {
        "Skeleton": 0.9,
        "Roughs": 0.8,
        "Tie Down": 0.6,
        "CleanUp": 0.5,
        "Colors": 0.4,
    }
    
    base_denoise = phase_denoise.get(dest_phase, 0.6)
    
    # Adjust for anatomy fix demand
    if anatomy_level >= 80:
        # User wants aggressive fixes
        base_denoise += 0.1
    elif anatomy_level <= 30:
        # User wants minimal changes
        base_denoise -= 0.1
    
    # CRITICAL: Clamp based on phase safety
    if dest_phase in ["Tie Down", "CleanUp"]:
        # Never exceed 0.65 for cleanup phases
        base_denoise = min(0.65, base_denoise)
    
    return max(0.4, min(0.9, base_denoise))


def compute_steps(goal_info: Dict, damage_level: str) -> int:
    """
    Step 3.3: Compute number of steps.
    
    Returns:
        Steps value in safe range [20, 36]
    """
    goal_type = goal_info["goal_type"]
    
    if goal_type == "INK_ONLY":
        # Simple cleanup: Fewer steps
        base_steps = 24
    elif goal_type == "COLOR_ONLY":
        # Colors need detail: More steps
        base_steps = 32
    elif damage_level == "HIGH":
        # Complex repair: More steps
        base_steps = 30
    else:
        base_steps = 28
    
    return max(20, min(36, base_steps))


def compute_controlnet_params(
    goal_info: Dict, damage_level: str, pose_lock: bool
) -> Dict[str, float]:
    """
    Step 3.4: Compute ControlNet parameters.
    
    Returns:
        dict with lineart_strength, lineart_end, canny_strength, canny_end
    """
    goal_type = goal_info["goal_type"]
    dest_phase = goal_info["transition"].split("→")[1].strip()
    
    if damage_level == "HIGH" or goal_type == "REBUILD":
        # Need freedom to repair
        lineart_end = 0.65
        canny_end = 0.6
        lineart_strength = 1.0
        canny_strength = 0.8
    elif goal_type == "INK_ONLY" or dest_phase == "CleanUp":
        # Lock structure tightly
        lineart_end = 0.95
        canny_end = 0.9
        lineart_strength = 1.2 if pose_lock else 1.0
        canny_strength = 1.0
    else:
        # Balanced
        lineart_end = 0.85
        canny_end = 0.75
        lineart_strength = 1.1 if pose_lock else 1.0
        canny_strength = 0.9
    
    return {
        "lineart_strength": lineart_strength,
        "lineart_end": lineart_end,
        "canny_strength": canny_strength,
        "canny_end": canny_end,
    }


def resolve_conflicts(plan: ParameterPlan, goal_info: Dict) -> list:
    """
    Step 4: Resolve parameter conflicts.
    
    Returns:
        List of conflict fixes applied
    """
    conflicts_fixed = []
    dest_phase = goal_info["transition"].split("→")[1].strip()
    
    # Rule 1: High denoise + Late ControlNet release = Bad
    if plan.denoise >= 0.75 and plan.lineart_end >= 0.9:
        plan.denoise = min(0.65, plan.denoise)
        conflicts_fixed.append(
            "Reduced denoise to prevent artifacts with late ControlNet release"
        )
    
    # Rule 2: Tie Down/CleanUp + High denoise = Not allowed
    if dest_phase in ["Tie Down", "CleanUp"] and plan.denoise > 0.65:
        plan.denoise = 0.6
        conflicts_fixed.append(f"Clamped denoise to 0.6 for {dest_phase} phase")
    
    # Rule 3: Pose lock + Weak ControlNet = Not allowed
    if goal_info.get("pose_lock") and plan.lineart_strength < 0.9:
        plan.lineart_strength = 1.0
        conflicts_fixed.append("Increased ControlNet strength for pose lock")
    
    # Rule 4: High CFG + High denoise = Risk of burn
    if plan.cfg > 8.0 and plan.denoise > 0.7:
        plan.cfg = 7.5
        conflicts_fixed.append("Reduced CFG to prevent overbaking with high denoise")
    
    # Rule 5: Low steps + High denoise = Not enough convergence
    if plan.steps < 24 and plan.denoise > 0.7:
        plan.steps = 28
        conflicts_fixed.append(
            "Increased steps for better convergence with high denoise"
        )
    
    # Rule 6: Wrong model for phase
    if plan.model_name == "Realistic_Vision_V5.1.safetensors":
        if dest_phase in ["Skeleton", "Roughs", "Tie Down", "CleanUp"]:
            plan.model_name = DEFAULT_LINE_ART_MODEL
            conflicts_fixed.append(
                "Switched to line art model (Realistic Vision not suitable for line art)"
            )
    
    return conflicts_fixed


def validate_plan(plan: ParameterPlan, goal_info: Dict) -> list:
    """
    Step 5: Final validation & safety check.
    
    Returns:
        List of warnings (errors raise exceptions)
    """
    warnings = []
    dest_phase = goal_info["transition"].split("→")[1].strip()
    
    # Hard limits
    if plan.denoise < 0.3 or plan.denoise > 0.95:
        raise ValueError(
            f"Denoise {plan.denoise} out of safe range [0.3, 0.95]"
        )
    
    if plan.cfg < 5.0 or plan.cfg > 10.0:
        raise ValueError(f"CFG {plan.cfg} out of safe range [5.0, 10.0]")
    
    if plan.steps < 15 or plan.steps > 50:
        raise ValueError(f"Steps {plan.steps} out of safe range [15, 50]")
    
    # Phase-specific limits
    if dest_phase in ["Tie Down", "CleanUp"]:
        if plan.denoise > 0.7:
            raise ValueError(
                f"Denoise {plan.denoise} too high for {dest_phase} (max 0.65)"
            )
        if plan.lineart_end < 0.85:
            warnings.append(
                f"ControlNet end {plan.lineart_end} may be too early for {dest_phase}"
            )
    
    return warnings


def generate_reasoning(plan: ParameterPlan, goal_info: Dict, conflicts_fixed: list) -> str:
    """
    Step 6: Generate human-readable reasoning.
    
    Returns:
        2-3 line explanation string
    """
    goal_type = goal_info["goal_type"]
    damage_level = goal_info["damage_level"]
    transition = goal_info["transition"]
    
    reasoning_parts = []
    
    # Goal explanation
    if goal_type == "INK_ONLY":
        reasoning_parts.append(
            f"Cleanup phase ({transition}): Preserving structure, cleaning lines only."
        )
    elif goal_type == "REFINE":
        reasoning_parts.append(
            f"Refinement ({transition}): Fixing anatomy while maintaining pose."
        )
    elif goal_type == "REBUILD":
        reasoning_parts.append(
            f"Major rebuild ({transition}): Allowing structural changes."
        )
    elif goal_type == "COLOR_ONLY":
        reasoning_parts.append(
            f"Coloring ({transition}): Adding fills while locking structure."
        )
    
    # Parameter highlights
    if plan.denoise <= 0.6:
        reasoning_parts.append(
            f"Low denoise ({plan.denoise:.2f}) ensures minimal structure change."
        )
    elif plan.denoise >= 0.8:
        reasoning_parts.append(
            f"High denoise ({plan.denoise:.2f}) allows significant repair."
        )
    
    if plan.lineart_end >= 0.9:
        reasoning_parts.append("ControlNet locked until end to prevent pose drift.")
    
    # Conflicts
    if conflicts_fixed:
        reasoning_parts.append(f"Adjusted: {', '.join(conflicts_fixed[:2])}")
    
    return " ".join(reasoning_parts)


def _extract_subject(preserve: list) -> str:
    """Extract subject from preserve[0]."""
    if not preserve or len(preserve) == 0:
        return ""
    
    preserve_0 = preserve[0]
    if isinstance(preserve_0, str):
        if preserve_0.startswith("Subject:"):
            return preserve_0.replace("Subject:", "").strip()
        return preserve_0
    
    return ""

