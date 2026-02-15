"""
ComfyUI API Client - Submit M3 workflow and download generated images.
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
from PIL import Image, ImageFilter, ImageOps


def call_comfyui(
    image_bytes: bytes,
    prompts: dict,
    model_name: str = None,
    status_writer=None,
    workflow_path: Optional[str] = None,
    reference_image_bytes: Optional[bytes] = None,
    m3_plan: Optional[dict] = None,
    debug_mode: bool = False,
) -> Optional[Union[Tuple[bytes, bytes], dict]]:
    """
    Submit M3 workflow to ComfyUI API and retrieve generated images.
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

    log("🎯 M3: Using AD-Agent parameters for workflow node updates")

    try:
        # Step 1: Upload input image
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
            st.error("M3 workflow requires a reference image.")
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
            m3_plan,
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
        return _poll_and_download(base_url, actual_prompt_id, log, debug_mode=debug_mode)

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
    m3_plan: Optional[dict],
    log,
) -> dict:
    """Update M3 v10 workflow with prompts, images, and parameters."""
    if "nodes" in workflow:
        return _update_m3_nodes_workflow(
            workflow,
            prompts,
            uploaded_filename,
            reference_uploaded_filename,
            model_name,
            log,
        )
    return _update_m3_v10_workflow(
        workflow,
        prompts,
        uploaded_filename,
        reference_uploaded_filename,
        model_name,
        m3_plan,
        log,
    )


def _update_m3_nodes_workflow(
    workflow: dict,
    prompts: dict,
    uploaded_filename: str,
    reference_uploaded_filename: str,
    model_name: Optional[str],
    log,
) -> dict:
    """Update M3 workflow in nodes format with prompts and image filenames only."""
    log("📝 Updating M3 workflow (nodes format)...")

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
    log("✅ Updated M3 prompts (nodes format)")

    _set_load_image(4, uploaded_filename)
    _set_load_image(72, reference_uploaded_filename)
    log("✅ Updated image filenames (nodes format)")

    return workflow

def _update_m3_v10_workflow(
    workflow: dict,
    prompts: dict,
    uploaded_filename: str,
    reference_uploaded_filename: str,
    model_name: Optional[str],
    m3_plan: Optional[dict],
    log,
) -> dict:
    """Update M3 API workflow (v10) with dual prompts and reference image."""
    log("📝 Updating M3 workflow (v10 API)...")

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

    # Always disable LoRAs for API runs unless explicitly supported by the app.
    for node_id, node in workflow.items():
        if not (isinstance(node, dict) and node.get("class_type") == "LoraLoader"):
            continue
        inputs = node.get("inputs") or {}
        inputs["strength_model"] = 0.0
        inputs["strength_clip"] = 0.0
        node["inputs"] = inputs
        workflow[node_id] = node
        log(f"🧼 Disabled LoRA strengths (Node {node_id})")

    # Stage 1 prompts
    if "2" in workflow and workflow["2"].get("class_type") == "CLIPTextEncode":
        workflow["2"]["inputs"]["text"] = pos1
        log("✅ Updated M3 Stage 1 positive prompt (Node 2)")
    if "3" in workflow and workflow["3"].get("class_type") == "CLIPTextEncode":
        workflow["3"]["inputs"]["text"] = neg1
        log("✅ Updated M3 Stage 1 negative prompt (Node 3)")

    # Stage 2 prompts
    if "77" in workflow and workflow["77"].get("class_type") == "CLIPTextEncode":
        workflow["77"]["inputs"]["text"] = pos2
        log("✅ Updated M3 Stage 2 positive prompt (Node 77)")
    if "76" in workflow and workflow["76"].get("class_type") == "CLIPTextEncode":
        workflow["76"]["inputs"]["text"] = neg2
        log("✅ Updated M3 Stage 2 negative prompt (Node 76)")

    # Main image
    if "4" in workflow and workflow["4"].get("class_type") == "LoadImage":
        workflow["4"]["inputs"]["image"] = uploaded_filename
        log(f"✅ Updated main image filename: {uploaded_filename}")

    _update_reference_image_nodes(workflow, reference_uploaded_filename, log)

    if not m3_plan:
        log("ℹ️ Skipping dynamic parameter updates; using workflow defaults")
        return workflow

    ks1 = m3_plan.get("ksampler1", {})
    ks2 = m3_plan.get("ksampler2", {})
    cn_union = m3_plan.get("controlnet_union", {})
    cn_openpose = m3_plan.get("controlnet_openpose", {})
    ip = m3_plan.get("ip_adapter", {})
    ip_dual = m3_plan.get("ip_adapter_dual") or {}

    if "5" in workflow and workflow["5"].get("class_type") == "KSampler":
        workflow["5"]["inputs"]["steps"] = ks1.get("steps", workflow["5"]["inputs"].get("steps"))
        workflow["5"]["inputs"]["cfg"] = ks1.get("cfg", workflow["5"]["inputs"].get("cfg"))
        workflow["5"]["inputs"]["denoise"] = ks1.get("denoise", workflow["5"]["inputs"].get("denoise"))
        log("✅ Updated M3 KSampler1 params")

    if "55" in workflow and workflow["55"].get("class_type") == "KSampler":
        workflow["55"]["inputs"]["steps"] = ks2.get("steps", workflow["55"]["inputs"].get("steps"))
        workflow["55"]["inputs"]["cfg"] = ks2.get("cfg", workflow["55"]["inputs"].get("cfg"))
        workflow["55"]["inputs"]["denoise"] = ks2.get("denoise", workflow["55"]["inputs"].get("denoise"))
        log("✅ Updated M3 KSampler2 params")

    if "62" in workflow and workflow["62"].get("class_type") == "ControlNetApplyAdvanced":
        workflow["62"]["inputs"]["strength"] = cn_union.get("strength", workflow["62"]["inputs"].get("strength"))
        workflow["62"]["inputs"]["end_percent"] = cn_union.get("end_percent", workflow["62"]["inputs"].get("end_percent"))
        log("✅ Updated M3 ControlNet Union params")

    if "79" in workflow and workflow["79"].get("class_type") == "ControlNetApplyAdvanced":
        workflow["79"]["inputs"]["strength"] = cn_openpose.get("strength", workflow["79"]["inputs"].get("strength"))
        workflow["79"]["inputs"]["end_percent"] = cn_openpose.get("end_percent", workflow["79"]["inputs"].get("end_percent"))
        log("✅ Updated M3 OpenPose params")

    # IP-Adapter (supports dual-IP workflows):
    # - Node 66 typically feeds KS1 model input.
    # - Node 90 (if present) typically feeds KS2 model input.
    if "66" in workflow and workflow["66"].get("class_type") == "IPAdapterAdvanced":
        ip1 = (ip_dual.get("ksampler1") or {}) if isinstance(ip_dual, dict) else {}
        workflow["66"]["inputs"]["weight"] = ip1.get("weight", ip.get("weight", workflow["66"]["inputs"].get("weight")))
        workflow["66"]["inputs"]["end_at"] = ip1.get("end_at", ip.get("end_at", workflow["66"]["inputs"].get("end_at")))
        log("✅ Updated M3 IP-Adapter params (KS1)")
    if "90" in workflow and workflow["90"].get("class_type") == "IPAdapterAdvanced":
        ip2 = (ip_dual.get("ksampler2") or {}) if isinstance(ip_dual, dict) else {}
        workflow["90"]["inputs"]["weight"] = ip2.get("weight", ip.get("weight", workflow["90"]["inputs"].get("weight")))
        workflow["90"]["inputs"]["end_at"] = ip2.get("end_at", ip.get("end_at", workflow["90"]["inputs"].get("end_at")))
        log("✅ Updated M3 IP-Adapter params (KS2)")

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

    # Fallback for legacy mapping
    if not updated and "72" in workflow and workflow["72"].get("class_type") == "LoadImage":
        workflow["72"]["inputs"]["image"] = reference_uploaded_filename
        updated = True

    if updated:
        log(f"✅ Updated reference image filename: {reference_uploaded_filename}")
    else:
        log("⚠️ Reference image node not found for IP-Adapter")


def _poll_and_download(base_url: str, prompt_id: str, log, debug_mode: bool = False) -> Optional[Union[Tuple[bytes, bytes], dict]]:
    """Poll ComfyUI for completion and download generated images."""
    log("⏳ Waiting for generation (this may take up to 4 minutes)...")
    max_wait = 240
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

    st.error("ComfyUI generation timeout (exceeded 4 minutes)")
    return None


def _download_images(base_url: str, status: dict, log, debug_mode: bool = False) -> Optional[Union[Tuple[bytes, bytes], dict]]:
    """Download generated images from ComfyUI."""
    outputs = status.get("outputs", {})
    downloaded: list[bytes] = []
    raw_downloaded: list[bytes] = []
    raw_node_ids: list[str] = []
    downloaded_nodes: set[str] = set()

    def _sort_key(k: str):
        try:
            return (0, int(k))
        except Exception:
            return (1, k)

    def _download_from_node(node_id: str) -> None:
        out = outputs.get(node_id)
        if not isinstance(out, dict):
            return
        images = out.get("images")
        if not isinstance(images, list):
            return

        for img_info in images:
            if not isinstance(img_info, dict):
                continue
            filename = img_info.get("filename")
            subfolder = img_info.get("subfolder", "")
            if not filename:
                continue

            view_url = f"{base_url}/view"
            params = {"filename": filename}
            if subfolder:
                params["subfolder"] = subfolder
            img_resp = requests.get(view_url, params=params, timeout=30)
            img_resp.raise_for_status()
            raw_downloaded.append(img_resp.content)
            raw_node_ids.append(node_id)
            downloaded.append(img_resp.content)
            downloaded_nodes.add(node_id)
            log(f"✅ Output image downloaded (Node {node_id})")
            if len(downloaded) >= 2:
                return

    # Prefer final outputs when present in this workflow.
    for preferred_node in ("54", "74"):
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
            # Apply post-processing only to KS2 output path (Node 54).
            if node_id == "54":
                processed.append(_postprocess_line_art_bytes(img, log))
            else:
                processed.append(img)
        log("✅ Two output images downloaded successfully!")
        if debug_mode:
            return {
                "final": (processed[0], processed[1]),
                "debug": {
                    "raw": raw_downloaded[:2],
                    "raw_node_ids": raw_node_ids[:2],
                    "processed": processed,
                },
            }
        return (processed[0], processed[1])
    if len(downloaded) == 1:
        single = _postprocess_line_art_bytes(downloaded[0], log)
        log("⚠️ Only one output image found, using it for both")
        if debug_mode:
            return {
                "final": (single, single),
                "debug": {
                    "raw": raw_downloaded[:1],
                    "raw_node_ids": raw_node_ids[:1],
                    "processed": [single],
                },
            }
        return (single, single)

    st.error("No output images found in ComfyUI response")
    return None


def _postprocess_line_art_bytes(image_bytes: bytes, log) -> bytes:
    """
    Post-process generated image to suppress color fringes and connect fragmented line art.
    Pipeline (soft cleanup, non-binary):
      1) grayscale (remove color fringe)
      2) mild contrast normalization
      3) light smoothing (preserve anti-aliased edges; avoid harsh/pixel look)
      4) border cleanup to remove frame artifacts from raw generations
    """
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        gray = ImageOps.grayscale(img)
        # Keep smoothing very light so lines stay clean but not over-sharp/pixelated.
        soft = gray.filter(ImageFilter.GaussianBlur(radius=0.30))

        # Force near-white paper tones to pure white to avoid textured/griddy canvas artifacts.
        soft = soft.point(lambda p: 255 if p >= 228 else p)

        # Remove border/frame artifacts often present in raw ComfyUI outputs.
        border = 6
        px = soft.load()
        w, h = soft.size
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

        final = soft.convert("RGB")

        out = BytesIO()
        final.save(out, format="PNG")
        log("🧼 Applied post-process line-art cleanup (grayscale+threshold+heal)")
        return out.getvalue()
    except Exception as exc:
        log(f"⚠️ Post-process skipped: {exc}")
        return image_bytes
