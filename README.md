# 🎬 AI Animation Studio

A sophisticated AI-powered animation cleanup pipeline that converts rough sketches into various animation phases (Skeleton, Roughs, Tie Down, Cleanup, Colors) using Gemini LLM agents and ComfyUI (Stable Diffusion).

## ✨ Features

- **Multi-Phase Animation Pipeline**: Convert between all animation phases (Skeleton ↔ Roughs ↔ Tie Down ↔ CleanUp ↔ Colors)
- **AI-Powered Analysis**: Gemini multimodal agent analyzes input sketches and identifies fixes
- **Intelligent Prompt Engineering**: Gemini text agent generates optimized Stable Diffusion prompts
- **Advanced ControlNet Strategy**: "Timed Release" strategy for anatomy correction
- **Transparent Background Support**: Generate images with transparent backgrounds
- **Dual Image Output**: Display both transparent and original images side-by-side
- **Interactive Parameters Tuning**: Dedicated page for fine-tuning ComfyUI parameters
- **Robust Error Handling**: Smart fallback mechanisms for API failures

## 📁 Project Structure

```
M1/
├── app.py                          # Main Streamlit application (entry point)
├── pages/                          # Streamlit multi-page app
│   └── 2_🎛️_Parameters_Tuning.py  # Interactive parameter tuning interface
├── modules/                        # Core modular components
│   ├── __init__.py                 # Module exports
│   ├── config.py                   # Configuration, constants, prompts
│   ├── utils.py                    # Helper functions
│   ├── gemini_client.py            # Gemini API client initialization
│   ├── visual_analyst.py           # Visual Analyst agent (multimodal)
│   ├── prompt_engineer.py          # Prompt Engineer agent (text)
│   └── comfyui_client.py           # ComfyUI API client
├── workflows/                      # ComfyUI workflow templates
│   ├── ANIMATION_M1_api_version.json  # v10 format (preferred for API)
│   └── ANIMATION_M1.json              # v11 format (ComfyUI UI export)
├── docs/                           # Documentation (Markdown only)
│   ├── COMFYUI_INTEGRATION.md      # ComfyUI integration guide
│   ├── CONTROLNET_ANATOMY_STRATEGY.md  # ControlNet strategies
│   ├── PARAMETERS_GUIDE.md         # Parameter tuning guide
│   └── TECHNICAL_REPORT.md         # Technical architecture report
├── scripts/                        # Utility scripts
│   └── convert_md_to_pdf.py        # Markdown to PDF converter
├── pyproject.toml                  # Project dependencies (uv)
├── .env                            # Environment variables (create this)
├── .gitignore                      # Git ignore rules
└── README.md                       # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Gemini API key (get from [Google AI Studio](https://makersuite.google.com/app/apikey))
- ComfyUI instance (local or RunPod)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/mohi0017/animation_brain_analyst_frontend.git
   cd M1
   ```

2. **Install dependencies using uv**
   ```bash
   uv sync
   ```

3. **Create `.env` file**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Configure environment variables in `.env`**
   ```env
   # Required
   GOOGLE_GENAI_API_KEY=your_gemini_api_key_here
   COMFYUI_API_URL=http://localhost:8188

   # Optional
   GEMINI_MODEL=gemini-2.5-flash
   GEMINI_THINK_BUDGET=0
   COMFYUI_WORKFLOW_URL=https://your-server.com/workflow.json
   COMFYUI_WORKFLOW_PATH=ANIMATION_M1.json
   ```

5. **Run the application**
   ```bash
   uv run streamlit run app.py
   ```

6. **Access the application**
   - Open your browser to `http://localhost:8501`

## 🎯 Usage

### Basic Workflow

1. **Upload Image**: Upload your rough sketch (PNG, JPG, JPEG)
2. **Select Phases**: Choose source and destination phases
3. **Configure**: Set pose/style locks and anatomical correction level
4. **Generate**: Click "Generate Phase" to start processing
5. **Review**: View generated images and analysis reports

### Phase Transitions

The system supports all animation phase transitions:

- **Forward Transitions** (increasing detail):
  - Skeleton → Roughs → Tie Down → CleanUp → Colors
  
- **Backward Transitions** (decreasing detail):
  - Colors → CleanUp → Tie Down → Roughs → Skeleton
  
- **Lateral Transitions** (same level):
  - Skeleton ↔ Roughs
  - Tie Down ↔ CleanUp

### Advanced Features

#### Parameters Tuning Page

Access the Parameters Tuning page from the sidebar to:
- Adjust KSampler settings (Steps, CFG, Denoise)
- Tune ControlNet parameters (Strength, Start/End Percent)
- Configure preprocessors (LineArt, Canny)
- Use built-in presets (Gentle Cleanup, Aggressive Fix, etc.)
- Export/import custom configurations

#### Transparent Background Output

The system generates two versions of each image:
1. **Transparent Background** (Node 42 - ImageRemoveBackground+)
2. **Original with Background** (Node 54 - VAEDecode)

Both are displayed side-by-side for comparison.

## 🧠 AI Brain Architecture

### Two-Agent System

1. **Visual Analyst (Agent 1)**
   - **Input**: Raw image + phase configuration
   - **Model**: Gemini 2.5 Flash (multimodal)
   - **Output**: Structured report (fixes, removes, preserve, notes)
   - **Purpose**: Analyze anatomical issues and phase-specific requirements

2. **Prompt Engineer (Agent 2)**
   - **Input**: Visual Analyst report + destination phase
   - **Model**: Gemini 2.5 Flash (text)
   - **Output**: Optimized SD prompts (positive, negative, rationale)
   - **Purpose**: Generate SD-specific prompts with weighting syntax

### Smart Fallback Mechanisms

Both agents implement graceful degradation:
- **429 RESOURCE_EXHAUSTED**: Phase-specific fallback prompts
- **503 UNAVAILABLE**: Smart fallback based on phase transition
- **Network Errors**: Mock outputs for testing without API keys

## 🎨 ComfyUI Integration

### Workflow Templates

Two workflow formats are supported:
- **v10 Format** (`ANIMATION_M1_api_version.json`): Preferred for API submission
- **v11 Format** (`ANIMATION_M1.json`): ComfyUI UI export format

The system automatically converts v11 to v10 if needed.

### Dynamic Parameter Update

The system dynamically updates workflow parameters based on destination phase:

| Phase | CFG | Lineart End | Canny End |
|-------|-----|-------------|-----------|
| Skeleton | 7.5 | 0.7 | 0.6 |
| Roughs | 7.0 | 0.6 | 0.5 |
| Tie Down | 7.5 | 0.7 | 0.6 |
| CleanUp | 7.5 | 0.7 | 0.6 |
| Colors | 7.5 | 0.8 | 0.7 |

## 📚 Documentation

Detailed documentation is available in the `docs/` directory:

- **[ComfyUI Integration](docs/COMFYUI_INTEGRATION.md)**: Complete integration guide
- **[ControlNet Anatomy Strategy](docs/CONTROLNET_ANATOMY_STRATEGY.md)**: "Timed Release" strategy explained
- **[Parameters Guide](docs/PARAMETERS_GUIDE.md)**: Comprehensive parameter tuning reference
- **[Technical Report](docs/TECHNICAL_REPORT.md)**: System architecture and design decisions

## 🔧 Development

### Adding a New Module

1. Create a new Python file in `modules/`
2. Add exports to `modules/__init__.py`
3. Import in `app.py` or other modules as needed

### Modifying Prompts

Edit the default prompts in `modules/config.py`:
- `DEFAULT_ANALYST_PROMPT`: Visual Analyst instructions
- `DEFAULT_PROMPT_ENGINEER`: Prompt Engineer instructions

### Testing Locally

```bash
# Run with auto-reload
uv run streamlit run app.py --server.runOnSave true

# Run in headless mode (for servers)
uv run streamlit run app.py --server.headless true
```

## 🐛 Troubleshooting

### Common Issues

1. **"No workflow found"**
   - Ensure `ANIMATION_M1_api_version.json` is in `workflows/` directory
   - Or set `COMFYUI_WORKFLOW_URL` in `.env`

2. **"Gemini API error: 429"**
   - You've exceeded the free tier quota
   - The system will use smart fallback prompts
   - Consider upgrading to a paid plan

3. **"ComfyUI connection failed"**
   - Check `COMFYUI_API_URL` in `.env`
   - Ensure ComfyUI is running and accessible
   - Test with `curl http://your-comfyui-url/system_stats`

4. **"Invalid width value: None"** (Streamlit Cloud)
   - This was fixed in the latest version
   - Ensure you have `package-mode = false` in `pyproject.toml`

## 📝 License

[Your License Here]

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📧 Contact

**Mohi** - [mohi.pk0017@gmail.com](mailto:mohi.pk0017@gmail.com)

**GitHub**: [@mohi0017](https://github.com/mohi0017)

---

Built with ❤️ using Streamlit, Gemini, and ComfyUI
