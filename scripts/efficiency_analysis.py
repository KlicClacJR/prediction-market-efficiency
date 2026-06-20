#!/usr/bin/env python3
"""Run chronological paired-horizon efficiency and martingale tests."""

from __future__ import annotations

import argparse

from pm_efficiency.analysis.paired_efficiency_study import run_paired_efficiency_from_files
from pm_efficiency.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/mvp.yaml")
    parser.add_argument("--snapshots", default="data/processed/market_snapshots.csv")
    parser.add_argument("--features", default="data/processed/efficiency_panel.parquet")
    parser.add_argument("--metrics", default="reports/tables/efficiency_metrics.csv")
    parser.add_argument("--coefficients", default="reports/tables/efficiency_coefficients.csv")
    parser.add_argument("--predictions", default="reports/tables/efficiency_predictions.csv")
    parser.add_argument("--figure", default="reports/figures/predicted_vs_actual_revisions.png")
    parser.add_argument("--report", default="reports/efficiency_report.md")
    args = parser.parse_args()
    config = load_config(args.config)
    settings = config.efficiency
    run_paired_efficiency_from_files(
        args.snapshots,
        args.features,
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
        metrics_path=args.metrics,
        coefficients_path=args.coefficients,
        predictions_path=args.predictions,
        figure_path=args.figure,
        report_path=args.report,
    )
    print(args.metrics)
    print(args.coefficients)
    print(args.figure)
    print(args.report)


if __name__ == "__main__":
    main()
