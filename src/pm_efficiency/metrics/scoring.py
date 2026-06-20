"""Proper scoring rules for binary forecasts."""

from __future__ import annotations

import numpy as np


def _arrays(y_true: object, probability: object) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(probability, dtype=float)
    if y.shape != p.shape:
        raise ValueError("y_true and probability must have identical shapes")
    valid = np.isfinite(y) & np.isfinite(p)
    y, p = y[valid], p[valid]
    if not len(y):
        raise ValueError("no finite forecast/outcome pairs")
    if not np.isin(y, [0, 1]).all():
        raise ValueError("outcomes must be binary")
    if ((p < 0) | (p > 1)).any():
        raise ValueError("probabilities must lie in [0, 1]")
    return y, p


def brier_score(y_true: object, probability: object) -> float:
    y, p = _arrays(y_true, probability)
    return float(np.mean((p - y) ** 2))


def binary_log_loss(y_true: object, probability: object, epsilon: float = 1e-6) -> float:
    if not 0 < epsilon < 0.5:
        raise ValueError("epsilon must lie between 0 and 0.5")
    y, p = _arrays(y_true, probability)
    p = np.clip(p, epsilon, 1 - epsilon)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
