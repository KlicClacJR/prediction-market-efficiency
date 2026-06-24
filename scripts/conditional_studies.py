#!/usr/bin/env python3
"""Run liquidity, information-arrival, and extreme-event studies."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from pm_efficiency.analysis.conditional_studies import (
    HORIZONS,
    run_extreme_study,
    run_information_arrival_study,
    run_liquidity_study,
    write_frame,
)
from pm_efficiency.config import load_config

plt.switch_backend("Agg")


def save_liquidity(results: dict[str, pd.DataFrame], root: Path) -> None:
    write_frame(results["metrics"], root / "reports/tables/liquidity_calibration_metrics.csv")
    write_frame(results["comparisons"], root / "reports/tables/liquidity_comparisons.csv")
    write_frame(results["reliability"], root / "reports/tables/liquidity_reliability.csv")
    reliability = results["reliability"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 9), sharex=True, sharey=True)
    for axis, horizon in zip(axes.flat, HORIZONS, strict=True):
        sample = reliability[reliability.forecast_horizon_hours == horizon]
        for quartile, group in sample.groupby("liquidity_quartile"):
            valid = group[group["count"] > 0]
            axis.plot(valid.mean_prediction, valid.empirical_rate, marker="o", label=quartile)
        axis.plot([0, 1], [0, 1], "--", color="0.4", linewidth=1)
        axis.set(title=f"{horizon}h before close", xlabel="Mean probability", ylabel="Outcome rate")
    axes[0, 0].legend(title="Liquidity quartile")
    fig.suptitle("KXHIGHNY reliability by point-in-time liquidity", y=1.01)
    fig.tight_layout()
    fig.savefig(root / "reports/figures/liquidity_reliability.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_arrival(results: dict[str, pd.DataFrame], root: Path) -> None:
    write_frame(results["scores"], root / "reports/tables/information_arrival_scores.csv")
    write_frame(
        results["decomposition"], root / "reports/tables/information_arrival_decomposition.csv"
    )
    scores = results["scores"].sort_values("forecast_horizon_hours", ascending=False)
    decomposition = results["decomposition"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].errorbar(
        scores.forecast_horizon_hours,
        scores.brier_score,
        yerr=[
            scores.brier_score - scores.brier_score_ci_lower,
            scores.brier_score_ci_upper - scores.brier_score,
        ],
        marker="o",
        capsize=3,
    )
    axes[0].invert_xaxis()
    axes[0].set(xlabel="Hours before close", ylabel="Brier score", title="Matched-contract error")
    sns.barplot(data=decomposition, x="interval", y="share_total_brier_reduction", ax=axes[1])
    axes[1].axhline(0, color="0.4", linewidth=1)
    axes[1].set(
        xlabel="Interval", ylabel="Share of 24h→1h Brier reduction", title="Information arrival"
    )
    fig.tight_layout()
    fig.savefig(root / "reports/figures/information_arrival.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_extreme(results: dict, root: Path) -> None:
    write_frame(
        results["temperature_events"], root / "reports/tables/extreme_temperature_events.csv"
    )
    write_frame(
        pd.DataFrame([results["thresholds"]]), root / "reports/tables/extreme_thresholds.csv"
    )
    write_frame(
        results["calibration_metrics"], root / "reports/tables/extreme_calibration_metrics.csv"
    )
    write_frame(results["calibration_tests"], root / "reports/tables/extreme_calibration_tests.csv")
    write_frame(
        results["efficiency_metrics"], root / "reports/tables/extreme_efficiency_metrics.csv"
    )
    calibration = results["calibration_metrics"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    sns.lineplot(
        data=calibration,
        x="forecast_horizon_hours",
        y="brier_score",
        hue="extreme_group",
        marker="o",
        ax=axes[0],
    )
    axes[0].invert_xaxis()
    axes[0].set(title="Calibration error", xlabel="Hours before close", ylabel="Brier score")
    efficiency = results["efficiency_metrics"]
    fitted = efficiency[efficiency.model != "zero_change_baseline"]
    sns.barplot(
        data=fitted,
        x="pair",
        y="oos_r2_vs_zero",
        hue="extreme_group",
        errorbar=None,
        ax=axes[1],
    )
    axes[1].axhline(0, color="0.4", linewidth=1)
    axes[1].set(
        title="Mean across fitted models",
        xlabel="Horizon pair",
        ylabel="Mean OOS R² vs zero",
    )
    axes[1].tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(root / "reports/figures/extreme_weather.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    config = load_config("config/mvp.yaml")
    root = config.root
    forecast = pd.read_parquet(root / "data/processed/forecast_panel.parquet")
    markets = pd.read_parquet(root / "data/interim/markets.parquet")
    predictions = pd.read_csv(root / "reports/tables/efficiency_predictions.csv")
    liquidity = run_liquidity_study(
        forecast,
        iterations=config.bootstrap_iterations,
        bins=config.calibration_bins,
        seed=config.random_seed,
    )
    arrival = run_information_arrival_study(
        forecast, iterations=config.bootstrap_iterations, seed=config.random_seed
    )
    extreme = run_extreme_study(
        forecast,
        markets,
        predictions,
        iterations=config.bootstrap_iterations,
        bins=config.calibration_bins,
        seed=config.random_seed,
    )
    save_liquidity(liquidity, root)
    save_arrival(arrival, root)
    save_extreme(extreme, root)
    print(root / "reports/tables/liquidity_calibration_metrics.csv")
    print(root / "reports/tables/information_arrival_decomposition.csv")
    print(root / "reports/tables/extreme_efficiency_metrics.csv")


if __name__ == "__main__":
    main()
