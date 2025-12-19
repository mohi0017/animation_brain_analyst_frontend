# 🎬 Animation Director Agent (AD-Agent) - Complete Implementation Plan

**Version:** v1.0  
**Status:** Implementation Ready  
**Date:** December 2024

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Complete Workflow](#complete-workflow)
4. [Agent Thinking Steps](#agent-thinking-steps)
5. [Implementation Tasks](#implementation-tasks)
6. [Code Structure](#code-structure)
7. [Integration Points](#integration-points)
8. [Testing Strategy](#testing-strategy)

---

## 🎯 Overview

**AD-Agent** is an intelligent parameter optimization system that:
- Analyzes animation cleanup goals
- Selects optimal Stable Diffusion model
- Computes all generation parameters (CFG, Denoise, ControlNet, Steps)
- Resolves parameter conflicts automatically
- Provides self-correction loops for quality assurance

**Goal:** Make the system think like a senior animation technical director who balances creativity with technical constraints.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER INPUT                                    │
│  • Image + Source Phase + Dest Phase                            │
│  • pose_lock, style_lock, anatomy_level                         │
│  • Optional: Manual model/CFG override                         │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              VISUAL ANALYST (Existing)                          │
│  • Analyzes image                                               │
│  • Returns: fixes[], removes[], preserve[], notes[]             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              AD-AGENT (NEW - Core Logic)                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 1: Goal Understanding                                │  │
│  │ Step 2: Model Selection                                   │  │
│  │ Step 3: Parameter Design                                  │  │
│  │ Step 4: Conflict Resolution                               │  │
│  │ Step 5: Validation & Safety Check                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│  Output: ParameterPlan object                                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│         PROMPT ENGINEER (Existing - Updated)                    │
│  • Receives ParameterPlan constraints                           │
│  • Generates prompts respecting ink color + background          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              COMFYUI CLIENT (Updated)                            │
│  • Uses ParameterPlan values                                    │
│  • Updates workflow: CFG, Denoise, Steps, ControlNet           │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              GENERATION RESULT                                   │
│  • Transparent lines (Node 42)                                 │
│  • Original background (Node 54)                                │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│         SELF-CORRECTION LOOP (Optional - Stage 3)               │
│  • Visual Analyst re-analyzes output                            │
│  • AD-Agent adjusts parameters                                  │
│  • Max 1-2 retries                                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Complete Workflow

### Phase 1: Pre-Generation Analysis

```
1. User uploads image + selects phases
   ↓
2. Visual Analyst analyzes image
   Output: { fixes, removes, preserve, notes, recommended_model }
   ↓
3. AD-Agent receives:
   • Visual Analyst report
   • source_phase, dest_phase
   • pose_lock, style_lock, anatomy_level
   • Optional user overrides
   ↓
4. AD-Agent executes thinking steps (see below)
   ↓
5. AD-Agent outputs ParameterPlan
```

### Phase 2: Generation Execution

```
6. Prompt Engineer receives ParameterPlan constraints
   Generates: pos_prompt, neg_prompt
   ↓
7. ComfyUI Client receives ParameterPlan
   Updates workflow with all parameters
   ↓
8. ComfyUI generates image
   ↓
9. Returns: (transparent_img, original_img)
```

### Phase 3: Self-Correction (Optional)

```
10. Visual Analyst re-analyzes output
    ↓
11. AD-Agent checks if quality goals met
    ↓
12. If not met:
    • Adjust parameters
    • Retry (max 1-2 times)
    ↓
13. Final output to user
```

---

## 🧠 Agent Thinking Steps (Detailed)

### Step 0: Sanity Check

**Input:** `source_phase`, `dest_phase`

**Logic:**
```python
if dest_phase == "Colors" and source_phase in ["Skeleton", "Roughs"]:
    # Suggest intermediate step
    suggest_intermediate = "Tie Down" or "CleanUp"
    reasoning = f"Colors phase requires clean lines. Consider {suggest_intermediate} first."
```

**Output:** Validated phases or warning message

---

### Step 1: Goal Understanding

**Input:** 
- `source_phase`, `dest_phase`
- Visual Analyst `fixes[]` (damage indicators)
- `anatomy_level` slider

**Logic:**

```python
def determine_goal_type(source, dest, fixes, anatomy_level):
    # Transition type
    if source in ["Skeleton", "Roughs"] and dest in ["Skeleton", "Roughs"]:
        goal_type = "REBUILD"  # Major structural change
    elif source == "Roughs" and dest == "Tie Down":
        goal_type = "REFINE"   # Cleanup + anatomy fix
    elif source == "Tie Down" and dest == "CleanUp":
        goal_type = "INK_ONLY" # Pure inking, minimal change
    elif dest == "Colors":
        goal_type = "COLOR_ONLY" # Add fills, lock structure
    
    # Damage assessment
    damage_keywords = ["hands", "face", "torso", "broken", "messy", "fused"]
    damage_count = sum(1 for fix in fixes if any(kw in fix.lower() for kw in damage_keywords))
    
    if damage_count >= 3 or anatomy_level >= 80:
        damage_level = "HIGH"
    elif damage_count >= 1 or anatomy_level >= 50:
        damage_level = "MEDIUM"
    else:
        damage_level = "LOW"
    
    return {
        "goal_type": goal_type,
        "damage_level": damage_level,
        "transition": f"{source} → {dest}"
    }
```

**Output:** `goal_info` dict

---

### Step 2: Model Selection

**Input:**
- `goal_info`
- Visual Analyst `preserve[0]` (subject)
- Visual Analyst `recommended_model`
- User manual model (if any)

**Logic:**

```python
def select_model(goal_info, preserve_subject, analyst_recommendation, user_override):
    dest_phase = goal_info["transition"].split("→")[1].strip()
    
    # User override takes priority (but warn if mismatch)
    if user_override:
        model = user_override
        if dest_phase in ["Skeleton", "Roughs", "Tie Down", "CleanUp"]:
            if model == "Realistic_Vision_V5.1.safetensors":
                warning = "Realistic Vision adds shading to line art. Consider AnythingXL Ink Base."
        return model, warning
    
    # Use analyst recommendation (already smart)
    if analyst_recommendation:
        return analyst_recommendation, None
    
    # Fallback: Phase-based selection
    if dest_phase in ["Skeleton", "Roughs", "Tie Down", "CleanUp"]:
        return "anything-v5-PrtRE.safetensors", None
    elif dest_phase == "Colors":
        # Subject-based selection for Colors
        subject_lower = preserve_subject.lower()
        if any(kw in subject_lower for kw in ["anime", "character", "girl", "boy"]):
            return "Counterfeit-V3.0.safetensors", None
        elif any(kw in subject_lower for kw in ["fantasy", "magic"]):
            return "GhostMix-v2.0.safetensors", None
        else:
            return "Counterfeit-V3.0.safetensors", None  # Default
```

**Output:** `model_name`, optional `warning`

---

### Step 3: Core Parameter Design

#### 3.1 CFG Computation

**Logic:**

```python
def compute_cfg(goal_info, damage_level):
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
```

#### 3.2 Denoise Computation

**Logic:**

```python
def compute_denoise(goal_info, anatomy_level):
    goal_type = goal_info["goal_type"]
    dest_phase = goal_info["transition"].split("→")[1].strip()
    
    # Base denoise by phase
    phase_denoise = {
        "Skeleton": 0.9,
        "Roughs": 0.8,
        "Tie Down": 0.6,
        "CleanUp": 0.5,
        "Colors": 0.4
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
```

#### 3.3 Steps Computation

**Logic:**

```python
def compute_steps(goal_info, damage_level):
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
```

#### 3.4 ControlNet Strategy

**Logic:**

```python
def compute_controlnet_params(goal_info, damage_level, pose_lock):
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
        "canny_end": canny_end
    }
```

---

### Step 4: Conflict Resolution

**Input:** All computed parameters

**Conflict Rules:**

```python
def resolve_conflicts(plan, goal_info):
    """
    Apply conflict resolution rules in priority order.
    """
    conflicts_fixed = []
    
    # Rule 1: High denoise + Late ControlNet release = Bad
    if plan.denoise >= 0.75 and plan.lineart_end >= 0.9:
        plan.denoise = min(0.65, plan.denoise)
        conflicts_fixed.append("Reduced denoise to prevent artifacts with late ControlNet release")
    
    # Rule 2: Tie Down/CleanUp + High denoise = Not allowed
    dest_phase = goal_info["transition"].split("→")[1].strip()
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
        conflicts_fixed.append("Increased steps for better convergence with high denoise")
    
    # Rule 6: Wrong model for phase
    if plan.model_name == "Realistic_Vision_V5.1.safetensors":
        if dest_phase in ["Skeleton", "Roughs", "Tie Down", "CleanUp"]:
            plan.model_name = "anything-v5-PrtRE.safetensors"
            conflicts_fixed.append("Switched to line art model (Realistic Vision not suitable for line art)")
    
    return conflicts_fixed
```

**Output:** Updated `ParameterPlan` + list of fixes applied

---

### Step 5: Validation & Safety Check

**Final validation before ComfyUI call:**

```python
def validate_plan(plan, goal_info):
    """
    Final safety checks - ensure no impossible combinations.
    """
    errors = []
    warnings = []
    
    # Hard limits
    if plan.denoise < 0.3 or plan.denoise > 0.95:
        errors.append(f"Denoise {plan.denoise} out of safe range [0.3, 0.95]")
    
    if plan.cfg < 5.0 or plan.cfg > 10.0:
        errors.append(f"CFG {plan.cfg} out of safe range [5.0, 10.0]")
    
    if plan.steps < 15 or plan.steps > 50:
        errors.append(f"Steps {plan.steps} out of safe range [15, 50]")
    
    # Phase-specific limits
    dest_phase = goal_info["transition"].split("→")[1].strip()
    if dest_phase in ["Tie Down", "CleanUp"]:
        if plan.denoise > 0.7:
            errors.append(f"Denoise {plan.denoise} too high for {dest_phase} (max 0.65)")
        if plan.lineart_end < 0.85:
            warnings.append(f"ControlNet end {plan.lineart_end} may be too early for {dest_phase}")
    
    if errors:
        raise ValueError(f"Parameter validation failed: {errors}")
    
    return warnings
```

---

### Step 6: Reasoning Generation

**Human-readable explanation:**

```python
def generate_reasoning(plan, goal_info, conflicts_fixed):
    """
    Generate 2-3 line explanation for user.
    """
    goal_type = goal_info["goal_type"]
    damage_level = goal_info["damage_level"]
    transition = goal_info["transition"]
    
    reasoning_parts = []
    
    # Goal explanation
    if goal_type == "INK_ONLY":
        reasoning_parts.append(f"Cleanup phase ({transition}): Preserving structure, cleaning lines only.")
    elif goal_type == "REFINE":
        reasoning_parts.append(f"Refinement ({transition}): Fixing anatomy while maintaining pose.")
    elif goal_type == "REBUILD":
        reasoning_parts.append(f"Major rebuild ({transition}): Allowing structural changes.")
    
    # Parameter highlights
    if plan.denoise <= 0.6:
        reasoning_parts.append(f"Low denoise ({plan.denoise}) ensures minimal structure change.")
    elif plan.denoise >= 0.8:
        reasoning_parts.append(f"High denoise ({plan.denoise}) allows significant repair.")
    
    if plan.lineart_end >= 0.9:
        reasoning_parts.append("ControlNet locked until end to prevent pose drift.")
    
    # Conflicts
    if conflicts_fixed:
        reasoning_parts.append(f"Adjusted: {', '.join(conflicts_fixed[:2])}")
    
    return " ".join(reasoning_parts)
```

---

## 📝 Implementation Tasks

### Task 1: Create ParameterPlan Dataclass

**File:** `modules/parameter_plan.py`

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ParameterPlan:
    """Complete parameter plan for one generation."""
    
    # Model
    model_name: str
    
    # Core SD parameters
    cfg: float
    denoise: float
    steps: int
    sampler: str = "euler"
    scheduler: str = "simple"
    
    # ControlNet parameters
    lineart_strength: float = 1.0
    lineart_end: float = 0.9
    canny_strength: float = 0.8
    canny_end: float = 0.6
    
    # Metadata
    reasoning: str = ""
    warnings: list = None
    conflicts_fixed: list = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.conflicts_fixed is None:
            self.conflicts_fixed = []
```

---

### Task 2: Create AD-Agent Module

**File:** `modules/animation_director.py`

**Functions:**
1. `create_parameter_plan()` - Main entry point
2. `determine_goal_type()` - Step 1
3. `select_model()` - Step 2
4. `compute_cfg()` - Step 3.1
5. `compute_denoise()` - Step 3.2
6. `compute_steps()` - Step 3.3
7. `compute_controlnet_params()` - Step 3.4
8. `resolve_conflicts()` - Step 4
9. `validate_plan()` - Step 5
10. `generate_reasoning()` - Step 6

---

### Task 3: Update ComfyUI Client

**File:** `modules/comfyui_client.py`

**Changes:**
- Accept `ParameterPlan` object instead of individual params
- Update workflow with all ParameterPlan values:
  - CFG (Node 5)
  - Denoise (Node 5)
  - Steps (Node 5)
  - ControlNet strengths + ends (Node 39)

---

### Task 4: Update App.py Integration

**File:** `app.py`

**Changes:**
- After Visual Analyst, call `create_parameter_plan()`
- Pass `ParameterPlan` to ComfyUI client
- Display AD-Agent reasoning in UI

---

### Task 5: Self-Correction Loop (Stage 3)

**File:** `modules/animation_director.py`

**Function:** `self_correct_plan(original_plan, new_analysis_report)`

**Logic:**
- Compare new analysis with original goals
- Adjust parameters if quality not met
- Return updated plan or None (if retry not needed)

---

## 💻 Code Structure

```
modules/
├── __init__.py              # Export ParameterPlan, create_parameter_plan
├── parameter_plan.py        # Dataclass definition
├── animation_director.py    # AD-Agent core logic
├── visual_analyst.py        # Existing (no changes)
├── prompt_engineer.py       # Existing (may receive ParameterPlan constraints)
├── comfyui_client.py        # Updated to use ParameterPlan
└── config.py                # Existing (PHASE_PARAMS, SD_MODELS)
```

---

## 🔌 Integration Points

### Point 1: After Visual Analyst

```python
# In app.py, after Visual Analyst
report = normalize_report(raw_report)

# NEW: Create parameter plan
from modules import create_parameter_plan

plan = create_parameter_plan(
    report=report,
    source_phase=source_phase,
    dest_phase=dest_phase,
    pose_lock=pose_lock,
    style_lock=style_lock,
    anatomy_level=anat_level,
    user_model_override=selected_model if model_choice == "Manual" else None
)

# Display reasoning
status.write(f"🎯 AD-Agent Plan: {plan.reasoning}")
if plan.warnings:
    for warning in plan.warnings:
        status.write(f"⚠️ {warning}")
```

### Point 2: ComfyUI Call

```python
# In app.py, ComfyUI call
generated_image = call_comfyui(
    image_bytes,
    pos_prompt,
    neg_prompt,
    parameter_plan=plan,  # NEW: Pass plan instead of individual params
    status_writer=status
)
```

### Point 3: Self-Correction (Optional)

```python
# After first generation
if enable_self_correction:
    new_report = run_visual_analyst(output_image_bytes, mime, cfg)
    adjusted_plan = self_correct_plan(plan, new_report)
    if adjusted_plan:
        # Retry with adjusted plan
        generated_image = call_comfyui(..., parameter_plan=adjusted_plan)
```

---

## 🧪 Testing Strategy

### Unit Tests

1. **Goal Type Detection**
   - Test all phase transitions → correct goal_type

2. **Model Selection**
   - Test phase-based selection
   - Test subject-based selection (Colors)
   - Test user override handling

3. **Parameter Computation**
   - Test CFG ranges for each goal type
   - Test Denoise clamping for Tie Down/CleanUp
   - Test ControlNet end steps for damage levels

4. **Conflict Resolution**
   - Test high denoise + late release → auto-fix
   - Test wrong model for phase → auto-switch
   - Test pose_lock + weak ControlNet → auto-strengthen

### Integration Tests

1. **End-to-End Flow**
   - Upload sketch → Visual Analyst → AD-Agent → ComfyUI → Output
   - Verify all parameters applied correctly

2. **Self-Correction**
   - Generate → Re-analyze → Adjust → Retry
   - Verify retry limit (max 2)

### Manual Testing Checklist

- [ ] Skeleton → Roughs: High denoise, early release
- [ ] Roughs → Tie Down: Medium denoise, balanced release
- [ ] Tie Down → CleanUp: Low denoise, late release
- [ ] CleanUp → Colors: Very low denoise, model switch
- [ ] High damage sketch: Appropriate repair parameters
- [ ] Pose lock ON: Strong ControlNet
- [ ] User override model: Respect + warn if mismatch

---

## 🚀 Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Create `ParameterPlan` dataclass
- [ ] Create `animation_director.py` skeleton
- [ ] Implement Step 1-3 (Goal, Model, Parameters)
- [ ] Unit tests for core logic

### Phase 2: Conflict Resolution (Week 1-2)
- [ ] Implement Step 4 (Conflict Resolution)
- [ ] Implement Step 5 (Validation)
- [ ] Test all conflict scenarios

### Phase 3: Integration (Week 2)
- [ ] Update `comfyui_client.py` to use ParameterPlan
- [ ] Update `app.py` to call AD-Agent
- [ ] End-to-end testing

### Phase 4: Self-Correction (Week 3)
- [ ] Implement Step 6 (Self-Correction Loop)
- [ ] Add retry limit logic
- [ ] Test retry scenarios

### Phase 5: Polish (Week 3-4)
- [ ] Improve reasoning messages
- [ ] Add UI display for AD-Agent decisions
- [ ] Performance optimization
- [ ] Documentation

---

## 📊 Success Metrics

1. **Parameter Quality**
   - No conflicts in generated plans
   - All parameters within safe ranges
   - Appropriate values for each phase transition

2. **User Experience**
   - Clear reasoning displayed
   - Warnings shown when needed
   - Better output quality vs manual tuning

3. **System Reliability**
   - No crashes from invalid parameters
   - Self-correction improves quality
   - Retry limit prevents infinite loops

---

## 🎯 Next Steps

1. **Review this plan** with team
2. **Start Phase 1** implementation
3. **Create GitHub issues** for each task
4. **Set up testing framework**
5. **Begin coding!**

---

**End of Implementation Plan**

