"""Command-line workflow for fetch, clean, build, analyze, and cached reproduction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from pm_efficiency.analysis.fixed_horizon_calibration import run_calibration_from_file
from pm_efficiency.analysis.paired_efficiency_study import run_paired_efficiency_from_files
from pm_efficiency.config import ProjectConfig, load_config
from pm_efficiency.data.clean import clean_raw_run
from pm_efficiency.data.ingest import fetch_series_history, verify_raw_manifest
from pm_efficiency.data.snapshots import (
    build_market_snapshots,
    filter_markets_to_event_window,
    write_market_snapshots,
)
from pm_efficiency.data.validate import (
    validate_candles,
    validate_market_snapshots,
    validate_markets,
    validate_outcomes,
)
from pm_efficiency.features.market_features import build_efficiency_panel, build_fixed_horizon_panel


def _latest_run(config: ProjectConfig) -> Path:
    root = Path(config.paths.raw) / "kalshi" / config.series_id
    runs = sorted(path for path in root.glob("*") if (path / "manifest.json").exists())
    if not runs:
        raise FileNotFoundError("No raw runs found. Run `pm-efficiency fetch` first.")
    return runs[-1]


def clean(config: ProjectConfig, run_dir: str | Path | None = None) -> None:
    selected_run = Path(run_dir or _latest_run(config))
    verify_raw_manifest(selected_run)
    paths = clean_raw_run(selected_run, config.paths.interim)
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
    analysis_end = config.fetch.end_date or pd.Timestamp.now(tz="UTC").date()
    markets = filter_markets_to_event_window(markets, config.fetch.start_date, analysis_end)
    forecast = build_fixed_horizon_panel(
        candles,
        markets,
        outcomes,
        config.forecast_horizons_hours,
        config.max_staleness_hours,
    )
    efficiency = build_efficiency_panel(candles, markets, config.efficiency_horizons_hours)
    snapshots = build_market_snapshots(candles, markets, outcomes)
    snapshot_report = validate_market_snapshots(snapshots)
    snapshot_report.raise_for_errors()
    target = Path(config.paths.processed)
    target.mkdir(parents=True, exist_ok=True)
    forecast.to_parquet(target / "forecast_panel.parquet", index=False)
    efficiency.to_parquet(target / "efficiency_panel.parquet", index=False)
    retrieval_dates = (
        pd.to_datetime(candles["retrieved_at"], utc=True, errors="coerce")
        .dropna()
        .dt.date.astype(str)
        .unique()
        .tolist()
    )
    write_market_snapshots(
        snapshots,
        target / "market_snapshots.csv",
        source_retrieval_dates=retrieval_dates,
    )


def analyze(config: ProjectConfig) -> None:
    root = Path(config.paths.processed)
    run_calibration_from_file(
        root / "market_snapshots.csv",
        metrics_path=Path(config.paths.tables) / "calibration_metrics.csv",
        deciles_path=Path(config.paths.tables) / "calibration_deciles.csv",
        figure_path=Path(config.paths.figures) / "reliability_diagram.png",
        horizons=config.forecast_horizons_hours,
        bins=config.calibration_bins,
        bootstrap_iterations=config.bootstrap_iterations,
        seed=config.random_seed,
        max_staleness_hours=config.max_staleness_hours,
    )
    settings = config.efficiency
    run_paired_efficiency_from_files(
        root / "market_snapshots.csv",
        root / "efficiency_panel.parquet",
        train_fraction=settings.train_fraction,
        minimum_training_events=config.minimum_training_events,
        max_staleness_hours=config.max_staleness_hours,
        ridge_alpha=settings.ridge_alpha,
        sign_tolerance=settings.sign_tolerance,
        block_length_events=settings.block_length_events,
        bootstrap_iterations=settings.bootstrap_iterations,
        bucket_min_frequency=settings.bucket_min_frequency,
        random_forest_min_events=settings.random_forest_min_events,
        random_forest_min_observations=settings.random_forest_min_observations,
        random_forest_estimators=settings.random_forest_estimators,
        seed=config.random_seed,
        metrics_path=Path(config.paths.tables) / "efficiency_metrics.csv",
        coefficients_path=Path(config.paths.tables) / "efficiency_coefficients.csv",
        predictions_path=Path(config.paths.tables) / "efficiency_predictions.csv",
        figure_path=Path(config.paths.figures) / "predicted_vs_actual_revisions.png",
        report_path=config.root / "reports" / "efficiency_report.md",
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pm-efficiency")
    parser.add_argument("--config", default="config/mvp.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)
    fetch_parser = subparsers.add_parser("fetch", help="Fetch a new immutable Kalshi raw run")
    fetch_parser.add_argument("--resume-run")
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
        run = fetch_series_history(config, resume_dir=args.resume_run)
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
