"""
Line Quality Analyzer (post-generation sensor).

This is a measurement module (closed-loop control signal), not a generator.
We keep it lightweight: PIL + numpy only (no OpenCV dependency).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter, ImageOps


@dataclass(frozen=True)
class LineQualityMetrics:
    edge_density: float          # ratio of edge pixels
    noise_ratio: float           # ratio of small disconnected components (proxy)
    thickness_variance: float    # proxy variance of edge "strength" around stroke
    reference_edge_similarity: float | None  # 0..1 cosine similarity on edge maps


def _edge_map(png_bytes: bytes, size: int = 256) -> np.ndarray:
    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    img = img.resize((size, size), Image.Resampling.BICUBIC)
    # Slight blur reduces sensitivity to chromatic fringing converted into gray noise.
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    edges = img.filter(ImageFilter.FIND_EDGES)
    arr = np.asarray(edges, dtype=np.float32) / 255.0
    return arr


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    av = a.reshape(-1)
    bv = b.reshape(-1)
    na = float(np.linalg.norm(av) + 1e-8)
    nb = float(np.linalg.norm(bv) + 1e-8)
    cos = float(np.dot(av, bv) / (na * nb))
    return max(0.0, min(1.0, cos))


def _connected_components(binary: np.ndarray) -> list[int]:
    """
    Simple connected components on a small grid (<=256x256).
    Returns a list of component sizes.
    """
    h, w = binary.shape
    visited = np.zeros((h, w), dtype=np.uint8)
    sizes: list[int] = []

    # 4-neighborhood
    for y in range(h):
        for x in range(w):
            if binary[y, x] == 0 or visited[y, x]:
                continue
            stack = [(y, x)]
            visited[y, x] = 1
            size = 0
            while stack:
                cy, cx = stack.pop()
                size += 1
                if cy > 0 and binary[cy - 1, cx] and not visited[cy - 1, cx]:
                    visited[cy - 1, cx] = 1
                    stack.append((cy - 1, cx))
                if cy + 1 < h and binary[cy + 1, cx] and not visited[cy + 1, cx]:
                    visited[cy + 1, cx] = 1
                    stack.append((cy + 1, cx))
                if cx > 0 and binary[cy, cx - 1] and not visited[cy, cx - 1]:
                    visited[cy, cx - 1] = 1
                    stack.append((cy, cx - 1))
                if cx + 1 < w and binary[cy, cx + 1] and not visited[cy, cx + 1]:
                    visited[cy, cx + 1] = 1
                    stack.append((cy, cx + 1))
            sizes.append(size)
    return sizes


def analyze_line_quality(
    output_png: bytes,
    *,
    reference_png: bytes | None = None,
    size: int = 256,
) -> LineQualityMetrics:
    """
    Compute metrics from a generated output (KS2 preferred).

    Notes:
    - edge_density too high => noisy/sketchy
    - noise_ratio too high  => dots / broken artifacts
    - thickness_variance high => inconsistent stroke (proxy)
    """
    edges = _edge_map(output_png, size=size)

    # Edge density: strong edges only.
    strong = (edges >= 0.25).astype(np.uint8)
    edge_density = float(strong.mean())

    # Noise ratio: count small components among all edge components.
    sizes = _connected_components(strong)
    if not sizes:
        noise_ratio = 0.0
    else:
        small = sum(1 for s in sizes if s <= 12)
        noise_ratio = float(small / max(1, len(sizes)))

    # Thickness variance proxy:
    # compute local contrast around edges by looking at a dilated edge response.
    # Higher variance tends to indicate fragmented/jittery lines.
    # We avoid true distance transforms to keep deps minimal.
    kernel = np.array([[0.0, 1.0, 0.0],
                       [1.0, 1.0, 1.0],
                       [0.0, 1.0, 0.0]], dtype=np.float32)
    # very small convolution via padding + sum of shifted arrays
    pad = np.pad(edges, 1, mode="edge")
    neigh = (
        pad[1:-1, 1:-1] +
        pad[0:-2, 1:-1] +
        pad[2:  , 1:-1] +
        pad[1:-1, 0:-2] +
        pad[1:-1, 2:  ]
    ) / 5.0
    # evaluate variance only where edges exist
    mask = edges >= 0.25
    if mask.any():
        thickness_variance = float(np.var(neigh[mask]))
    else:
        thickness_variance = 0.0

    ref_sim = None
    if reference_png:
        ref_edges = _edge_map(reference_png, size=size)
        ref_sim = float(_cosine_sim(edges, ref_edges))

    return LineQualityMetrics(
        edge_density=edge_density,
        noise_ratio=noise_ratio,
        thickness_variance=thickness_variance,
        reference_edge_similarity=ref_sim,
    )

