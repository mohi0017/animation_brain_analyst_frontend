# AI Animation Studio Frontend

Streamlit control panel for the Gemini-powered Visual Analyst + Prompt Engineer + ComfyUI pipeline.

## Setup (uv)
```bash
uv sync          # install dependencies from pyproject.toml
uv run streamlit run app.py
```

Set environment variables (can also be pasted into the sidebar):
- `GOOGLE_GENAI_API_KEY` - Required for Gemini API calls
- `COMFYUI_API_URL` - Required (e.g., `https://your-runpod.proxy.runpod.net`)
- `COMFYUI_AUTH_TOKEN` - Optional, if API requires authentication
- `COMFYUI_WORKFLOW_URL` - Optional, full URL to workflow JSON on server
- `COMFYUI_WORKFLOW_PATH` - Optional, filename/path of workflow on server (e.g., `ANIMATION_M1.json`)

**Workflow Loading Priority:**
1. Server workflow URL (`COMFYUI_WORKFLOW_URL`) - if set
2. Server workflow path (`COMFYUI_WORKFLOW_PATH`) - if set
3. Local files: `ANIMATION_M1_Complete.json` → `ANIMATION_M1.json` → `ANIMATION_M1 (10).json` → `ANIMATION_M1 (11).json`

## Workflow
1) Upload Rough/Skeleton image.  
2) Select Source/Destination phase.  
3) Configure locks and anatomy level; optionally edit the master prompt.  
4) Generate → Gemini Analyst → Gemini Prompt Engineer → ComfyUI KSampler.  
5) View prompts and the generated image.

`app.py` contains placeholders for the ComfyUI call—wire it to your RunPod endpoint.

