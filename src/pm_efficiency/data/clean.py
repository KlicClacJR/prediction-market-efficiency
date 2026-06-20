"""Normalize versioned Kalshi payloads into stable research tables."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pm_efficiency.schemas import MARKET_COLUMNS, OUTCOME_COLUMNS, PRICE_COLUMNS


def _utc(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, utc=True, errors="coerce")


def _number(value: Any) -> float:
    if value in (None, ""):
        return np.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def _nested_number(record: dict[str, Any], group: str, field: str) -> float:
    payload = record.get(group) or {}
    return _number(payload.get(f"{field}_dollars", payload.get(field)))


def _event_date(record: dict[str, Any], event_id: str, close_at: pd.Timestamp) -> object:
    occurrence = _utc(record.get("occurrence_datetime"))
    if not pd.isna(occurrence):
        return occurrence.tz_convert("America/New_York").date()
    match = re.search(r"-(\d{2}[A-Za-z]{3}\d{2})(?:-|$)", event_id)
    if match:
        try:
            return datetime.strptime(match.group(1).upper(), "%y%b%d").date()
        except ValueError:
            pass
    if not pd.isna(close_at):
        return close_at.tz_convert("America/New_York").date()
    return pd.NaT


def normalize_markets(
    raw_records: Iterable[dict[str, Any]],
    *,
    series_id: str = "KXHIGHNY",
    category: str = "Weather",
    retrieved_at: datetime | str | None = None,
) -> pd.DataFrame:
    """Map Kalshi market payloads to one row per binary contract."""
    fetched = pd.Timestamp(retrieved_at or datetime.now(UTC))
    if fetched.tzinfo is None:
        fetched = fetched.tz_localize("UTC")
    rows = []
    for record in raw_records:
        market_id = record.get("ticker")
        if not market_id:
            continue
        event_id = record.get("event_ticker", "")
        close_at = _utc(record.get("close_time") or record.get("expiration_time"))
        rows.append(
            {
                "source": "kalshi",
                "series_id": series_id,
                "event_id": event_id,
                "event_date": _event_date(record, event_id, close_at),
                "market_id": market_id,
                "title": record.get("title", ""),
                "subtitle": record.get("subtitle") or record.get("yes_sub_title", ""),
                "category": category,
                "market_type": record.get("market_type", "binary"),
                "strike_type": record.get("strike_type"),
                "floor_strike": _number(record.get("floor_strike")),
                "cap_strike": _number(record.get("cap_strike")),
                "created_at": _utc(record.get("created_time")),
                "open_at": _utc(record.get("open_time")),
                "close_at": close_at,
                "resolved_at": _utc(record.get("settlement_ts")),
                "status": str(record.get("status", "")).lower(),
                "result": str(record.get("result", "")).lower() or None,
                "settlement_value": _number(record.get("settlement_value_dollars")),
                "rules_primary": record.get("rules_primary", ""),
                "retrieved_at": fetched,
            }
        )
    frame = pd.DataFrame(rows, columns=MARKET_COLUMNS)
    if frame.empty:
        return frame
    return (
        frame.sort_values(["market_id", "retrieved_at"])
        .drop_duplicates("market_id", keep="last")
        .reset_index(drop=True)
    )


def normalize_candles(
    raw_records: Iterable[dict[str, Any]],
    market_id: str,
    *,
    interval_minutes: int = 60,
    retrieved_at: datetime | str | None = None,
) -> pd.DataFrame:
    """Normalize both current (`*_dollars`) and archived candle field names."""
    fetched = pd.Timestamp(retrieved_at or datetime.now(UTC))
    if fetched.tzinfo is None:
        fetched = fetched.tz_localize("UTC")
    rows = []
    for record in raw_records:
        timestamp = pd.to_datetime(record.get("end_period_ts"), unit="s", utc=True, errors="coerce")
        row: dict[str, Any] = {
            "market_id": market_id,
            "timestamp": timestamp,
            "interval_minutes": interval_minutes,
            "volume_interval": _number(record.get("volume_fp", record.get("volume"))),
            "open_interest": _number(record.get("open_interest_fp", record.get("open_interest"))),
            "liquidity_dollars": np.nan,
            "retrieved_at": fetched,
        }
        for prefix, group in (("yes_bid", "yes_bid"), ("yes_ask", "yes_ask")):
            for field in ("open", "low", "high", "close"):
                row[f"{prefix}_{field}"] = _nested_number(record, group, field)
        for field in ("open", "low", "high", "close", "mean", "previous"):
            row[f"trade_price_{field}"] = _nested_number(record, "price", field)
        bid, ask = row["yes_bid_close"], row["yes_ask_close"]
        row["probability_mid"] = (
            (bid + ask) / 2 if np.isfinite(bid) and np.isfinite(ask) else np.nan
        )
        row["bid_ask_spread"] = ask - bid if np.isfinite(bid) and np.isfinite(ask) else np.nan
        rows.append(row)
    frame = pd.DataFrame(rows, columns=PRICE_COLUMNS)
    if frame.empty:
        return frame
    return (
        frame.sort_values(["market_id", "timestamp", "retrieved_at"])
        .drop_duplicates(["market_id", "timestamp"], keep="last")
        .reset_index(drop=True)
    )


def extract_outcomes(markets: pd.DataFrame) -> pd.DataFrame:
    """Create an explicit outcome table while retaining exceptional resolutions."""
    if markets.empty:
        return pd.DataFrame(columns=OUTCOME_COLUMNS)
    result = markets["result"].astype("string").str.lower()
    valid = result.isin(["yes", "no"]) & markets["resolved_at"].notna()
    outcome = result.map({"yes": 1, "no": 0}).astype("Int64")
    frame = pd.DataFrame(
        {
            "market_id": markets["market_id"],
            "event_id": markets["event_id"],
            "result": result,
            "outcome": outcome,
            "settlement_value": markets["settlement_value"],
            "resolved_at": markets["resolved_at"],
            "resolution_source": "NWS Daily Climate Report",
            "is_valid_resolution": valid,
        }
    )
    return frame[OUTCOME_COLUMNS].reset_index(drop=True)


def load_raw_run(
    run_dir: str | Path,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Read one immutable raw run for deterministic downstream processing."""
    root = Path(run_dir)
    manifest = json.loads((root / "manifest.json").read_text())
    markets = json.loads((root / "markets.json").read_text())
    candles = {
        path.stem: json.loads(path.read_text())
        for path in sorted((root / "candles").glob("*.json"))
    }
    return markets, candles, manifest


def clean_raw_run(run_dir: str | Path, interim_dir: str | Path) -> tuple[Path, Path, Path]:
    """Normalize a raw run and write canonical Parquet tables."""
    markets_raw, candle_payloads, manifest = load_raw_run(run_dir)
    retrieved_at = manifest["retrieved_at"]
    markets = normalize_markets(
        markets_raw,
        series_id=manifest["series_id"],
        retrieved_at=retrieved_at,
    )
    frames = [
        normalize_candles(
            records,
            market_id,
            interval_minutes=manifest["candle_interval_minutes"],
            retrieved_at=retrieved_at,
        )
        for market_id, records in candle_payloads.items()
    ]
    candles = (
        pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=PRICE_COLUMNS)
    )
    outcomes = extract_outcomes(markets)
    target = Path(interim_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = (
        target / "markets.parquet",
        target / "outcomes.parquet",
        target / "price_history.parquet",
    )
    markets.to_parquet(paths[0], index=False)
    outcomes.to_parquet(paths[1], index=False)
    candles.to_parquet(paths[2], index=False)
    return paths
