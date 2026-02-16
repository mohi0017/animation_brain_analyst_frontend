# M4 Workflow Parameters (Implementation Notes)

> Canonical reference: `docs/M4_MASTER_PLAN_DYNAMIC_STATIC.md`

This document describes what the app actually does at runtime (dynamic planning + a few explicit presets),
not static defaults baked into a single workflow JSON.

## Step Policy
- KSampler1 steps: 40 (locked)
- KSampler2 steps: 40 by default
- KSampler2 steps: 50 for some harder presets (single_complex and multi_object cases)

## Typical Ranges (adaptive path)
- IP-Adapter: weight ~0.2-0.6, end_at ~0.25-0.6
- ControlNet Union: strength ~0.3-0.6, end_percent ~0.45-0.8
- ControlNet OpenPose: strength >= 0.9 (often 1.0), end_percent ~0.85-1.0
- KSampler1: cfg policy 7.0-10.0 (effective caps apply), denoise varies by case
- KSampler2: cfg policy 7.0-10.0 (effective caps apply), denoise varies by case

## Preset Overrides (early-return cases)
The Director may return a full preset plan for specific combinations of:
`entity_type`, `construction_lines`, `broken_lines`.

These presets may intentionally pin some values (including `end_percent=1.0`) to behave like a strong
"trace/ink" pass. In those presets, the usual sequential-gap constraints do not necessarily apply.

## Auto-Adaptive Rules (Implemented)

### Core Constraints (general intent)
- OpenPose strength >= 0.90
- (Adaptive path) Union strength typically clamped to ~0.30-0.60
- KSampler1/2 global CFG allowed range: 7.0–10.0
- Effective CFG caps are stage/case dependent (KS2 stricter than KS1)
- (Adaptive path) IP-Adapter typically ends before Union
- KSampler2 denoise < KSampler1 denoise
- KS2 safety coupling:
  - if `ip2 > 0.40` then `cfg2 <= 7.8`
  - if `ip2 > 0.50` then `cfg2 <= 7.4`

### Input-Driven Adjustments
- Messy lines -> KS1 denoise +, Union strength/end +, IP weight/end -
- Clean lines -> KS1 denoise -, Union strength/end -, KS2 denoise +
- High anatomy risk -> OpenPose strength/end +, IP weight -
- Simple design -> KS1 denoise -, IP weight -
- Detailed design -> KS1 denoise +, IP weight + (keep IP end < Union end)
- Pose lock on -> OpenPose strength/end +, KS1 cfg mid
- Style lock on -> IP weight capped (unless style_match is true)
- CleanUp phase -> anatomy/structure priority (OpenPose/Union +, IP weight -)
- Tie Down phase -> reduce style influence (IP weight/end -, KS1 denoise capped)

### Issue-Based Overrides (optional signals)
- Over-processed -> KS2 denoise -, KS2 cfg -, IP weight -
- Pose drift -> OpenPose strength/end +, Union strength +, KS1 denoise -
- Lines too thin/weak -> KS2 cfg +, KS2 denoise + (slightly), Union strength +
