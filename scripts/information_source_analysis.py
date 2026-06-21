#!/usr/bin/env python3
"""Explain the concentration of information arrival between 12h and 6h."""

from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from pm_efficiency.analysis.information_sources import (
    INTERVALS,
    LIQUIDITY_LABELS,
    SEASON_ORDER,
    TEMPERATURE_ORDER,
    build_information_source_panels,
    combine_tables,
    run_information_source_study,
    write_information_source_report,
)
from pm_efficiency.config import load_config

matplotlib.use("Agg")


def main() -> None:
    config = load_config("config/mvp.yaml")
    root = config.root
    forecast = pd.read_parquet(root / "data/processed/forecast_panel.parquet")
    history = pd.read_parquet(root / "data/interim/price_history.parquet")
    markets = pd.read_parquet(root / "data/interim/markets.parquet")
    predictions = pd.read_csv(root / "reports/tables/efficiency_predictions.csv")
    training_end = pd.to_datetime(predictions.event_date).min() - pd.Timedelta(days=1)
    horizon, intervals = build_information_source_panels(
        forecast, history, markets, training_end=training_end
    )
    results = run_information_source_study(
        horizon, intervals, iterations=config.bootstrap_iterations, seed=config.random_seed
    )
    combined = combine_tables(results)
    table_path = root / "reports/tables/information_source_tables.csv"
    combined.to_csv(table_path, index=False)
    write_information_source_report(results, root / "reports/information_source_report.md")

    order = [f"{a}h_to_{b}h" for a, b in INTERVALS]
    summary = results["interval_summary"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    sns.barplot(data=summary, x="interval", y="volume_per_hour", order=order, ax=axes[0])
    sns.barplot(
        data=summary,
        x="interval",
        y="open_interest_growth_per_hour",
        order=order,
        ax=axes[1],
    )
    sns.barplot(data=summary, x="interval", y="absolute_revision", order=order, ax=axes[2])
    axes[0].set(title="Trading activity", ylabel="Contracts per hour", xlabel="Interval")
    axes[1].set(title="Position growth", ylabel="Open-interest change per hour", xlabel="Interval")
    axes[2].set(
        title="Forecast updating", ylabel="Mean absolute probability revision", xlabel="Interval"
    )
    for axis in axes:
        axis.tick_params(axis="x", rotation=20)
    fig.suptitle("Activity and forecast revisions across pre-close intervals", y=1.02)
    fig.tight_layout()
    fig.savefig(
        root / "reports/figures/information_source_dynamics.png", dpi=220, bbox_inches="tight"
    )
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.7))
    seasonal = (
        results["seasonal"]
        .pivot(index="season", columns="interval", values="share_brier_reduction")
        .reindex(index=SEASON_ORDER, columns=order)
    )
    liquidity = (
        results["liquidity"]
        .pivot(index="liquidity_quartile_24h", columns="interval", values="share_brier_reduction")
        .reindex(index=LIQUIDITY_LABELS, columns=order)
    )
    temperature = (
        results["temperature_regime"]
        .pivot(index="temperature_regime", columns="interval", values="share_brier_reduction")
        .reindex(index=TEMPERATURE_ORDER, columns=order)
    )
    sns.heatmap(seasonal, annot=True, fmt=".1%", cmap="Blues", ax=axes[0], cbar=False)
    sns.heatmap(temperature, annot=True, fmt=".1%", cmap="Blues", ax=axes[1], cbar=False)
    sns.heatmap(liquidity, annot=True, fmt=".1%", cmap="Blues", ax=axes[2], cbar=False)
    axes[0].set(title="By season", xlabel="Interval", ylabel="Season")
    axes[1].set(title="By temperature regime", xlabel="Interval", ylabel="Regime")
    axes[2].set(title="By 24h liquidity", xlabel="Interval", ylabel="Liquidity quartile")
    fig.suptitle("Share of total Brier-score reduction", y=1.02)
    fig.tight_layout()
    fig.savefig(
        root / "reports/figures/information_source_conditions.png", dpi=220, bbox_inches="tight"
    )
    plt.close(fig)
    print(table_path)
    print(root / "reports/information_source_report.md")


if __name__ == "__main__":
    main()
