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
from io import BytesIO

import streamlit as st
from dotenv import load_dotenv

# Import all modular components
from modules import (
    AnalysisConfig,
    load_image_bytes,
    normalize_report,
    run_visual_analyst_m2,
    run_prompt_engineer_m2,
    call_comfyui,
    create_parameter_plan_m2,
    get_workflow_spec,
)

# Load environment variables from .env file
load_dotenv()

# ---------- Streamlit Page Configuration ----------
st.set_page_config(
    page_title="AI Animation Studio", 
    page_icon="🎬", 
    layout="wide"
)

# ---------- Sidebar Label Hack: Show "Studio 🎬" Instead of File Name ----------
# Streamlit names the top-level page in the sidebar based on the filename (e.g. "app").
# Because Streamlit Cloud UI does not expose a way to change the main file path,
# we use a small CSS override to rename the sidebar label to "Studio 🎬".
st.markdown(
    """
    <style>
    /* Target the first item in the sidebar navigation (the main page) */
    [data-testid="stSidebarNav"] li:first-child a span {
        visibility: hidden;
    }
    [data-testid="stSidebarNav"] li:first-child a span::after {
        content: '🎬 Studio';
        visibility: visible;
        display: inline-block;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Main UI ----------
st.title("🎬 AI Animation Studio")
st.markdown("_Transform rough sketches into polished animation frames_")

# ---------- Sidebar: Environment Configuration ----------
with st.sidebar:
    use_server_workflow = False
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

    # Workflow selection (M2 only)
    workflow_spec = get_workflow_spec("M2")
    st.caption(f"✅ Selected: {workflow_spec.label}")
    st.caption(f"📄 Workflow file: {workflow_spec.api_path}")
    
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
            help="Example: ANIMATION_M2_Api.json"
        )
        if workflow_url_input:
            os.environ["COMFYUI_WORKFLOW_URL"] = workflow_url_input
            use_server_workflow = True
        if workflow_path_input:
            os.environ["COMFYUI_WORKFLOW_PATH"] = workflow_path_input
            use_server_workflow = True
    
    # Local workflow file check
    if not os.path.exists(workflow_spec.api_path):
        if not os.getenv("COMFYUI_WORKFLOW_URL") and not os.getenv("COMFYUI_WORKFLOW_PATH"):
            st.warning(
                "⚠️ Selected workflow file not found. "
                "Please add the file locally or use the server workflow settings above."
            )

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

reference_uploaded = None
if workflow_spec.requires_reference:
    reference_uploaded = st.file_uploader(
        "Upload Reference Style Image (Required for M2)",
        type=["png", "jpg", "jpeg"],
        help="Used by IP-Adapter to inject style for M2"
    )
    if reference_uploaded:
        st.markdown("**Reference Image Preview**")
        st.image(reference_uploaded, caption="This reference image guides style transfer")

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

# Model Selection
from modules import SD_MODELS, DEFAULT_LINE_ART_MODEL, DEFAULT_M2_MODEL

st.markdown("**🎨 Stable Diffusion Model**")
m2_options = [DEFAULT_M2_MODEL]
m2_labels = [
    f"{SD_MODELS[m]['name']} - {SD_MODELS[m]['category']}" if m in SD_MODELS else m
    for m in m2_options
]
model_key = "m2_model_choice"
auto_key = "m2_model_auto"
if auto_key in st.session_state and st.session_state[auto_key] in m2_options:
    st.session_state[model_key] = st.session_state[auto_key]
selected_model = st.selectbox(
    "Select Model (M2):",
    m2_options,
    format_func=lambda m: m2_labels[m2_options.index(m)],
    key=model_key,
    help="Animagine XL 3.1 is the locked M2 model."
)
st.caption("Model is locked to Animagine XL 3.1 for M2.")

# ---------- Section 3: Generation Control & Output ----------
st.header("3️⃣ Generate Your Animation Frame")
st.markdown("_Click the button below to start processing_")

generate = st.button("🚀 Start Generation", type="primary", use_container_width=True)
status_placeholder = st.empty()
img_placeholder = st.empty()

# ---------- Generation Logic ----------
if generate:
    if not uploaded:
        st.warning("⚠️ Please upload an image first before generating.")
    elif workflow_spec.requires_reference and not reference_uploaded:
        st.warning("⚠️ Please upload a reference image for M2 workflow.")
    else:
        # Load image
        image_bytes, mime = load_image_bytes(uploaded)
        reference_bytes = None
        reference_mime = None
        if workflow_spec.requires_reference and reference_uploaded:
            reference_bytes, reference_mime = load_image_bytes(reference_uploaded)
        
        # Create analysis configuration
        cfg = AnalysisConfig(
            source_phase=source_phase,
            dest_phase=dest_phase,
            pose_lock=pose_lock,
            style_lock=style_lock,
            anatomical_level=anat_level,
        )

        # Execute workflow with status updates
        with st.status("Processing your image...", expanded=True) as status:
            selected_workflow_path = None if use_server_workflow else workflow_spec.api_path
            # Step 1: Visual Analyst
            status.write("🔍 Step 1: Analyzing your image with AI...")
            raw_report = run_visual_analyst_m2(
                image_bytes,
                mime,
                cfg,
                reference_bytes=reference_bytes,
                reference_mime=reference_mime,
            )
            report = normalize_report(raw_report)

            required_fields = ["subject_details", "line_quality", "anatomy_risk", "complexity"]
            missing = [f for f in required_fields if not report.get(f)]
            if missing:
                status.write("❌ Visual Analyst output incomplete for M2.")
                st.error(
                    "Image analysis failed. Please re-upload or check your connection "
                    "to ensure anatomy-lock is active."
                )
                st.caption(f"Missing required fields: {', '.join(missing)}")
                st.stop()

            if selected_model:
                model_info = SD_MODELS.get(selected_model, {})
                model_name_display = model_info.get("name", selected_model)
                status.write(f"🎨 Using model: {model_name_display} (M2 default)")
            status.write("🎯 Step 1.5: AD-Agent computing M2 parameters...")
            m2_plan = create_parameter_plan_m2(
                report=report,
                source_phase=source_phase,
                dest_phase=dest_phase,
                pose_lock=pose_lock,
                style_lock=style_lock,
            )
            # Director's decision log
            status.write(
                f"🧭 Director: line_quality={report.get('line_quality')}, "
                f"anatomy_risk={report.get('anatomy_risk')}, "
                f"complexity={report.get('complexity')}"
            )
            if m2_plan:
                status.write(
                    "🧭 Director: "
                    f"CN Union end={m2_plan['controlnet_union']['end_percent']}, "
                    f"OpenPose end={m2_plan['controlnet_openpose']['end_percent']}, "
                    f"IP end_at={m2_plan['ip_adapter']['end_at']}"
                )
                if m2_plan.get("model_name"):
                    selected_model = m2_plan["model_name"]
                    st.session_state["m2_model_auto"] = selected_model
                    status.write(f"🧭 Director: model auto-switch → {selected_model}")

            # Step 2: Prompt Engineer
            status.write("✍️ Step 2: Creating instructions for image generation...")
            pos_prompt, neg_prompt, pos_prompt_stage2, neg_prompt_stage2, rationale = run_prompt_engineer_m2(
                report,
                dest_phase,
                source_phase=source_phase,
                pose_lock=pose_lock,
                style_lock=style_lock,
                workflow_path=workflow_spec.api_path,
            )
            prompts = {
                "stage1": {"positive": pos_prompt, "negative": neg_prompt},
                "stage2": {"positive": pos_prompt_stage2, "negative": neg_prompt_stage2},
            }

            # Step 3: ComfyUI Generation
            status.write("🎨 Step 3: Generating your new image (this may take up to 4 minutes)...")
            generated_image = call_comfyui(
                image_bytes,
                prompts,
                model_name=selected_model,
                status_writer=status,
                workflow_path=selected_workflow_path,
                reference_image_bytes=reference_bytes,
                m2_plan=m2_plan,
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

        st.markdown("**Stage 1 Positive Instructions** (Character + Style)")
        st.code(pos_prompt or "None")
        st.markdown("**Stage 1 Negative Instructions**")
        st.code(neg_prompt or "None")
        st.markdown("**Stage 2 Positive Instructions** (Cleanup + Ink)")
        st.code(pos_prompt_stage2 or "None")
        st.markdown("**Stage 2 Negative Instructions**")
        st.code(neg_prompt_stage2 or "None")
        st.markdown("**Why These Instructions Were Created**")
        st.info(rationale or "No explanation available")

        if m2_plan:
            summary = []
            line_quality = report.get("line_quality", "")
            anatomy_risk = report.get("anatomy_risk", "")
            complexity = report.get("complexity", "")
            if line_quality == "messy":
                summary.append("Messy lines detected; prioritizing heavy structure lock and high denoise to stabilize anatomy.")
            elif line_quality == "structured":
                summary.append("Structured sketch detected; applying light refinement and high-fidelity inking for crisp outlines.")
            elif line_quality == "clean":
                summary.append("Clean lines detected; preserving structure while focusing on final inking polish.")
            if anatomy_risk == "high":
                summary.append("Complex pose detected; maximizing Motion-Lock Engine (OpenPose) to prevent skeletal shift.")
            if not summary and complexity:
                summary.append("Dynamic parameters set based on sketch complexity and anatomy risk.")
            st.info(summary[0] if summary else "Waiting for analysis.")

            with st.expander("🧭 AI Strategy (M2 Parameter Plan)"):
                st.markdown("**Sampler 1: Structural Setup**")
                st.code(
                    f"steps: {m2_plan['ksampler1']['steps']}, "
                    f"cfg: {m2_plan['ksampler1']['cfg']}, "
                    f"denoise: {m2_plan['ksampler1']['denoise']}"
                )
                st.markdown("**Sampler 2: Ink Refinement**")
                st.code(
                    f"steps: {m2_plan['ksampler2']['steps']}, "
                    f"cfg: {m2_plan['ksampler2']['cfg']}, "
                    f"denoise: {m2_plan['ksampler2']['denoise']}"
                )
                st.markdown("**Motion-Lock Engine**")
                st.code(
                    f"Union strength: {m2_plan['controlnet_union']['strength']}, "
                    f"Union end: {m2_plan['controlnet_union']['end_percent']}"
                )
                st.code(
                    f"OpenPose strength: {m2_plan['controlnet_openpose']['strength']}, "
                    f"OpenPose end: {m2_plan['controlnet_openpose']['end_percent']}"
                )
                st.markdown("**Style Injection (IP-Adapter)**")
                st.code(
                    f"weight: {m2_plan['ip_adapter']['weight']}, "
                    f"end_at: {m2_plan['ip_adapter']['end_at']}"
                )
                if m2_plan.get("model_name"):
                    st.markdown("**Model Auto-Switch**")
                    st.code(f"model: {m2_plan['model_name']}")
        # Display generated images
        if generated_image:
            img_placeholder.empty()  # Clear placeholder
            if isinstance(generated_image, tuple) and len(generated_image) == 2:
                # transparent_img and original_img are PNG bytes from ComfyUI
                transparent_img, original_img = generated_image

                # Display both images side by side, exactly as generated by the model
                st.markdown("### 🎨 Your Generated Images")
                st.markdown("_Two versions of your processed animation frame:_")
                col1, col2 = st.columns(2)
                with col1:
                    st.image(
                        transparent_img,
                        caption="✨ Transparent Lines Only (no background)",
                        width='stretch'
                    )
                with col2:
                    st.image(
                        original_img,
                        caption="📄 Original Background Generated by Model",
                        width='stretch',
                    )
            else:
                # Fallback for single image (backward compatibility)
                img_placeholder.image(generated_image, caption="Your Generated Image")
        else:
            img_placeholder.info("💡 Your generated image will appear here after you click 'Start Generation'")

st.caption("Built with Streamlit + Google Gemini AI + ComfyUI. Set your API keys in the sidebar to get started.")
