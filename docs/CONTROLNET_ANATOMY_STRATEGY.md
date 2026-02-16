# ControlNet Anatomy Strategy (M4)
## Motion-Lock Engine with Sequential Gap

> Canonical reference: `docs/M4_MASTER_PLAN_DYNAMIC_STATIC.md`

---

## Core Idea
M4 uses a **sequential ControlNet chain** to preserve pose while allowing cleanup:

1) **ControlNet Union XL** defines the line/shape boundary
2) **OpenPose** locks joints and skeleton

This creates a motion lock without permanently freezing messy sketch lines.

---

## Adaptive End Scheduling
The **end schedule** is critical:

- Prefer: Union ends before OpenPose
- IP (especially KS2 IP) may end earlier for stability

This lets the model fix line quality while keeping pose locked.

**Rule:**
- Adaptive path prefers sequential ordering.
- Controller can override ordering/caps for conflict, pose risk, or artifact suppression.

---

## Required Limits
- **OpenPose end_percent**: typically `>= 0.85` when pose lock is desired (often 1.0)
- **Union end_percent**:
  - `<= ~0.65` for messy/high-construction roughs
  - can be higher for clean tie-down
- **IP-Adapter end_at**:
  - dual-path (`KS1`, `KS2`) and dynamically clamped

---

## Why It Works
- Union keeps the drawing inside the original silhouette
- OpenPose keeps joints and gesture correct
- The gap gives the model freedom to clean lines

---

## Summary
This strategy preserves motion while allowing high-quality cleanup. It is the core of the M4 Motion-Lock Engine.
