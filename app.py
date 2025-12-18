"""
Streamlit frontend for the AI Animation Studio.

This is the main entry point for the application. It handles the UI and orchestrates
the workflow between Visual Analyst, Prompt Engineer, and ComfyUI.

Environment Variables:
- GOOGLE_GENAI_API_KEY or GEMINI_API_KEY: Required for Gemini calls
- COMFYUI_API_URL: Base URL to your ComfyUI HTTP API (e.g., http://host:port)
- COMFYUI_WORKFLOW_URL: (Optional) URL to workflow JSON on server
- COMFYUI_WORKFLOW_PATH: (Optional) Path to workflow JSON on server
- GEMINI_MODEL: (Optional) Gemini model to use (default: gemini-2.5-flash)
- GEMINI_THINK_BUDGET: (Optional) Thinking budget for Gemini (in tokens)
"""

import os
import streamlit as st
from dotenv import load_dotenv

# Import all modular components
from modules import (
    AnalysisConfig,
    load_image_bytes,
    normalize_report,
    run_visual_analyst,
    run_prompt_engineer,
    call_comfyui,
)

# Load environment variables from .env file
load_dotenv()

# ---------- Streamlit Page Configuration ----------
st.set_page_config(
    page_title="AI Animation Studio", 
    page_icon="🎬", 
    layout="wide"
)

# ---------- Main UI ----------
st.title("🎬 AI Animation Studio")
st.markdown("_Transform rough sketches into polished animation frames_")

# ---------- Sidebar: Environment Configuration ----------
with st.sidebar:
    st.markdown("**API Keys & Settings**")
    st.text_input(
        "Google AI API Key", 
        type="password", 
        value=os.getenv("GOOGLE_GENAI_API_KEY", ""),
        help="Your API key from Google AI Studio (ai.google.dev)"
    )
    comfy_url = st.text_input(
        "ComfyUI Server URL", 
        value=os.getenv("COMFYUI_API_URL", "https://j9z3h3awdbe4rf-8188.proxy.runpod.net"),
        help="The web address where your ComfyUI server is running"
    )
    if comfy_url:
        st.caption(f"✅ Connected to: {comfy_url}")
    
    st.markdown("**Workflow Settings**")
    
    # Server workflow options
    with st.expander("🔧 Advanced: Use Workflow from Server (Optional)", expanded=False):
        st.caption("Only change these if your workflow file is on a remote server")
        workflow_url_input = st.text_input(
            "Workflow File URL",
            value=os.getenv("COMFYUI_WORKFLOW_URL", ""),
            help="Example: https://your-server.com/workflow.json"
        )
        workflow_path_input = st.text_input(
            "Workflow File Name on Server",
            value=os.getenv("COMFYUI_WORKFLOW_PATH", ""),
            help="Example: ANIMATION_M1.json"
        )
        if workflow_url_input:
            os.environ["COMFYUI_WORKFLOW_URL"] = workflow_url_input
        if workflow_path_input:
            os.environ["COMFYUI_WORKFLOW_PATH"] = workflow_path_input
    
    # Local workflow files
    workflow_files = []
    for search_dir in ["workflows", "."]:
        if os.path.isdir(search_dir):
            workflow_files.extend([
                os.path.join(search_dir, f) 
                for f in os.listdir(search_dir) 
                if f.startswith("ANIMATION_M1") and f.endswith(".json")
            ])
    
    if workflow_files:
        # Show priority order (API version first, then v11 format)
        priority_order = ["workflows/ANIMATION_M1_api_version.json", "workflows/ANIMATION_M1.json"]
        found_priority = [f for f in priority_order if f in workflow_files]
        if found_priority:
            st.caption(f"✅ Local: {found_priority[0]}")
            if len(found_priority) > 1:
                st.caption(f"Also: {found_priority[1]}")
        else:
            st.caption(f"Local files: {', '.join(workflow_files[:2])}")
    else:
        if not os.getenv("COMFYUI_WORKFLOW_URL") and not os.getenv("COMFYUI_WORKFLOW_PATH"):
            st.warning("⚠️ No workflow file found. Please either:\n- Add ANIMATION_M1_api_version.json to the workflows/ folder, OR\n- Use the server workflow settings above")

# ---------- Section 1: Input & Upload ----------
st.header("1️⃣ Upload Your Image")
st.markdown("_Upload the animation frame you want to transform_")

uploaded = st.file_uploader(
    "Choose an image file", 
    type=["png", "jpg", "jpeg"],
    help="Supported formats: PNG, JPG, JPEG"
)
if uploaded:
    st.markdown("**Your Image Preview**")
    st.image(uploaded, caption="This is the image that will be processed")

col_src, col_dst = st.columns(2)
with col_src:
    source_phase = st.selectbox(
        "What stage is your image now?",
        ["Skeleton", "Roughs", "Tie Down", "CleanUp", "Colors"],
        index=1,  # Default: Roughs
        help="Select the current animation phase of your drawing"
    )
with col_dst:
    dest_phase = st.selectbox(
        "What stage do you want to reach?",
        ["Skeleton", "Roughs", "Tie Down", "CleanUp", "Colors"],
        index=2,  # Default: Tie Down
        help="Select the target animation phase you want to create"
    )

# ---------- Section 2: Phase Configuration ----------
st.header("2️⃣ Settings & Options")
st.markdown("_Configure how the AI should process your image_")

col_lock1, col_lock2 = st.columns(2)
with col_lock1:
    pose_lock = st.checkbox(
        "Keep Same Pose", 
        value=True,
        help="If checked, the character's pose and motion will stay the same. Only fixes anatomy issues."
    )
with col_lock2:
    style_lock = st.checkbox(
        "Keep Same Style", 
        value=True,
        help="If checked, the art style and proportions will be preserved."
    )

anat_level = st.slider(
    "How Much to Fix Anatomy", 
    0, 100, 70,
    help="0 = Don't fix anatomy issues, 100 = Fix all anatomy problems strictly"
)
master_instruction = st.text_area(
    "Custom Instructions (Optional - for advanced users)",
    value="",
    placeholder="Leave this empty to use the default settings. Only fill this if you know what you're doing.",
)

# ---------- Section 3: Generation Control & Output ----------
st.header("3️⃣ Generate Your Animation Frame")
st.markdown("_Click the button below to start processing_")

generate = st.button("🚀 Start Generation", type="primary", use_container_width=True)
status_placeholder = st.empty()
img_placeholder = st.empty()

with st.expander("View Generated Prompts"):
    pos_box = st.empty()
    neg_box = st.empty()

# ---------- Generation Logic ----------
if generate:
    if not uploaded:
        st.warning("⚠️ Please upload an image first before generating.")
    else:
        # Load image
        image_bytes, mime = load_image_bytes(uploaded)
        
        # Create analysis configuration
        cfg = AnalysisConfig(
            source_phase=source_phase,
            dest_phase=dest_phase,
            pose_lock=pose_lock,
            style_lock=style_lock,
            anatomical_level=anat_level,
            master_instruction=master_instruction,
        )

        # Execute workflow with status updates
        with st.status("Processing your image...", expanded=True) as status:
            # Step 1: Visual Analyst
            status.write("🔍 Step 1: Analyzing your image with AI...")
            raw_report = run_visual_analyst(image_bytes, mime, cfg)
            report = normalize_report(raw_report)

            # Step 2: Prompt Engineer
            status.write("✍️ Step 2: Creating instructions for image generation...")
            pos_prompt, neg_prompt, rationale = run_prompt_engineer(
                report, dest_phase, master_instruction, 
                source_phase=source_phase, 
                pose_lock=pose_lock, 
                style_lock=style_lock
            )

            # Step 3: ComfyUI Generation
            status.write("🎨 Step 3: Generating your new image (this may take 30-60 seconds)...")
            generated_image = call_comfyui(
                image_bytes, 
                pos_prompt, 
                neg_prompt, 
                dest_phase=dest_phase,
                status_writer=status
            )

            status.update(label="✅ Complete! Your image is ready.", state="complete")

        # Display results
        with st.expander("📊 AI Analysis Report (What the AI Found)"):
            st.write("**Things to Fix**")
            st.caption("These are anatomy or quality issues that need correction")
            st.code("\n".join(report.get("fixes", [])) or "None")
            
            st.write("**Things to Remove**")
            st.caption("These elements should be removed from the image")
            st.code("\n".join(report.get("removes", [])) or "None")
            
            st.write("**Things to Keep the Same**")
            st.caption("These elements should be preserved and not changed")
            st.code("\n".join(report.get("preserve", [])) or "None")
            
            # Highlight colour scheme if present in preserve/notes
            colour_lines = []
            for section in (report.get("preserve", []), report.get("notes", [])):
                for line in section:
                    if isinstance(line, str) and any(
                        key in line.lower()
                        for key in ["line art", "background", "colour", "color"]
                    ):
                        colour_lines.append(line)
            st.write("**Color Scheme**")
            st.caption("Information about colors and background")
            st.code("\n".join(colour_lines) or "None")
            
            st.write("**Additional Notes**")
            st.caption("Extra information and context")
            st.code("\n".join(report.get("notes", [])) or "None")

        st.markdown("**Positive Instructions** (What to include)")
        pos_box.code(pos_prompt or "None")
        st.markdown("**Negative Instructions** (What to avoid)")
        neg_box.code(neg_prompt or "None")
        st.markdown("**Why These Instructions Were Created**")
        st.info(rationale or "No explanation available")

        # Display generated images
        if generated_image:
            img_placeholder.empty()  # Clear placeholder
            if isinstance(generated_image, tuple) and len(generated_image) == 2:
                transparent_img, original_img = generated_image
                # Display both images side by side
                st.markdown("### 🎨 Your Generated Images")
                st.markdown("_Two versions of your processed animation frame:_")
                col1, col2 = st.columns(2)
                with col1:
                    st.image(
                        transparent_img, 
                        caption="✨ With Transparent Background (Perfect for compositing)", 
                        width='stretch'
                    )
                with col2:
                    st.image(
                        original_img, 
                        caption="📄 With White Background (Ready to use)", 
                        width='stretch'
                    )
            else:
                # Fallback for single image (backward compatibility)
                img_placeholder.image(generated_image, caption="Your Generated Image")
        else:
            img_placeholder.info("💡 Your generated image will appear here after you click 'Start Generation'")

st.caption("Built with Streamlit + Google Gemini AI + ComfyUI. Set your API keys in the sidebar to get started.")
