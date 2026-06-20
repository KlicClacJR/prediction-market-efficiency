"""Fixed-horizon calibration analysis from canonical KXHIGHNY snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from pm_efficiency.data.validate import validate_market_snapshots
from pm_efficiency.metrics.calibration import calibration_table, cluster_bootstrap_metrics

DEFAULT_HORIZONS = (24, 12, 6, 1)
LOG_LOSS_EPSILON = 1e-6


def select_fixed_horizon_quotes(
    snapshots: pd.DataFrame,
    *,
    horizons: Iterable[int] = DEFAULT_HORIZONS,
    max_staleness_hours: float = 2,
) -> pd.DataFrame:
    """Select each contract's latest quote at or before each pre-close target."""
    validation = validate_market_snapshots(snapshots)
    validation.raise_for_errors()
    data = snapshots.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="coerce")
    data["close_time"] = pd.to_datetime(data["close_time"], utc=True, errors="coerce")
    data["midpoint_probability"] = pd.to_numeric(data["midpoint_probability"], errors="coerce")
    rows = []
    requested_horizons = tuple(int(horizon) for horizon in horizons)
    if not requested_horizons or min(requested_horizons) <= 0:
        raise ValueError("horizons must contain positive hours")
    for contract_id, history in data.groupby("contract_id", sort=False):
        history = history.sort_values("timestamp")
        event_ids = history["event_id"].dropna().unique()
        close_times = history["close_time"].dropna().unique()
        outcomes = history["resolved_yes"].dropna().astype(bool).unique()
        if len(event_ids) != 1 or len(close_times) != 1 or len(outcomes) != 1:
            raise ValueError(f"inconsistent contract metadata for {contract_id}")
        close_time = pd.Timestamp(close_times[0])
        for horizon in requested_horizons:
            target_time = close_time - pd.Timedelta(hours=horizon)
            eligible = history.loc[
                (history["timestamp"] <= target_time) & history["midpoint_probability"].notna()
            ]
            if eligible.empty:
                continue
            selected = eligible.iloc[-1]
            staleness = (target_time - selected["timestamp"]).total_seconds() / 3600
            if staleness > max_staleness_hours:
                continue
            rows.append(
                {
                    "event_id": event_ids[0],
                    "contract_id": contract_id,
                    "forecast_horizon_hours": horizon,
                    "target_time": target_time,
                    "quote_timestamp": selected["timestamp"],
                    "staleness_hours": staleness,
                    "probability": float(selected["midpoint_probability"]),
                    "outcome": int(outcomes[0]),
                }
            )
    panel = pd.DataFrame(rows)
    observed_horizons = set(panel.get("forecast_horizon_hours", pd.Series(dtype=int)))
    missing_horizons = sorted(set(requested_horizons) - observed_horizons, reverse=True)
    if missing_horizons:
        raise ValueError(f"no eligible quotes for horizons: {missing_horizons}")
    return panel.sort_values(
        ["forecast_horizon_hours", "event_id", "contract_id"],
        ascending=[False, True, True],
    ).reset_index(drop=True)


def run_fixed_horizon_calibration(
    snapshots: pd.DataFrame,
    *,
    horizons: Iterable[int] = DEFAULT_HORIZONS,
    bins: int = 10,
    bootstrap_iterations: int = 1000,
    seed: int = 20260619,
    max_staleness_hours: float = 2,
    metrics_path: str | Path | None = None,
    deciles_path: str | Path | None = None,
    figure_path: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Compute proper scores, decile calibration, clustered CIs, and reliability plot."""
    panel = select_fixed_horizon_quotes(
        snapshots,
        horizons=horizons,
        max_staleness_hours=max_staleness_hours,
    )
    metric_rows = []
    decile_tables = []
    for horizon in horizons:
        sample = panel.loc[panel["forecast_horizon_hours"] == int(horizon)]
        if sample["event_id"].nunique() < 2:
            raise ValueError(
                f"horizon {horizon}h needs at least two events for clustered bootstrap"
            )
        bootstrap = cluster_bootstrap_metrics(
            sample,
            outcome="outcome",
            probability="probability",
            cluster="event_id",
            bins=bins,
            iterations=bootstrap_iterations,
            seed=seed + int(horizon),
        ).set_index("metric")
        metric_rows.append(
            {
                "forecast_horizon_hours": int(horizon),
                "observations": len(sample),
                "events": sample["event_id"].nunique(),
                "prevalence": sample["outcome"].mean(),
                "mean_staleness_hours": sample["staleness_hours"].mean(),
                "brier_score": bootstrap.loc["brier_score", "estimate"],
                "brier_score_ci_lower": bootstrap.loc["brier_score", "ci_lower"],
                "brier_score_ci_upper": bootstrap.loc["brier_score", "ci_upper"],
                "log_loss": bootstrap.loc["log_loss", "estimate"],
                "log_loss_ci_lower": bootstrap.loc["log_loss", "ci_lower"],
                "log_loss_ci_upper": bootstrap.loc["log_loss", "ci_upper"],
                "log_loss_clip_epsilon": LOG_LOSS_EPSILON,
                "ece": bootstrap.loc["ece", "estimate"],
                "ece_ci_lower": bootstrap.loc["ece", "ci_lower"],
                "ece_ci_upper": bootstrap.loc["ece", "ci_upper"],
                "bootstrap_clusters": bootstrap.loc["ece", "clusters"],
                "bootstrap_iterations": bootstrap_iterations,
            }
        )
        deciles = calibration_table(sample["outcome"], sample["probability"], bins)
        deciles.insert(0, "forecast_horizon_hours", int(horizon))
        decile_tables.append(deciles)
    metrics = pd.DataFrame(metric_rows).sort_values("forecast_horizon_hours", ascending=False)
    decile_table = pd.concat(decile_tables, ignore_index=True)

    if metrics_path is not None:
        destination = Path(metrics_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        metrics.to_csv(destination, index=False)
    if deciles_path is not None:
        destination = Path(deciles_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        decile_table.to_csv(destination, index=False)
    if figure_path is not None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        from pm_efficiency.visualization.plots import plot_reliability_diagram

        figure = plot_reliability_diagram(decile_table, output_path=figure_path)
        plt.close(figure)
    return {"metrics": metrics, "calibration_deciles": decile_table, "panel": panel}


def run_calibration_from_file(
    input_path: str | Path = "data/processed/market_snapshots.csv",
    *,
    metrics_path: str | Path = "reports/tables/calibration_metrics.csv",
    deciles_path: str | Path = "reports/tables/calibration_deciles.csv",
    figure_path: str | Path = "reports/figures/reliability_diagram.png",
    **kwargs: object,
) -> dict[str, pd.DataFrame]:
    """Load canonical snapshots and write all fixed-horizon calibration outputs."""
    source = Path(input_path)
    if not source.is_file():
        raise FileNotFoundError(
            f"Snapshot dataset not found at {source}. Run `pm-efficiency build` first."
        )
    snapshots = pd.read_csv(source)
    return run_fixed_horizon_calibration(
        snapshots,
        metrics_path=metrics_path,
        deciles_path=deciles_path,
        figure_path=figure_path,
        **kwargs,
    )
