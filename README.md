# 🎬 AI Animation Studio (M3)

AI Animation Studio M3 is a dual-stage animation cleanup pipeline. It preserves pose with a Motion-Lock engine and converts rough sketches into clean line art using ComfyUI + Gemini.

## ✨ What It Does

- **Rough → Tie Down / CleanUp** with strong pose preservation
- **Dual-Stage Generation**: structure first, inking second
- **Reference Image** used only for IP-Adapter style injection
- **Dynamic Parameters** per phase and input quality
- **Transparent PNG** output for compositing

## 📁 Project Structure

```
M3/
├── app.py
├── pages/
│   └── 3_📚_Documentation.py
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
├── pyproject.toml
├── .env
└── README.md
```

## 🚀 Getting Started

### Requirements
- Python 3.10+
- `uv`
- Gemini API key
- ComfyUI server

### Install
```bash
uv sync
```

### Configure
```bash
cp .env.example .env
```

Add to `.env`:
```env
GOOGLE_GENAI_API_KEY=your_key
COMFYUI_API_URL=http://localhost:8188
```

### Run
```bash
uv run streamlit run app.py
```

## 🧠 M3 Pipeline (Short)

1) **Visual Analyst** analyzes input image and outputs buckets:
   - line_quality, anatomy_risk, complexity, subject_details
2) **AD-Agent** computes dynamic parameters (KSamplers, ControlNet, IP-Adapter)
3) **Prompt Engineer** builds dual-stage prompts:
   - Stage 1 = structure + subject tags
   - Stage 2 = inking template
4) **ComfyUI** runs dual KSampler pipeline and outputs transparent + original PNG

## 🤝 Agents (Easy Summary + Plan)

### Visual Analyst (Observer)
**Summary:** Looks at the input sketch like a real animator and describes what needs fixing.\n  
**Plan:**\n  
1) Identify subject and pose from the input image\n  
2) Rate line quality, anatomy risk, and complexity\n  
3) Output structured tags for the Director and Prompt Engineer

### AD-Agent (Director)
**Summary:** Chooses the right parameters to keep pose locked and clean lines.\n  
**Plan:**\n  
1) Read buckets from Visual Analyst\n  
2) Apply the transition matrix (Rough→Tie Down / CleanUp)\n  
3) Enforce Motion‑Lock rules (IP‑Adapter < Union < OpenPose)

### Prompt Engineer (Writer)
**Summary:** Builds dual-stage prompts that match the workflow.\n  
**Plan:**\n  
1) Stage 1: add score tags + subject + pose\n  
2) Stage 2: inking template for solid black lines\n  
3) Apply 75‑tag cap to avoid dilution

## 📚 Docs
Open the Documentation page in the app, or read files in `docs/`.
