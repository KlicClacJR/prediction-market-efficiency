"""Shared plotting helpers for generated research outputs."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def _finish(fig: plt.Figure, output_path: str | Path | None) -> plt.Figure:
    fig.tight_layout()
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=180, bbox_inches="tight")
    return fig


def plot_reliability_diagram(
    calibration_bins: pd.DataFrame,
    *,
    output_path: str | Path | None = None,
) -> plt.Figure:
    required = {"mean_prediction", "empirical_rate", "forecast_horizon_hours"}
    if missing := required - set(calibration_bins.columns):
        raise ValueError(f"calibration table missing columns: {sorted(missing)}")
    data = calibration_bins.loc[calibration_bins["count"] > 0].copy()
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot([0, 1], [0, 1], linestyle="--", color="0.45", label="Perfect calibration")
    lineplot_options = {
        "data": data,
        "x": "mean_prediction",
        "y": "empirical_rate",
        "hue": "forecast_horizon_hours",
        "marker": "o",
        "ax": ax,
    }
    if "probability_definition" in data:
        lineplot_options["style"] = "probability_definition"
    sns.lineplot(**lineplot_options)
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean market probability", ylabel="Observed frequency")
    ax.set_title("Reliability by forecast horizon")
    return _finish(fig, output_path)


def plot_predicted_vs_actual_revisions(
    predictions: pd.DataFrame,
    *,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Plot chronological out-of-sample revisions by horizon pair and model."""
    data = predictions.loc[predictions["model"] != "zero_change_baseline"].copy()
    pairs = data["pair"].drop_duplicates().tolist()
    if not pairs:
        raise ValueError("no fitted-model predictions available for plotting")
    fig, axes = plt.subplots(1, len(pairs), figsize=(5.2 * len(pairs), 4.8), squeeze=False)
    for axis, pair in zip(axes[0], pairs, strict=True):
        subset = data.loc[data["pair"] == pair]
        sns.scatterplot(
            data=subset,
            x="actual_revision",
            y="predicted_revision",
            hue="model",
            alpha=0.55,
            s=28,
            ax=axis,
        )
        finite = subset[["actual_revision", "predicted_revision"]].to_numpy(dtype=float)
        bound = float(np.nanmax(np.abs(finite))) if finite.size else 0.1
        bound = max(bound, 0.01)
        axis.plot([-bound, bound], [-bound, bound], "--", color="0.35", linewidth=1)
        axis.axhline(0, color="0.75", linewidth=0.8)
        axis.axvline(0, color="0.75", linewidth=0.8)
        axis.set(
            title=pair.replace("_", " "),
            xlim=(-bound, bound),
            ylim=(-bound, bound),
            xlabel="Actual probability revision",
            ylabel="Predicted probability revision",
        )
    fig.suptitle("Chronological out-of-sample probability revisions", y=1.02)
    return _finish(fig, output_path)
