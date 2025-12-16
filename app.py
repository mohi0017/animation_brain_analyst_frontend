"""
Streamlit frontend for the AI Animation Studio.
Controls the Roughs -> Tie Down / CleanUp / Colors pipeline by:
1) Taking user image + phase settings.
2) Calling Gemini (multimodal) for analysis.
3) Calling Gemini (text) for prompt engineering.
4) Sending prompts + image to ComfyUI (RunPod) for generation.

Environment:
- GOOGLE_GENAI_API_KEY: required for Gemini calls.
- COMFYUI_API_URL: base URL to your ComfyUI HTTP API (e.g., http://host:port).
- COMFYUI_AUTH_TOKEN: optional bearer token if your API is protected.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import requests
import streamlit as st
from PIL import Image
from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None
    genai_types = None

load_dotenv()


# ---------- Default Master Prompts ----------
DEFAULT_ANALYST_PROMPT = """You are a Multi-Modal Visual Analyst (“Brain”) for animation cleanup.

Phases (authoritative dictionary):
0) Skeleton: posing/proportion; stick figure joints; sometimes before/after Roughs.
1) Roughs: gestural scribbles capturing movement; can be volumetric; construction/building-block lines.
2) Tie Down: puts subject on-model (shapes/proportions); cleaner lines; non-essential elements removed; adds definition.
3) Cleanup: perfect, smooth, uniform line work on top of tie-down shapes.
4) Colors: fills between clean lines (some styles colorize the lines).

Inputs:
- Image (user rough/skeleton).
- SOURCE_PHASE (default Roughs).
- DEST_PHASE (default Tie Down/CleanUp/Colors).

Required analysis steps:
A) Recognition: identify characters/objects (hands, sunglasses, steering wheel, etc.).
B) Pose/Action analysis: find anatomical/pose issues (e.g., “left hand anatomically incorrect”).
C) Phase comparison (SOURCE -> DEST):
   - Moving EARLIER in the pipeline (e.g., Tie Down -> Roughs, Roughs -> Skeleton, Cleanup -> Roughs/Skeleton, Colors -> Roughs/Skeleton):
       * Simplify detail; REMOVE non-essential volume and cleanup-quality lines.
       * Preserve pose, timing, and overall composition.
       * Skeleton DEST: reduce to posing/proportion lines and stick-figure / simple construction.
       * Roughs DEST: keep gestural scribbles and movement, with some volumetric hints but not on-model shapes.
   - Moving FORWARD in the pipeline (e.g., Skeleton -> Roughs/Tie Down/Cleanup/Colors, Roughs -> Tie Down/Cleanup/Colors, Tie Down -> Cleanup/Colors, Cleanup -> Colors):
       * Increase clarity and fidelity appropriate to DEST_PHASE.
       * Skeleton/Roughs -> Tie Down: remove scribbles and clutter; fix shapes/proportions; make the subject on-model, but do not produce ink-perfect lineart.
       * Tie Down -> Cleanup: focus on line quality; keep shapes as-is; avoid changing pose/composition.
       * Any -> Colors: conceptually perform cleanup first (as if -> Tie Down/Cleanup) and THEN apply colours while preserving existing line/background colours.
   - Lateral moves at same “level” (e.g., Skeleton <-> Roughs, Tie Down <-> Cleanup when explicitly requested):
       * Adjust cleanliness and structural emphasis to match DEST_PHASE definitions, keeping the same character, pose, and timing.
D) Output a concise report: 3-4 critical FIXES and 3-4 REMOVES, plus NOTES if needed.
E) PRESERVE: list 2-3 items/gestures/styles that must be kept (e.g., “preserve right-hand gesture”, “keep sunglasses angle”).
F) Colour & background analysis: describe dominant line colour(s) and background (e.g., “blue line art on white background”) and whether they should be preserved.

Locks/levels:
- Pose lock: if true, keep pose/action; only fix anatomy.
- Style lock: if true, keep art style.
- Anatomical level (0-100): how strictly to correct anatomy.

Colour & background rules:
- Detect dominant line colour(s) and background colour.
- By default, PRESERVE the existing colour scheme (line colours + background) across phases, unless explicitly instructed otherwise.
- For phase upgrades, refine structure and cleanliness, not the colour scheme.
- For Roughs -> Colors, assume the same line/background colours in the final result unless notes clearly say otherwise.
- ALWAYS include at least one PRESERVE entry that explicitly states the colour scheme, e.g. “Preserve blue line art on a white background.”

Output JSON ONLY:
{
  "fixes": ["..."],
  "removes": ["..."],
  "preserve": ["..."],
  "notes": ["..."]
}
Keep it short, SD-friendly, and specific."""

DEFAULT_PROMPT_ENGINEER = """You are the Prompt Engineer (Strategist) for animation cleanup.

Input:
- report JSON: fixes[], removes[], notes[]
- dest_phase: Skeleton | Roughs | Tie Down | CleanUp | Colors
- Locks: pose_lock (keep pose), style_lock (keep art style)

Strategy:
- Positive Prompt: turn fixes into high-weight, specific SD-friendly terms targeted to dest_phase fidelity.
  * Skeleton: focus on posing and proportion; reduce volumes to simple construction and stick-figure lines; keep gesture and timing; DO NOT produce clean final shapes or perfect circles—embrace slightly rough structural lines.
  * Roughs: gestural movement capture with some volumetric cues; looser than Skeleton but not fully on-model shapes.
  * Tie Down: on-model shapes, defined forms, clean single lines (not ink-perfect), preserve intended gesture.
  * Cleanup: perfect smooth uniform linework on existing tie-down shapes.
  * Colors: accurate fills behind clean lines; keep line integrity; colour inside shapes while preserving existing line art.
- Negative Prompt: removes + anything that would overshoot the phase.
  * Skeleton: block fully on-model final shapes, detailed volumetric rendering, perfect lineart, inked outlines, shading, colours, gradients.
  * Tie Down: block rough sketch, messy/double/fuzzy lines, construction lines, dense scribbles, off-model anatomy, warped proportions, colored backgrounds if not wanted, “perfect crisp ink lines”, “ultra-clean lineart”.
  * Cleanup: block sketchiness, noise, color bleed; keep shapes unchanged.
- Respect locks: if pose_lock, do not change pose/action except minimal anatomical correction; if style_lock, preserve art style.
- Colour scheme:
  * Read from report.preserve/notes any mention of line colour and background colour.
  * You MUST add an explicit phrase like “preserve blue line art on a white background” in POSITIVE_PROMPT when a colour scheme is present.
  * Do NOT recolour line art or background unless the notes clearly request a style/colour change.
  * In NEGATIVE_PROMPT, block unwanted recolouring such as “black ink lines, dark background” if they would change the original scheme.
- Roughs -> Colors behaviour:
  * Treat this as a two-step process in one generation: first cleanup/define lines (as if doing Tie Down/Cleanup), then apply colours.
  * Encode this in the prompts: describe both the cleanup and the final coloured look, while preserving existing line/background colours.
- Rationale: briefly explain the intended edits so the diffusion model “knows what to fix” (e.g., “edit left hand to read as on-model animated character anatomy”).

Return EXACTLY:
POSITIVE_PROMPT: ...
NEGATIVE_PROMPT: ...
RATIONALE: ...
"""


# ---------- Data Models ----------
@dataclass
class AnalysisConfig:
    source_phase: str
    dest_phase: str
    pose_lock: bool
    style_lock: bool
    anatomical_level: int
    master_instruction: str


# ---------- Helpers ----------
def _load_image_bytes(file) -> Tuple[bytes, str]:
    image = Image.open(file).convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue(), "image/png"


def _get_genai_client() -> Optional["genai.Client"]:
    # Prefer official GEMINI_API_KEY; fallback to GOOGLE_GENAI_API_KEY for compatibility.
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
    if not api_key or genai is None:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def _thinking_config():
    """Optional thinking budget from env (in tokens)."""
    try:
        budget = os.getenv("GEMINI_THINK_BUDGET")
        if budget is None:
            return None
        budget_val = int(budget)
        return genai_types.ThinkingConfig(thinking_budget=budget_val)
    except Exception:
        return None


def _parse_report_blob(blob: str) -> dict:
    """Try to parse JSON from a string, stripping code fences."""
    if not blob:
        return {}
    text = blob.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].strip()
    if text.lower().startswith("json"):
        text = text[4:].strip()
    try:
        import json

        return json.loads(text)
    except Exception:
        return {}


def normalize_report(report: dict) -> dict:
    """If structured fields are missing, but notes contain JSON, extract them."""
    if not isinstance(report, dict):
        return {}
    fixes = report.get("fixes") or []
    removes = report.get("removes") or []
    preserve = report.get("preserve") or []
    raw_notes = report.get("notes") or []
    cleaned_notes = []

    if isinstance(raw_notes, list):
        for n in raw_notes:
            if isinstance(n, str):
                parsed = _parse_report_blob(n)
                if parsed:
                    fixes = fixes or parsed.get("fixes", fixes)
                    removes = removes or parsed.get("removes", removes)
                    preserve = preserve or parsed.get("preserve", preserve)
                    extra_notes = parsed.get("notes")
                    if extra_notes:
                        if isinstance(extra_notes, list):
                            cleaned_notes.extend(extra_notes)
                        elif isinstance(extra_notes, str):
                            cleaned_notes.append(extra_notes)
                    # do not keep the raw JSON blob in cleaned notes
                    continue
            cleaned_notes.append(n)

    return {
        "fixes": fixes,
        "removes": removes,
        "preserve": preserve,
        "notes": cleaned_notes,
    }


def run_visual_analyst(image_bytes: bytes, mime: str, cfg: AnalysisConfig) -> dict:
    client = _get_genai_client()
    prompt = cfg.master_instruction.strip() or DEFAULT_ANALYST_PROMPT
    if not client:
        # Fallback mock if no key
        return {
            "fixes": [
                "anatomically correct left hand on steering wheel",
                "clear volumetric forearm and wrist",
                "on-model torso proportions",
                "defined facial plane"
            ],
            "removes": [
                "rough sketch",
                "messy lines",
                "construction lines",
                "dense scribbles"
            ],
            "preserve": [
                "preserve overall steering gesture",
                "maintain sunglasses angle"
            ],
            "notes": ["Mock output (no GOOGLE_GENAI_API_KEY set)"],
        }

    # Build multimodal content
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=mime)
    # Inject run-time config so the model knows the transition and constraints.
    config_block = f"""
SOURCE_PHASE: {cfg.source_phase}
DEST_PHASE: {cfg.dest_phase}
POSE_LOCK: {cfg.pose_lock}
STYLE_LOCK: {cfg.style_lock}
ANATOMICAL_LEVEL: {cfg.anatomical_level}
"""
    full_prompt = f"{prompt}\n\n{config_block}"
    # Follow Gemini docs: contents can be a mix of Parts and plain text strings.
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[image_part, full_prompt],
            config=genai_types.GenerateContentConfig(
                temperature=0.2,
                thinking_config=_thinking_config(),
            ),
        )
        text = response.text or ""
        # Naive extraction; expect the model to return JSON
        try:
            import json

            return json.loads(text)
        except Exception:
            return {"fixes": [], "removes": [], "notes": [text.strip()]}
    except Exception as exc:
        # Graceful degradation on overload/404/etc.
        st.warning(f"Gemini analyst fallback (error: {exc})")
        return {
            "fixes": [
                "anatomically correct left hand on steering wheel",
                "clear volumetric forearm and wrist",
                "on-model torso proportions",
                "defined facial plane"
            ],
            "removes": [
                "rough sketch",
                "messy lines",
                "construction lines",
                "dense scribbles"
            ],
            "notes": [f"Fallback due to Gemini error: {exc}"],
        }


def run_prompt_engineer(report: dict, dest_phase: str, override: str) -> Tuple[str, str, str]:
    client = _get_genai_client()
    prompt = override.strip() or DEFAULT_PROMPT_ENGINEER
    if not client:
        pos = "anatomically correct left hand, on-model torso, clean single lines"
        neg = "rough sketch, messy lines, construction lines, perfect crisp ink lines"
        rationale = "Offline fallback rationale: focus on anatomy fixes; strip scribbles; avoid over-inking."
        return pos, neg, rationale

    merged_prompt = f"""{prompt}

dest_phase: {dest_phase}
report: {report}
"""
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[merged_prompt],
            config=genai_types.GenerateContentConfig(
                temperature=0.3,
                thinking_config=_thinking_config(),
            ),
        )
        text = response.text or ""
        # Simple split
        pos, neg, rationale = "", "", ""
        for line in text.splitlines():
            if line.lower().startswith("positive_prompt"):
                pos = line.split(":", 1)[-1].strip()
            if line.lower().startswith("negative_prompt"):
                neg = line.split(":", 1)[-1].strip()
            if line.lower().startswith("rationale"):
                rationale = line.split(":", 1)[-1].strip()
        return pos or text.strip(), neg, rationale
    except Exception as exc:
        st.warning(f"Gemini prompt-engineer fallback (error: {exc})")
        pos = "anatomically correct left hand, on-model torso, clean single lines"
        neg = "rough sketch, messy lines, construction lines, perfect crisp ink lines"
        rationale = "Fallback rationale: apply anatomy corrections; remove scribbles; avoid ink-perfect lines."
        return pos, neg, rationale


def call_comfyui(image_bytes: bytes, pos_prompt: str, neg_prompt: str) -> Optional[bytes]:
    """
    Placeholder ComfyUI call. Replace with your actual RunPod/ComfyUI HTTP call.
    Expected: return image bytes on success.
    """
    base_url = os.getenv("COMFYUI_API_URL")
    token = os.getenv("COMFYUI_AUTH_TOKEN")
    if not base_url:
        return None

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        resp = requests.post(
            f"{base_url}/generate",
            headers=headers,
            files={"image": ("input.png", image_bytes, "image/png")},
            data={
                "positive_prompt": pos_prompt,
                "negative_prompt": neg_prompt,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.content
    except Exception as exc:  # pragma: no cover - network path
        st.error(f"ComfyUI call failed: {exc}")
        return None


# ---------- Streamlit UI ----------
st.set_page_config(page_title="AI Animation Studio", page_icon="🎬", layout="wide")
st.title("AI Animation Studio Control Panel")

with st.sidebar:
    st.markdown("**Environment**")
    st.text_input("GOOGLE_GENAI_API_KEY", type="password", value=os.getenv("GOOGLE_GENAI_API_KEY", ""))
    st.text_input("COMFYUI_API_URL", value=os.getenv("COMFYUI_API_URL", ""))

# 1) Input & Upload
st.header("Input & Upload")
uploaded = st.file_uploader("Upload Rough Image", type=["png", "jpg", "jpeg"])
if uploaded:
    st.image(uploaded, caption="Preview")

col_src, col_dst = st.columns(2)
with col_src:
    source_phase = st.selectbox(
        "Source Phase",
        ["Skeleton", "Roughs", "Tie Down", "CleanUp", "Colors"],
        index=1,
    )
with col_dst:
    dest_phase = st.selectbox(
        "Destination Phase",
        ["Skeleton", "Roughs", "Tie Down", "CleanUp", "Colors"],
        index=2,
    )

# 2) Phase Configuration
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

# 3) Generation Control & Output
st.header("Generation")
generate = st.button("Generate Phase")
status_placeholder = st.empty()
img_placeholder = st.empty()

with st.expander("View Generated Prompts"):
    pos_box = st.empty()
    neg_box = st.empty()

if generate:
    if not uploaded:
        st.warning("Please upload an image first.")
    else:
        image_bytes, mime = _load_image_bytes(uploaded)
        cfg = AnalysisConfig(
            source_phase=source_phase,
            dest_phase=dest_phase,
            pose_lock=pose_lock,
            style_lock=style_lock,
            anatomical_level=anat_level,
            master_instruction=master_instruction,
        )

        with st.status("Processing...", expanded=True) as status:
            status.write("1) Running Visual Analyst (Gemini multimodal)...")
            raw_report = run_visual_analyst(image_bytes, mime, cfg)
            report = normalize_report(raw_report)

            status.write("2) Running Prompt Engineer (Gemini text)...")
            pos_prompt, neg_prompt, rationale = run_prompt_engineer(report, dest_phase, master_instruction)

            status.write("3) Calling ComfyUI / KSampler...")
            generated_image = call_comfyui(image_bytes, pos_prompt, neg_prompt)

            status.update(label="Done", state="complete")

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

        if generated_image:
            img_placeholder.image(generated_image, caption="Generated Output")
        else:
            img_placeholder.info("Image will appear here after backend wiring or when COMFYUI_API_URL is set.")

st.caption("Built with Streamlit + Gemini + ComfyUI. Configure API keys in the sidebar.")

