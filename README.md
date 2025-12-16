# AI Animation Studio Frontend

Streamlit control panel for the Gemini-powered Visual Analyst + Prompt Engineer + ComfyUI pipeline.

## Setup (uv)
```bash
uv sync          # install dependencies from pyproject.toml
uv run streamlit run app.py
```

Set environment variables (can also be pasted into the sidebar):
- `GOOGLE_GENAI_API_KEY`
- `COMFYUI_API_URL` (e.g., http://host:8188)
- `COMFYUI_AUTH_TOKEN` (optional)

## Workflow
1) Upload Rough/Skeleton image.  
2) Select Source/Destination phase.  
3) Configure locks and anatomy level; optionally edit the master prompt.  
4) Generate → Gemini Analyst → Gemini Prompt Engineer → ComfyUI KSampler.  
5) View prompts and the generated image.

`app.py` contains placeholders for the ComfyUI call—wire it to your RunPod endpoint.

