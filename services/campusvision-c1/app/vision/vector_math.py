from __future__ import annotations

import numpy as np


def cosine_similarity(a: list[float], b: list[float]) -> float:
    av = np.asarray(a, dtype="float32").reshape(-1)
    bv = np.asarray(b, dtype="float32").reshape(-1)

    if av.shape != bv.shape:
        raise ValueError(f"Embedding dimensions do not match: {av.size} != {bv.size}")

    denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
    if denom < 1e-8:
        return 0.0
    return float(np.dot(av, bv) / denom)
