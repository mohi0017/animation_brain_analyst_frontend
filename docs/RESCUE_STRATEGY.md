# M3 Rescue Strategy: Aggressive Cleanup

## Overview

The **Rescue Strategy** ("Aggressive Cleanup") is a specialized parameter set designed for `Roughs -> CleanUp` transitions where the input analysis detects `line_quality="messy"`. 

Messy inputs (construction lines, smudges, multiple passes) confuse standard ControlNets, leading to "double lines" or retained artifacts in the final output. This strategy sacrifices some structural fidelity to force the model to hallucinate clean, singular lines.

---

## Strategy Logic

### 1. High Denoise (Re-imagination)
We push the Stage 1 Denoise (`ks1_denoise`) significantly higher than normal. This gives the model permission to ignore the specific pixel arrangement of the messy sketch and rebuild the concept from the prompt and general pose.

- **Standard CleanUp Denoise:** 0.70 - 0.75
- **Aggressive Rescue Denoise:** 0.82 - 0.85

### 2. Early ControlNet Cutoff
Standard workflows keep ControlNet active until 70-80% of the generation to preserve details. For messy sketches, holding on too long forces the model to render the construction lines. We cut it off early so the model finishes the drawing using its internal knowledge of "clean line art".

- **Standard Union End:** 0.75 - 0.80
- **Aggressive Union End:** 0.55 (Release control at 55%)

### 3. Targeted Negative Prompts
We explicitly negate the artifacts common to rough sketches.

- **Added Negatives:** `(construction lines:1.3), (graphite:1.2), (sketch artifacts:1.2), (smudge:1.2), (guidelines:1.1)`

---

## Activation Conditions

This strategy activates automatically when:
1. **Transition:** `Roughs -> CleanUp` (Direct jump)
2. **Analysis:** `line_quality == "messy"`

## Risks

- **Structural Drift:** Because we release control early (0.55), complex details (hands, specific accessories) may drift from the original sketch.
- **Pose Shift:** If OpenPose fails on the messy input, the character pose might shift slightly.

## Mitigation
- We force `controlnet_openpose` to `1.0` strength to anchor the general posture even as we release line art control.
