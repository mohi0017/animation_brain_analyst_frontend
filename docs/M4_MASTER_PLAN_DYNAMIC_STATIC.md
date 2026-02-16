# M4 Master Plan: Dynamic vs Static System Design

This document is the source of truth for how M4 works end-to-end:
- which parts are static (locked),
- which parts are dynamic (computed per request),
- how each agent participates,
- and how parameters/prompts are generated per use case.

## 1) Pipeline Overview (Execution Order)

1. `app.py` receives input image + reference image.
2. `visual_analyst.py` extracts sketch semantics (quality, anatomy risk, complexity, etc.).
3. `reference_compare.py` computes input-vs-reference signals (similarity, conflicts, style distance).
4. `animation_director.py` creates adaptive M4 plan:
   - KSampler1/2 values
   - ControlNet Union/OpenPose
   - dual IP-Adapter weights/end_at
   - diagnostics and prompt modifiers
5. `prompt_engineer.py` generates dual-stage prompts (KS1/KS2 semantic separation).
6. `comfyui_client.py` updates workflow nodes and runs ComfyUI.
7. Optional feedback pass (`line_quality_analyzer.py`) can re-run once with safer settings.
8. UI renders debug metrics, raw outputs, post-processed outputs, final result.

---

## 2) Static vs Dynamic (Clear Separation)

## Static (Locked / Policy)

- **Model:** `animagine-xl-3.1.safetensors` (M4 locked default).
- **Workflow template:** `workflows/Animation_Workflow_M4_Api.json`.
- **Node mapping:** fixed node IDs for prompts, samplers, controlnets, dual IP.
- **Global CFG policy:** allowed `[7.0, 10.0]`.
- **Hard safety constraints:**
  - `cfg2 <= cfg1`
  - `ip2 <= ip1 - 0.10` (asymmetric dual-IP)
  - `ip2 <= 0.55`
  - `denoise2 <= 0.60`
  - union end clamp and pose safety limits

## Dynamic (Computed Per Request)

- Case type and object scale.
- Structural and reference signals: `S, R, D, P, H`.
- Conflict and colored-reference handling.
- Dynamic bounds and effective stage caps.
- Actual KS1/KS2 cfg/denoise.
- Union/OpenPose strengths.
- Dual IP weights and end-at values.
- Prompt modifiers and stage-specific semantic guards.
- Optional feedback correction trigger.

---

## 3) Agent Responsibilities

## A) Visual Analyst (`modules/visual_analyst.py`)

Produces primary analysis fields:
- `line_quality`: messy / structured / clean
- `anatomy_risk`: low / medium / high
- `complexity`: simple / complex
- subject details, fix/remove/keep notes

Purpose:
- classify sketch state and quality baseline.

## B) Reference Compare (`modules/reference_compare.py`)

Produces reference reliability signals:
- `reference_final_score`
- `reference_conflict_penalty`
- `reference_style_distance`
- accessory mismatch / colored-reference indicators

Purpose:
- decide how much reference should influence generation.

## C) Animation Director (`modules/animation_director.py`)

Core adaptive controller:
- computes `S/R/D/P/H`
- computes raw parameter candidates
- applies case-based bounds
- applies signal-based bound adjustments
- applies hard rules
- outputs final parameter plan + diagnostics + dual IP plan

## D) Prompt Engineer (`modules/prompt_engineer.py`)

Generates separate prompts for:
- Stage 1 / KS1: structure authority
- Stage 2 / KS2: cleanup/refinement authority

Rules:
- no stage contamination
- inject dynamic guardrails from director
- prioritize concise tags and dedupe conflicts

## E) ComfyUI Client (`modules/comfyui_client.py`)

Applies plan to workflow nodes:
- KSampler1/2
- Union/OpenPose
- IP-Adapter KS1 (node path 1)
- IP-Adapter KS2 (node path 2)

Optional:
- feedback retry via `line_quality_analyzer.py` thresholds.

---

## 4) Use Cases and Parameter Strategy

Use-case buckets are selected by analyst + director logic.

## 4.1 `single_simple`
Example: circle/logo/small object, low construction noise.

Target behavior:
- strong structure lock allowed,
- reference can be stronger,
- higher effective CFG ceiling in KS1.

Effective caps:
- `cfg1_eff_max = 9.6`
- `cfg2_eff_max = 8.6`

Typical range (adaptive):
- KS1 cfg high-mid, KS2 cfg mid-low.
- Union may go very high for small objects.

## 4.2 `single_complex`
Example: single character with difficult pose, construction lines.

Target behavior:
- preserve anatomy,
- avoid over-lock choking refinement,
- keep KS2 safer to prevent edge tearing/jitter.

Effective caps:
- `cfg1_eff_max = 9.2`
- `cfg2_eff_max = 8.4`

Typical range (adaptive):
- union generally moderate,
- KS2 denoise conservative,
- dual IP asymmetric (KS1 > KS2).

## 4.3 `multi_object`
Example: multiple subjects/interaction.

Target behavior:
- avoid hallucinated duplicates,
- maintain scene structure with controlled style transfer.

Effective caps:
- `cfg1_eff_max = 9.2`
- `cfg2_eff_max = 8.2`

Typical range (adaptive):
- stronger structure controls,
- lower KS2 aggression.

---

## 5) CFG Controller Policy (Final)

Global allowed:
- `CFG ∈ [7.0, 10.0]`

Base adaptive seed:
- `base_cfg = 7.2 + 1.8 * intent_strength`
- `cfg1 >= base_cfg`
- `cfg2 >= base_cfg - 0.5`

Interaction safety:
- if `ip2 > 0.40` => `cfg2 <= 7.8`
- if `ip2 > 0.50` => `cfg2 <= 7.4`
- if `union_strength > 0.75` or `pose_strength > 0.90` => `cfg1 -= 0.4`
- if `H > 0.6` => `cfg1 -= 0.3`, `cfg2 -= 0.5`
- final: `cfg2 <= cfg1`

Interpretation:
- policy allows 7–10,
- controller selects safe sub-range by stage and risk.

---

## 6) Dynamic Bounds Logic

Case profile gives initial bounds, then adjusted by:

- conflict high:
  - lower `ip1_max`, `ip2_max`
- reference colored:
  - lower `ip2_max`, earlier `ip2_end_at`
- line quality low:
  - allow slightly more KS1 denoise/IP1
- line quality high:
  - reduce KS2 interference
- pose risk high:
  - stronger pose lock, lower risky style force
- object scale:
  - large object => reduce union ceiling
  - small object => allow stronger union

This is the core dynamic/static hybrid controller.

---

## 7) Prompt Generation Plan (Stage-Aware)

## KS1 Prompt (Structure Pass)
- preserve pose/proportions/accessories
- remove rough construction ambiguity
- no aggressive style transfer directives

## KS2 Prompt (Cleanup Pass)
- line continuity, stroke confidence, final polish
- style transfer intensity only if safe (`reference_mode` + low conflict)
- artifact suppression negatives (fringing, dotted lines, jitter)

Dynamic prompt modifiers are injected from director diagnostics.

---

## 8) Diagnostics to Monitor (Debug Mode)

Always inspect:
- `S_structure_confidence`
- `R_reference_reliability`
- `D_style_distance`
- `P_pose_risk`
- `H_hallucination_risk`
- `conflict_penalty`
- `reference_mode`
- `_influence_scalar`
- dual IP weights/end_at
- `cfg1_effective_max`, `cfg2_effective_max`

If outputs degrade, first verify diagnostics before changing presets.

---

## 9) Node Ownership (ComfyUI Apply Layer)

Runtime updates:
- Stage1 positive/negative prompt nodes
- Stage2 positive/negative prompt nodes
- KS1 node params
- KS2 node params
- ControlNet Union node
- OpenPose node
- IP Adapter node for KS1
- IP Adapter node for KS2
- optional LoRA enable/strength

Workflow graph is static; values are dynamic.

---

## 10) Practical Guardrails

- Do not make KS1 and KS2 prompts identical.
- Do not force identity mode on high-conflict references.
- Do not use KS2 high CFG with high IP2.
- Do not over-lock Union for large complex objects.
- Prefer adjusting denoise/IP/Union before pushing CFG upward.

---

## 11) Current Implementation Status (as of latest policy)

Implemented:
- adaptive controller with diagnostics
- dynamic bounds and effective CFG caps
- global CFG policy [7,10] + stage caps
- interaction safety rules (ip2/union/pose/H)
- dual-IP per sampler
- stage-aware prompt separation
- optional post-generation feedback retry

Open calibration work (recommended):
- collect 50–100 run diagnostics,
- tune thresholds from empirical distributions,
- tighten per-use-case bounds if repeated artifacts appear.

---

## 12) Formal Signal Computation Spec

Use normalized `0..1` signals.

- `S` (structure confidence): derived from `construction_lines`, `broken_lines`, `line_quality`.
  - low construction/broken + clean lines => `S` high
  - high construction/broken + messy lines => `S` low
- `R` (reference reliability):
  - `R = similarity * (1 - conflict_penalty)`
- `D` (style distance):
  - edge-density delta + grayscale-contrast delta (input vs reference)
- `P` (pose risk):
  - derived from `anatomy_risk` (+ pose-lock bias)
- `H` (hallucination risk):
  - function of `cfg2`, `denoise2`, `ip2`, `conflict`

Controller interpretation:
- `S` drives Union + KS1 denoise envelope
- `R` drives IP strength/end-at and refinement trust
- `D` drives cleanup pressure (KS2 denoise, optional LoRA)
- `P` drives OpenPose strength and conservative identity forcing
- `H` triggers late-stage dampening

---

## 13) Node Driver Map (Who Drives Which Node)

For `workflows/Animation_Workflow_M4_Api.json`:

- Node `5` (KS1): `steps`, `cfg`, `denoise` from Director
- Node `55` (KS2): `steps`, `cfg`, `denoise` from Director
- Node `103` (ControlNet Union): `strength`, `end_percent`
- Node `104` (OpenPose): `strength`, `end_percent`
- Node `66` (IP KS1): `weight`, `end_at`
- Node `105` (IP KS2): `weight`, `end_at`
- Nodes `2/3` (Stage 1 prompts): from Prompt Engineer
- Nodes `77/76` (Stage 2 prompts): from Prompt Engineer
- Optional LoRA node(s): enabled by runtime flag + plan strength

Static:
- workflow graph/node IDs and base template.
Dynamic:
- all values listed above.

---

## 14) Dynamic Bounds Enforcement Order

The controller must apply this order:

1. Classify case (`single_simple`, `single_complex`, `multi_object`) and object scale.
2. Load base bounds for that case.
3. Apply signal modifiers:
   - conflict/color => tighten IP2 and end-at
   - low LQ => more KS1 repair room
   - high LQ => less KS2 interference
   - high P => stronger OpenPose target
   - large object => tighter Union max
4. Compute raw values from signal formulas.
5. Clamp into dynamic bounds.
6. Apply hard safety rules:
   - `ip2 <= ip1 - 0.10`
   - `cfg2 <= cfg1`
   - `ip2`-coupled `cfg2` caps (`7.8` / `7.4`)
   - high `H` dampening
7. Emit diagnostics + reasons for key clamps.

---

## 15) Prompt Semantics Contract (Non-Negotiable)

KS1 and KS2 prompts must stay semantically separated:

- KS1 (structure authority):
  - preserve pose/proportions/accessories
  - cleanup construction ambiguity
  - avoid style-heavy directives
- KS2 (refinement authority):
  - line consistency, contour confidence, final polish
  - reference style directives only if safe
  - anti-artifact negatives (fringe, jitter, dotted lines)

Hard rule:
- KS1 must not receive KS2-only style directives (e.g., direct stroke matching language).

---

## 16) Missing/Next Dynamic Signals (Roadmap)

To reduce text-only conflict blind spots, add image-level detectors in `reference_compare.py`:

- `CR` (colored-reference flag): HSV saturation-based
- `AC` (accessory conflict): upper-face dark-blob mismatch heuristic

Then fold into conflict model:
- `conflict_penalty = f(text_conflict, image_conflict)` (max or weighted fusion)

Expected effect:
- safer `reference_mode` selection
- earlier `ip2_end_at` clamping
- fewer identity/accessory mismatches and color-fringe failures.
