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
    normalize_sequence_frames,
    extract_frames_from_video_bytes,
    extract_frames_from_zip_bytes,
    pick_keyframe_indices,
    run_visual_analyst_m4,
    run_prompt_engineer_m4,
    call_comfyui,
    create_parameter_plan_m4,
    get_workflow_spec,
)
from modules.reference_compare import compare_input_reference

# Load environment variables from .env file
load_dotenv()


def _merge_reports(reports: list[dict]) -> dict:
    """Merge keyframe analyst reports into one sequence-level report."""
    if not reports:
        return {}
    merged = dict(reports[0])
    # Majority-vote categorical fields.
    majority_fields = ("entity_type", "entity_examples", "line_quality", "complexity")
    for field in majority_fields:
        vals = [str(r.get(field) or "").strip() for r in reports if r.get(field)]
        if not vals:
            continue
        merged[field] = max(set(vals), key=vals.count)
    # Conservative max-risk fields.
    risk_order = {"low": 0, "medium": 1, "high": 2}
    for field in ("construction_lines", "broken_lines", "anatomy_risk"):
        vals = [str(r.get(field) or "").strip().lower() for r in reports if r.get(field)]
        if vals:
            merged[field] = max(vals, key=lambda x: risk_order.get(x, 0))
    # Keep all fixes/removes/notes/preserve unique across keyframes.
    for field in ("fixes", "removes", "preserve", "notes", "issues"):
        all_items = []
        for r in reports:
            items = r.get(field) or []
            if isinstance(items, list):
                all_items.extend([x for x in items if isinstance(x, str) and x.strip()])
        merged[field] = list(dict.fromkeys(all_items))
    # Subject details: union unique tags.
    subjects = []
    for r in reports:
        s = str(r.get("subject_details") or "").strip()
        if s:
            subjects.extend([x.strip() for x in s.split(",") if x.strip()])
    if subjects:
        merged["subject_details"] = ", ".join(list(dict.fromkeys(subjects)))
    # Keep mandatory low-construction sublevel if present.
    for r in reports:
        sub = str(r.get("low_construction_sublevel") or "").strip()
        if sub:
            merged["low_construction_sublevel"] = sub
            break
    return merged

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

    # Workflow selection (M4 only)
    workflow_spec = get_workflow_spec("M4")
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
            help="Example: Animation_Workflow_M4_Api.json"
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
st.markdown("_Upload single frame, sequence frames, or a video for M4 processing_")

uploaded = None
sequence_files = []
video_uploaded = None
detected_input_type = None

input_files = st.file_uploader(
    "Upload input (single frame, sequence, or video)",
    type=["png", "jpg", "jpeg", "mp4", "mov", "avi", "mkv", "webm", "mpeg4", "zip"],
    accept_multiple_files=True,
    help="Upload one image, multiple sequence images, one video, or one ZIP (sequence folder export).",
)

if input_files:
    image_exts = {".png", ".jpg", ".jpeg"}
    video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".mpeg4"}
    archive_exts = {".zip"}
    images = []
    videos = []
    archives = []
    for f in input_files:
        ext = os.path.splitext(f.name)[-1].lower()
        if ext in image_exts:
            images.append(f)
        elif ext in video_exts:
            videos.append(f)
        elif ext in archive_exts:
            archives.append(f)
        else:
            st.warning(f"Unsupported file type skipped: {f.name}")

    active_groups = int(bool(images)) + int(bool(videos)) + int(bool(archives))
    if active_groups > 1:
        st.error("Please upload one input mode at a time: image(s), one video, or one ZIP.")
    elif len(videos) > 1:
        st.error("Please upload only one video file at a time.")
    elif len(archives) > 1:
        st.error("Please upload only one ZIP file at a time.")
    elif archives:
        detected_input_type = "Image Sequence"
        try:
            zip_bytes = archives[0].read()
            sequence_frames = extract_frames_from_zip_bytes(zip_bytes)
            st.caption(f"✅ Auto-detected input type: Image Sequence from ZIP ({len(sequence_frames)} frames)")
            if sequence_frames:
                st.image(BytesIO(sequence_frames[0][1]), caption="First frame extracted from ZIP")
            # Populate sequence_files surrogate so downstream 'has_input' remains true.
            sequence_files = [archives[0]]
            st.session_state["_zip_sequence_frames"] = sequence_frames
        except Exception as exc:
            st.error(f"ZIP input error: {exc}")
    elif images:
        sequence_files = images
        if len(images) == 1:
            uploaded = images[0]
            detected_input_type = "Single Image"
            st.caption("✅ Auto-detected input type: Single Image")
            st.image(uploaded, caption="Single-frame input")
        else:
            detected_input_type = "Image Sequence"
            st.caption(f"✅ Auto-detected input type: Image Sequence ({len(images)} files)")
            st.image(images[0], caption=f"First uploaded file: {images[0].name}")
    elif videos:
        video_uploaded = videos[0]
        detected_input_type = "Video"
        st.caption(f"✅ Auto-detected input type: Video ({video_uploaded.name})")
    else:
        st.warning("No valid input files detected.")

reference_uploaded = None
if workflow_spec.requires_reference:
    reference_uploaded = st.file_uploader(
        "Upload Reference Style Image (Required for M4)",
        type=["png", "jpg", "jpeg"],
        help="Used by IP-Adapter to inject style for M4"
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
# These options are agent-controlled for M4; keep them out of the UI to avoid conflicts.
pose_lock = True
style_lock = True

# Anatomy fix level is controlled by the agent/presets; keep it out of the UI to avoid conflicts.
anat_level = 70

# Model is locked for M4; don't show model selection UI.
from modules import DEFAULT_M4_MODEL, SD_MODELS
selected_model = DEFAULT_M4_MODEL

# ---------- Section 3: Generation Control & Output ----------
st.header("2️⃣ Generate Your Animation Frame")
st.markdown("_Click the button below to start processing_")

generate = st.button("🚀 Start Generation", type="primary", use_container_width=True)
status_placeholder = st.empty()
img_placeholder = st.empty()

# ---------- Sequence Performance Controls ----------
with st.expander("⚙️ Sequence Performance (Low VRAM)", expanded=False):
    seq_frame_step = st.number_input(
        "Use every Nth frame",
        min_value=1,
        max_value=10,
        value=int(os.getenv("M4_SEQ_FRAME_STEP", "1") or "1"),
        step=1,
        help="1 = use all frames, 2 = use every second frame, etc.",
    )
    seq_max_frames = st.number_input(
        "Max frames per request",
        min_value=1,
        max_value=1000,
        value=int(os.getenv("M4_SEQ_MAX_FRAMES", "120") or "120"),
        step=1,
        help="Hard cap to prevent OOM on smaller GPUs.",
    )
    seq_batch_size = st.number_input(
        "Batch size (frames)",
        min_value=1,
        max_value=300,
        value=int(os.getenv("M4_SEQ_BATCH_SIZE", "32") or "32"),
        step=1,
        help="Sequence is split into batches of this size and processed sequentially.",
    )

# ---------- Generation Logic ----------
if generate:
    has_input = bool(uploaded) or bool(sequence_files) or bool(video_uploaded)
    if not has_input:
        st.warning("⚠️ Please upload an input (single image, sequence, or video) before generating.")
    elif workflow_spec.requires_reference and not reference_uploaded:
        st.warning("⚠️ Please upload a reference image for M4 workflow.")
    else:
        # Build input payload(s)
        sequence_frames: list[tuple[str, bytes]] = []
        try:
            if detected_input_type == "Single Image":
                image_bytes, mime = load_image_bytes(uploaded)
            elif detected_input_type == "Image Sequence":
                zip_frames = st.session_state.pop("_zip_sequence_frames", None)
                if zip_frames:
                    sequence_frames = zip_frames
                else:
                    for f in sequence_files:
                        frame_bytes, _ = load_image_bytes(f)
                        sequence_frames.append((f.name, frame_bytes))
                    sequence_frames = normalize_sequence_frames(sequence_frames)
                image_bytes = sequence_frames[0][1]
                mime = "image/png"
            elif detected_input_type == "Video":
                video_bytes = video_uploaded.read()
                video_suffix = os.path.splitext(video_uploaded.name)[-1].lower() or ".mp4"
                sequence_frames = normalize_sequence_frames(
                    extract_frames_from_video_bytes(video_bytes, suffix=video_suffix)
                )
                image_bytes = sequence_frames[0][1]
                mime = "image/png"
            else:
                st.error("Unable to detect input type. Please upload image(s) or a video.")
                st.stop()
        except Exception as exc:
            st.error(f"Failed to prepare input frames: {exc}")
            st.stop()

        # Sequence optimization for limited VRAM: stride + hard cap.
        if sequence_frames:
            original_count = len(sequence_frames)
            if seq_frame_step > 1:
                sequence_frames = sequence_frames[:: int(seq_frame_step)]
            if len(sequence_frames) > int(seq_max_frames):
                sequence_frames = sequence_frames[: int(seq_max_frames)]
            if not sequence_frames:
                st.error("No sequence frames remain after optimization filters.")
                st.stop()
            if len(sequence_frames) != original_count:
                st.caption(
                    f"⚙️ Sequence optimized for VRAM: {original_count} → {len(sequence_frames)} frames "
                    f"(step={int(seq_frame_step)}, max={int(seq_max_frames)})."
                )
            # Keep primary analysis preview frame synced with optimized sequence.
            image_bytes = sequence_frames[0][1]
            mime = "image/png"

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
            if sequence_frames:
                status.write(
                    f"🎞️ Sequence mode detected: {len(sequence_frames)} frames. "
                    "Running keyframe analysis (first/middle/last)."
                )
                idxs = pick_keyframe_indices(len(sequence_frames))
                reports = []
                for i in idxs:
                    kb = sequence_frames[i][1]
                    raw_k = run_visual_analyst_m4(
                        kb,
                        "image/png",
                        cfg,
                        reference_bytes=reference_bytes,
                        reference_mime=reference_mime,
                    )
                    reports.append(normalize_report(raw_k))
                report = _merge_reports(reports)
            else:
                raw_report = run_visual_analyst_m4(
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
                    if sequence_frames:
                        idxs = pick_keyframe_indices(len(sequence_frames))
                        comps = []
                        for i in idxs:
                            kb = sequence_frames[i][1]
                            comps.append(
                                compare_input_reference(
                                    kb,
                                    reference_bytes,
                                    subject_details=report.get("subject_details") or "",
                                    reference_summary=report.get("reference_summary") or "",
                                )
                            )
                        report["reference_structural_score"] = sum(c.structural_score for c in comps) / len(comps)
                        report["reference_proportion_score"] = sum(c.proportion_score for c in comps) / len(comps)
                        report["reference_feature_match_score"] = sum(c.feature_match_score for c in comps) / len(comps)
                        report["reference_conflict_penalty"] = max(c.conflict_penalty for c in comps)
                        report["reference_text_conflict"] = max(c.text_conflict for c in comps)
                        report["reference_image_conflict"] = max(c.image_conflict for c in comps)
                        report["reference_accessory_mismatch"] = max(c.accessory_mismatch for c in comps)
                        report["reference_is_colored"] = any(c.reference_is_colored for c in comps)
                        report["reference_style_distance"] = sum(c.style_distance for c in comps) / len(comps)
                        report["reference_final_score"] = sum(c.final_score for c in comps) / len(comps)
                    else:
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
                        report["reference_text_conflict"] = comp.text_conflict
                        report["reference_image_conflict"] = comp.image_conflict
                        report["reference_accessory_mismatch"] = comp.accessory_mismatch
                        report["reference_is_colored"] = comp.reference_is_colored
                        report["reference_style_distance"] = comp.style_distance
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
                status.write("❌ Visual Analyst output incomplete for M4.")
                st.error(
                    "Image analysis failed. Please re-upload or check your connection "
                    "to ensure anatomy-lock is active."
                )
                st.caption(f"Missing required fields: {', '.join(missing)}")
                st.stop()

            if selected_model:
                model_info = SD_MODELS.get(selected_model, {})
                model_name_display = model_info.get("name", selected_model)
                status.write(f"🎨 Using model: {model_name_display} (M4 default)")
            status.write("🎯 Step 1.5: AD-Agent computing M4 parameters...")
            m4_plan = create_parameter_plan_m4(
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
            if m4_plan:
                # Allow director to drive prompt guardrails / reference handling.
                if m4_plan.get("prompt_modifiers"):
                    report["prompt_modifiers"] = m4_plan["prompt_modifiers"]
                if m4_plan.get("reference_mode"):
                    report["reference_mode"] = m4_plan["reference_mode"]
                if m4_plan.get("reference_mode_ks2"):
                    report["reference_mode_ks2"] = m4_plan["reference_mode_ks2"]
                if m4_plan.get("_influence_scalar") is not None:
                    report["_influence_scalar"] = m4_plan["_influence_scalar"]
                try:
                    report["ip_weight"] = float(m4_plan["ip_adapter"]["weight"])
                    report["ip_end_at"] = float(m4_plan["ip_adapter"]["end_at"])
                except Exception:
                    pass
                if m4_plan.get("ip_adapter_dual"):
                    report["ip_adapter_dual"] = m4_plan["ip_adapter_dual"]
                status.write(
                    "🧭 Director: "
                    f"CN Union end={m4_plan['controlnet_union']['end_percent']}, "
                    f"OpenPose end={m4_plan['controlnet_openpose']['end_percent']}, "
                    f"IP end_at={m4_plan['ip_adapter']['end_at']}"
                )
                if m4_plan.get("model_name"):
                    selected_model = m4_plan["model_name"]
                    st.session_state["m4_model_auto"] = selected_model
                    status.write(f"🧭 Director: model auto-switch → {selected_model}")

            # Step 2: Prompt Engineer
            status.write("✍️ Step 2: Creating instructions for image generation...")
            pos_prompt, neg_prompt, pos_prompt_stage2, neg_prompt_stage2, rationale = run_prompt_engineer_m4(
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
            status.write("🎨 Step 3: Generating your new image (dynamic timeout based on sequence size)...")
            if sequence_frames and len(sequence_frames) > int(seq_batch_size):
                total = len(sequence_frames)
                batch_size = int(seq_batch_size)
                status.write(
                    f"🧩 Sequence batching enabled: {total} frames in "
                    f"{(total + batch_size - 1) // batch_size} batches (size={batch_size})."
                )
                batch_results = []
                all_media = []
                for start in range(0, total, batch_size):
                    end = min(start + batch_size, total)
                    batch = sequence_frames[start:end]
                    status.write(f"🚚 Running batch {start + 1}-{end} / {total}...")
                    batch_result = call_comfyui(
                        batch[0][1],
                        prompts,
                        model_name=selected_model,
                        status_writer=status,
                        workflow_path=selected_workflow_path,
                        reference_image_bytes=reference_bytes,
                        m4_plan=m4_plan,
                        sequence_frames=batch,
                        debug_mode=debug_mode,
                    )
                    if not batch_result:
                        generated_image = None
                        break
                    if isinstance(batch_result, dict):
                        all_media.extend(batch_result.get("media") or [])
                    batch_results.append(batch_result)
                else:
                    generated_image = batch_results[-1] if batch_results else None
                    if isinstance(generated_image, dict):
                        generated_image["media"] = all_media
                if 'generated_image' not in locals():
                    generated_image = None
            else:
                generated_image = call_comfyui(
                    image_bytes,
                    prompts,
                    model_name=selected_model,
                    status_writer=status,
                    workflow_path=selected_workflow_path,
                    reference_image_bytes=reference_bytes,
                    m4_plan=m4_plan,
                    sequence_frames=sequence_frames or None,
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

        if debug_mode:
            with st.expander("🧩 Workflow + Controller Info"):
                st.markdown("**Workflow Source**")
                st.code(
                    f"mode: {'server' if use_server_workflow else 'local'}\n"
                    f"path: {selected_workflow_path or workflow_spec.api_path}\n"
                    f"requires_reference: {workflow_spec.requires_reference}"
                )
                st.markdown("**ComfyUI Node Map (M4 API Workflow)**")
                st.json(
                    {
                        "stage1_prompts": {"positive": 2, "negative": 3},
                        "stage2_prompts": {"positive": 77, "negative": 76},
                        "ksampler1": 5,
                        "ksampler2": 55,
                        "controlnet_union": 103,
                        "openpose_controlnet": 104,
                        "ip_adapter_ks1": 66,
                        "ip_adapter_ks2": 105,
                        "input_image": 96,
                        "reference_image": 72,
                        "output_nodes_preferred": [41, 73, 100, 99],
                    }
                )
                ref_metrics = {
                    "reference_structural_score": report.get("reference_structural_score"),
                    "reference_proportion_score": report.get("reference_proportion_score"),
                    "reference_feature_match_score": report.get("reference_feature_match_score"),
                    "reference_conflict_penalty": report.get("reference_conflict_penalty"),
                    "reference_text_conflict": report.get("reference_text_conflict"),
                    "reference_image_conflict": report.get("reference_image_conflict"),
                    "reference_accessory_mismatch": report.get("reference_accessory_mismatch"),
                    "reference_is_colored": report.get("reference_is_colored"),
                    "reference_style_distance": report.get("reference_style_distance"),
                    "reference_final_score": report.get("reference_final_score"),
                }
                if any(v is not None for v in ref_metrics.values()):
                    st.markdown("**Input vs Reference Analysis**")
                    st.json(ref_metrics)

        if m4_plan:
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

            with st.expander("🧭 AI Strategy (M4 Parameter Plan)"):
                st.markdown("**Sampler 1: Structural Setup**")
                st.code(
                    f"steps: {m4_plan['ksampler1']['steps']}, "
                    f"cfg: {m4_plan['ksampler1']['cfg']}, "
                    f"denoise: {m4_plan['ksampler1']['denoise']}"
                )
                st.markdown("**Sampler 2: Ink Refinement**")
                st.code(
                    f"steps: {m4_plan['ksampler2']['steps']}, "
                    f"cfg: {m4_plan['ksampler2']['cfg']}, "
                    f"denoise: {m4_plan['ksampler2']['denoise']}"
                )
                st.markdown("**Motion-Lock Engine**")
                st.code(
                    f"Union strength: {m4_plan['controlnet_union']['strength']}, "
                    f"Union end: {m4_plan['controlnet_union']['end_percent']}"
                )
                st.code(
                    f"OpenPose strength: {m4_plan['controlnet_openpose']['strength']}, "
                    f"OpenPose end: {m4_plan['controlnet_openpose']['end_percent']}"
                )
                st.markdown("**Style Injection (IP-Adapter)**")
                st.code(
                    f"weight: {m4_plan['ip_adapter']['weight']}, "
                    f"end_at: {m4_plan['ip_adapter']['end_at']}"
                )
                ip_dual = m4_plan.get("ip_adapter_dual") or {}
                if ip_dual:
                    ks1_ip = ip_dual.get("ksampler1", {})
                    ks2_ip = ip_dual.get("ksampler2", {})
                    st.markdown("**Style Injection (Dual IP-Adapter)**")
                    st.code(
                        f"KS1 IP: weight={ks1_ip.get('weight')}, end_at={ks1_ip.get('end_at')}\n"
                        f"KS2 IP: weight={ks2_ip.get('weight')}, end_at={ks2_ip.get('end_at')}"
                    )
                if m4_plan.get("model_name"):
                    st.markdown("**Model Auto-Switch**")
                    st.code(f"model: {m4_plan['model_name']}")
                st.markdown("**Control Diagnostics (Runtime)**")
                diag = m4_plan.get("diagnostics") or {}
                if diag:
                    summary_diag = {
                        "case": diag.get("case"),
                        "object_scale": diag.get("object_scale"),
                        "reference_mode": m4_plan.get("reference_mode"),
                        "_influence_scalar": m4_plan.get("_influence_scalar"),
                        "S_structure_confidence": diag.get("S_structure_confidence"),
                        "R_reference_reliability": diag.get("R_reference_reliability"),
                        "D_style_distance": diag.get("D_style_distance"),
                        "P_pose_risk": diag.get("P_pose_risk"),
                        "H_hallucination_risk": diag.get("H_hallucination_risk"),
                        "conflict_penalty": diag.get("conflict_penalty"),
                        "text_conflict": diag.get("text_conflict"),
                        "image_conflict": diag.get("image_conflict"),
                        "reference_accessory_mismatch": diag.get("reference_accessory_mismatch"),
                        "reference_is_colored": diag.get("reference_is_colored"),
                        "cfg1_effective_max": diag.get("cfg1_effective_max"),
                        "cfg2_effective_max": diag.get("cfg2_effective_max"),
                        "clamp_reasons": diag.get("clamp_reasons"),
                    }
                    st.json(summary_diag)
                else:
                    st.caption("No diagnostics available.")

                if debug_mode:
                    st.markdown("**Full Parameter Plan (Debug)**")
                    st.json(m4_plan)
        # Display generated images
        if generated_image:
            img_placeholder.empty()  # Clear placeholder
            debug_payload = None
            media_payload = []
            if isinstance(generated_image, dict):
                debug_payload = generated_image.get("debug")
                media_payload = generated_image.get("media") or []
                generated_image = generated_image.get("final")

            if isinstance(generated_image, tuple) and len(generated_image) == 2:
                # Two returned outputs from ComfyUI/post-process pipeline.
                output_1, output_2 = generated_image
                final_output = output_1

                if debug_mode:
                    st.markdown("### 🧪 Step-by-Step Debug View")
                    st.markdown("_Pipeline images from input to raw outputs to final cleaned outputs._")

                    st.markdown("**Step 1: Input Image**")
                    st.image(BytesIO(image_bytes), caption="Input frame used for preview/analysis", width='stretch')

                    if reference_uploaded:
                        st.markdown("**Step 2: Reference Image**")
                        st.image(reference_uploaded, caption="Reference image sent to IP-Adapter", width='stretch')

                    # Diagnostics are shown in "AI Strategy" and "Workflow + Controller Info".

                    if debug_payload:
                        raw_imgs = debug_payload.get("raw", [])
                        raw_nodes = debug_payload.get("raw_node_ids", [])
                        processed_imgs = debug_payload.get("processed", [])
                        node_role = {
                            "41": "KSampler 2 Decode Output (Node 41)",
                            "73": "KSampler 1 Decode Output (Node 73)",
                            "100": "Video Combine from KSampler 1 (Node 100)",
                            "99": "Video Combine from KSampler 2 (Node 99)",
                        }

                        if raw_imgs:
                            st.markdown("**Step 3: Raw ComfyUI Outputs (before post-process)**")
                            cols = st.columns(2)
                            for i, raw in enumerate(raw_imgs[:2]):
                                node_label = raw_nodes[i] if i < len(raw_nodes) else "?"
                                role_label = node_role.get(str(node_label), "Output")
                                with cols[i % 2]:
                                    st.image(
                                        raw,
                                        caption=f"{role_label} — Raw (Node {node_label})",
                                        width='stretch',
                                    )

                        if processed_imgs:
                            st.markdown("**Step 4: Post-Processed Outputs (grayscale + threshold + heal)**")
                            cols = st.columns(2)
                            for i, proc in enumerate(processed_imgs[:2]):
                                node_label = raw_nodes[i] if i < len(raw_nodes) else "?"
                                role_label = node_role.get(str(node_label), "Output")
                                with cols[i % 2]:
                                    st.image(
                                        proc,
                                        caption=f"{role_label} — Post-Processed",
                                        width='stretch',
                                    )

                    st.markdown("**Step 5: Final Display**")
                    st.image(final_output, caption="✅ Final primary output (M4 final path)", width='stretch')
                else:
                    st.markdown("### 🎨 Final Generated Image")
                    st.image(final_output, caption="✅ Final output (M4 production mode)", width='stretch')

                if media_payload:
                    with st.expander("🎞️ Sequence Media Outputs", expanded=True):
                        st.caption("Downloaded media generated by VHS video combine nodes.")
                        for i, media in enumerate(media_payload, start=1):
                            kind = str(media.get("kind") or "media")
                            filename = str(media.get("filename") or f"output_{i}")
                            data = media.get("bytes") or b""
                            if kind == "video":
                                st.video(data)
                            elif kind == "gif":
                                st.image(data, caption=filename)
                            st.download_button(
                                label=f"Download {filename}",
                                data=data,
                                file_name=filename,
                                mime="application/octet-stream",
                                key=f"m4_media_{i}_{filename}",
                            )
            else:
                # Fallback for single image (backward compatibility)
                img_placeholder.image(generated_image, caption="Your Generated Image")
        else:
            img_placeholder.info("💡 Your generated image will appear here after you click 'Start Generation'")

st.caption("Built with Streamlit + Google Gemini AI + ComfyUI. Set your API keys in the sidebar to get started.")
