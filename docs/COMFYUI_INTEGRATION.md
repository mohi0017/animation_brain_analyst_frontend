# ComfyUI Integration (M3)
## How the M3 Pipeline Works End-to-End

> Canonical reference: `docs/M3_MASTER_PLAN_DYNAMIC_STATIC.md`

---

## Overview
Milestone 3 uses a dual-stage generation pipeline that separates **structure preservation** from **final inking**.
The workflow runs in ComfyUI with two KSamplers and a sequential ControlNet chain:

- **ControlNet Union XL** (line/shape boundary)
- **OpenPose** (skeleton lock)
- **IP-Adapter** (style injection from reference image)
- **KSampler 1** (structure + cleanup)
- **KSampler 2** (final inking)

---

## Input Flow
1) **Input Image** (rough or tie-down)
2) **Reference Image** (style only; used by IP-Adapter)

Reference is primarily used for dual-IP style conditioning and adaptive control signals.
Director can also inject prompt guardrails/modifiers based on reference conflicts.

---

## Workflow File
Use the API workflow (v10 format):

- `workflows/Animation_Workflow_M3_Api.json`

This is required for the ComfyUI API submission.

---

## Execution Stages

### Stage 1: Structure & Style (KSampler 1)
- **KSampler**: Node `5`
- **Prompts**: Node `2` (positive), Node `3` (negative)
- **ControlNet Union XL**: Node `62`
- **OpenPose**: Node `79`
- **IP-Adapter**: Node `66`

This stage locks pose and structure while allowing controlled cleanup.

### Stage 2: Cleanup & Ink (KSampler 2)
- **KSampler**: Node `55`
- **Prompts**: Node `77` (positive), Node `76` (negative)

This stage converts the output into clean, solid line art.

---

## Node Map (M3)
- **CheckpointLoaderSimple**: `1`
- **Input LoadImage**: `4`
- **Reference LoadImage**: `72`
- **IPAdapterAdvanced**: `66`
- **IPAdapterAdvanced (KS2 path)**: `90`
- **ControlNet Union XL**: `62`
- **OpenPose ControlNet**: `79`
- **KSampler 1**: `5`
- **KSampler 2**: `55`
- **Stage 1 Prompts**: `2` / `3`
- **Stage 2 Prompts**: `77` / `76`
- **DWPreprocessor**: `78`
- **Outputs**: one or more `SaveImage` nodes (IDs vary by workflow)

---

## Dynamic Parameters (AD-Agent)
The app computes parameters per transition and updates these nodes at runtime:

- **KSampler 1**: steps, cfg, denoise
- **KSampler 2**: steps, cfg, denoise
- **ControlNet Union**: strength, end_percent
- **OpenPose**: strength, end_percent
- **IP-Adapter KS1**: weight, end_at
- **IP-Adapter KS2**: weight, end_at

Rules enforced:
- In the adaptive path, the Director typically aims for:
  - IP-Adapter ending before Union
  - Union ending before OpenPose
- Some explicit presets intentionally pin end_percent values to 1.0 for trace-like behavior.
- When construction/broken lines are high, Union and IP-Adapter are reduced to avoid tracing/hallucination.

---

## API Submission Flow
1) Upload input image to `/upload/image`
2) Upload reference image to `/upload/image`
3) Load `Animation_Workflow_M3_Api.json`
4) Update prompts + nodes
5) Submit to `/prompt`
6) Poll `/history/{prompt_id}`
7) Download results from `/view`

---

## Troubleshooting
- **No output**: Check `COMFYUI_API_URL` in `.env`
- **Wrong workflow**: Ensure v10 API format
- **Bad pose lock**: Check OpenPose strength is high (often 1.0) and end_percent is not being cut too early
- **Over-stylized output**: Reduce IP-Adapter weight
