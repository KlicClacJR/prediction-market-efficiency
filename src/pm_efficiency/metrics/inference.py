"""Small inference utilities shared across research analyses."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def adjust_pvalues(values: Sequence[float]) -> np.ndarray:
    """Apply Benjamini-Hochberg adjustment while preserving missing entries."""
    array = np.asarray(values, dtype=float)
    output = np.full_like(array, np.nan)
    valid = np.isfinite(array)
    if valid.any():
        pvalues = array[valid]
        order = np.argsort(pvalues)
        ranked = pvalues[order]
        adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
        adjusted = np.minimum.accumulate(adjusted[::-1])[::-1].clip(0, 1)
        restored = np.empty_like(adjusted)
        restored[order] = adjusted
        output[valid] = restored
    return output
