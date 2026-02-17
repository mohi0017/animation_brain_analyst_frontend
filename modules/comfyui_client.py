"""
ComfyUI API Client - Submit M4 workflow and download generated images.
"""

from __future__ import annotations

import os
import json
import time
import uuid
from io import BytesIO
from typing import Optional, Tuple, Union

import requests
import streamlit as st
from PIL import Image, ImageFilter, ImageOps, ImageSequence

from .line_quality_analyzer import analyze_line_quality

def call_comfyui(
    image_bytes: bytes,
    prompts: dict,
    model_name: str = None,
    status_writer=None,
    workflow_path: Optional[str] = None,
    reference_image_bytes: Optional[bytes] = None,
    m4_plan: Optional[dict] = None,
    sequence_frames: Optional[list[tuple[str, bytes]]] = None,
    debug_mode: bool = False,
) -> Optional[Union[Tuple[bytes, bytes], dict]]:
    """
    Submit M4 workflow to ComfyUI API and retrieve generated images.
    """
    base_url = os.getenv("COMFYUI_API_URL", "").rstrip("/")
    if not base_url:
        if status_writer:
            status_writer.write("⚠️ COMFYUI_API_URL not set in environment")
        return None

    def log(msg):
        if status_writer:
            status_writer.write(msg)
        else:
            st.info(msg)

    log("🎯 M4: Using AD-Agent parameters for workflow node updates")

    try:
        expected_frames = max(1, len(sequence_frames) if sequence_frames else 1)
        # Step 1: Upload input image or sequence
        sequence_subfolder = None
        if sequence_frames:
            sequence_subfolder = f"m4_seq_{uuid.uuid4().hex[:10]}"
            log(f"📤 Uploading {len(sequence_frames)} sequence frames to ComfyUI...")
            for frame_name, frame_bytes in sequence_frames:
                up_resp = requests.post(
                    f"{base_url}/upload/image",
                    data={"subfolder": sequence_subfolder, "type": "input", "overwrite": "true"},
                    files={"image": (frame_name, frame_bytes, "image/png")},
                    timeout=30,
                )
                up_resp.raise_for_status()
            # Keep first frame as fallback when workflow uses LoadImage path.
            uploaded_filename = f"{sequence_subfolder}/{sequence_frames[0][0]}"
            log(f"✅ Sequence uploaded to input/{sequence_subfolder}")
        else:
            log("📤 Uploading image to ComfyUI...")
            upload_resp = requests.post(
                f"{base_url}/upload/image",
                files={"image": ("input.png", image_bytes, "image/png")},
                timeout=30,
            )
            upload_resp.raise_for_status()
            upload_data = upload_resp.json()
            uploaded_filename = upload_data.get("name")
            if not uploaded_filename:
                st.error("ComfyUI upload failed: no filename returned")
                return None
            log(f"✅ Image uploaded: {uploaded_filename}")

        # Step 2: Upload reference image
        if not reference_image_bytes:
            st.error("M4 workflow requires a reference image.")
            return None
        log("📤 Uploading reference image to ComfyUI...")
        ref_resp = requests.post(
            f"{base_url}/upload/image",
            files={"image": ("reference.png", reference_image_bytes, "image/png")},
            timeout=30,
        )
        ref_resp.raise_for_status()
        ref_data = ref_resp.json()
        reference_uploaded_filename = ref_data.get("name")
        if not reference_uploaded_filename:
            st.error("ComfyUI reference upload failed: no filename returned")
            return None
        log(f"✅ Reference image uploaded: {reference_uploaded_filename}")

        # Step 3: Load workflow template
        workflow = _load_workflow(base_url, log, workflow_path)
        if workflow is None:
            return None

        # Step 4: Update workflow with prompts and params
        workflow = _update_workflow(
            workflow,
            prompts,
            uploaded_filename,
            reference_uploaded_filename,
            model_name,
            m4_plan,
            sequence_subfolder,
            log,
        )
        log("✅ Workflow updated with prompts, image, and parameters")

        # Step 5: Submit workflow
        log("🚀 Submitting workflow to ComfyUI...")
        prompt_id = str(uuid.uuid4())
        submit_resp = requests.post(
            f"{base_url}/prompt",
            json={"prompt": workflow, "client_id": prompt_id},
            timeout=30,
        )
        submit_resp.raise_for_status()
        submit_data = submit_resp.json()
        actual_prompt_id = submit_data.get("prompt_id")
        if not actual_prompt_id:
            st.error("ComfyUI submission failed: no prompt_id returned")
            st.json(submit_data)
            return None
        log(f"✅ Workflow submitted (ID: {actual_prompt_id[:8]}...)")

        # Step 6: Poll and download images
        result = _poll_and_download(
            base_url,
            actual_prompt_id,
            log,
            debug_mode=debug_mode,
            expected_frames=expected_frames,
        )

        # Optional closed-loop feedback: analyze KS2 output and (at most once) re-run with adjusted KS2/IP2.
        max_retries = int(os.getenv("M4_FEEDBACK_MAX_RETRIES", "0") or "0")
        if max_retries > 0 and m4_plan and reference_image_bytes and result:
            try:
                if isinstance(result, dict):
                    ks2_bytes = result.get("final", (None, None))[0]
                else:
                    ks2_bytes = result[0]

                metrics = analyze_line_quality(ks2_bytes, reference_png=reference_image_bytes)
                log(
                    "📏 LineQuality: "
                    f"density={metrics.edge_density:.3f} noise={metrics.noise_ratio:.3f} "
                    f"th_var={metrics.thickness_variance:.4f} ref_sim="
                    f"{(metrics.reference_edge_similarity if metrics.reference_edge_similarity is not None else -1):.3f}"
                )

                # Targets (tunable via env). Defaults are conservative.
                tgt_noise = float(os.getenv("M4_TGT_NOISE_RATIO", "0.08"))
                tgt_density_hi = float(os.getenv("M4_TGT_EDGE_DENSITY_HI", "0.14"))
                tgt_density_lo = float(os.getenv("M4_TGT_EDGE_DENSITY_LO", "0.02"))

                needs_retry = (
                    metrics.noise_ratio > tgt_noise
                    or metrics.edge_density > tgt_density_hi
                    or metrics.edge_density < tgt_density_lo
                )

                if needs_retry and max_retries >= 1:
                    log("🔁 Feedback: quality out of range; re-running once with dampened KS2/IP2...")
                    # Dampeners: reduce KS2 cfg a bit, reduce IP2, and slightly reduce denoise to preserve structure.
                    m4_plan2 = json.loads(json.dumps(m4_plan))
                    ks2 = m4_plan2.get("ksampler2", {})
                    ks2["cfg"] = max(8.5, float(ks2.get("cfg", 8.5)) - 0.5)
                    ks2["denoise"] = max(0.2, float(ks2.get("denoise", 0.4)) - 0.05)
                    m4_plan2["ksampler2"] = ks2
                    ipd = (m4_plan2.get("ip_adapter_dual") or {})
                    if isinstance(ipd, dict):
                        ip2 = dict(ipd.get("ksampler2") or {})
                        ip2["weight"] = max(0.15, float(ip2.get("weight", 0.25)) - 0.05)
                        ip2["end_at"] = min(float(ip2.get("end_at", 0.5)), 0.5)
                        ipd["ksampler2"] = ip2
                        m4_plan2["ip_adapter_dual"] = ipd

                    # Rebuild workflow with updated params and resubmit (no re-upload needed).
                    wf2 = _load_workflow(base_url, log, workflow_path)
                    wf2 = _update_workflow(
                        wf2,
                        prompts,
                        uploaded_filename,
                        reference_uploaded_filename,
                        model_name,
                        m4_plan2,
                        sequence_subfolder,
                        log,
                    )
                    log("🚀 Submitting feedback-adjusted workflow to ComfyUI...")
                    prompt_id2 = str(uuid.uuid4())
                    submit_resp2 = requests.post(
                        f"{base_url}/prompt",
                        json={"prompt": wf2, "client_id": prompt_id2},
                        timeout=30,
                    )
                    submit_resp2.raise_for_status()
                    submit_data2 = submit_resp2.json()
                    actual_prompt_id2 = submit_data2.get("prompt_id")
                    if actual_prompt_id2:
                        log(f"✅ Feedback workflow submitted (ID: {actual_prompt_id2[:8]}...)")
                        return _poll_and_download(
                            base_url,
                            actual_prompt_id2,
                            log,
                            debug_mode=debug_mode,
                            expected_frames=expected_frames,
                        )
            except Exception as exc:
                log(f"⚠️ Feedback loop skipped: {exc}")

        return result

    except requests.exceptions.RequestException as exc:
        error_msg = f"ComfyUI API error: {exc}"
        st.error(error_msg)
        if status_writer:
            status_writer.write(f"❌ {error_msg}")
        return None
    except Exception as exc:
        error_msg = f"ComfyUI call failed: {exc}"
        st.error(error_msg)
        if status_writer:
            status_writer.write(f"❌ {error_msg}")
        import traceback
        st.code(traceback.format_exc())
        return None


def _load_workflow(base_url: str, log, workflow_path: Optional[str] = None) -> Optional[dict]:
    """Load workflow from server URL, server path, or local file."""
    log("📋 Loading workflow template...")
    workflow = None
    workflow_source = None

    if workflow_path:
        if os.path.exists(workflow_path):
            try:
                with open(workflow_path, "r") as f:
                    workflow = json.load(f)
                workflow_source = f"Local: {workflow_path}"
                log("✅ Loaded workflow from selected local file")
            except Exception as e:
                log(f"⚠️ Could not read local workflow file: {e}")
        else:
            log(f"⚠️ Selected workflow path not found: {workflow_path}")

    if workflow is None:
        workflow_url = os.getenv("COMFYUI_WORKFLOW_URL", "").strip()
        if workflow_url:
            log(f"🔍 Fetching workflow from URL: {workflow_url}")
            try:
                resp = requests.get(workflow_url, timeout=15)
                resp.raise_for_status()
                workflow = resp.json()
                workflow_source = f"Server URL: {workflow_url}"
                log("✅ Loaded workflow from server URL")
            except Exception as e:
                log(f"⚠️ Could not fetch from URL: {e}")

    if workflow is None:
        workflow_path_server = os.getenv("COMFYUI_WORKFLOW_PATH", "").strip()
        if workflow_path_server:
            log(f"🔍 Trying to fetch workflow from server path: {workflow_path_server}")
            endpoints_to_try = [
                f"{base_url}/view?filename={workflow_path_server}&type=workflow",
                f"{base_url}/workflows/{workflow_path_server}",
                f"{base_url}/api/workflow?filename={workflow_path_server}",
            ]
            for endpoint in endpoints_to_try:
                try:
                    resp = requests.get(endpoint, timeout=10)
                    if resp.status_code == 200 and "application/json" in resp.headers.get("content-type", ""):
                        workflow = resp.json()
                        workflow_source = f"Server Path: {workflow_path_server}"
                        log("✅ Loaded workflow from server path")
                        break
                except requests.exceptions.RequestException:
                    continue

    if workflow is None:
        st.error(
            "❌ ComfyUI workflow template not found.\n\n"
            "Set `COMFYUI_WORKFLOW_URL` or `COMFYUI_WORKFLOW_PATH`, "
            "or provide a local workflow file."
        )
        return None

    if workflow_source:
        log(f"✅ Using template: {workflow_source}")

    return workflow


def _update_workflow(
    workflow: dict,
    prompts: dict,
    uploaded_filename: str,
    reference_uploaded_filename: str,
    model_name: Optional[str],
    m4_plan: Optional[dict],
    sequence_subfolder: Optional[str],
    log,
) -> dict:
    """Update workflow with prompts, images, and parameters."""
    if "nodes" in workflow:
        return _update_m4_nodes_workflow(
            workflow,
            prompts,
            uploaded_filename,
            reference_uploaded_filename,
            model_name,
            sequence_subfolder,
            log,
        )
    return _update_m4_v10_workflow(
        workflow,
        prompts,
        uploaded_filename,
        reference_uploaded_filename,
        model_name,
        m4_plan,
        sequence_subfolder,
        log,
    )


def _update_m4_nodes_workflow(
    workflow: dict,
    prompts: dict,
    uploaded_filename: str,
    reference_uploaded_filename: str,
    model_name: Optional[str],
    sequence_subfolder: Optional[str],
    log,
) -> dict:
    """Update M4 workflow in nodes format with prompts and image filenames only."""
    log("📝 Updating M4 workflow (nodes format)...")

    stage1 = prompts.get("stage1", {})
    stage2 = prompts.get("stage2", {})
    pos1 = stage1.get("positive", "")
    neg1 = stage1.get("negative", "")
    pos2 = stage2.get("positive", "")
    neg2 = stage2.get("negative", "")

    nodes = workflow.get("nodes", [])
    node_map = {n.get("id"): n for n in nodes if isinstance(n, dict)}

    def _set_widget_text(node_id: int, text: str) -> None:
        node = node_map.get(node_id)
        if not node:
            return
        if node.get("type") != "CLIPTextEncode":
            return
        widgets = node.get("widgets_values") or []
        if widgets:
            widgets[0] = text
        else:
            node["widgets_values"] = [text]

    def _set_load_image(node_id: int, filename: str) -> None:
        node = node_map.get(node_id)
        if not node:
            return
        if node.get("type") != "LoadImage":
            return
        widgets = node.get("widgets_values") or []
        if widgets:
            widgets[0] = filename
        else:
            node["widgets_values"] = [filename, "image"]

    if model_name:
        node = node_map.get(1)
        if node and node.get("type") == "CheckpointLoaderSimple":
            widgets = node.get("widgets_values") or []
            if widgets:
                widgets[0] = model_name
            else:
                node["widgets_values"] = [model_name]
            log(f"🎨 Updated SD Model: {model_name}")

    # Always disable LoRAs for API runs unless explicitly supported by the app.
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("type") != "LoraLoader":
            continue
        widgets = node.get("widgets_values") or []
        # Common widget order in ComfyUI: [lora_name, strength_model, strength_clip, ...]
        if len(widgets) >= 3:
            widgets[1] = 0.0
            widgets[2] = 0.0
            node["widgets_values"] = widgets
        log("🧼 Disabled LoRA strengths (nodes format)")

    _set_widget_text(2, pos1)
    _set_widget_text(3, neg1)
    _set_widget_text(77, pos2)
    _set_widget_text(76, neg2)
    log("✅ Updated M4 prompts (nodes format)")

    _set_load_image(4, uploaded_filename)
    _set_load_image(96, uploaded_filename)
    _set_load_image(72, reference_uploaded_filename)
    # Best-effort for node-based M4 sequence templates using directory loaders.
    if sequence_subfolder:
        node96 = node_map.get(96)
        if node96 and node96.get("type") == "VHS_LoadImages":
            widgets = node96.get("widgets_values") or []
            if widgets:
                widgets[0] = sequence_subfolder
                node96["widgets_values"] = widgets
    log("✅ Updated image filenames (nodes format)")

    return workflow

def _update_m4_v10_workflow(
    workflow: dict,
    prompts: dict,
    uploaded_filename: str,
    reference_uploaded_filename: str,
    model_name: Optional[str],
    m4_plan: Optional[dict],
    sequence_subfolder: Optional[str],
    log,
) -> dict:
    """Update M4 API workflow with dual prompts, reference image, and M4 node mapping."""
    log("📝 Updating M4 workflow (API)...")
    required_nodes = ("2", "3", "5", "55", "72", "76", "77", "96", "103", "104", "105")
    missing_nodes = [nid for nid in required_nodes if nid not in workflow]
    if missing_nodes:
        raise ValueError(f"M4 workflow is missing required nodes: {', '.join(missing_nodes)}")

    stage1 = prompts.get("stage1", {})
    stage2 = prompts.get("stage2", {})
    pos1 = stage1.get("positive", "")
    neg1 = stage1.get("negative", "")
    pos2 = stage2.get("positive", "")
    neg2 = stage2.get("negative", "")

    if model_name and "1" in workflow and workflow["1"].get("class_type") == "CheckpointLoaderSimple":
        old_model = workflow["1"]["inputs"].get("ckpt_name", "N/A")
        workflow["1"]["inputs"]["ckpt_name"] = model_name
        log(f"🎨 Updated SD Model: {old_model} → {model_name}")

    # LoRA policy:
    # - Default: disabled (historical behavior, safe for production).
    # - Optional: enable via env `M4_ENABLE_LORA=true` and a director-provided `m4_plan['lora_strength']`.
    enable_lora = os.getenv("M4_ENABLE_LORA", "false").strip().lower() in ("1", "true", "yes", "on")
    plan_lora_strength = None
    if enable_lora and m4_plan:
        try:
            plan_lora_strength = float(m4_plan.get("lora_strength"))
        except Exception:
            plan_lora_strength = None
        if plan_lora_strength is not None:
            plan_lora_strength = max(0.0, min(1.0, plan_lora_strength))

    # Always disable LoRAs unless explicitly enabled.
    for node_id, node in workflow.items():
        if not (isinstance(node, dict) and node.get("class_type") == "LoraLoader"):
            continue
        inputs = node.get("inputs") or {}
        strength = plan_lora_strength if plan_lora_strength is not None else 0.0
        inputs["strength_model"] = strength
        inputs["strength_clip"] = strength
        node["inputs"] = inputs
        workflow[node_id] = node
        if strength == 0.0:
            log(f"🧼 Disabled LoRA strengths (Node {node_id})")
        else:
            log(f"🧩 Enabled LoRA strengths={strength:.2f} (Node {node_id})")

    # Stage 1 prompts
    if "2" in workflow and workflow["2"].get("class_type") == "CLIPTextEncode":
        workflow["2"]["inputs"]["text"] = pos1
        log("✅ Updated M4 Stage 1 positive prompt (Node 2)")
    if "3" in workflow and workflow["3"].get("class_type") == "CLIPTextEncode":
        workflow["3"]["inputs"]["text"] = neg1
        log("✅ Updated M4 Stage 1 negative prompt (Node 3)")

    # Stage 2 prompts
    if "77" in workflow and workflow["77"].get("class_type") == "CLIPTextEncode":
        workflow["77"]["inputs"]["text"] = pos2
        log("✅ Updated M4 Stage 2 positive prompt (Node 77)")
    if "76" in workflow and workflow["76"].get("class_type") == "CLIPTextEncode":
        workflow["76"]["inputs"]["text"] = neg2
        log("✅ Updated M4 Stage 2 negative prompt (Node 76)")

    # Main image: support single-frame and sequence mode via node 96.
    if "4" in workflow and workflow["4"].get("class_type") == "LoadImage":
        workflow["4"]["inputs"]["image"] = uploaded_filename
        log(f"✅ Updated main image filename: {uploaded_filename}")
    if "96" in workflow:
        node96 = workflow["96"]
        if node96.get("class_type") == "VHS_LoadImages":
            if sequence_subfolder:
                workflow["96"]["inputs"]["directory"] = sequence_subfolder
                workflow["96"]["inputs"]["image_load_cap"] = 0
                workflow["96"]["inputs"]["skip_first_images"] = 0
                workflow["96"]["inputs"]["select_every_nth"] = 1
                log(f"✅ Updated node 96 VHS_LoadImages directory: {sequence_subfolder}")
            else:
                # Single-frame mode: convert VHS loader to LoadImage for API uploads.
                workflow["96"] = {
                    "inputs": {"image": uploaded_filename},
                    "class_type": "LoadImage",
                    "_meta": {"title": "Load Image (API override for M4)"},
                }
                log("✅ Converted node 96 VHS_LoadImages → LoadImage for single-frame API mode")
        elif node96.get("class_type") == "LoadImage":
            workflow["96"]["inputs"]["image"] = uploaded_filename
            log(f"✅ Updated M4 main image filename (Node 96): {uploaded_filename}")

    _update_reference_image_nodes(workflow, reference_uploaded_filename, log)

    if not m4_plan:
        log("ℹ️ Skipping dynamic parameter updates; using workflow defaults")
        return workflow

    ks1 = m4_plan.get("ksampler1", {})
    ks2 = m4_plan.get("ksampler2", {})
    cn_union = m4_plan.get("controlnet_union", {})
    cn_openpose = m4_plan.get("controlnet_openpose", {})
    ip = m4_plan.get("ip_adapter", {})
    ip_dual = m4_plan.get("ip_adapter_dual") or {}

    if "5" in workflow and workflow["5"].get("class_type") == "KSampler":
        workflow["5"]["inputs"]["steps"] = ks1.get("steps", workflow["5"]["inputs"].get("steps"))
        workflow["5"]["inputs"]["cfg"] = ks1.get("cfg", workflow["5"]["inputs"].get("cfg"))
        workflow["5"]["inputs"]["denoise"] = ks1.get("denoise", workflow["5"]["inputs"].get("denoise"))
        log("✅ Updated KSampler1 params")

    if "55" in workflow and workflow["55"].get("class_type") == "KSampler":
        workflow["55"]["inputs"]["steps"] = ks2.get("steps", workflow["55"]["inputs"].get("steps"))
        workflow["55"]["inputs"]["cfg"] = ks2.get("cfg", workflow["55"]["inputs"].get("cfg"))
        workflow["55"]["inputs"]["denoise"] = ks2.get("denoise", workflow["55"]["inputs"].get("denoise"))
        log("✅ Updated KSampler2 params")

    if "103" in workflow and workflow["103"].get("class_type") in ("ACN_AdvancedControlNetApply_v2", "ControlNetApplyAdvanced"):
        workflow["103"]["inputs"]["strength"] = cn_union.get("strength", workflow["103"]["inputs"].get("strength"))
        workflow["103"]["inputs"]["end_percent"] = cn_union.get("end_percent", workflow["103"]["inputs"].get("end_percent"))
        log("✅ Updated M4 ControlNet Union params (Node 103)")

    if "104" in workflow and workflow["104"].get("class_type") in ("ACN_AdvancedControlNetApply_v2", "ControlNetApplyAdvanced"):
        workflow["104"]["inputs"]["strength"] = cn_openpose.get("strength", workflow["104"]["inputs"].get("strength"))
        workflow["104"]["inputs"]["end_percent"] = cn_openpose.get("end_percent", workflow["104"]["inputs"].get("end_percent"))
        log("✅ Updated M4 OpenPose params (Node 104)")

    # IP-Adapter (supports dual-IP workflows):
    # - Node 66 typically feeds KS1 model input.
    # - Node 105 feeds KS2 model input in M4.
    if "66" in workflow and workflow["66"].get("class_type") == "IPAdapterAdvanced":
        ip1 = (ip_dual.get("ksampler1") or {}) if isinstance(ip_dual, dict) else {}
        workflow["66"]["inputs"]["weight"] = ip1.get("weight", ip.get("weight", workflow["66"]["inputs"].get("weight")))
        workflow["66"]["inputs"]["end_at"] = ip1.get("end_at", ip.get("end_at", workflow["66"]["inputs"].get("end_at")))
        log("✅ Updated IP-Adapter params (KS1)")
    if "105" in workflow and workflow["105"].get("class_type") == "IPAdapterAdvanced":
        ip2 = (ip_dual.get("ksampler2") or {}) if isinstance(ip_dual, dict) else {}
        workflow["105"]["inputs"]["weight"] = ip2.get("weight", ip.get("weight", workflow["105"]["inputs"].get("weight")))
        workflow["105"]["inputs"]["end_at"] = ip2.get("end_at", ip.get("end_at", workflow["105"]["inputs"].get("end_at")))
        log("✅ Updated M4 IP-Adapter params (KS2)")

    return workflow


def _update_reference_image_nodes(workflow: dict, reference_uploaded_filename: str, log) -> None:
    """Update the reference image LoadImage node feeding IP-Adapter, even if IDs change."""
    updated = False
    ipadapter_nodes = [
        (node_id, node)
        for node_id, node in workflow.items()
        if isinstance(node, dict) and node.get("class_type") == "IPAdapterAdvanced"
    ]

    for _, ip_node in ipadapter_nodes:
        image_input = ip_node.get("inputs", {}).get("image")
        if not (isinstance(image_input, list) and len(image_input) >= 1):
            continue
        image_node_id = str(image_input[0])
        image_node = workflow.get(image_node_id)
        if not isinstance(image_node, dict):
            continue

        if image_node.get("class_type") == "LoadImage":
            image_node["inputs"]["image"] = reference_uploaded_filename
            updated = True
            continue

        if image_node.get("class_type") == "PrepImageForClipVision":
            upstream = image_node.get("inputs", {}).get("image")
            if isinstance(upstream, list) and len(upstream) >= 1:
                upstream_id = str(upstream[0])
                upstream_node = workflow.get(upstream_id)
                if isinstance(upstream_node, dict) and upstream_node.get("class_type") == "LoadImage":
                    upstream_node["inputs"]["image"] = reference_uploaded_filename
                    updated = True

    # Fallback for compat mapping
    if not updated and "72" in workflow and workflow["72"].get("class_type") == "LoadImage":
        workflow["72"]["inputs"]["image"] = reference_uploaded_filename
        updated = True

    if updated:
        log(f"✅ Updated reference image filename: {reference_uploaded_filename}")
    else:
        log("⚠️ Reference image node not found for IP-Adapter")


def _poll_and_download(
    base_url: str,
    prompt_id: str,
    log,
    debug_mode: bool = False,
    expected_frames: int = 1,
) -> Optional[Union[Tuple[bytes, bytes], dict]]:
    """Poll ComfyUI for completion and download generated images."""
    per_frame_sec = int(os.getenv("M4_TIMEOUT_PER_FRAME_SEC", "120") or "120")
    base_buffer_sec = int(os.getenv("M4_TIMEOUT_BASE_BUFFER_SEC", "120") or "120")
    min_wait_sec = int(os.getenv("M4_TIMEOUT_MIN_SEC", "240") or "240")
    max_wait = max(min_wait_sec, expected_frames * per_frame_sec + base_buffer_sec)
    log(f"⏳ Waiting for generation (timeout up to {max_wait // 60}m {max_wait % 60}s)...")
    poll_interval = 2
    elapsed = 0

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        history_resp = requests.get(f"{base_url}/history/{prompt_id}", timeout=10)
        history_resp.raise_for_status()
        history = history_resp.json()

        if prompt_id in history:
            status = history[prompt_id]
            if status.get("status", {}).get("completed", False):
                log("✅ Generation complete! Downloading images...")
                return _download_images(base_url, status, log, debug_mode=debug_mode)
            elif status.get("status", {}).get("error"):
                error_msg = status.get("status", {}).get("error", "Unknown error")
                st.error(f"ComfyUI generation error: {error_msg}")
                return None

        if elapsed % 10 == 0:
            log(f"⏳ Still processing... ({elapsed}s/{max_wait}s)")

    st.error(f"ComfyUI generation timeout (exceeded {max_wait // 60}m {max_wait % 60}s)")
    return None


def _download_images(base_url: str, status: dict, log, debug_mode: bool = False) -> Optional[Union[Tuple[bytes, bytes], dict]]:
    """Download generated images from ComfyUI."""
    outputs = status.get("outputs", {})
    downloaded: list[bytes] = []
    raw_downloaded: list[bytes] = []
    raw_node_ids: list[str] = []
    media_outputs: list[dict] = []
    downloaded_nodes: set[str] = set()

    def _sort_key(k: str):
        try:
            return (0, int(k))
        except Exception:
            return (1, k)

    def _fetch_file_bytes(file_info: dict) -> bytes | None:
        filename = file_info.get("filename")
        subfolder = file_info.get("subfolder", "")
        file_type = file_info.get("type", "")
        if not filename:
            return None
        params = {"filename": filename}
        if subfolder:
            params["subfolder"] = subfolder
        if file_type:
            params["type"] = file_type
        img_resp = requests.get(f"{base_url}/view", params=params, timeout=30)
        img_resp.raise_for_status()
        return img_resp.content

    def _gif_first_frame_png(gif_bytes: bytes) -> bytes | None:
        try:
            with Image.open(BytesIO(gif_bytes)) as im:
                first = next(ImageSequence.Iterator(im)).convert("RGB")
                out = BytesIO()
                first.save(out, format="PNG")
                return out.getvalue()
        except Exception:
            return None

    def _download_from_node(node_id: str) -> None:
        out = outputs.get(node_id)
        if not isinstance(out, dict):
            return
        images = out.get("images")
        gifs = out.get("gifs")
        videos = out.get("videos")

        if isinstance(images, list):
            for img_info in images:
                if not isinstance(img_info, dict):
                    continue
                file_bytes = _fetch_file_bytes(img_info)
                if not file_bytes:
                    continue
                raw_downloaded.append(file_bytes)
                raw_node_ids.append(node_id)
                downloaded.append(file_bytes)
                downloaded_nodes.add(node_id)
                log(f"✅ Output image downloaded (Node {node_id})")
                if len(downloaded) >= 2:
                    return
        for media_key, items in (("gif", gifs), ("video", videos)):
            if len(downloaded) >= 2:
                return
            if not isinstance(items, list):
                continue
            for media_info in items:
                if not isinstance(media_info, dict):
                    continue
                media_bytes = _fetch_file_bytes(media_info)
                if not media_bytes:
                    continue
                media_outputs.append(
                    {
                        "node_id": node_id,
                        "kind": media_key,
                        "filename": media_info.get("filename", ""),
                        "bytes": media_bytes,
                    }
                )
                raw_downloaded.append(media_bytes)
                raw_node_ids.append(node_id)
                # Media bytes are not reliable inputs for the line-art image post-process path.
                # Keep media for playback/download only, and only use GIF first-frame preview when decodable.
                if media_key == "gif":
                    preview_bytes = _gif_first_frame_png(media_bytes)
                    if preview_bytes:
                        downloaded.append(preview_bytes)
                        downloaded_nodes.add(node_id)
                log(f"✅ Output {media_key} downloaded (Node {node_id})")
                if len(downloaded) >= 2:
                    return

    # Prefer decoded frame outputs first, then media combine fallbacks.
    for preferred_node in ("41", "73", "100", "99"):
        if preferred_node in outputs and len(downloaded) < 2:
            _download_from_node(preferred_node)

    # Fallback for other workflows/node IDs.
    for node_id in sorted(outputs.keys(), key=_sort_key):
        if len(downloaded) >= 2:
            break
        if node_id in downloaded_nodes:
            continue
        _download_from_node(node_id)

    if len(downloaded) >= 2:
        processed: list[bytes] = []
        for i, img in enumerate(downloaded[:2]):
            node_id = raw_node_ids[i] if i < len(raw_node_ids) else ""
            # Apply post-processing only to decoded image outputs.
            # Media-combine previews (99/100) are already encoded and can degrade further if post-processed.
            if node_id in ("41", "73", "141", "173"):
                processed.append(_postprocess_line_art_bytes(img, log))
            else:
                processed.append(img)
        log("✅ Two output images downloaded successfully!")
        if debug_mode:
            return {
                "final": (processed[0], processed[1]),
                "media": media_outputs,
                "debug": {
                    "raw": raw_downloaded[:2],
                    "raw_node_ids": raw_node_ids[:2],
                    "processed": processed,
                },
            }
        if media_outputs:
            return {"final": (processed[0], processed[1]), "media": media_outputs}
        return (processed[0], processed[1])
    if len(downloaded) == 1:
        single = _postprocess_line_art_bytes(downloaded[0], log)
        log("⚠️ Only one output image found, using it for both")
        if debug_mode:
            return {
                "final": (single, single),
                "media": media_outputs,
                "debug": {
                    "raw": raw_downloaded[:1],
                    "raw_node_ids": raw_node_ids[:1],
                    "processed": [single],
                },
            }
        if media_outputs:
            return {"final": (single, single), "media": media_outputs}
        return (single, single)

    st.error("No output images found in ComfyUI response")
    return None


def _postprocess_line_art_bytes(image_bytes: bytes, log) -> bytes:
    """
    Post-process generated image to suppress color fringes and connect fragmented line art.
    Pipeline (line-art cleanup):
      1) grayscale (remove color fringe)
      2) median + slight blur (reduce jagged micro-noise)
      3) soft binarization + morphological close (connect broken lines)
      4) optional thinning pass (prevent over-bold strokes)
      5) border cleanup (remove raw frame artifacts)
    """
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        gray = ImageOps.grayscale(img)

        # Tunables (safe defaults; can be overridden from env without code change).
        pp_thresh = int(os.getenv("M4_PP_THRESHOLD", "210") or "210")
        pp_white = int(os.getenv("M4_PP_WHITE_CLIP", "228") or "228")
        pp_close_size = max(3, int(os.getenv("M4_PP_CLOSE_SIZE", "3") or "3"))
        pp_thin_pass = max(0, int(os.getenv("M4_PP_THIN_PASS", "1") or "1"))

        # 1) Remove small edge noise and mild jaggedness.
        den = gray.filter(ImageFilter.MedianFilter(size=3))
        den = den.filter(ImageFilter.GaussianBlur(radius=0.35))

        # 2) Build an ink mask (dark lines only).
        #    Higher threshold captures faint broken segments that need healing.
        ink_mask = den.point(lambda p: 0 if p < pp_thresh else 255, mode="L")

        # 3) Morphological close using PIL filters: dilate then erode.
        #    This joins dotted segments and closes tiny gaps in strokes.
        closed = ink_mask.filter(ImageFilter.MaxFilter(size=pp_close_size))
        closed = closed.filter(ImageFilter.MinFilter(size=pp_close_size))

        # 4) Optional thinning so lines do not become overly bold after close.
        for _ in range(pp_thin_pass):
            closed = closed.filter(ImageFilter.MinFilter(size=3))

        # 5) Compose final monochrome line-art (pure black lines on clean white canvas).
        final_gray = closed.point(lambda p: 255 if p >= 128 else 0, mode="L")
        final_gray = final_gray.point(lambda p: 255 if p >= pp_white else p)

        # Remove border/frame artifacts often present in raw ComfyUI outputs.
        border = 6
        px = final_gray.load()
        w, h = final_gray.size
        for x in range(w):
            for y in range(min(border, h)):
                px[x, y] = 255
            for y in range(max(0, h - border), h):
                px[x, y] = 255
        for y in range(h):
            for x in range(min(border, w)):
                px[x, y] = 255
            for x in range(max(0, w - border), w):
                px[x, y] = 255

        final = final_gray.convert("RGB")

        out = BytesIO()
        final.save(out, format="PNG")
        log("🧼 Applied post-process line-art cleanup (smooth+close+thin)")
        return out.getvalue()
    except Exception as exc:
        log(f"⚠️ Post-process skipped: {exc}")
        return image_bytes
