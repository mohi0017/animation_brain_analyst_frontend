# M3 Parameters Guide
## Dynamic Parameters by Phase Transition

---

## Analyst Buckets (Input)
Visual Analyst outputs these fields (from input image only):

- `line_quality`: messy | structured | clean
- `anatomy_risk`: low | medium | high
- `complexity`: simple | detailed
- `subject_details`: tags for Stage-1 prompt
- `entity_type`: single_complex | single_simple | multi_object
- `entity_examples`: short label for the entity/entities (person, car, house, ball, crowd)
- `construction_lines`: low | medium | high
- `broken_lines`: low | medium | high

These drive AD-Agent parameter selection.

---

## Transition Matrix (Core Ranges)

| Transition | KS1 Denoise | KS1 CFG | KS2 Denoise | Union Str/End | OpenPose Str/End | IP-Adapter Wt/End |
|---|---|---|---|---|---|---|
| Roughs → Tie Down | 0.55–0.65 | 6.5–7.5 | 0.20–0.25 | 0.55–0.65 / 0.50 | 0.9 / 0.80 | 0.4–0.5 / 0.40 |
| Roughs → CleanUp | 0.70–0.80 | 7.0–8.0 | 0.30–0.35 | 0.7–0.8 / 0.50 | 1.0 / 0.85 | 0.6–0.8 / 0.60 |
| Tie Down → CleanUp | 0.35–0.45 | 7.0–8.0 | 0.20–0.30 | 0.5–0.6 / 0.80 | 0.8 / 0.90 | 0.5–0.7 / 0.50 |

---

## Conflict Rules (AD-Agent)

**Rule A (Anatomy Risk High):**
- OpenPose strength forced to 1.0
- IP-Adapter weight reduced by 0.2

**Rule B (Sequential Gap, adaptive path):**
- Typical intent: `ip_adapter.end_at < union.end_percent < openpose.end_percent`
- Some explicit presets intentionally pin `end_percent` to 1.0 for trace-like behavior.

**Rule C (High Construction/Broken Lines):**
- Union strength/end reduced
- IP-Adapter reduced (avoid hallucinated details/objects)
- OpenPose kept strong (often 1.0) for consistency
- KS1 denoise typically capped around ~0.70 to avoid over-hallucination

---

## Prompt Impact (M3)
- Stage 1 prompt: quality tags + subject + pose
- Stage 2 prompt: inking template
- If `line_quality == messy`, Stage 2 uses `(solid black lines:1.5)`

---

## Notes
- Reference image only feeds IP-Adapter
- No reference analysis is injected into prompts
- Output always includes transparent PNG via RemBG
- Detailed case playbook: `docs/CASE_SINGLE_COMPLEX_CLEANUP_PLAYBOOK.md`
