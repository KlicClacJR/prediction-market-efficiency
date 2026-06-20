"""End-to-end calibration study tables."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pm_efficiency.metrics.calibration import (
    calibration_table,
    cluster_bootstrap_metrics,
    expected_calibration_error,
)
from pm_efficiency.metrics.scoring import binary_log_loss, brier_score


def add_expanding_prevalence_benchmark(panel: pd.DataFrame) -> pd.DataFrame:
    """Add a base rate based only on fully earlier events at the same horizon."""
    result = panel.copy()
    result["expanding_prevalence"] = np.nan
    for horizon, subset in result.groupby("forecast_horizon_hours"):
        event_stats = (
            subset.groupby("event_id", sort=False)
            .agg(
                event_time=("close_at", "min"),
                successes=("outcome", "sum"),
                trials=("outcome", "size"),
            )
            .sort_values("event_time")
        )
        prior_successes = event_stats["successes"].cumsum().shift(fill_value=0)
        prior_trials = event_stats["trials"].cumsum().shift(fill_value=0)
        prevalence = ((prior_successes + 0.5) / (prior_trials + 1)).to_dict()
        mask = result["forecast_horizon_hours"] == horizon
        result.loc[mask, "expanding_prevalence"] = result.loc[mask, "event_id"].map(prevalence)
    return result


def run_calibration_analysis(
    panel: pd.DataFrame,
    *,
    bins: int = 10,
    bootstrap_iterations: int = 1000,
    seed: int = 20260619,
    output_dir: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Score raw and event-normalized forecasts by fixed pre-close horizon."""
    data = add_expanding_prevalence_benchmark(panel)
    metric_rows = []
    bin_tables = []
    probability_columns = ["probability_mid"]
    if "probability_normalized" in data:
        probability_columns.append("probability_normalized")
    probability_columns.extend(["expanding_prevalence"])
    for horizon, subset in data.groupby("forecast_horizon_hours", sort=False):
        for probability in probability_columns:
            sample = subset[["outcome", probability, "event_id"]].dropna()
            if sample.empty:
                continue
            row = {
                "forecast_horizon_hours": int(horizon),
                "probability_definition": probability,
                "observations": len(sample),
                "events": sample["event_id"].nunique(),
                "prevalence": sample["outcome"].mean(),
                "brier_score": brier_score(sample["outcome"], sample[probability]),
                "log_loss": binary_log_loss(sample["outcome"], sample[probability]),
                "ece": expected_calibration_error(sample["outcome"], sample[probability], bins),
                "mean_bias": (sample["outcome"] - sample[probability]).mean(),
            }
            if sample["event_id"].nunique() >= 2 and bootstrap_iterations > 0:
                renamed = sample.rename(columns={probability: "probability"})
                boot = cluster_bootstrap_metrics(
                    renamed,
                    probability="probability",
                    bins=bins,
                    iterations=bootstrap_iterations,
                    seed=seed + int(horizon),
                ).set_index("metric")
                for metric in ("brier_score", "log_loss", "ece"):
                    row[f"{metric}_ci_lower"] = boot.loc[metric, "ci_lower"]
                    row[f"{metric}_ci_upper"] = boot.loc[metric, "ci_upper"]
            metric_rows.append(row)
            table = calibration_table(sample["outcome"], sample[probability], bins)
            table.insert(0, "probability_definition", probability)
            table.insert(0, "forecast_horizon_hours", int(horizon))
            bin_tables.append(table)
    outputs = {
        "metrics": pd.DataFrame(metric_rows),
        "calibration_bins": (
            pd.concat(bin_tables, ignore_index=True) if bin_tables else pd.DataFrame()
        ),
        "forecast_panel_with_benchmark": data,
    }
    if output_dir is not None:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        outputs["metrics"].to_csv(target / "calibration_metrics.csv", index=False)
        outputs["calibration_bins"].to_csv(target / "calibration_bins.csv", index=False)
    return outputs
