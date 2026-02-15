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

    conflict_penalty = max(accessory_mismatch, style_conflict)
    feature_match = 1.0 - conflict_penalty
    return feature_match, conflict_penalty


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
    feature_match, conflict_penalty = _feature_match_score(subject_details, reference_summary)

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
        style_distance=float(style_distance),
        final_score=float(final_score),
    )
