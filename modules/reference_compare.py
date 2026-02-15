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

import numpy as np
from PIL import Image, ImageFilter


@dataclass(frozen=True)
class ReferenceComparison:
    similarity: float  # 0..1 (higher = more similar)


def _to_edge_vector(png_bytes: bytes, size: int = 256) -> np.ndarray:
    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    img = img.resize((size, size), Image.Resampling.BICUBIC)
    # Edge map reduces sensitivity to background tint and focuses on strokes.
    img = img.filter(ImageFilter.FIND_EDGES)
    arr = np.asarray(img, dtype=np.float32).reshape(-1)
    # Normalize to [0,1]
    arr /= 255.0
    return arr


def edge_cosine_similarity(input_png: bytes, reference_png: bytes) -> ReferenceComparison:
    """
    Compare two images using cosine similarity of their edge maps.

    Returns a score in [0, 1] where 1 is most similar.
    """
    a = _to_edge_vector(input_png)
    b = _to_edge_vector(reference_png)
    na = float(np.linalg.norm(a) + 1e-8)
    nb = float(np.linalg.norm(b) + 1e-8)
    cos = float(np.dot(a, b) / (na * nb))
    # Cosine can be [-1,1]; in practice edges are non-negative so it's [0,1].
    sim = max(0.0, min(1.0, cos))
    return ReferenceComparison(similarity=sim)

