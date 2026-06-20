#!/usr/bin/env python3
"""Run fixed-horizon calibration analysis for canonical KXHIGHNY snapshots."""

from __future__ import annotations

import argparse

from pm_efficiency.analysis.fixed_horizon_calibration import run_calibration_from_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/processed/market_snapshots.csv")
    parser.add_argument("--metrics", default="reports/tables/calibration_metrics.csv")
    parser.add_argument("--deciles", default="reports/tables/calibration_deciles.csv")
    parser.add_argument("--figure", default="reports/figures/reliability_diagram.png")
    parser.add_argument("--bootstrap-iterations", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260619)
    parser.add_argument("--max-staleness-hours", type=float, default=2)
    args = parser.parse_args()
    run_calibration_from_file(
        args.input,
        metrics_path=args.metrics,
        deciles_path=args.deciles,
        figure_path=args.figure,
        bootstrap_iterations=args.bootstrap_iterations,
        seed=args.seed,
        max_staleness_hours=args.max_staleness_hours,
    )
    print(args.metrics)
    print(args.figure)


if __name__ == "__main__":
    main()
