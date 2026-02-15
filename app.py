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
    run_visual_analyst_m3,
    run_prompt_engineer_m3,
    call_comfyui,
    create_parameter_plan_m3,
    get_workflow_spec,
)
from modules.reference_compare import compare_input_reference

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

    # Workflow selection (M3 only)
    workflow_spec = get_workflow_spec("M3")
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
            help="Example: Animation_Workflow_M3_Api.json"
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
    st.markdown("**Debug Settings**")
    debug_mode = st.checkbox(
        "Show Step-by-Step Debug Images",
        value=True,
        help="ON: show raw and processed images by steps. OFF: show final image only (production mode).",
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
        "Upload Reference Style Image (Required for M3)",
        type=["png", "jpg", "jpeg"],
        help="Used by IP-Adapter to inject style for M3"
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
# These options are agent-controlled for M3; keep them out of the UI to avoid conflicts.
pose_lock = True
style_lock = True

# Anatomy fix level is controlled by the agent/presets; keep it out of the UI to avoid conflicts.
anat_level = 70

# Model is locked for M3; don't show model selection UI.
from modules import DEFAULT_M3_MODEL, SD_MODELS
selected_model = DEFAULT_M3_MODEL

# ---------- Section 3: Generation Control & Output ----------
st.header("2️⃣ Generate Your Animation Frame")
st.markdown("_Click the button below to start processing_")

generate = st.button("🚀 Start Generation", type="primary", use_container_width=True)
status_placeholder = st.empty()
img_placeholder = st.empty()

# ---------- Generation Logic ----------
if generate:
    if not uploaded:
        st.warning("⚠️ Please upload an image first before generating.")
    elif workflow_spec.requires_reference and not reference_uploaded:
        st.warning("⚠️ Please upload a reference image for M3 workflow.")
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
            raw_report = run_visual_analyst_m3(
                image_bytes,
                mime,
                cfg,
                reference_bytes=reference_bytes,
                reference_mime=reference_mime,
            )
            report = normalize_report(raw_report)
            # Compute input-vs-reference signals so the director can scale IP/Union/KS params
            # when the reference conflicts with the sketch.
            if reference_bytes:
                try:
                    comp = compare_input_reference(
                        image_bytes,
                        reference_bytes,
                        subject_details=report.get("subject_details") or "",
                        reference_summary=report.get("reference_summary") or "",
                    )
                    report["reference_structural_score"] = comp.structural_score
                    report["reference_proportion_score"] = comp.proportion_score
                    report["reference_feature_match_score"] = comp.feature_match_score
                    report["reference_conflict_penalty"] = comp.conflict_penalty
                    report["reference_final_score"] = comp.final_score
                except Exception:
                    report["reference_final_score"] = None
            required_fields = [
                "subject_details",
                "entity_type",
                "construction_lines",
                "low_construction_sublevel",
                "broken_lines",
                "line_quality",
                "anatomy_risk",
                "complexity",
            ]
            missing = [f for f in required_fields if not report.get(f)]
            if missing:
                status.write("❌ Visual Analyst output incomplete for M3.")
                st.error(
                    "Image analysis failed. Please re-upload or check your connection "
                    "to ensure anatomy-lock is active."
                )
                st.caption(f"Missing required fields: {', '.join(missing)}")
                st.stop()

            if selected_model:
                model_info = SD_MODELS.get(selected_model, {})
                model_name_display = model_info.get("name", selected_model)
                status.write(f"🎨 Using model: {model_name_display} (M3 default)")
            status.write("🎯 Step 1.5: AD-Agent computing M3 parameters...")
            m3_plan = create_parameter_plan_m3(
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
            if m3_plan:
                # Allow director to drive prompt guardrails / reference handling.
                if m3_plan.get("prompt_modifiers"):
                    report["prompt_modifiers"] = m3_plan["prompt_modifiers"]
                if m3_plan.get("reference_mode"):
                    report["reference_mode"] = m3_plan["reference_mode"]
                if m3_plan.get("_influence_scalar") is not None:
                    report["_influence_scalar"] = m3_plan["_influence_scalar"]
                try:
                    report["ip_weight"] = float(m3_plan["ip_adapter"]["weight"])
                    report["ip_end_at"] = float(m3_plan["ip_adapter"]["end_at"])
                except Exception:
                    pass
                if m3_plan.get("ip_adapter_dual"):
                    report["ip_adapter_dual"] = m3_plan["ip_adapter_dual"]
                status.write(
                    "🧭 Director: "
                    f"CN Union end={m3_plan['controlnet_union']['end_percent']}, "
                    f"OpenPose end={m3_plan['controlnet_openpose']['end_percent']}, "
                    f"IP end_at={m3_plan['ip_adapter']['end_at']}"
                )
                if m3_plan.get("model_name"):
                    selected_model = m3_plan["model_name"]
                    st.session_state["m3_model_auto"] = selected_model
                    status.write(f"🧭 Director: model auto-switch → {selected_model}")

            # Step 2: Prompt Engineer
            status.write("✍️ Step 2: Creating instructions for image generation...")
            pos_prompt, neg_prompt, pos_prompt_stage2, neg_prompt_stage2, rationale = run_prompt_engineer_m3(
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
                m3_plan=m3_plan,
                debug_mode=debug_mode,
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

        if m3_plan:
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

            with st.expander("🧭 AI Strategy (M3 Parameter Plan)"):
                st.markdown("**Sampler 1: Structural Setup**")
                st.code(
                    f"steps: {m3_plan['ksampler1']['steps']}, "
                    f"cfg: {m3_plan['ksampler1']['cfg']}, "
                    f"denoise: {m3_plan['ksampler1']['denoise']}"
                )
                st.markdown("**Sampler 2: Ink Refinement**")
                st.code(
                    f"steps: {m3_plan['ksampler2']['steps']}, "
                    f"cfg: {m3_plan['ksampler2']['cfg']}, "
                    f"denoise: {m3_plan['ksampler2']['denoise']}"
                )
                st.markdown("**Motion-Lock Engine**")
                st.code(
                    f"Union strength: {m3_plan['controlnet_union']['strength']}, "
                    f"Union end: {m3_plan['controlnet_union']['end_percent']}"
                )
                st.code(
                    f"OpenPose strength: {m3_plan['controlnet_openpose']['strength']}, "
                    f"OpenPose end: {m3_plan['controlnet_openpose']['end_percent']}"
                )
                st.markdown("**Style Injection (IP-Adapter)**")
                st.code(
                    f"weight: {m3_plan['ip_adapter']['weight']}, "
                    f"end_at: {m3_plan['ip_adapter']['end_at']}"
                )
                if m3_plan.get("model_name"):
                    st.markdown("**Model Auto-Switch**")
                    st.code(f"model: {m3_plan['model_name']}")
        # Display generated images
        if generated_image:
            img_placeholder.empty()  # Clear placeholder
            debug_payload = None
            if isinstance(generated_image, dict):
                debug_payload = generated_image.get("debug")
                generated_image = generated_image.get("final")

            if isinstance(generated_image, tuple) and len(generated_image) == 2:
                # Two returned outputs from ComfyUI/post-process pipeline.
                output_1, output_2 = generated_image
                final_output = output_1

                if debug_mode:
                    st.markdown("### 🧪 Step-by-Step Debug View")
                    st.markdown("_Pipeline images from input to raw outputs to final cleaned outputs._")

                    st.markdown("**Step 1: Input Image**")
                    st.image(uploaded, caption="Original input uploaded by user", width='stretch')

                    if reference_uploaded:
                        st.markdown("**Step 2: Reference Image**")
                        st.image(reference_uploaded, caption="Reference image sent to IP-Adapter", width='stretch')

                    if debug_payload:
                        raw_imgs = debug_payload.get("raw", [])
                        raw_nodes = debug_payload.get("raw_node_ids", [])
                        processed_imgs = debug_payload.get("processed", [])

                        if raw_imgs:
                            st.markdown("**Step 3: Raw ComfyUI Outputs (before post-process)**")
                            cols = st.columns(2)
                            for i, raw in enumerate(raw_imgs[:2]):
                                node_label = raw_nodes[i] if i < len(raw_nodes) else "?"
                                with cols[i % 2]:
                                    st.image(raw, caption=f"Raw output from Node {node_label}", width='stretch')

                        if processed_imgs:
                            st.markdown("**Step 4: Post-Processed Outputs (grayscale + threshold + heal)**")
                            cols = st.columns(2)
                            for i, proc in enumerate(processed_imgs[:2]):
                                with cols[i % 2]:
                                    st.image(proc, caption=f"Processed output #{i+1}", width='stretch')

                    st.markdown("**Step 5: Final Display**")
                    st.image(final_output, caption="✅ Final primary output (KS2 / Node 54)", width='stretch')
                else:
                    st.markdown("### 🎨 Final Generated Image")
                    st.image(final_output, caption="✅ Final output (KS2 / Node 54, production mode)", width='stretch')
            else:
                # Fallback for single image (backward compatibility)
                img_placeholder.image(generated_image, caption="Your Generated Image")
        else:
            img_placeholder.info("💡 Your generated image will appear here after you click 'Start Generation'")

st.caption("Built with Streamlit + Google Gemini AI + ComfyUI. Set your API keys in the sidebar to get started.")
