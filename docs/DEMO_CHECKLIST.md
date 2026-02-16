# M4 Demo Checklist (Task 2.8)

Use this for recording the final demo. Each case should show the UI logs + output images.

---

## ✅ Scenario 1: Rough Sketch → AnythingXL (Pure Cleanup)

**Goal:** Show heavy cleanup on messy roughs.

**Input:** Very messy rough sketch (scribbles, construction lines)
**Reference:** Any clean style image
**Expected:**
- Visual Analyst: line_quality = messy, anatomy_risk = high/medium
- AD-Agent: KS1 denoise ~0.65–0.75
- Model auto-switch → AnythingXL Ink Base
- Stage 2 prompt includes `(solid black lines:1.5)`
- Output: clean black lineart, no shading

**Expected logs:**
- `🧭 Director: line_quality=messy, anatomy_risk=high, complexity=...`
- `🧭 Director: CN Union end=..., OpenPose end=..., IP end_at=...`

**Validation pointers:**
- Confirm no shading/gradients (Stage 2 negatives doing their job)
- Show Director Summary line for “messy lines”

**Screenshot targets:**
- Director Summary
- AI Strategy (M4 Parameter Plan)
- Final transparent output

---

## ✅ Scenario 2: Complex Pose → OpenPose Lock

**Goal:** Show pose preservation with skeleton lock.

**Input:** Complex pose sketch (extreme limb angles)
**Reference:** Any style image
**Expected:**
- anatomy_risk = high
- OpenPose strength = 1.0
- Output pose matches input closely

**Expected logs:**
- `🧭 Director: line_quality=..., anatomy_risk=high, complexity=...`
- `✅ Updated M4 OpenPose params`

**Validation pointers:**
- Confirm OpenPose strength is high and end_percent is not being cut too early
- Highlight Motion‑Lock in Director Summary

**Screenshot targets:**
- Director Summary showing Motion‑Lock emphasis
- Output comparison (pose preserved)

---

## ✅ Scenario 3: Final Polish → Animagine XL

**Goal:** Show studio-finish line quality.

**Input:** Tie Down or CleanUp sketch
**Reference:** High quality anime lineart
**Expected:**
- line_quality = structured/clean
- Model auto-switch → Animagine XL 3.1
- Output has polished anime line quality

**Expected logs:**
- `🧭 Director: line_quality=structured, anatomy_risk=...`
- `🧭 Director: model auto-switch → animagine-xl-3.1.safetensors`

**Validation pointers:**
- Show Director Summary for auto-switch reasoning
- Confirm crisp outlines and refined facial features

**Screenshot targets:**
- Director Summary + model auto-switch log
- Final output with crisp outlines

---

## ✅ Checklist Before Recording

- [ ] `COMFYUI_API_URL` set in `.env`
- [ ] Gemini API key is active
- [ ] M4 workflow file exists (`Animation_Workflow_M4_Api.json`)
- [ ] Reference image uploaded
- [ ] Output shows transparent PNG (checkerboard background)

---

## ✅ Live Recording Tips

- Always show **Director Summary** before generating
- Use **AI Strategy** expander to confirm sequential gap values
- If results look off, check buckets (line_quality/anatomy_risk)
