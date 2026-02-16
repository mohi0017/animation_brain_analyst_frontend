# M4 Case Playbook: `single_complex` Cleanup

> Status: legacy tactical playbook.  
> Current adaptive source of truth: `docs/M4_MASTER_PLAN_DYNAMIC_STATIC.md`.

This document defines the working strategy for the stylized character cleanup case where output often shows dotted lines, edge separation, or color/fringe artifacts.

## 1) Case Definition

Primary case family:
- `entity_type = single_complex`
- `source_phase -> dest_phase = Roughs -> CleanUp` (or Tie Down in some runs)
- `construction_lines = medium|high`
- `broken_lines = low|medium|high`

Typical visual pattern:
- highly stylized character
- exaggerated proportions (long legs, big hands, dynamic pose)
- overdraw/construction residue in torso, hands, prop

## 2) Confirmed Failure Symptoms

When settings are too aggressive/generative, output degrades as:
- dotted or segmented contours (not continuous ink lines)
- cyan/green/red edge fringe near black lines
- anatomy drift in hands/face/prop
- line cleanup not converging to single decisive contours
- second output image looking noisier than first

## 3) Root Causes (Observed)

Main causes behind dotted/separated line artifacts:
- high `KSampler2 denoise` (e.g. `0.6+`) in cleanup pass
- strong/long `IP-Adapter` injection (`weight >= 0.4`, `end_at=1.0`)
- ControlNet Union ending too early for some noisy sketches (mid-stage freedom causes fragmented redraw)
- mixed prompt tags with duplicate semantics reducing constraint focus

## 4) Active Presets (Current)

### A) `single_complex + construction=medium + broken=low|medium`
Locked preset:
- `ksampler1`: `steps=40, cfg=9.0, denoise=0.65`
- `ksampler2`: `steps=50, cfg=9.0, denoise=0.35`
- `controlnet_union`: `strength=0.75, end_percent=1.0`
- `controlnet_openpose`: `strength=1.0, end_percent=1.0`
- `ip_adapter`: `weight=0.15, end_at=0.2`

Intent:
- strong structure preservation
- low late-stage style injection
- low redraw pressure in stage 2

### B) `single_complex + construction=high + broken=medium|high`
Locked preset:
- `ksampler1`: `steps=40, cfg=9.0, denoise=0.65`
- `ksampler2`: `steps=50, cfg=9.0, denoise=0.35`
- `controlnet_union`: `strength=0.75, end_percent=1.0`
- `controlnet_openpose`: `strength=1.0, end_percent=1.0`
- `ip_adapter`: `weight=0.15, end_at=0.2`

Intent:
- avoid hallucination and color/fringe bleed
- reduce dot-like contour breakup

## 5) Prompt Strategy (Current Rules)

For character cleanup quality:
- remove rigid geometry tags in character-like cases:
  - `precise geometry`
  - `stable silhouette`
  - `single unbroken stroke`
  - `uniform line thickness`
- keep line quality terms (`solid black lines`, `continuous and smooth lines`)
- add Stage 2 hand cleanup tags:
  - `clean hand anatomy`
  - `clear finger separation`
  - `single decisive contour per limb`
- drop plain line-noise tags when weighted variant exists:
  - e.g. keep `(broken lines:1.5)`, remove plain `broken lines`

## 6) Output Handling Rule

ComfyUI download order prioritizes:
1. Node `100` (primary clean output)
2. Node `99` (secondary/debug-like output)
3. fallback to other available nodes

Operational note:
- judge quality primarily from Node `100`
- Node `99` can be noisier and may show fringe/ghost artifacts

## 7) Troubleshooting Matrix (Quick)

If dotted/separated lines persist:
1. reduce `ksampler2.denoise` by `0.05` (minimum practical ~`0.30`)
2. reduce `ip_adapter.weight` by `0.05` (minimum practical ~`0.10`)
3. keep `controlnet_union.end_percent = 1.0`

If anatomy drifts:
1. keep `openpose = 1.0 @ 1.0`
2. increase `controlnet_union.strength` by `+0.05` (up to `0.8`)
3. avoid increasing `ip_adapter.end_at`

If cleanup looks too rigid/stiff:
1. verify rigid character tags are not reintroduced
2. avoid `uniform line thickness` in character-specific output

## 8) Expected Log Signature

Healthy case logs should include one of these:
- `single_complex+construction medium+broken low_or_medium override`
- `single_complex+construction high/medium_or_high override`

and parameter block should match section 4 values.
