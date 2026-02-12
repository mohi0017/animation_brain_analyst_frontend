#!/usr/bin/env python3
"""
Validate that the ComfyUI workflow JSON matches what the app patches at runtime.

This is a lightweight guardrail: if node IDs/types change in the workflow, the app
will fail at generation time. Run this after editing the workflow.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


EXPECTED = {
    # Core model/prompt nodes
    "1": "CheckpointLoaderSimple",
    "2": "CLIPTextEncode",
    "3": "CLIPTextEncode",
    "76": "CLIPTextEncode",
    "77": "CLIPTextEncode",
    # Image inputs
    "4": "LoadImage",
    # Sampling
    "5": "KSampler",
    "55": "KSampler",
    # Control
    "62": "ControlNetApplyAdvanced",
    "79": "ControlNetApplyAdvanced",
    # Style injection
    "66": "IPAdapterAdvanced",
}


def _fail(msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    wf_path = Path(argv[1]) if len(argv) > 1 else Path("workflows/Animation_Workflow_M3_Api.json")
    if not wf_path.exists():
        return _fail(f"Workflow not found: {wf_path}")

    try:
        data = json.loads(wf_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _fail(f"Failed to parse JSON: {wf_path} ({exc})")

    if not isinstance(data, dict):
        return _fail("Workflow JSON must be an object/dict (ComfyUI v10 API format).")

    missing = [nid for nid in EXPECTED if nid not in data]
    if missing:
        return _fail(f"Missing required node IDs: {', '.join(missing)}")

    mismatched: list[str] = []
    for nid, expected_type in EXPECTED.items():
        node = data.get(nid)
        if not isinstance(node, dict):
            mismatched.append(f"{nid}: not an object")
            continue
        actual = node.get("class_type")
        if actual != expected_type:
            mismatched.append(f"{nid}: expected {expected_type}, got {actual}")
    if mismatched:
        return _fail("Node type mismatches:\n- " + "\n- ".join(mismatched))

    # Check that IPAdapter has an image input we can trace back to a LoadImage node.
    ip = data.get("66", {})
    image_in = (ip.get("inputs") or {}).get("image")
    if not (isinstance(image_in, list) and image_in and str(image_in[0]).isdigit()):
        return _fail("Node 66 (IPAdapterAdvanced) must have inputs.image = [node_id, index].")

    # Walk one step up; common patterns are LoadImage directly or PrepImageForClipVision -> LoadImage.
    upstream_id = str(image_in[0])
    upstream = data.get(upstream_id, {})
    if not isinstance(upstream, dict):
        return _fail(f"Node 66 inputs.image points to missing node: {upstream_id}")

    upstream_type = upstream.get("class_type")
    if upstream_type == "LoadImage":
        pass
    elif upstream_type == "PrepImageForClipVision":
        up2 = (upstream.get("inputs") or {}).get("image")
        if not (isinstance(up2, list) and up2 and str(up2[0]).isdigit()):
            return _fail(f"Node {upstream_id} PrepImageForClipVision must have inputs.image = [node_id, index].")
        up2_id = str(up2[0])
        up2_node = data.get(up2_id, {})
        if not (isinstance(up2_node, dict) and up2_node.get("class_type") == "LoadImage"):
            return _fail(
                f"Node {upstream_id} upstream must be a LoadImage, got {up2_node.get('class_type')} ({up2_id})."
            )
    else:
        return _fail(
            f"Unexpected IPAdapter image upstream type: {upstream_type} (node {upstream_id}). "
            "Expected LoadImage or PrepImageForClipVision."
        )

    print(f"OK: workflow looks compatible: {wf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

