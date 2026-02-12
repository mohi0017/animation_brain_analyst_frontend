# M3 Technical Report
## AI Animation Studio - Milestone 3

---

## Quick Summary
Milestone 3 introduces a **dual-stage pipeline** that decouples pose preservation from line cleanup using a sequential ControlNet chain and dual KSamplers.

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
- Enforces sequential gap and motion-lock rules
- Updates KSampler, ControlNet, and IP-Adapter node parameters

### 3) Prompt Engineer (Writer)
- Stage 1: Structure + subject tags with score_9 sequence
- Stage 2: Cleanup/inK template with priority lock for messy lines

### 4) ComfyUI (Executor)
- Runs `Animation_Workflow_M3_Api.json`
- Uses dual KSampler process with ControlNet chain
- Outputs transparent and original PNG

---

## Workflow (M3)

### Key Nodes
- `2/3` → Stage 1 prompts
- `77/76` → Stage 2 prompts
- `5` → KSampler 1 (structure)
- `55` → KSampler 2 (inking)
- `62` → Union XL ControlNet
- `79` → OpenPose ControlNet
- `66` → IP-Adapter
- `4/72` → input and reference images

---

## Data Flow
Input image → Visual Analyst → AD-Agent params → Prompt Engineer → ComfyUI workflow update → outputs

---

## Key Guarantees
- Pose preservation via strong OpenPose (often strength=1.0) when pose lock is desired
- Adaptive path typically uses a sequential end_percent gap (IP-Adapter < Union < OpenPose)
- Preset paths may intentionally pin end_percent values to 1.0 for trace-like behavior

---

## Project Structure
```
M3/
├── app.py
├── modules/
│   ├── animation_director.py
│   ├── visual_analyst.py
│   ├── prompt_engineer.py
│   ├── comfyui_client.py
│   ├── config.py
│   └── utils.py
├── workflows/
│   ├── Animation_Workflow_M3_Api.json
│   └── (optional) other workflow variants
├── docs/
│   ├── COMFYUI_INTEGRATION.md
│   ├── CONTROLNET_ANATOMY_STRATEGY.md
│   ├── PARAMETERS_GUIDE.md
│   ├── TECHNICAL_REPORT.md
│   └── WORKFLOW_REGISTRY.md
```
