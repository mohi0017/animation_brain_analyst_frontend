#!/usr/bin/env python3
"""
Validate that the ComfyUI M4 workflow JSON matches runtime patch expectations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


EXPECTED = {
    "1": "CheckpointLoaderSimple",
    "2": "CLIPTextEncode",
    "3": "CLIPTextEncode",
    "5": "KSampler",
    "55": "KSampler",
    "66": "IPAdapterAdvanced",
    "72": "LoadImage",
    "76": "CLIPTextEncode",
    "77": "CLIPTextEncode",
    "96": "VHS_LoadImages",
    "103": "ACN_AdvancedControlNetApply_v2",
    "104": "ACN_AdvancedControlNetApply_v2",
    "105": "IPAdapterAdvanced",
}


def _fail(msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    wf_path = Path(argv[1]) if len(argv) > 1 else Path("workflows/Animation_Workflow_M4_Api.json")
    if not wf_path.exists():
        return _fail(f"Workflow not found: {wf_path}")

    try:
        data = json.loads(wf_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _fail(f"Failed to parse JSON: {wf_path} ({exc})")

    if not isinstance(data, dict):
        return _fail("Workflow JSON must be a dict (ComfyUI API format).")

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

    print(f"OK: M4 workflow looks compatible: {wf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
