"""
ComfyUI API Client - Submit workflows and download generated images.
"""

from __future__ import annotations
import os
import json
import time
import uuid
from typing import Optional, Tuple
import requests
import streamlit as st

from .config import PHASE_PARAMS


def call_comfyui(
    image_bytes: bytes, 
    pos_prompt: str, 
    neg_prompt: str, 
    dest_phase: str = "CleanUp",
    model_name: str = None,
    cfg_scale: float = None,
    lineart_end: float = None,
    canny_end: float = None,
    denoise: float = None,
    parameter_plan=None,  # NEW: Optional ParameterPlan object
    status_writer=None
) -> Optional[Tuple[bytes, bytes]]:
    """
    Submit workflow to ComfyUI API (RunPod) and retrieve generated image.
    Uses workflow template from ANIMATION_M1_api_version.json (preferred, API format) or ANIMATION_M1.json (v11 format).
    
    Args:
        image_bytes: Input image bytes
        pos_prompt: Positive prompt text
        neg_prompt: Negative prompt text
        dest_phase: Destination phase (for automatic parameter tuning)
        model_name: Stable Diffusion model filename (default: anything-v5-PrtRE.safetensors)
        cfg_scale: Override CFG scale (default: phase-specific) - DEPRECATED if parameter_plan provided
        lineart_end: Override Lineart ending percent (default: phase-specific) - DEPRECATED if parameter_plan provided
        canny_end: Override Canny ending percent (default: phase-specific) - DEPRECATED if parameter_plan provided
        denoise: Override Denoise (default: phase-specific) - DEPRECATED if parameter_plan provided
        parameter_plan: Optional ParameterPlan object (if provided, overrides individual params)
        status_writer: Streamlit status widget for logging
    
    Returns:
        Tuple of (transparent_image_bytes, original_image_bytes) or None if failed
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

    # NEW: Use ParameterPlan if provided, otherwise fall back to old logic
    if parameter_plan:
        # Use AD-Agent's computed parameters
        final_cfg = parameter_plan.cfg
        final_denoise = parameter_plan.denoise
        final_steps = parameter_plan.steps
        final_sampler = parameter_plan.sampler
        final_scheduler = parameter_plan.scheduler
        final_lineart_strength = parameter_plan.lineart_strength
        final_lineart_end = parameter_plan.lineart_end
        final_canny_strength = parameter_plan.canny_strength
        final_canny_end = parameter_plan.canny_end
        model_name = parameter_plan.model_name
        
        log(f"🎯 AD-Agent Plan: {parameter_plan.reasoning}")
        log(f"📊 CFG: {final_cfg} | Denoise: {final_denoise} | Steps: {final_steps}")
        log(f"🎨 Model: {model_name} | Lineart: {final_lineart_strength}@{final_lineart_end} | Canny: {final_canny_strength}@{final_canny_end}")
        if parameter_plan.warnings:
            for warning in parameter_plan.warnings:
                log(f"⚠️ {warning}")
    else:
        # OLD: Determine optimal parameters based on dest_phase if not explicitly provided
        from .config import DEFAULT_LINE_ART_MODEL
        phase_params = PHASE_PARAMS.get(dest_phase, PHASE_PARAMS["CleanUp"])
        final_cfg = cfg_scale if cfg_scale is not None else phase_params["cfg"]
        final_lineart_end = lineart_end if lineart_end is not None else phase_params["lineart_end"]
        final_canny_end = canny_end if canny_end is not None else phase_params["canny_end"]
        final_denoise = denoise if denoise is not None else phase_params.get("denoise", 1.0)
        final_steps = 30  # Default
        final_sampler = "euler"
        final_scheduler = "simple"
        final_lineart_strength = 1.0
        final_canny_strength = 0.8
        
        # Use default model if none specified
        if not model_name:
            model_name = DEFAULT_LINE_ART_MODEL
        
        log(f"🎯 Phase: {dest_phase} | CFG: {final_cfg} | Lineart End: {final_lineart_end} | Canny End: {final_canny_end} | Denoise: {final_denoise}")
    
    try:
        # Step 1: Upload image to ComfyUI
        log("📤 Uploading image to ComfyUI...")
        upload_resp = requests.post(
            f"{base_url}/upload/image",
            files={"image": ("input.png", image_bytes, "image/png")},
            timeout=30,
        )
        upload_resp.raise_for_status()
        upload_data = upload_resp.json()
        uploaded_filename = upload_data.get("name")  # e.g., "input_abc123.png"
        if not uploaded_filename:
            st.error("ComfyUI upload failed: no filename returned")
            return None
        log(f"✅ Image uploaded: {uploaded_filename}")

        # Step 2: Load workflow template
        workflow = _load_workflow(base_url, log)
        if workflow is None:
            return None

        # Step 3: Update workflow with prompts and image
        workflow = _update_workflow(
            workflow, pos_prompt, neg_prompt, uploaded_filename,
            final_cfg, final_lineart_end, final_canny_end, final_denoise, model_name,
            final_steps, final_sampler, final_scheduler,
            final_lineart_strength, final_canny_strength,
            log
        )
        
        log("✅ Workflow updated with prompts, image, and parameters")

        # Step 4: Submit workflow
        log("🚀 Submitting workflow to ComfyUI...")
        prompt_id = str(uuid.uuid4())
        try:
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
                st.json(submit_data)  # Debug output
                return None
            log(f"✅ Workflow submitted (ID: {actual_prompt_id[:8]}...)")
        except requests.exceptions.HTTPError as e:
            error_detail = "Unknown error"
            try:
                error_detail = submit_resp.json() if 'submit_resp' in locals() else str(e.response.text) if hasattr(e, 'response') else str(e)
            except:
                error_detail = str(e)
            st.error(f"ComfyUI API error (400 Bad Request): {error_detail}")
            st.json({"workflow_keys": list(workflow.keys())[:10]})  # Show first 10 node IDs
            return None

        # Step 5: Poll for completion (max 2 minutes)
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
        st.code(traceback.format_exc())  # Debug traceback
        return None


def _load_workflow(base_url: str, log) -> Optional[dict]:
    """Load workflow from server URL, server path, or local files."""
    log("📋 Loading workflow template...")
    workflow = None
    workflow_source = None
    
    # Option 1: Try to fetch from server URL if provided
    workflow_url = os.getenv("COMFYUI_WORKFLOW_URL", "").strip()
    if workflow_url:
        log(f"🔍 Fetching workflow from URL: {workflow_url}")
        try:
            resp = requests.get(workflow_url, timeout=15)
            resp.raise_for_status()
            workflow = resp.json()
            workflow_source = f"Server URL: {workflow_url}"
            log(f"✅ Loaded workflow from server URL")
        except Exception as e:
            log(f"⚠️ Could not fetch from URL: {e}")
            log("📁 Falling back to local files...")
    
    # Option 2: Try to fetch from server file path (if server allows file access)
    if workflow is None:
        workflow_path_server = os.getenv("COMFYUI_WORKFLOW_PATH", "").strip()
        if workflow_path_server:
            log(f"🔍 Trying to fetch workflow from server path: {workflow_path_server}")
            try:
                # Try common ComfyUI workflow endpoints
                endpoints_to_try = [
                    f"{base_url}/view?filename={workflow_path_server}&type=workflow",
                    f"{base_url}/workflows/{workflow_path_server}",
                    f"{base_url}/api/workflow?filename={workflow_path_server}",
                ]
                
                for endpoint in endpoints_to_try:
                    try:
                        resp = requests.get(endpoint, timeout=10)
                        if resp.status_code == 200:
                            content_type = resp.headers.get("content-type", "")
                            if "application/json" in content_type:
                                workflow = resp.json()
                                workflow_source = f"Server Path: {workflow_path_server}"
                                log(f"✅ Loaded workflow from server path")
                                break
                    except requests.exceptions.RequestException:
                        continue
            except Exception as e:
                log(f"⚠️ Could not fetch from server path: {e}")
    
    # Option 3: Load from local files
    if workflow is None:
        workflow_path = None
        # Priority: API version (v10 format) first, then v11 format
        for path in ["workflows/ANIMATION_M1_api_version.json", "workflows/ANIMATION_M1.json", 
                     "ANIMATION_M1_api_version.json", "ANIMATION_M1.json"]:
            if os.path.exists(path):
                workflow_path = path
                break
        
        if workflow_path:
            log(f"📁 Loading from local file: {workflow_path}")
            with open(workflow_path, "r") as f:
                workflow = json.load(f)
            workflow_source = f"Local: {workflow_path}"
        else:
            error_msg = (
                "❌ ComfyUI workflow template not found.\n\n"
                "**Options to fix:**\n"
                "1. **Use server workflow URL**: Set `COMFYUI_WORKFLOW_URL` in .env\n"
                "   Example: `COMFYUI_WORKFLOW_URL=https://your-server.com/workflow.json`\n\n"
                "2. **Use server workflow path**: Set `COMFYUI_WORKFLOW_PATH` in .env\n"
                "   Example: `COMFYUI_WORKFLOW_PATH=ANIMATION_M1.json`\n\n"
                "3. **Use local file**: Place `ANIMATION_M1_api_version.json` or `ANIMATION_M1.json` in workflows/ or project root"
            )
            st.error(error_msg)
            return None
    
    if workflow_source:
        log(f"✅ Using template: {workflow_source}")
    
    return workflow


def _update_workflow(
    workflow: dict, pos_prompt: str, neg_prompt: str, uploaded_filename: str,
    final_cfg: float, final_lineart_end: float, final_canny_end: float, final_denoise: float,
    model_name: str,
    final_steps: int, final_sampler: str, final_scheduler: str,
    final_lineart_strength: float, final_canny_strength: float,
    log
) -> dict:
    """Update workflow with prompts, image, and parameters."""
    is_v11_format = "nodes" in workflow
    
    if is_v11_format:
        # v11 format - update nodes directly by ID, then convert to v10
        workflow = _update_v11_workflow(
            workflow, pos_prompt, neg_prompt, uploaded_filename,
            final_cfg, final_lineart_end, final_canny_end, final_denoise, model_name,
            final_steps, final_sampler, final_scheduler,
            final_lineart_strength, final_canny_strength,
            log
        )
    else:
        # v10 format - update directly
        workflow = _update_v10_workflow(
            workflow, pos_prompt, neg_prompt, uploaded_filename,
            final_cfg, final_lineart_end, final_canny_end, final_denoise, model_name,
            final_steps, final_sampler, final_scheduler,
            final_lineart_strength, final_canny_strength,
            log
        )
    
    return workflow


def _update_v11_workflow(
    workflow: dict, pos_prompt: str, neg_prompt: str, uploaded_filename: str,
    final_cfg: float, final_lineart_end: float, final_canny_end: float, final_denoise: float,
    model_name: str,
    final_steps: int, final_sampler: str, final_scheduler: str,
    final_lineart_strength: float, final_canny_strength: float,
    log
) -> dict:
    """Update v11 format workflow and convert to v10 for API submission."""
    log("📝 Updating v11 format workflow...")
    node_2_found = False
    node_3_found = False
    node_4_found = False
    
    for node in workflow["nodes"]:
        node_id = node.get("id")
        node_type = node.get("type")
        
        # Node 1: Checkpoint model (CheckpointLoaderSimple)
        if node_id == 1 and node_type == "CheckpointLoaderSimple":
            if model_name and "widgets_values" in node and len(node["widgets_values"]) > 0:
                old_model = node["widgets_values"][0]
                node["widgets_values"][0] = model_name
                log(f"🎨 Updated SD Model: {old_model} → {model_name}")
        
        # Node 2: Positive prompt (CLIPTextEncode)
        elif node_id == 2 and node_type == "CLIPTextEncode":
            if "widgets_values" in node and len(node["widgets_values"]) > 0:
                old_pos = node["widgets_values"][0][:50] if isinstance(node["widgets_values"][0], str) else ""
                node["widgets_values"][0] = pos_prompt
                log(f"✅ Updated positive prompt (was: {old_pos}...)")
                node_2_found = True
        
        # Node 3: Negative prompt (CLIPTextEncode)
        elif node_id == 3 and node_type == "CLIPTextEncode":
            if "widgets_values" in node and len(node["widgets_values"]) > 0:
                old_neg = node["widgets_values"][0][:50] if isinstance(node["widgets_values"][0], str) else ""
                node["widgets_values"][0] = neg_prompt
                log(f"✅ Updated negative prompt (was: {old_neg}...)")
                node_3_found = True
        
        # Node 4: LoadImage
        elif node_id == 4 and node_type == "LoadImage":
            if "widgets_values" in node and len(node["widgets_values"]) > 0:
                node["widgets_values"][0] = uploaded_filename
                log(f"✅ Updated image filename: {uploaded_filename}")
                node_4_found = True
        
        # Node 5: KSampler - Update Steps, CFG, Sampler, Scheduler, Denoise
        elif node_id == 5 and node_type == "KSampler":
            if "widgets_values" in node and len(node["widgets_values"]) >= 7:
                # Widget indices: 0=seed, 1=control_after_generate, 2=steps, 3=cfg, 4=sampler_name, 5=scheduler, 6=denoise
                old_steps = node["widgets_values"][2]
                node["widgets_values"][2] = final_steps
                log(f"✅ Updated Steps: {old_steps} → {final_steps}")
                
                old_cfg = node["widgets_values"][3]
                node["widgets_values"][3] = final_cfg
                log(f"✅ Updated CFG: {old_cfg} → {final_cfg}")
                
                old_sampler = node["widgets_values"][4]
                node["widgets_values"][4] = final_sampler
                log(f"✅ Updated Sampler: {old_sampler} → {final_sampler}")
                
                old_scheduler = node["widgets_values"][5]
                node["widgets_values"][5] = final_scheduler
                log(f"✅ Updated Scheduler: {old_scheduler} → {final_scheduler}")
                
                old_denoise = node["widgets_values"][6]
                node["widgets_values"][6] = final_denoise
                log(f"✅ Updated Denoise: {old_denoise} → {final_denoise}")
        
        # Node 39: CR Multi-ControlNet Stack - Update Strengths and Ending Steps
        elif node_id == 39 and node_type == "CR Multi-ControlNet Stack":
            if "widgets_values" in node and len(node["widgets_values"]) >= 15:
                # Widget indices: 
                # 2 = lineart strength (controlnet_strength_1)
                # 4 = lineart end_percent_1
                # 7 = canny strength (controlnet_strength_2)
                # 9 = canny end_percent_2
                old_lineart_strength = node["widgets_values"][2]
                node["widgets_values"][2] = final_lineart_strength
                log(f"✅ Updated Lineart Strength: {old_lineart_strength} → {final_lineart_strength}")
                
                old_lineart_end = node["widgets_values"][4]
                node["widgets_values"][4] = final_lineart_end
                log(f"✅ Updated Lineart End: {old_lineart_end} → {final_lineart_end}")
                
                old_canny_strength = node["widgets_values"][7]
                node["widgets_values"][7] = final_canny_strength
                log(f"✅ Updated Canny Strength: {old_canny_strength} → {final_canny_strength}")
                
                old_canny_end = node["widgets_values"][9]
                node["widgets_values"][9] = final_canny_end
                log(f"✅ Updated Canny End: {old_canny_end} → {final_canny_end}")
    
    if not node_2_found:
        log("⚠️ Node 2 (positive prompt) not found in workflow")
    if not node_3_found:
        log("⚠️ Node 3 (negative prompt) not found in workflow")
    if not node_4_found:
        log("⚠️ Node 4 (LoadImage) not found in workflow")
    
    # Convert v11 to v10 format for API submission
    log("🔄 Converting v11 to v10 format for API submission...")
    return _convert_v11_to_v10(
        workflow, final_cfg, final_lineart_end, final_canny_end, final_denoise,
        final_steps, final_sampler, final_scheduler,
        final_lineart_strength, final_canny_strength,
        log
    )


def _convert_v11_to_v10(
    workflow: dict, final_cfg: float, final_lineart_end: float, final_canny_end: float, final_denoise: float,
    final_steps: int, final_sampler: str, final_scheduler: str,
    final_lineart_strength: float, final_canny_strength: float,
    log
) -> dict:
    """Convert v11 workflow format (nodes array) to v10 format (flat dict)."""
    v10_workflow = {}
    
    # Create a map of node_id -> node for quick lookup
    node_map = {str(node.get("id")): node for node in workflow["nodes"]}
    
    # Step 1: Create all nodes in v10 format
    for node in workflow["nodes"]:
        node_id = str(node.get("id"))
        node_type = node.get("type")
        v10_node = {
            "class_type": node_type,
            "inputs": {}
        }
        v10_workflow[node_id] = v10_node
    
    # Step 2: Process widgets_values to set static inputs
    for node in workflow["nodes"]:
        node_id = str(node.get("id"))
        node_type = node.get("type")
        v10_node = v10_workflow[node_id]
        
        if "widgets_values" in node:
            widgets = node["widgets_values"]
            
            # CLIPTextEncode: text is first widget
            if node_type == "CLIPTextEncode" and len(widgets) > 0:
                v10_node["inputs"]["text"] = widgets[0]
            
            # LoadImage: image filename is first widget
            elif node_type == "LoadImage" and len(widgets) > 0:
                v10_node["inputs"]["image"] = widgets[0]
            
            # CheckpointLoaderSimple: ckpt_name is first widget
            elif node_type == "CheckpointLoaderSimple" and len(widgets) > 0:
                v10_node["inputs"]["ckpt_name"] = widgets[0]
            
            # KSampler: multiple inputs
            elif node_type == "KSampler" and len(widgets) >= 7:
                ksampler_inputs = ["seed", "control_after_generate", "steps", "cfg", "sampler_name", "scheduler", "denoise"]
                for i, widget_val in enumerate(widgets[:7]):
                    if i < len(ksampler_inputs):
                        # Use updated values if this is Node 5
                        if node_id == "5":
                            if ksampler_inputs[i] == "steps":
                                v10_node["inputs"]["steps"] = final_steps
                            elif ksampler_inputs[i] == "cfg":
                                v10_node["inputs"]["cfg"] = final_cfg
                            elif ksampler_inputs[i] == "sampler_name":
                                v10_node["inputs"]["sampler_name"] = final_sampler
                            elif ksampler_inputs[i] == "scheduler":
                                v10_node["inputs"]["scheduler"] = final_scheduler
                            elif ksampler_inputs[i] == "denoise":
                                v10_node["inputs"]["denoise"] = final_denoise
                            else:
                                v10_node["inputs"][ksampler_inputs[i]] = widget_val
                        else:
                            v10_node["inputs"][ksampler_inputs[i]] = widget_val
            
            # LineArtPreprocessor: mode and resolution
            elif node_type == "LineArtPreprocessor" and len(widgets) >= 2:
                v10_node["inputs"]["mode"] = widgets[0]
                v10_node["inputs"]["resolution"] = widgets[1]
            
            # Canny: low_threshold and high_threshold
            elif node_type == "Canny" and len(widgets) >= 2:
                v10_node["inputs"]["low_threshold"] = widgets[0]
                v10_node["inputs"]["high_threshold"] = widgets[1]
            
            # RemBGSession+: model and device
            elif node_type == "RemBGSession+" and len(widgets) >= 2:
                v10_node["inputs"]["model"] = widgets[0]
                v10_node["inputs"]["device_mode"] = widgets[1]
            
            # SaveImage: filename_prefix
            elif node_type == "SaveImage" and len(widgets) > 0:
                v10_node["inputs"]["filename_prefix"] = widgets[0]
            
            # CR Multi-ControlNet Stack: complex widget handling
            elif node_type == "CR Multi-ControlNet Stack" and len(widgets) >= 15 and node_id == "39":
                v10_node["inputs"]["switch_1"] = widgets[0]
                v10_node["inputs"]["controlnet_1"] = widgets[1]
                v10_node["inputs"]["controlnet_strength_1"] = final_lineart_strength  # Use updated value
                v10_node["inputs"]["start_percent_1"] = widgets[3]
                v10_node["inputs"]["end_percent_1"] = final_lineart_end  # Use updated value
                v10_node["inputs"]["switch_2"] = widgets[5]
                v10_node["inputs"]["controlnet_2"] = widgets[6]
                v10_node["inputs"]["controlnet_strength_2"] = final_canny_strength  # Use updated value
                v10_node["inputs"]["start_percent_2"] = widgets[8]
                v10_node["inputs"]["end_percent_2"] = final_canny_end  # Use updated value
                v10_node["inputs"]["switch_3"] = widgets[10]
                v10_node["inputs"]["controlnet_3"] = widgets[11]
                v10_node["inputs"]["controlnet_strength_3"] = widgets[12]
                v10_node["inputs"]["start_percent_3"] = widgets[13]
                v10_node["inputs"]["end_percent_3"] = widgets[14]
    
    # Step 3: Process links array to set up all connections
    if "links" in workflow:
        for link in workflow["links"]:
            if len(link) >= 6:
                link_id = link[0]
                source_id = str(link[1])
                source_output = link[2]
                target_id = str(link[3])
                target_input_index = link[4]
                
                # Ensure both nodes exist
                if source_id not in v10_workflow or target_id not in v10_workflow:
                    continue
                
                # Find the target node's input name from the original v11 structure
                target_node = node_map.get(target_id)
                if target_node and "inputs" in target_node:
                    # Find which input corresponds to this link
                    for inp in target_node["inputs"]:
                        if inp.get("link") == link_id:  # Match link ID
                            inp_name = inp.get("name")
                            if inp_name:
                                v10_workflow[target_id]["inputs"][inp_name] = [source_id, source_output]
                                break
                else:
                    # Fallback: common input names by node type and index
                    target_node_type = v10_workflow[target_id]["class_type"]
                    input_name_maps = {
                        "VAEEncode": {0: "pixels", 1: "vae"},
                        "VAEDecode": {0: "samples", 1: "vae"},
                        "KSampler": {0: "model", 1: "positive", 2: "negative", 3: "latent_image"},
                        "CLIPTextEncode": {0: "clip"},
                        "ImageRemoveBackground+": {0: "rembg_session", 1: "image"},
                        "SaveImage": {0: "images"},
                        "CR Apply Multi-ControlNet": {0: "base_positive", 1: "base_negative", 2: "controlnet_stack"},
                        "CR Multi-ControlNet Stack": {0: "image_1", 1: "image_2", 2: "image_3", 3: "controlnet_stack"},
                    }
                    if target_node_type in input_name_maps:
                        input_map = input_name_maps[target_node_type]
                        if target_input_index in input_map:
                            v10_workflow[target_id]["inputs"][input_map[target_input_index]] = [source_id, source_output]
    
    log(f"✅ Converted v11 to v10 format ({len(v10_workflow)} nodes)")
    return v10_workflow


def _update_v10_workflow(
    workflow: dict, pos_prompt: str, neg_prompt: str, uploaded_filename: str,
    final_cfg: float, final_lineart_end: float, final_canny_end: float, final_denoise: float,
    model_name: str,
    final_steps: int, final_sampler: str, final_scheduler: str,
    final_lineart_strength: float, final_canny_strength: float,
    log
) -> dict:
    """Update v10 format workflow directly."""
    log("📝 Updating v10 format workflow...")
    
    # Update checkpoint model (Node 1)
    if model_name and "1" in workflow and workflow["1"].get("class_type") == "CheckpointLoaderSimple":
        old_model = workflow["1"]["inputs"].get("ckpt_name", "N/A")
        workflow["1"]["inputs"]["ckpt_name"] = model_name
        log(f"🎨 Updated SD Model: {old_model} → {model_name}")
    
    if "2" in workflow and workflow["2"].get("class_type") == "CLIPTextEncode":
        old_pos = workflow["2"]["inputs"].get("text", "")[:50]
        workflow["2"]["inputs"]["text"] = pos_prompt
        log(f"✅ Updated positive prompt (was: {old_pos}...)")
    else:
        log("⚠️ Node 2 (positive prompt) not found in workflow")
    
    if "3" in workflow and workflow["3"].get("class_type") == "CLIPTextEncode":
        old_neg = workflow["3"]["inputs"].get("text", "")[:50]
        workflow["3"]["inputs"]["text"] = neg_prompt
        log(f"✅ Updated negative prompt (was: {old_neg}...)")
    else:
        log("⚠️ Node 3 (negative prompt) not found in workflow")
    
    if "4" in workflow and workflow["4"].get("class_type") == "LoadImage":
        workflow["4"]["inputs"]["image"] = uploaded_filename
        log(f"✅ Updated image filename: {uploaded_filename}")
    else:
        log("⚠️ Node 4 (LoadImage) not found in workflow")
    
    # Update KSampler Steps, CFG, Sampler, Scheduler & Denoise (Node 5)
    if "5" in workflow and workflow["5"].get("class_type") == "KSampler":
        old_steps = workflow["5"]["inputs"].get("steps", "N/A")
        workflow["5"]["inputs"]["steps"] = final_steps
        log(f"✅ Updated Steps: {old_steps} → {final_steps}")
        
        old_cfg = workflow["5"]["inputs"].get("cfg", "N/A")
        workflow["5"]["inputs"]["cfg"] = final_cfg
        log(f"✅ Updated CFG: {old_cfg} → {final_cfg}")
        
        old_sampler = workflow["5"]["inputs"].get("sampler_name", "N/A")
        workflow["5"]["inputs"]["sampler_name"] = final_sampler
        log(f"✅ Updated Sampler: {old_sampler} → {final_sampler}")
        
        old_scheduler = workflow["5"]["inputs"].get("scheduler", "N/A")
        workflow["5"]["inputs"]["scheduler"] = final_scheduler
        log(f"✅ Updated Scheduler: {old_scheduler} → {final_scheduler}")
        
        old_denoise = workflow["5"]["inputs"].get("denoise", "N/A")
        workflow["5"]["inputs"]["denoise"] = final_denoise
        log(f"✅ Updated Denoise: {old_denoise} → {final_denoise}")
    
    # Update ControlNet Strengths & Ending Steps (Node 39)
    if "39" in workflow and workflow["39"].get("class_type") == "CR Multi-ControlNet Stack":
        old_lineart_strength = workflow["39"]["inputs"].get("controlnet_strength_1", "N/A")
        workflow["39"]["inputs"]["controlnet_strength_1"] = final_lineart_strength
        log(f"✅ Updated Lineart Strength: {old_lineart_strength} → {final_lineart_strength}")
        
        old_lineart_end = workflow["39"]["inputs"].get("end_percent_1", "N/A")
        workflow["39"]["inputs"]["end_percent_1"] = final_lineart_end
        log(f"✅ Updated Lineart End: {old_lineart_end} → {final_lineart_end}")
        
        old_canny_strength = workflow["39"]["inputs"].get("controlnet_strength_2", "N/A")
        workflow["39"]["inputs"]["controlnet_strength_2"] = final_canny_strength
        log(f"✅ Updated Canny Strength: {old_canny_strength} → {final_canny_strength}")
        
        old_canny_end = workflow["39"]["inputs"].get("end_percent_2", "N/A")
        workflow["39"]["inputs"]["end_percent_2"] = final_canny_end
        log(f"✅ Updated Canny End: {old_canny_end} → {final_canny_end}")
    
    return workflow


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
        
        if elapsed % 10 == 0:  # Update every 10 seconds
            log(f"⏳ Still processing... ({elapsed}s/{max_wait}s)")

    st.error("ComfyUI generation timeout (exceeded 4 minutes)")
    return None


def _download_images(base_url: str, status: dict, log) -> Optional[Tuple[bytes, bytes]]:
    """Download generated images from ComfyUI."""
    outputs = status.get("outputs", {})
    transparent_image = None
    original_image = None
    
    # Node 42: ImageRemoveBackground+ output (transparent background)
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
    
    # Node 54: VAEDecode output (original with background)
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
    
    # Return both images (transparent first, original second)
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
        # Fallback: try to get any image
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for img_info in node_output["images"]:
                    filename = img_info.get("filename")
                    subfolder = img_info.get("subfolder", "")
                    if filename:
                        view_url = f"{base_url}/view"
                        params = {"filename": filename}
                        if subfolder:
                            params["subfolder"] = subfolder
                        img_resp = requests.get(view_url, params=params, timeout=30)
                        img_resp.raise_for_status()
                        log(f"✅ Image downloaded from node {node_id}")
                        return (img_resp.content, img_resp.content)
        st.error("No output images found in ComfyUI response")
        return None

