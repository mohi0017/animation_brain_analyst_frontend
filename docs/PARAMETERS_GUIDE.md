# M2 Parameters Guide
## Dynamic Parameters by Phase Transition

---

## Analyst Buckets (Input)
Visual Analyst outputs these fields (from input image only):

- `line_quality`: messy | structured | clean
- `anatomy_risk`: low | medium | high
- `complexity`: simple | detailed
- `subject_details`: tags for Stage-1 prompt

These drive AD-Agent parameter selection.

---

## Transition Matrix (Core Ranges)

| Transition | KS1 Denoise | KS1 CFG | KS2 Denoise | Union Str/End | OpenPose Str/End | IP-Adapter Wt/End |
|---|---|---|---|---|---|---|
| Roughs → Tie Down | 0.50–0.60 | 6.5–7.5 | 0.20–0.25 | 0.4–0.5 / 0.50 | 0.8 / 0.80 | 0.4–0.5 / 0.40 |
| Roughs → CleanUp | 0.65–0.75 | 8.0–9.0 | 0.30–0.35 | 0.7–0.8 / 0.65 | 1.0 / 0.85 | 0.6–0.8 / 0.60 |
| Tie Down → CleanUp | 0.40–0.50 | 7.0–8.0 | 0.20–0.30 | 0.5–0.6 / 0.75 | 0.8 / 0.90 | 0.5–0.7 / 0.50 |

---

## Conflict Rules (AD-Agent)

**Rule A (Anatomy Risk High):**
- OpenPose strength forced to 1.0
- IP-Adapter weight reduced by 0.2

**Rule B (Sequential Gap):**
- OpenPose end >= 0.80
- Union end = OpenPose end - 0.15

**Rule C (Messy Lines):**
- KS1 denoise +0.1 (capped)
- Union end <= 0.65

---

## Prompt Impact (M2)
- Stage 1 prompt: quality tags + subject + pose
- Stage 2 prompt: inking template
- If `line_quality == messy`, Stage 2 uses `(solid black lines:1.5)`

---

## Notes
- Reference image only feeds IP-Adapter
- No reference analysis is injected into prompts
- Output always includes transparent PNG via RemBG
