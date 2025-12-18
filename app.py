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
st.title("AI Animation Studio Control Panel")

# ---------- Sidebar: Environment Configuration ----------
with st.sidebar:
    st.markdown("**Environment**")
    st.text_input(
        "GOOGLE_GENAI_API_KEY", 
        type="password", 
        value=os.getenv("GOOGLE_GENAI_API_KEY", "")
    )
    comfy_url = st.text_input(
        "COMFYUI_API_URL", 
        value=os.getenv("COMFYUI_API_URL", "https://j9z3h3awdbe4rf-8188.proxy.runpod.net")
    )
    if comfy_url:
        st.caption(f"Using: {comfy_url}")
    
    st.markdown("**Workflow Template**")
    
    # Server workflow options
    with st.expander("🔧 Server Workflow (Optional)", expanded=False):
        st.caption("Use workflow saved on ComfyUI server")
        workflow_url_input = st.text_input(
            "Workflow URL (COMFYUI_WORKFLOW_URL)",
            value=os.getenv("COMFYUI_WORKFLOW_URL", ""),
            help="Full URL to workflow JSON file on server"
        )
        workflow_path_input = st.text_input(
            "Workflow Path (COMFYUI_WORKFLOW_PATH)",
            value=os.getenv("COMFYUI_WORKFLOW_PATH", ""),
            help="Filename/path of workflow on server (e.g., ANIMATION_M1.json)"
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
            st.warning("No local workflow found. Use server workflow options above or place ANIMATION_M1_api_version.json in workflows/ directory.")

# ---------- Section 1: Input & Upload ----------
st.header("Input & Upload")
uploaded = st.file_uploader("Upload Rough Image", type=["png", "jpg", "jpeg"])
if uploaded:
    st.image(uploaded, caption="Preview")

col_src, col_dst = st.columns(2)
with col_src:
    source_phase = st.selectbox(
        "Source Phase",
        ["Skeleton", "Roughs", "Tie Down", "CleanUp", "Colors"],
        index=1,  # Default: Roughs
    )
with col_dst:
    dest_phase = st.selectbox(
        "Destination Phase",
        ["Skeleton", "Roughs", "Tie Down", "CleanUp", "Colors"],
        index=2,  # Default: Tie Down
    )

# ---------- Section 2: Phase Configuration ----------
st.header("Phase Configuration (LLM Analyst Control)")
col_lock1, col_lock2 = st.columns(2)
with col_lock1:
    pose_lock = st.checkbox("Motion / Pose Lock", value=True)
with col_lock2:
    style_lock = st.checkbox("Style / Artistic Lock", value=True)

anat_level = st.slider("Anatomical Correction Level", 0, 100, 70)
master_instruction = st.text_area(
    "LLM Master Instruction (advanced override)",
    value="",
    placeholder="Leave blank to use the default Master Prompt.",
)

# ---------- Section 3: Generation Control & Output ----------
st.header("Generation")
generate = st.button("Generate Phase")
status_placeholder = st.empty()
img_placeholder = st.empty()

with st.expander("View Generated Prompts"):
    pos_box = st.empty()
    neg_box = st.empty()

# ---------- Generation Logic ----------
if generate:
    if not uploaded:
        st.warning("Please upload an image first.")
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
        with st.status("Processing...", expanded=True) as status:
            # Step 1: Visual Analyst
            status.write("1) Running Visual Analyst (Gemini multimodal)...")
            raw_report = run_visual_analyst(image_bytes, mime, cfg)
            report = normalize_report(raw_report)

            # Step 2: Prompt Engineer
            status.write("2) Running Prompt Engineer (Gemini text)...")
            pos_prompt, neg_prompt, rationale = run_prompt_engineer(
                report, dest_phase, master_instruction, 
                source_phase=source_phase, 
                pose_lock=pose_lock, 
                style_lock=style_lock
            )

            # Step 3: ComfyUI Generation
            status.write("3) Calling ComfyUI / KSampler...")
            generated_image = call_comfyui(
                image_bytes, 
                pos_prompt, 
                neg_prompt, 
                dest_phase=dest_phase,
                status_writer=status
            )

            status.update(label="Done", state="complete")

        # Display results
        with st.expander("Visual Analyst Report"):
            st.write("**Fixes**")
            st.code("\n".join(report.get("fixes", [])) or "N/A")
            st.write("**Removes**")
            st.code("\n".join(report.get("removes", [])) or "N/A")
            st.write("**Preserve**")
            st.code("\n".join(report.get("preserve", [])) or "N/A")
            
            # Highlight colour scheme if present in preserve/notes
            colour_lines = []
            for section in (report.get("preserve", []), report.get("notes", [])):
                for line in section:
                    if isinstance(line, str) and any(
                        key in line.lower()
                        for key in ["line art", "background", "colour", "color"]
                    ):
                        colour_lines.append(line)
            st.write("**Colour Scheme**")
            st.code("\n".join(colour_lines) or "N/A")
            st.write("**Notes**")
            st.code("\n".join(report.get("notes", [])) or "N/A")

        pos_box.code(pos_prompt or "N/A")
        neg_box.code(neg_prompt or "N/A")
        st.markdown("**Prompt Engineer Rationale**")
        st.info(rationale or "N/A")

        # Display generated images
        if generated_image:
            img_placeholder.empty()  # Clear placeholder
            if isinstance(generated_image, tuple) and len(generated_image) == 2:
                transparent_img, original_img = generated_image
                # Display both images side by side
                st.markdown("### Generated Outputs")
                col1, col2 = st.columns(2)
                with col1:
                    st.image(
                        transparent_img, 
                        caption="🟢 Transparent Background (Node 42 - ImageRemoveBackground+)", 
                        use_container_width=True
                    )
                with col2:
                    st.image(
                        original_img, 
                        caption="🔵 Original with Background (Node 54 - VAEDecode)", 
                        use_container_width=True
                    )
            else:
                # Fallback for single image (backward compatibility)
                img_placeholder.image(generated_image, caption="Generated Output")
        else:
            img_placeholder.info("Image will appear here after backend wiring or when COMFYUI_API_URL is set.")

st.caption("Built with Streamlit + Gemini + ComfyUI. Configure API keys in the sidebar.")
