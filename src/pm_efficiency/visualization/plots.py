"""Small plotting surface shared by notebooks and CLI analyses."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
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


def plot_probability_paths(
    candles: pd.DataFrame,
    event_id: str,
    *,
    output_path: str | Path | None = None,
) -> plt.Figure:
    data = candles.loc[candles["event_id"] == event_id]
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=data, x="timestamp", y="probability_mid", hue="market_id", ax=ax)
    ax.set(title=f"Market-implied probabilities: {event_id}", ylabel="YES midpoint probability")
    return _finish(fig, output_path)
