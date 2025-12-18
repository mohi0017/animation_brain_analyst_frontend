# 🎬 AI Animation Studio

An AI-powered tool that helps you transform rough animation sketches into polished frames. It uses Google's Gemini AI to understand your drawings and ComfyUI to create clean, professional animation frames automatically.

## ✨ What Can It Do?

- **Transform Between Animation Stages**: Convert your drawings between any animation phase:
  - Skeleton (basic stick figures)
  - Roughs (rough sketches with movement)
  - Tie Down (refined shapes and proportions)
  - CleanUp (clean line art)
  - Colors (fully colored frames)

- **Smart AI Analysis**: The AI looks at your drawing and figures out what needs to be fixed

- **Automatic Instructions**: The AI creates detailed instructions for the image generator

- **Fix Anatomy Problems**: Special technique that helps fix anatomy issues while keeping your character's pose

- **Transparent Backgrounds**: Get your frames with or without backgrounds

- **Two Versions**: See your image with and without a background, side by side

- **Easy Controls**: Simple page to adjust how the AI processes your images

- **Works Offline**: Even if the AI services are down, you can still use basic features

## 📁 Project Structure

```
M1/
├── app.py                          # Main Streamlit application (entry point)
├── pages/                          # Streamlit multi-page app
│   ├── 2_🎛️_Parameters_Tuning.py  # Interactive parameter tuning interface
│   └── 3_📚_Documentation.py       # Documentation viewer
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

## 🚀 Getting Started

### What You Need Before Starting

- **Python 3.10 or newer** (programming language)
- **uv** (tool to install Python packages) - [Get it here](https://github.com/astral-sh/uv)
- **Gemini API Key** (free from [Google AI Studio](https://makersuite.google.com/app/apikey))
- **ComfyUI Server** (the image generation software - can be on your computer or in the cloud)

### How to Install (Step by Step)

**Step 1: Download the Project**
   ```bash
   git clone https://github.com/mohi0017/animation_brain_analyst_frontend.git
   cd M1
   ```
   _(This downloads all the project files to your computer)_

**Step 2: Install Required Software**
   ```bash
   uv sync
   ```
   _(This installs all the Python packages the project needs)_

**Step 3: Create Settings File**
   ```bash
   cp .env.example .env
   # Then open .env in a text editor and add your API keys
   ```
   _(This creates a file where you'll put your secret API keys)_

**Step 4: Add Your API Keys to the `.env` File**
   
   Open the `.env` file in any text editor and fill in your information:
   
   ```env
   # YOU MUST FILL THESE IN:
   GOOGLE_GENAI_API_KEY=paste_your_gemini_key_here
   COMFYUI_API_URL=http://localhost:8188

   # OPTIONAL (only change if you know what these do):
   GEMINI_MODEL=gemini-2.5-flash
   GEMINI_THINK_BUDGET=0
   ```

**Step 5: Start the Application**
   ```bash
   uv run streamlit run app.py
   ```
   _(This starts the web app on your computer)_

**Step 6: Open in Your Web Browser**
   - Go to `http://localhost:8501`
   - You should now see the AI Animation Studio interface!

## 🎯 How to Use

### Simple 5-Step Process

1. **Upload Your Drawing**: Click to upload your sketch (PNG, JPG, or JPEG files work)
2. **Tell Us What You Have**: Select what stage your drawing is at now (Roughs, Skeleton, etc.)
3. **Tell Us What You Want**: Select what stage you want to reach (CleanUp, Colors, etc.)
4. **Adjust Settings**: Choose if you want to keep the same pose and style
5. **Click Generate**: Hit the big "Start Generation" button and wait 30-60 seconds

That's it! The AI will process your drawing and show you the result.

### What Changes Can You Make?

You can transform your drawing in any direction:

- **Add More Detail** (make it more polished):
  - Skeleton → Roughs → Tie Down → CleanUp → Colors
  
- **Remove Detail** (make it simpler):
  - Colors → CleanUp → Tie Down → Roughs → Skeleton
  
- **Switch Between Similar Stages**:
  - Skeleton ↔ Roughs (both are rough stages)
  - Tie Down ↔ CleanUp (both are clean stages)

**Example**: You can go directly from a rough sketch to fully colored, or from colored back to clean lines!

### Extra Features for Power Users

#### Advanced Settings Page

Click "Advanced Settings & Fine-Tuning" in the sidebar to:
- **Change How the AI Processes Images**: Adjust speed vs quality, how much to change, etc.
- **Control How Strictly It Follows Your Pose**: Make the AI follow your lines exactly, or give it freedom to fix problems
- **Use Ready-Made Presets**: Choose from settings like "Fix Messy Sketches" or "Keep Exact Pose"
- **Save Your Own Settings**: Create and reuse your favorite configurations

#### Help & Documentation Page

Click "Documentation" in the sidebar to read:
- **Settings Explained**: What each setting does in simple terms
- **How the AI Fixes Anatomy**: The strategy the AI uses to fix proportion problems
- **Technical Details**: For developers who want to understand how it works
- **Download Guides**: Save any guide as a file to read offline

#### Two Image Versions

Every time you generate an image, you get TWO versions:
1. **With Transparent Background**: Perfect for putting in other software or compositing
2. **With White Background**: Ready to use as-is

Both appear side-by-side so you can pick which one you prefer!

## 🧠 How the AI Works (Behind the Scenes)

### Two AI Helpers Working Together

The app uses TWO AI assistants that work one after another:

**1. The Image Analyst (First AI)**
   - **What it does**: Looks at your drawing and makes a list of problems
   - **What it uses**: Google's Gemini AI (can understand images)
   - **What it creates**: A report that says:
     - What needs to be fixed (like "left hand looks awkward")
     - What should be removed (like "messy construction lines")
     - What should stay the same (like "keep the character's pose")

**2. The Instruction Writer (Second AI)**
   - **What it does**: Takes the report and writes detailed instructions
   - **What it uses**: Google's Gemini AI (text only)
   - **What it creates**: Instructions for the image generator, including:
     - What to add or fix in the image
     - What to avoid or remove
     - Why these instructions were chosen

### Backup System (If AI Services Go Down)

If the AI services are having problems, the app has backups:
- **If the service is overloaded**: Uses pre-made instructions based on your phase choices
- **If the internet is down**: Creates basic instructions so you can still generate images
- **For testing**: Works even without API keys using sample instructions

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

## 🐛 Common Problems and How to Fix Them

### Problem 1: "No workflow found"
**What it means**: The app can't find the instruction file it needs to generate images.

**How to fix**:
- Make sure the file `ANIMATION_M1_api_version.json` is in the `workflows/` folder
- OR add the location of this file to your `.env` settings file

### Problem 2: "Gemini API error: 429"
**What it means**: You've used up your free Google AI quota for today.

**What happens**: The app will automatically use backup instructions (you can still generate images!)

**How to fix**:  
- Wait until tomorrow (free quota resets daily)
- OR upgrade to a paid Google AI plan if you need more

### Problem 3: "ComfyUI connection failed"
**What it means**: The app can't talk to your ComfyUI image generator.

**How to fix**:
- Check that `COMFYUI_API_URL` in your `.env` file is correct
- Make sure ComfyUI is actually running
- Test if ComfyUI is working by visiting its web address in your browser

### Problem 4: App shows errors about image size
**What it means**: An old version had a bug (this is now fixed!).

**How to fix**: Just update to the latest version from GitHub

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
