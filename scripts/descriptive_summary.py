#!/usr/bin/env python3
"""Generate descriptive tables from canonical KXHIGHNY market snapshots."""

from __future__ import annotations

import argparse

from pm_efficiency.analysis.descriptive import write_descriptive_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="data/processed/market_snapshots.csv",
        help="Canonical market snapshot CSV",
    )
    parser.add_argument(
        "--output",
        default="reports/tables/descriptive_summary.csv",
        help="Destination for the tidy descriptive summary",
    )
    args = parser.parse_args()
    output = write_descriptive_summary(args.input, args.output)
    print(output)


if __name__ == "__main__":
    main()
