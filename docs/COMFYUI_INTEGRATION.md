# ComfyUI Integration (M2)
## How the M2 Pipeline Works End-to-End

---

## Overview
Milestone 2 uses a dual-stage generation pipeline that separates **structure preservation** from **final inking**.
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

The reference image does NOT affect prompts. It only feeds the IP-Adapter node.

---

## Workflow File
Use the API workflow (v10 format):

- `workflows/ANIMATION_M2_Api.json`

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

## Node Map (M2)
- **CheckpointLoaderSimple**: `1`
- **Input LoadImage**: `4`
- **Reference LoadImage**: `72`
- **IPAdapterAdvanced**: `66`
- **ControlNet Union XL**: `62`
- **OpenPose ControlNet**: `79`
- **KSampler 1**: `5`
- **KSampler 2**: `55`
- **Stage 1 Prompts**: `2` / `3`
- **Stage 2 Prompts**: `77` / `76`
- **DWPreprocessor**: `78`
- **Transparent Output**: `42` (ImageRemoveBackground+)
- **Original Output**: `54`

---

## Dynamic Parameters (AD-Agent)
The app computes parameters per transition and updates these nodes at runtime:

- **KSampler 1**: steps, cfg, denoise
- **KSampler 2**: steps, cfg, denoise
- **ControlNet Union**: strength, end_percent
- **OpenPose**: strength, end_percent
- **IP-Adapter**: weight, end_at

Rules enforced:
- IP-Adapter ends **before** Union
- Union ends **before** OpenPose
- OpenPose end >= 0.80
- Union end <= 0.65 when line_quality is messy

---

## API Submission Flow
1) Upload input image to `/upload/image`
2) Upload reference image to `/upload/image`
3) Load `ANIMATION_M2_Api.json`
4) Update prompts + nodes
5) Submit to `/prompt`
6) Poll `/history/{prompt_id}`
7) Download results from `/view`

---

## Troubleshooting
- **No output**: Check `COMFYUI_API_URL` in `.env`
- **Wrong workflow**: Ensure v10 API format
- **Bad pose lock**: Check OpenPose end_percent >= 0.80
- **Over-stylized output**: Reduce IP-Adapter weight
