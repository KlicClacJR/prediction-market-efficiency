#!/usr/bin/env python3
"""Fetch archived weather runs and test their alignment with market information arrival."""

from __future__ import annotations

import argparse

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from pm_efficiency.analysis.information_sources import build_information_source_panels
from pm_efficiency.analysis.weather_information import (
    aggregate_market_intervals,
    build_forecast_update_event_study,
    build_weather_revision_table,
    market_forecast_relationships,
    write_weather_report,
)
from pm_efficiency.config import load_config
from pm_efficiency.data.weather_forecasts import (
    build_forecast_requests,
    fetch_weather_archive,
    load_forecast_vintages,
    verify_weather_manifest,
)

matplotlib.use("Agg")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Fetch missing archived runs")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    config = load_config("config/mvp.yaml")
    root = config.root
    archive = root / "data/external/weather_information"
    manifest = archive / "manifest.json"
    markets = pd.read_parquet(root / "data/interim/markets.parquet")
    requests = build_forecast_requests(markets)
    if args.fetch or not manifest.exists():
        fetch_weather_archive(requests, archive, max_workers=args.workers)
    verify_weather_manifest(manifest)
    vintages = load_forecast_vintages(requests, archive)
    weather = build_weather_revision_table(vintages)
    weather_path = root / "reports/tables/weather_forecast_revisions.csv"
    weather.to_csv(weather_path, index=False)

    forecast_panel = pd.read_parquet(root / "data/processed/forecast_panel.parquet")
    price_history = pd.read_parquet(root / "data/interim/price_history.parquet")
    _, interval_panel = build_information_source_panels(
        forecast_panel, price_history, markets, training_end="2025-01-04"
    )
    market_intervals = aggregate_market_intervals(interval_panel)
    relationships = market_forecast_relationships(
        weather,
        market_intervals,
        iterations=config.bootstrap_iterations,
        seed=config.random_seed,
    )
    timeline, release_tests = build_forecast_update_event_study(
        weather,
        price_history,
        markets,
        iterations=config.bootstrap_iterations,
        seed=config.random_seed,
    )
    relationship_path = root / "reports/tables/market_vs_forecast_relationship.csv"
    combined = pd.concat([relationships, release_tests, timeline], ignore_index=True, sort=False)
    combined.to_csv(relationship_path, index=False)
    write_weather_report(
        weather,
        relationships,
        release_tests,
        root / "reports/weather_information_source_report.md",
    )

    mae = pd.DataFrame(
        {
            "horizon": [24, 12, 6],
            "mae": [
                weather.absolute_forecast_error_24h_f.mean(),
                weather.absolute_forecast_error_12h_f.mean(),
                weather.absolute_forecast_error_6h_f.mean(),
            ],
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.7))
    sns.lineplot(data=mae, x="horizon", y="mae", marker="o", ax=axes[0])
    axes[0].invert_xaxis()
    axes[0].set(
        title="ECMWF forecast error evolution",
        xlabel="Market hours before close",
        ylabel="Mean absolute high-temperature error (°F)",
    )
    sns.lineplot(
        data=timeline,
        x="relative_hour",
        y="volume",
        hue="forecast_update_group",
        marker="o",
        ax=axes[1],
    )
    axes[1].axvline(0, color="black", linestyle="--", linewidth=1)
    axes[1].set(
        title="Market activity around assumed 12Z-run release",
        xlabel="Hours relative to assumed availability",
        ylabel="Mean contracts traded",
    )
    fig.tight_layout()
    fig.savefig(root / "reports/figures/forecast_update_timeline.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7))
    for axis, label in zip(axes, ("24h_to_12h", "12h_to_6h"), strict=True):
        joined = market_intervals[market_intervals.interval == label].merge(
            weather[["event_id", f"absolute_forecast_revision_{label}_f"]],
            on="event_id",
            how="inner",
        )
        sns.regplot(
            data=joined,
            x=f"absolute_forecast_revision_{label}_f",
            y="market_absolute_revision",
            scatter_kws={"alpha": 0.35, "s": 18},
            line_kws={"color": "black"},
            ax=axis,
        )
        axis.set(
            title=label.replace("_", " "),
            xlabel="Absolute ECMWF high-forecast revision (°F)",
            ylabel="Mean absolute market probability revision",
        )
    fig.suptitle("Market revisions versus archived forecast updates", y=1.02)
    fig.tight_layout()
    fig.savefig(
        root / "reports/figures/market_vs_forecast_revisions.png",
        dpi=220,
        bbox_inches="tight",
    )
    plt.close(fig)
    print(weather_path)
    print(relationship_path)
    print(root / "reports/weather_information_source_report.md")


if __name__ == "__main__":
    main()
