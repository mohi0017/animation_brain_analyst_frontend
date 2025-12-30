"""
ComfyUI API Client - Submit M2 workflow and download generated images.
"""

from __future__ import annotations

import os
import json
import time
import uuid
from typing import Optional, Tuple

import requests
import streamlit as st


def call_comfyui(
    image_bytes: bytes,
    prompts: dict,
    model_name: str = None,
    status_writer=None,
    workflow_path: Optional[str] = None,
    reference_image_bytes: Optional[bytes] = None,
    m2_plan: Optional[dict] = None,
) -> Optional[Tuple[bytes, bytes]]:
    """
    Submit M2 workflow to ComfyUI API and retrieve generated images.
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

    log("🎯 M2: Using AD-Agent parameters for workflow node updates")

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
            st.error("M2 workflow requires a reference image.")
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
            m2_plan,
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
        return _poll_and_download(base_url, actual_prompt_id, log)

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
    m2_plan: Optional[dict],
    log,
) -> dict:
    """Update M2 v10 workflow with prompts, images, and parameters."""
    if "nodes" in workflow:
        log("⚠️ M2 workflow requires API (v10) format. Please use ANIMATION_M2_Api.json.")
        return workflow
    return _update_m2_v10_workflow(
        workflow,
        prompts,
        uploaded_filename,
        reference_uploaded_filename,
        model_name,
        m2_plan,
        log,
    )


def _update_m2_v10_workflow(
    workflow: dict,
    prompts: dict,
    uploaded_filename: str,
    reference_uploaded_filename: str,
    model_name: Optional[str],
    m2_plan: Optional[dict],
    log,
) -> dict:
    """Update M2 API workflow (v10) with dual prompts and reference image."""
    log("📝 Updating M2 workflow (v10 API)...")

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

    # Stage 1 prompts
    if "2" in workflow and workflow["2"].get("class_type") == "CLIPTextEncode":
        workflow["2"]["inputs"]["text"] = pos1
        log("✅ Updated M2 Stage 1 positive prompt (Node 2)")
    if "3" in workflow and workflow["3"].get("class_type") == "CLIPTextEncode":
        workflow["3"]["inputs"]["text"] = neg1
        log("✅ Updated M2 Stage 1 negative prompt (Node 3)")

    # Stage 2 prompts
    if "77" in workflow and workflow["77"].get("class_type") == "CLIPTextEncode":
        workflow["77"]["inputs"]["text"] = pos2
        log("✅ Updated M2 Stage 2 positive prompt (Node 77)")
    if "76" in workflow and workflow["76"].get("class_type") == "CLIPTextEncode":
        workflow["76"]["inputs"]["text"] = neg2
        log("✅ Updated M2 Stage 2 negative prompt (Node 76)")

    # Main image
    if "4" in workflow and workflow["4"].get("class_type") == "LoadImage":
        workflow["4"]["inputs"]["image"] = uploaded_filename
        log(f"✅ Updated main image filename: {uploaded_filename}")

    _update_reference_image_nodes(workflow, reference_uploaded_filename, log)

    if m2_plan:
        ks1 = m2_plan.get("ksampler1", {})
        ks2 = m2_plan.get("ksampler2", {})
        cn_union = m2_plan.get("controlnet_union", {})
        cn_openpose = m2_plan.get("controlnet_openpose", {})
        ip = m2_plan.get("ip_adapter", {})

        if "5" in workflow and workflow["5"].get("class_type") == "KSampler":
            workflow["5"]["inputs"]["steps"] = ks1.get("steps", workflow["5"]["inputs"].get("steps"))
            workflow["5"]["inputs"]["cfg"] = ks1.get("cfg", workflow["5"]["inputs"].get("cfg"))
            workflow["5"]["inputs"]["denoise"] = ks1.get("denoise", workflow["5"]["inputs"].get("denoise"))
            log("✅ Updated M2 KSampler1 params")

        if "55" in workflow and workflow["55"].get("class_type") == "KSampler":
            workflow["55"]["inputs"]["steps"] = ks2.get("steps", workflow["55"]["inputs"].get("steps"))
            workflow["55"]["inputs"]["cfg"] = ks2.get("cfg", workflow["55"]["inputs"].get("cfg"))
            workflow["55"]["inputs"]["denoise"] = ks2.get("denoise", workflow["55"]["inputs"].get("denoise"))
            log("✅ Updated M2 KSampler2 params")

        if "62" in workflow and workflow["62"].get("class_type") == "ControlNetApplyAdvanced":
            workflow["62"]["inputs"]["strength"] = cn_union.get("strength", workflow["62"]["inputs"].get("strength"))
            workflow["62"]["inputs"]["end_percent"] = cn_union.get("end_percent", workflow["62"]["inputs"].get("end_percent"))
            log("✅ Updated M2 ControlNet Union params")

        if "79" in workflow and workflow["79"].get("class_type") == "ControlNetApplyAdvanced":
            workflow["79"]["inputs"]["strength"] = cn_openpose.get("strength", workflow["79"]["inputs"].get("strength"))
            workflow["79"]["inputs"]["end_percent"] = cn_openpose.get("end_percent", workflow["79"]["inputs"].get("end_percent"))
            log("✅ Updated M2 OpenPose params")

        if "66" in workflow and workflow["66"].get("class_type") == "IPAdapterAdvanced":
            workflow["66"]["inputs"]["weight"] = ip.get("weight", workflow["66"]["inputs"].get("weight"))
            workflow["66"]["inputs"]["end_at"] = ip.get("end_at", workflow["66"]["inputs"].get("end_at"))
            log("✅ Updated M2 IP-Adapter params")

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


def _poll_and_download(base_url: str, prompt_id: str, log) -> Optional[Tuple[bytes, bytes]]:
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
                return _download_images(base_url, status, log)
            elif status.get("status", {}).get("error"):
                error_msg = status.get("status", {}).get("error", "Unknown error")
                st.error(f"ComfyUI generation error: {error_msg}")
                return None

        if elapsed % 10 == 0:
            log(f"⏳ Still processing... ({elapsed}s/{max_wait}s)")

    st.error("ComfyUI generation timeout (exceeded 4 minutes)")
    return None


def _download_images(base_url: str, status: dict, log) -> Optional[Tuple[bytes, bytes]]:
    """Download generated images from ComfyUI."""
    outputs = status.get("outputs", {})
    transparent_image = None
    original_image = None

    if "42" in outputs and "images" in outputs["42"]:
        for img_info in outputs["42"]["images"]:
            filename = img_info.get("filename")
            subfolder = img_info.get("subfolder", "")
            if filename:
                view_url = f"{base_url}/view"
                params = {"filename": filename}
                if subfolder:
                    params["subfolder"] = subfolder
                img_resp = requests.get(view_url, params=params, timeout=30)
                img_resp.raise_for_status()
                transparent_image = img_resp.content
                log("✅ Transparent background image downloaded (Node 42)")
                break

    if "54" in outputs and "images" in outputs["54"]:
        for img_info in outputs["54"]["images"]:
            filename = img_info.get("filename")
            subfolder = img_info.get("subfolder", "")
            if filename:
                view_url = f"{base_url}/view"
                params = {"filename": filename}
                if subfolder:
                    params["subfolder"] = subfolder
                img_resp = requests.get(view_url, params=params, timeout=30)
                img_resp.raise_for_status()
                original_image = img_resp.content
                log("✅ Original image downloaded (Node 54)")
                break

    if transparent_image and original_image:
        log("✅ Both images downloaded successfully!")
        return (transparent_image, original_image)
    elif transparent_image:
        log("⚠️ Only transparent image found, using it for both")
        return (transparent_image, transparent_image)
    elif original_image:
        log("⚠️ Only original image found, using it for both")
        return (original_image, original_image)
    else:
        st.error("No output images found in ComfyUI response")
        return None
