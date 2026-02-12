# ControlNet Anatomy Strategy (M3)
## Motion-Lock Engine with Sequential Gap

---

## Core Idea
M3 uses a **sequential ControlNet chain** to preserve pose while allowing cleanup:

1) **ControlNet Union XL** defines the line/shape boundary
2) **OpenPose** locks joints and skeleton

This creates a rigid motion lock without freezing messy sketch lines.

---

## Sequential Gap Rule
The **end_percent gap** is critical:

- Union ends first
- OpenPose ends later

This lets the model fix line quality while keeping pose locked.

**Rule:**
- Adaptive-path intent: `ip_adapter.end_at < controlnet_union.end_percent < openpose.end_percent`
- Preset-path exception: some explicit presets pin multiple `end_percent` values to 1.0 for trace-like behavior.

---

## Required Limits
- **OpenPose end_percent**: typically `>= 0.85` when pose lock is desired (often 1.0)
- **Union end_percent**:
  - `<= ~0.65` for messy/high-construction roughs
  - can be higher for clean tie-down
- **IP-Adapter end_at**:
  - typically before Union in the adaptive path

---

## Why It Works
- Union keeps the drawing inside the original silhouette
- OpenPose keeps joints and gesture correct
- The gap gives the model freedom to clean lines

---

## Summary
This strategy preserves motion while allowing high-quality cleanup. It is the core of the M3 Motion-Lock Engine.
