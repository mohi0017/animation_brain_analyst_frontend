# M3 Parameters Guide
## Dynamic Parameters by Phase Transition

> Canonical reference: `docs/M3_MASTER_PLAN_DYNAMIC_STATIC.md`  
> This file is a quick guide; master document has final policy and latest rules.

---

## Analyst Buckets (Input)
Visual Analyst outputs these fields:

- `line_quality`: messy | structured | clean
- `anatomy_risk`: low | medium | high
- `complexity`: simple | complex
- `subject_details`: tags for Stage-1 prompt
- `entity_type`: single_complex | single_simple | multi_object
- `entity_examples`: short label for the entity/entities (person, car, house, ball, crowd)
- `construction_lines`: low | medium | high
- `broken_lines`: low | medium | high

Reference comparison also contributes dynamic control signals (`reference_final_score`, `reference_conflict_penalty`, `reference_style_distance`, color/accessory conflict indicators).

---

## Transition Matrix (Core Ranges, Quick View)

| Transition | KS1 Denoise | KS1 CFG | KS2 Denoise | Union Str/End | OpenPose Str/End | IP-Adapter Wt/End |
|---|---|---|---|---|---|---|
| Roughs → Tie Down | dynamic | 7.0–10.0 (effective lower) | dynamic | dynamic | dynamic | dual-IP dynamic |
| Roughs → CleanUp | dynamic | 7.0–10.0 (effective by case) | dynamic | dynamic | dynamic | dual-IP dynamic |
| Tie Down → CleanUp | dynamic | 7.0–10.0 (effective by case) | dynamic | dynamic | dynamic | dual-IP dynamic |

---

## Conflict Rules (AD-Agent)

**Rule A (Anatomy Risk High):**
- OpenPose strength forced to 1.0
- IP-Adapter weight reduced by 0.2

**Rule B (Adaptive End Scheduling):**
- End values are dynamic and can be clamped by conflict/color risk.
- Sequential behavior is preferred, but controller may pin or cap values for stability.

**Rule C (High Construction/Broken Lines):**
- Union strength/end reduced
- IP-Adapter reduced (avoid hallucinated details/objects)
- OpenPose kept strong (often 1.0) for consistency
- KS1 denoise typically capped around ~0.70 to avoid over-hallucination

---

## Prompt Impact (M3)
- Stage 1 prompt: quality tags + subject + pose
- Stage 2 prompt: inking/refinement template
- If `line_quality == messy`, Stage 2 uses `(solid black lines:1.5)`
- Director may inject dynamic prompt modifiers (guardrails + reference mode handling).

---

## Notes
- Reference image drives dual-IP and dynamic control signals.
- Reference comparison can indirectly affect prompts via Director modifiers.
- Global CFG policy: allowed `7–10`; effective caps are case/stage dependent.
- Detailed final policy: `docs/M3_MASTER_PLAN_DYNAMIC_STATIC.md`
