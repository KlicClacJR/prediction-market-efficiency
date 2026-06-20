"""Descriptive audit tables for the canonical KXHIGHNY snapshot dataset."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pm_efficiency.data.snapshots import SNAPSHOT_COLUMNS

SUMMARY_COLUMNS = [
    "section",
    "event_id",
    "event_date",
    "timestamp",
    "variable",
    "metric",
    "value",
    "contracts_observed",
]

DESCRIBE_METRICS = ["count", "mean", "std", "min", "25%", "50%", "75%", "max"]


def _summary_rows(series: pd.Series, section: str, variable: str) -> list[dict[str, object]]:
    numeric = pd.to_numeric(series, errors="coerce")
    description = numeric.describe(percentiles=[0.25, 0.5, 0.75])
    return [
        {
            "section": section,
            "variable": variable,
            "metric": metric,
            "value": description.get(metric, pd.NA),
        }
        for metric in DESCRIBE_METRICS
    ]


def build_descriptive_summary(snapshots: pd.DataFrame) -> pd.DataFrame:
    """Return one tidy table containing coverage, missingness, and distributions."""
    missing_columns = sorted(set(SNAPSHOT_COLUMNS) - set(snapshots.columns))
    if missing_columns:
        raise ValueError(f"market snapshots missing columns: {missing_columns}")
    if snapshots.empty:
        raise ValueError("market snapshots dataset is empty")

    data = snapshots.copy()
    data["event_date"] = pd.to_datetime(data["event_date"], errors="coerce")
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="coerce")
    rows: list[dict[str, object]] = [
        {
            "section": "coverage",
            "variable": "event_id",
            "metric": "event_count",
            "value": data["event_id"].nunique(),
        },
        {
            "section": "coverage",
            "variable": "contract_id",
            "metric": "contract_count",
            "value": data["contract_id"].nunique(),
        },
        {
            "section": "coverage",
            "variable": "event_date",
            "metric": "first_event_date",
            "value": data["event_date"].min().date().isoformat(),
        },
        {
            "section": "coverage",
            "variable": "event_date",
            "metric": "last_event_date",
            "value": data["event_date"].max().date().isoformat(),
        },
    ]

    total_rows = len(data)
    for column in snapshots.columns:
        missing_count = int(snapshots[column].isna().sum())
        rows.extend(
            [
                {
                    "section": "missingness",
                    "variable": column,
                    "metric": "missing_count",
                    "value": missing_count,
                },
                {
                    "section": "missingness",
                    "variable": column,
                    "metric": "missing_fraction",
                    "value": missing_count / total_rows,
                },
            ]
        )

    rows.extend(
        _summary_rows(
            data["midpoint_probability"], "midpoint_probability_summary", "midpoint_probability"
        )
    )
    spread = pd.to_numeric(data["yes_ask"], errors="coerce") - pd.to_numeric(
        data["yes_bid"], errors="coerce"
    )
    rows.extend(_summary_rows(spread, "spread_summary", "bid_ask_spread"))
    rows.extend(_summary_rows(data["volume"], "activity_summary", "volume"))
    rows.extend(_summary_rows(data["open_interest"], "activity_summary", "open_interest"))

    event_sums = (
        data.dropna(subset=["event_id", "event_date", "timestamp"])
        .groupby(["event_id", "event_date", "timestamp"], as_index=False)
        .agg(
            value=("midpoint_probability", lambda values: values.sum(min_count=1)),
            contracts_observed=("contract_id", "nunique"),
        )
        .sort_values(["event_date", "event_id", "timestamp"])
    )
    for record in event_sums.to_dict("records"):
        rows.append(
            {
                "section": "event_probability_sums",
                "event_id": record["event_id"],
                "event_date": record["event_date"].date().isoformat(),
                "timestamp": record["timestamp"].isoformat(),
                "variable": "midpoint_probability",
                "metric": "sum",
                "value": record["value"],
                "contracts_observed": record["contracts_observed"],
            }
        )

    summary = pd.DataFrame(rows)
    for column in SUMMARY_COLUMNS:
        if column not in summary:
            summary[column] = pd.NA
    return summary[SUMMARY_COLUMNS]


def write_descriptive_summary(
    input_path: str | Path = "data/processed/market_snapshots.csv",
    output_path: str | Path = "reports/tables/descriptive_summary.csv",
) -> Path:
    """Read canonical snapshots and persist the descriptive audit table."""
    source = Path(input_path)
    if not source.is_file():
        raise FileNotFoundError(
            f"Snapshot dataset not found at {source}. Run `pm-efficiency build` first."
        )
    snapshots = pd.read_csv(source)
    summary = build_descriptive_summary(snapshots)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(destination, index=False)
    return destination
