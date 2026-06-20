"""Command-line workflow for fetch, clean, build, analyze, and cached reproduction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from pm_efficiency.analysis.calibration_study import run_calibration_analysis
from pm_efficiency.analysis.efficiency_study import run_efficiency_analysis
from pm_efficiency.config import ProjectConfig, load_config
from pm_efficiency.data.clean import clean_raw_run
from pm_efficiency.data.ingest import fetch_series_history
from pm_efficiency.data.validate import validate_candles, validate_markets, validate_outcomes
from pm_efficiency.features.market_features import build_efficiency_panel, build_fixed_horizon_panel


def _latest_run(config: ProjectConfig) -> Path:
    root = Path(config.paths.raw) / "kalshi" / config.series_id
    runs = sorted(path for path in root.glob("*") if (path / "manifest.json").exists())
    if not runs:
        raise FileNotFoundError("No raw runs found. Run `pm-efficiency fetch` first.")
    return runs[-1]


def clean(config: ProjectConfig, run_dir: str | Path | None = None) -> None:
    paths = clean_raw_run(run_dir or _latest_run(config), config.paths.interim)
    markets, outcomes, candles = (pd.read_parquet(path) for path in paths)
    reports = {
        "markets": validate_markets(markets),
        "outcomes": validate_outcomes(outcomes),
        "candles": validate_candles(candles),
    }
    for report in reports.values():
        report.raise_for_errors()
    summary = {
        name: {"ok": report.ok, "errors": report.errors, "warnings": report.warnings}
        for name, report in reports.items()
    }
    (Path(config.paths.interim) / "validation_report.json").write_text(
        json.dumps(summary, indent=2)
    )


def build(config: ProjectConfig) -> None:
    root = Path(config.paths.interim)
    markets = pd.read_parquet(root / "markets.parquet")
    outcomes = pd.read_parquet(root / "outcomes.parquet")
    candles = pd.read_parquet(root / "price_history.parquet")
    forecast = build_fixed_horizon_panel(
        candles,
        markets,
        outcomes,
        config.forecast_horizons_hours,
        config.max_staleness_hours,
    )
    efficiency = build_efficiency_panel(candles, markets, config.efficiency_horizons_hours)
    target = Path(config.paths.processed)
    target.mkdir(parents=True, exist_ok=True)
    forecast.to_parquet(target / "forecast_panel.parquet", index=False)
    efficiency.to_parquet(target / "efficiency_panel.parquet", index=False)


def analyze(config: ProjectConfig) -> None:
    import matplotlib.pyplot as plt

    from pm_efficiency.visualization.plots import plot_reliability_diagram

    root = Path(config.paths.processed)
    forecast = pd.read_parquet(root / "forecast_panel.parquet")
    efficiency = pd.read_parquet(root / "efficiency_panel.parquet")
    calibration = run_calibration_analysis(
        forecast,
        bins=config.calibration_bins,
        bootstrap_iterations=config.bootstrap_iterations,
        seed=config.random_seed,
        output_dir=config.paths.tables,
    )
    run_efficiency_analysis(
        efficiency,
        horizons=config.efficiency_horizons_hours,
        minimum_training_events=config.minimum_training_events,
        output_dir=config.paths.tables,
    )
    figure = plot_reliability_diagram(
        calibration["calibration_bins"],
        output_path=Path(config.paths.figures) / "reliability.png",
    )
    plt.close(figure)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pm-efficiency")
    parser.add_argument("--config", default="config/mvp.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("fetch", help="Fetch a new immutable Kalshi raw run")
    clean_parser = subparsers.add_parser("clean", help="Normalize and validate one raw run")
    clean_parser.add_argument("--run-dir")
    subparsers.add_parser("build", help="Build fixed-horizon and efficiency panels")
    subparsers.add_parser("analyze", help="Write statistical tables and figures")
    pipeline = subparsers.add_parser("pipeline", help="Clean, build, and analyze cached raw data")
    pipeline.add_argument("--run-dir")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    config.ensure_output_directories()
    if args.command == "fetch":
        run = fetch_series_history(config)
        print(run)
    elif args.command == "clean":
        clean(config, args.run_dir)
    elif args.command == "build":
        build(config)
    elif args.command == "analyze":
        analyze(config)
    elif args.command == "pipeline":
        clean(config, args.run_dir)
        build(config)
        analyze(config)


if __name__ == "__main__":
    main()
