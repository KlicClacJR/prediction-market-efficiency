import json

import pandas as pd

from pm_efficiency.data.snapshots import (
    SNAPSHOT_COLUMNS,
    build_market_snapshots,
    write_market_snapshots,
)
from pm_efficiency.data.validate import validate_market_snapshots


def _tables():
    markets = pd.DataFrame(
        {
            "market_id": ["M1", "M2"],
            "event_id": ["E1", "E1"],
            "event_date": [pd.Timestamp("2026-06-19").date()] * 2,
            "close_at": [pd.Timestamp("2026-06-20T05:00:00Z")] * 2,
            "subtitle": ["80° to 81°", "82° or above"],
        }
    )
    outcomes = pd.DataFrame(
        {
            "market_id": ["M1", "M2"],
            "event_id": ["E1", "E1"],
            "result": ["yes", "no"],
            "outcome": pd.Series([1, 0], dtype="Int64"),
            "is_valid_resolution": [True, True],
        }
    )
    candles = pd.DataFrame(
        {
            "market_id": ["M1", "M1", "M2"],
            "timestamp": pd.to_datetime(
                ["2026-06-19T12:00:00Z", "2026-06-19T13:00:00Z", "2026-06-19T12:00:00Z"]
            ),
            "yes_bid_close": [0.40, None, 0.55],
            "yes_ask_close": [0.44, None, 0.59],
            "probability_mid": [0.42, None, 0.57],
            "volume_interval": [10.0, 0.0, 7.0],
            "open_interest": [100.0, 100.0, 80.0],
            "retrieved_at": pd.to_datetime(["2026-06-20T00:00:00Z"] * 3),
        }
    )
    return candles, markets, outcomes


def test_builds_exact_resolved_snapshot_schema_and_filters_missing_quotes():
    snapshots = build_market_snapshots(*_tables())
    assert snapshots.columns.tolist() == SNAPSHOT_COLUMNS
    assert len(snapshots) == 2
    assert snapshots.attrs["excluded_missing_prices"] == 1
    assert snapshots.set_index("contract_id").loc["M1", "resolved_yes"]
    assert snapshots.set_index("contract_id").loc["M2", "resolution"] == "no"
    assert validate_market_snapshots(snapshots).ok


def test_snapshot_validation_detects_all_requested_failures():
    snapshots = build_market_snapshots(*_tables())
    broken = pd.concat([snapshots, snapshots.iloc[[0]]], ignore_index=True)
    broken.loc[0, "midpoint_probability"] = 1.2
    broken.loc[1, "yes_bid"] = None
    broken.loc[1, "resolution"] = "void"
    report = validate_market_snapshots(broken)
    assert not report.ok
    assert any("missing prices" in error for error in report.errors)
    assert any("duplicate contract timestamps" in error for error in report.errors)
    assert any("outside [0, 1]" in error for error in report.errors)
    assert any("invalid resolution labels" in error for error in report.errors)


def test_writes_csv_and_hashed_processed_manifest(tmp_path):
    snapshots = build_market_snapshots(*_tables())
    csv_path, manifest_path = write_market_snapshots(
        snapshots,
        tmp_path / "market_snapshots.csv",
        source_retrieval_dates=["2026-06-20"],
    )
    manifest = json.loads(manifest_path.read_text())
    assert csv_path.is_file()
    assert manifest["rows"] == 2
    assert manifest["excluded_missing_prices"] == 1
    assert len(manifest["sha256"]) == 64
    assert pd.read_csv(csv_path).columns.tolist() == SNAPSHOT_COLUMNS
