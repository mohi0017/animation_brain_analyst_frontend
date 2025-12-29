# ControlNet Anatomy Strategy (M2)
## Motion-Lock Engine with Sequential Gap

---

## Core Idea
M2 uses a **sequential ControlNet chain** to preserve pose while allowing cleanup:

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
- `ip_adapter.end_at < controlnet_union.end_percent < openpose.end_percent`

---

## Required Limits
- **OpenPose end_percent**: `>= 0.80` (always)
- **Union end_percent**:
  - `<= 0.65` for messy roughs
  - can be higher for clean tie-down
- **IP-Adapter end_at**:
  - always before Union

---

## Why It Works
- Union keeps the drawing inside the original silhouette
- OpenPose keeps joints and gesture correct
- The gap gives the model freedom to clean lines

---

## Summary
This strategy preserves motion while allowing high-quality cleanup. It is the core of the M2 Motion-Lock Engine.
