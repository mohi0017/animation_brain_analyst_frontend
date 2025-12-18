# AI Animation Studio Frontend

Streamlit control panel for the Gemini-powered Visual Analyst + Prompt Engineer + ComfyUI pipeline.

## 🎯 Key Features

- **Multi-Modal LLM Brain:** Gemini 2.5 Flash for visual analysis and prompt engineering
- **All Phase Transitions:** Skeleton ↔ Roughs ↔ Tie Down ↔ Cleanup ↔ Colors (any to any)
- **Advanced ControlNet Strategy:** "Timed Release" method for anatomy correction (see [CONTROLNET_ANATOMY_STRATEGY.md](CONTROLNET_ANATOMY_STRATEGY.md))
- **Transparent Background Generation:** All phases generate transparent PNG output
- **Dual Output Display:** View both transparent background (Node 42) and original (Node 54) side-by-side
- **Stable Diffusion Prompting:** Proper weighting syntax `(keyword:weight)` with comma-separated keywords
- **Robust Error Handling:** Smart fallback prompts when Gemini API fails

## 🚀 Setup (uv)

```bash
uv sync          # install dependencies from pyproject.toml
uv run streamlit run app.py
```

The app automatically includes multiple pages:
- **🎬 Main Generator** (`app.py`) - Main image generation interface
- **🎛️ Parameters Tuning** (`pages/2_🎛️_Parameters_Tuning.py`) - Interactive parameter adjustment with live explanations and presets

## ⚙️ Environment Variables

Set in `.env` file or paste into the sidebar:

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_GENAI_API_KEY` | ✅ | Gemini API key for LLM calls |
| `GEMINI_MODEL` | ❌ | Model name (default: `gemini-2.5-flash`) |
| `GEMINI_THINK_BUDGET` | ❌ | Thinking budget for Gemini (default: auto) |
| `COMFYUI_API_URL` | ✅ | RunPod endpoint (e.g., `https://xxx.proxy.runpod.net`) |
| `COMFYUI_AUTH_TOKEN` | ❌ | Bearer token if API requires auth |
| `COMFYUI_WORKFLOW_URL` | ❌ | Full URL to workflow JSON on server |
| `COMFYUI_WORKFLOW_PATH` | ❌ | Filename/path on server (e.g., `ANIMATION_M1.json`) |

**Workflow Loading Priority:**
1. Server workflow URL (`COMFYUI_WORKFLOW_URL`) - if set
2. Server workflow path (`COMFYUI_WORKFLOW_PATH`) - if set
3. Local files: `ANIMATION_M1_api_version.json` (preferred) → `ANIMATION_M1.json` → others

## 📋 Workflow

1. **Upload:** Rough/Skeleton image (PNG/JPG)
2. **Configure:** Select Source Phase → Destination Phase
3. **Locks:** Motion/Pose Lock, Style/Artistic Lock
4. **Generate:** 
   - Gemini Visual Analyst analyzes image
   - Gemini Prompt Engineer creates SD prompts
   - ComfyUI KSampler generates output
5. **Output:** View transparent + original images side-by-side

## 🎨 Supported Phase Transitions

| From → To | Behavior |
|-----------|----------|
| **Skeleton → Roughs** | Add gestural movement, volumetric forms |
| **Roughs → Tie Down** | Define on-model shapes, clean single lines |
| **Tie Down → Cleanup** | Perfect linework, anatomy correction, remove construction lines |
| **Cleanup → Colors** | Add full color fills, skin tones, vibrant palette |
| **Roughs → Cleanup** | Combined: define shapes + perfect lines in one pass |
| **Roughs → Colors** | Combined: cleanup lines + add colors in one pass |

All reverse transitions supported (e.g., Cleanup → Roughs).

## 🔧 Advanced: ControlNet "Timed Release" Strategy

For rough sketches with anatomy issues (distorted face, messy hands), we use an optimized ControlNet strategy:

- **CFG Scale:** 7.5 (balanced for ControlNet + prompt creativity)
- **Lineart ControlNet:** End at 70% (releases at step 21/30)
- **Canny ControlNet:** End at 60% (releases at step 18/30)
- **Result:** AI follows structure for 70% of generation, then fixes anatomy in last 30%

**See detailed documentation:** [CONTROLNET_ANATOMY_STRATEGY.md](CONTROLNET_ANATOMY_STRATEGY.md)

## 📚 Technical Documentation

All documentation moved to `docs/` directory:

- **[docs/TECHNICAL_REPORT.md](docs/TECHNICAL_REPORT.md)** - Complete system architecture and design
- **[docs/COMFYUI_INTEGRATION.md](docs/COMFYUI_INTEGRATION.md)** - ComfyUI integration details and challenges
- **[docs/CONTROLNET_ANATOMY_STRATEGY.md](docs/CONTROLNET_ANATOMY_STRATEGY.md)** - ControlNet optimization strategy
- **[docs/PARAMETERS_GUIDE.md](docs/PARAMETERS_GUIDE.md)** - ⭐ **NEW** Comprehensive parameters tuning guide
- **[convert_md_to_pdf.py](convert_md_to_pdf.py)** - Convert documentation to PDF

## 🎯 Prompt Engineering Rules

This system uses **Stable Diffusion 1.5** prompting best practices:

1. **Comma-separated keywords**, not sentences
2. **Weighting syntax:** `(keyword:weight)` where 1.0=normal, 1.1-1.4=strong
3. **Hierarchical structure:** Subject + Pose + Style + Environment + Quality
4. **Material focus** (not motion, since ControlNet locks motion)
5. **High-weight anatomy keywords:** `(perfectly drawn face:1.3)`, `(anatomically correct hands:1.3)`

## 🧪 Testing

**Test with rough sketch containing:**
- Distorted face (unclear eyes/nose/mouth)
- Messy hands (fused/extra/missing fingers)
- Off proportions

**Expected result:**
- Face becomes clear with defined features
- Hands correct to proper anatomy (5 fingers)
- Body proportions adjust to on-model
- Smooth, uniform line quality

## 🚢 Deployment

Deployed on **Streamlit Cloud**: [Link to your deployed app]

Push to GitHub `main` branch triggers auto-deployment.

## 📝 Version History

- **v1.0:** Initial Streamlit UI with Gemini + ComfyUI integration
- **v1.1:** Added all phase transition support (any to any)
- **v1.2:** Transparent background generation, dual output display
- **v1.3:** Stable Diffusion prompting rules with weighting syntax
- **v1.4:** ControlNet "Timed Release" strategy for anatomy correction
- **v1.5:** ⭐ **NEW** Parameters Tuning page, comprehensive PARAMETERS_GUIDE.md, workflow JSON synchronization, documentation reorganization

## 🛠️ Tech Stack

- **Frontend:** Streamlit
- **LLM:** Google Gemini 2.5 Flash (Multi-Modal)
- **Image Generation:** Stable Diffusion 1.5 via ComfyUI
- **ControlNets:** LineArt + Canny
- **Package Manager:** uv
- **Deployment:** Streamlit Cloud

---

Built with ❤️ for professional animation cleanup workflows.

