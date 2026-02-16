# M4 Technical Report
## AI Animation Studio - Milestone 4

> Canonical reference: `docs/M4_MASTER_PLAN_DYNAMIC_STATIC.md`

---

## Quick Summary
Milestone 4 introduces a **dual-stage pipeline** that decouples pose preservation from line cleanup using a sequential ControlNet chain and dual KSamplers.

---

## Architecture

### 1) Visual Analyst (Observer)
- Reads the input sketch
- Outputs structured buckets:
  - `line_quality`, `anatomy_risk`, `complexity`, `subject_details`
  - `entity_type`, `entity_examples`
  - `construction_lines`, `broken_lines`

### 2) AD-Agent (Director)
- Computes dynamic parameters per transition
- Applies adaptive control (`S/R/D/P/H`, dynamic bounds, hard safety rules)
- Updates KSampler, ControlNet, and dual IP-Adapter node parameters

### 3) Prompt Engineer (Writer)
- Stage 1: structure authority prompt
- Stage 2: cleanup/refinement authority prompt
- Applies director-driven modifiers and stage-safe filtering

### 4) ComfyUI (Executor)
- Runs `Animation_Workflow_M4_Api.json`
- Uses dual KSampler process with ControlNet chain
- Supports dual IP node updates (`66`, `105`)
- Outputs M4 video combines (`100`, `99`) and decode images (`41`, `73`)

---

## Workflow (M4)

### Key Nodes
- `2/3` → Stage 1 prompts
- `77/76` → Stage 2 prompts
- `5` → KSampler 1 (structure)
- `55` → KSampler 2 (inking)
- `103` → Union XL ControlNet
- `104` → OpenPose ControlNet
- `66` → IP-Adapter (KS1)
- `105` → IP-Adapter (KS2)
- `96/72` → input and reference images

---

## Data Flow
Input image + reference image → Visual Analyst + Reference Compare → AD-Agent params → Prompt Engineer → ComfyUI workflow update → outputs (+ optional feedback rerun)

---

## Key Guarantees
- Pose preservation via strong OpenPose (often strength=1.0) when pose lock is desired
- Adaptive path typically uses a sequential end_percent gap (IP-Adapter < Union < OpenPose)
- Preset paths may intentionally pin end_percent values to 1.0 for trace-like behavior

---

## Project Structure
```
M4/
├── app.py
├── modules/
│   ├── animation_director.py
│   ├── visual_analyst.py
│   ├── prompt_engineer.py
│   ├── comfyui_client.py
│   ├── config.py
│   └── utils.py
├── workflows/
│   ├── Animation_Workflow_M4_Api.json
│   └── (optional) other workflow variants
├── docs/
│   ├── COMFYUI_INTEGRATION.md
│   ├── CONTROLNET_ANATOMY_STRATEGY.md
│   ├── PARAMETERS_GUIDE.md
│   ├── TECHNICAL_REPORT.md
│   └── WORKFLOW_REGISTRY.md
```
