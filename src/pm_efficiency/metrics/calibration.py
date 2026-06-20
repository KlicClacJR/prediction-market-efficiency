"""Calibration bins, ECE, bias, and event-cluster bootstrap intervals."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from pm_efficiency.metrics.scoring import binary_log_loss, brier_score


def calibration_table(
    y_true: object,
    probability: object,
    bins: int = 10,
) -> pd.DataFrame:
    if bins < 2:
        raise ValueError("bins must be at least 2")
    frame = pd.DataFrame(
        {
            "outcome": np.asarray(y_true, dtype=float),
            "probability": np.asarray(probability, dtype=float),
        }
    ).dropna()
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "bin",
                "bin_lower",
                "bin_upper",
                "count",
                "mean_prediction",
                "empirical_rate",
                "calibration_gap",
                "weight",
            ]
        )
    if not frame["probability"].between(0, 1).all():
        raise ValueError("probabilities must lie in [0, 1]")
    edges = np.linspace(0, 1, bins + 1)
    frame["bin"] = pd.cut(frame["probability"], edges, include_lowest=True, labels=False)
    grouped = frame.groupby("bin", observed=False)
    result = grouped.agg(
        count=("outcome", "size"),
        mean_prediction=("probability", "mean"),
        empirical_rate=("outcome", "mean"),
    ).reindex(range(bins))
    result.index.name = "bin"
    result = result.reset_index()
    result["bin_lower"] = edges[:-1]
    result["bin_upper"] = edges[1:]
    result["count"] = result["count"].fillna(0).astype(int)
    result["calibration_gap"] = result["empirical_rate"] - result["mean_prediction"]
    result["weight"] = result["count"] / max(result["count"].sum(), 1)
    return result[
        [
            "bin",
            "bin_lower",
            "bin_upper",
            "count",
            "mean_prediction",
            "empirical_rate",
            "calibration_gap",
            "weight",
        ]
    ]


def expected_calibration_error(
    y_true: object,
    probability: object,
    bins: int = 10,
) -> float:
    table = calibration_table(y_true, probability, bins)
    return float((table["weight"] * table["calibration_gap"].abs()).sum())


def probability_range_bias(
    y_true: object,
    probability: object,
    bins: int = 10,
) -> pd.DataFrame:
    table = calibration_table(y_true, probability, bins)
    return table.rename(columns={"calibration_gap": "mean_outcome_minus_probability"})


def cluster_bootstrap_metrics(
    frame: pd.DataFrame,
    *,
    outcome: str = "outcome",
    probability: str = "probability_mid",
    cluster: str = "event_id",
    bins: int = 10,
    iterations: int = 1000,
    seed: int = 20260619,
) -> pd.DataFrame:
    """Bootstrap complete events, retaining within-event bucket dependence."""
    data = frame[[outcome, probability, cluster]].dropna()
    if data.empty or data[cluster].nunique() < 2:
        raise ValueError("cluster bootstrap requires at least two nonempty clusters")
    functions: dict[str, Callable[[object, object], float]] = {
        "brier_score": brier_score,
        "log_loss": binary_log_loss,
        "ece": lambda y, p: expected_calibration_error(y, p, bins),
    }
    point = {
        name: function(data[outcome], data[probability]) for name, function in functions.items()
    }
    clusters = data[cluster].drop_duplicates().to_numpy()
    rng = np.random.default_rng(seed)
    draws = {name: [] for name in functions}
    grouped = {key: value for key, value in data.groupby(cluster, sort=False)}
    for _ in range(iterations):
        selected = rng.choice(clusters, size=len(clusters), replace=True)
        sample = pd.concat([grouped[key] for key in selected], ignore_index=True)
        for name, function in functions.items():
            draws[name].append(function(sample[outcome], sample[probability]))
    return pd.DataFrame(
        [
            {
                "metric": name,
                "estimate": point[name],
                "ci_lower": np.quantile(draws[name], 0.025),
                "ci_upper": np.quantile(draws[name], 0.975),
                "clusters": len(clusters),
                "iterations": iterations,
            }
            for name in functions
        ]
    )
