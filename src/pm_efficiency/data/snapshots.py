"""Canonical resolved KXHIGHNY market snapshots and processed provenance."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from pm_efficiency.data.ingest import sha256_file

SNAPSHOT_COLUMNS = [
    "event_id",
    "contract_id",
    "event_date",
    "timestamp",
    "yes_bid",
    "yes_ask",
    "midpoint_probability",
    "volume",
    "open_interest",
    "close_time",
    "resolution",
    "resolved_yes",
    "bucket_label",
]


def build_market_snapshots(
    candles: pd.DataFrame,
    markets: pd.DataFrame,
    outcomes: pd.DataFrame,
    *,
    drop_missing_prices: bool = True,
) -> pd.DataFrame:
    """Join hourly quotes to valid resolved contracts using the requested public schema."""
    valid_outcomes = outcomes.loc[
        outcomes["is_valid_resolution"].fillna(False),
        ["market_id", "result", "outcome"],
    ].copy()
    metadata = markets[["market_id", "event_id", "event_date", "close_at", "subtitle"]].merge(
        valid_outcomes, on="market_id", how="inner", validate="one_to_one"
    )
    merged = candles.merge(metadata, on="market_id", how="inner", validate="many_to_one")
    missing_prices = (
        merged[["yes_bid_close", "yes_ask_close", "probability_mid"]].isna().any(axis=1)
    )
    excluded_missing_prices = int(missing_prices.sum())
    if drop_missing_prices:
        merged = merged.loc[~missing_prices].copy()
    snapshots = pd.DataFrame(
        {
            "event_id": merged["event_id"],
            "contract_id": merged["market_id"],
            "event_date": merged["event_date"],
            "timestamp": pd.to_datetime(merged["timestamp"], utc=True),
            "yes_bid": merged["yes_bid_close"],
            "yes_ask": merged["yes_ask_close"],
            "midpoint_probability": merged["probability_mid"],
            "volume": merged["volume_interval"],
            "open_interest": merged["open_interest"],
            "close_time": pd.to_datetime(merged["close_at"], utc=True),
            "resolution": merged["result"].astype("string").str.lower(),
            "resolved_yes": merged["outcome"].astype(bool),
            "bucket_label": merged["subtitle"].replace("", pd.NA).fillna(merged["market_id"]),
        }
    )
    snapshots = (
        snapshots[SNAPSHOT_COLUMNS]
        .sort_values(["event_date", "contract_id", "timestamp"])
        .reset_index(drop=True)
    )
    snapshots.attrs["excluded_missing_prices"] = excluded_missing_prices
    return snapshots


def write_market_snapshots(
    snapshots: pd.DataFrame,
    output_path: str | Path,
    *,
    source_retrieval_dates: list[str] | None = None,
) -> tuple[Path, Path]:
    """Write the canonical CSV plus a compact processed-file manifest."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshots.to_csv(path, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    manifest_path = path.with_suffix(".manifest.json")
    payload = {
        "manifest_version": 1,
        "source": "kalshi",
        "series_id": "KXHIGHNY",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_retrieval_dates": sorted(set(source_retrieval_dates or [])),
        "rows": len(snapshots),
        "events": int(snapshots["event_id"].nunique()),
        "contracts": int(snapshots["contract_id"].nunique()),
        "excluded_missing_prices": int(snapshots.attrs.get("excluded_missing_prices", 0)),
        "file": path.name,
        "sha256": sha256_file(path),
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n")
    return path, manifest_path
