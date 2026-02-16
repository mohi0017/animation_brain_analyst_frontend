"""
Lightweight input-vs-reference comparison utilities.

We intentionally avoid heavyweight ML dependencies here. The goal is to get a
stable numeric signal (0..1) that roughly correlates with how similar the
reference is to the input in terms of linework/structure, so the director can
scale IP-Adapter and related parameters.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
import re

import numpy as np
from PIL import Image, ImageFilter


@dataclass(frozen=True)
class ReferenceComparison:
    # Individual signals (0..1; higher = better match)
    structural_score: float
    proportion_score: float
    feature_match_score: float
    # Conflict penalty (0..1; higher = more conflict)
    conflict_penalty: float
    # Conflict decomposition for diagnostics
    text_conflict: float
    image_conflict: float
    # Accessory mismatch score (0..1)
    accessory_mismatch: float
    # Whether the reference looks colored (vs mostly grayscale)
    reference_is_colored: bool
    # Style distance (0..1; higher = more different in stroke/contrast)
    style_distance: float
    # Fused final similarity score (0..1)
    final_score: float


def _to_edge_vector(png_bytes: bytes, size: int = 256) -> np.ndarray:
    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    img = img.resize((size, size), Image.Resampling.BICUBIC)
    # Edge map reduces sensitivity to background tint and focuses on strokes.
    img = img.filter(ImageFilter.FIND_EDGES)
    arr = np.asarray(img, dtype=np.float32).reshape(-1)
    # Normalize to [0,1]
    arr /= 255.0
    return arr


def _edge_cosine_similarity(input_png: bytes, reference_png: bytes) -> float:
    """Cosine similarity of edge maps, in [0,1]."""
    a = _to_edge_vector(input_png)
    b = _to_edge_vector(reference_png)
    na = float(np.linalg.norm(a) + 1e-8)
    nb = float(np.linalg.norm(b) + 1e-8)
    cos = float(np.dot(a, b) / (na * nb))
    # Cosine can be [-1,1]; in practice edges are non-negative so it's [0,1].
    return max(0.0, min(1.0, cos))


def _edge_bbox(png_bytes: bytes, size: int = 256, thresh: float = 0.20) -> tuple[int, int, int, int] | None:
    """
    Bounding box of edge pixels in a resized edge-map space.
    Returns (x0,y0,x1,y1) inclusive, or None if nothing detected.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("L").resize((size, size), Image.Resampling.BICUBIC)
    edges = img.filter(ImageFilter.FIND_EDGES)
    arr = np.asarray(edges, dtype=np.float32) / 255.0
    ys, xs = np.where(arr >= thresh)
    if xs.size == 0 or ys.size == 0:
        return None
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return (x0, y0, x1, y1)


def _proportion_similarity(input_png: bytes, reference_png: bytes) -> float:
    """
    Compare silhouette proportions using edge bbox aspect ratio and area ratio.
    Returns score in [0,1] (higher = more similar).
    """
    b1 = _edge_bbox(input_png)
    b2 = _edge_bbox(reference_png)
    if not b1 or not b2:
        return 0.5

    def _metrics(b):
        x0, y0, x1, y1 = b
        w = max(1, x1 - x0 + 1)
        h = max(1, y1 - y0 + 1)
        aspect = w / h
        area = w * h
        return aspect, area

    a1, ar1 = _metrics(b1)
    a2, ar2 = _metrics(b2)
    # normalized diffs
    aspect_diff = abs(a1 - a2) / max(a1, a2, 1e-6)
    area_diff = abs(ar1 - ar2) / max(ar1, ar2, 1e-6)
    # Convert to similarity
    sim = 1.0 - (0.6 * aspect_diff + 0.4 * area_diff)
    return max(0.0, min(1.0, float(sim)))


def _text_has(text: str, *needles: str) -> bool:
    t = (text or "").lower()
    return any(n.lower() in t for n in needles)


def _feature_match_score(subject_details: str, reference_summary: str) -> tuple[float, float]:
    """
    Automated-but-lightweight feature conflict detection using the analyst text fields.
    Returns (feature_match_score, conflict_penalty) in [0,1].
    """
    subj = (subject_details or "").lower()
    ref = (reference_summary or "").lower()

    # Accessory conflict: sunglasses present in input but reference suggests no sunglasses.
    sunglasses_in = _text_has(subj, "sunglasses", "glasses")
    sunglasses_ref_absent = bool(re.search(r"without\\s+(sun)?glasses|no\\s+(sun)?glasses", ref))
    accessory_mismatch = 1.0 if (sunglasses_in and sunglasses_ref_absent) else 0.0

    # Style conflict signal from summary.
    style_conflict = 1.0 if _text_has(ref, "conflict", "conflicting style") else 0.0

    text_conflict = max(accessory_mismatch, style_conflict)
    feature_match = 1.0 - text_conflict
    return feature_match, text_conflict


def _upper_face_dark_blob_ratio(png_bytes: bytes, size: int = 256) -> float:
    """
    Heuristic: detect sunglasses-like dark blob density in upper face region.
    Returns ratio of near-black pixels in the top 40% of the frame.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("L").resize((size, size), Image.Resampling.BICUBIC)
    h = size
    region = img.crop((0, 0, size, int(h * 0.40)))
    arr = np.asarray(region, dtype=np.uint8)
    # Near-black threshold (tolerant).
    return float((arr <= 50).mean())


def _is_colored_reference(png_bytes: bytes, size: int = 256) -> bool:
    """
    Heuristic: reference is 'colored' if saturation is meaningfully present.
    This protects against tint/fringing when using a color guide as an IP reference.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB").resize((size, size), Image.Resampling.BICUBIC)
    hsv = img.convert("HSV")
    s = np.asarray(hsv, dtype=np.uint8)[:, :, 1].astype(np.float32) / 255.0
    # If saturation mean is above a small threshold, treat as colored.
    return bool(float(s.mean()) >= 0.08)


def compare_input_reference(
    input_png: bytes,
    reference_png: bytes,
    *,
    subject_details: str = "",
    reference_summary: str = "",
) -> ReferenceComparison:
    """
    Multi-layer similarity analysis (lightweight, production-safe).

    - structural_score: edge cosine similarity
    - proportion_score: edge bbox aspect/area similarity
    - feature_match_score: keyword-derived feature match (sunglasses etc)
    - final_score: weighted fusion
    """
    structural = _edge_cosine_similarity(input_png, reference_png)
    proportion = _proportion_similarity(input_png, reference_png)
    feature_match, text_conflict = _feature_match_score(subject_details, reference_summary)

    # Image-level accessory mismatch: sunglasses-like dark blob in input but not in reference.
    blob_in = _upper_face_dark_blob_ratio(input_png)
    blob_ref = _upper_face_dark_blob_ratio(reference_png)
    # Thresholds tuned for black-filled sunglasses vs line-only glasses.
    if blob_in >= 0.006 and blob_ref < 0.003:
        accessory_mismatch = max(0.0, min(1.0, (blob_in - blob_ref) / 0.02))
    else:
        accessory_mismatch = 0.0
    image_conflict = 0.6 * accessory_mismatch

    reference_is_colored = _is_colored_reference(reference_png)
    if reference_is_colored:
        # Colored reference is more likely to introduce tint/halos; treat as mild image conflict.
        image_conflict = max(image_conflict, 0.2)

    conflict_penalty = max(0.0, min(1.0, max(text_conflict, image_conflict)))

    # Style distance: edge density + grayscale contrast delta (robust to tint).
    def _edge_density(png_bytes: bytes, size: int = 256) -> float:
        v = _to_edge_vector(png_bytes, size=size)
        # density of "strong-ish" edges
        return float((v >= 0.25).mean())

    def _gray_contrast(png_bytes: bytes, size: int = 256) -> float:
        img = Image.open(io.BytesIO(png_bytes)).convert("L").resize((size, size), Image.Resampling.BICUBIC)
        arr = (np.asarray(img, dtype=np.float32) / 255.0).reshape(-1)
        return float(arr.std())

    ed_in = _edge_density(input_png)
    ed_ref = _edge_density(reference_png)
    cd_in = _gray_contrast(input_png)
    cd_ref = _gray_contrast(reference_png)

    edge_delta = abs(ed_in - ed_ref) / max(ed_in, ed_ref, 1e-6)
    contrast_delta = abs(cd_in - cd_ref) / max(cd_in, cd_ref, 1e-6)
    style_distance = max(0.0, min(1.0, float(0.6 * edge_delta + 0.4 * contrast_delta)))

    # Weighted fusion (tunable)
    final_score = 0.5 * structural + 0.3 * proportion + 0.2 * feature_match
    final_score = max(0.0, min(1.0, float(final_score)))

    return ReferenceComparison(
        structural_score=float(structural),
        proportion_score=float(proportion),
        feature_match_score=float(feature_match),
        conflict_penalty=float(conflict_penalty),
        text_conflict=float(text_conflict),
        image_conflict=float(image_conflict),
        accessory_mismatch=float(accessory_mismatch),
        reference_is_colored=bool(reference_is_colored),
        style_distance=float(style_distance),
        final_score=float(final_score),
    )
