"""Reproducible raw acquisition for a complete Kalshi series."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any

from pm_efficiency.config import ProjectConfig
from pm_efficiency.data.kalshi import KalshiClient


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _write_json(path: Path, payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, indent=2, default=str).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Hash a file in chunks so large raw candle files remain cheap to verify."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_raw_manifest(run_dir: str | Path) -> None:
    """Raise when a raw file is missing or no longer matches its recorded hash."""
    root = Path(run_dir)
    manifest = json.loads((root / "manifest.json").read_text())
    errors = []
    for entry in manifest.get("files", []):
        path = root / entry["path"]
        if not path.is_file():
            errors.append(f"missing raw file: {entry['path']}")
        elif sha256_file(path) != entry["sha256"]:
            errors.append(f"hash mismatch: {entry['path']}")
    if errors:
        raise ValueError("Raw manifest verification failed: " + "; ".join(errors))


def fetch_series_history(
    config: ProjectConfig,
    client: KalshiClient | None = None,
) -> Path:
    """Fetch metadata and candles, preserving an immutable timestamped raw run.

    Returns the run directory. Existing runs are never overwritten because the
    directory name includes microseconds.
    """
    config.ensure_output_directories()
    retrieved_at = datetime.now(UTC)
    run_id = retrieved_at.strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = Path(config.paths.raw) / "kalshi" / config.series_id / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    own_client = client is None
    api = client or KalshiClient(
        timeout=config.fetch.timeout_seconds,
        max_retries=config.fetch.max_retries,
    )
    files: list[dict[str, Any]] = []
    try:
        cutoff_payload = api.get_historical_cutoff()
        cutoff = _parse_timestamp(cutoff_payload.get("market_settled_ts"))
        live = api.list_series_markets(config.series_id, page_size=config.fetch.page_size)
        historical = api.list_historical_series_markets(
            config.series_id, page_size=config.fetch.page_size
        )
        by_ticker = {m["ticker"]: m for m in historical + live if m.get("ticker")}
        markets = list(by_ticker.values())
        files.append(
            {
                "path": "cutoff.json",
                "sha256": _write_json(run_dir / "cutoff.json", cutoff_payload),
            }
        )
        files.append(
            {
                "path": "markets.json",
                "sha256": _write_json(run_dir / "markets.json", markets),
            }
        )

        config_start = datetime.combine(config.fetch.start_date, time.min, tzinfo=UTC)
        config_end = (
            datetime.combine(config.fetch.end_date, time.max, tzinfo=UTC)
            if config.fetch.end_date
            else retrieved_at
        )
        for market in markets:
            ticker = market["ticker"]
            open_at = _parse_timestamp(market.get("open_time") or market.get("created_time"))
            close_at = _parse_timestamp(market.get("close_time") or market.get("expiration_time"))
            settled_at = _parse_timestamp(market.get("settlement_ts"))
            start = max(filter(None, [config_start, open_at]))
            end = min(filter(None, [config_end, close_at]))
            if start >= end:
                continue
            use_historical = bool(cutoff and settled_at and settled_at < cutoff)
            candles = api.get_candlesticks(
                ticker,
                start,
                end,
                config.candle_interval_minutes,
                series_ticker=config.series_id,
                historical=use_historical,
            )
            relative = f"candles/{ticker}.json"
            files.append(
                {
                    "path": relative,
                    "sha256": _write_json(run_dir / relative, candles),
                    "partition": "historical" if use_historical else "live",
                    "records": len(candles),
                }
            )
        manifest = {
            "manifest_version": 1,
            "source": "kalshi",
            "series_id": config.series_id,
            "retrieved_at": retrieved_at.isoformat(),
            "retrieval_date": retrieved_at.date().isoformat(),
            "candle_interval_minutes": config.candle_interval_minutes,
            "market_count": len(markets),
            "files": files,
        }
        _write_json(run_dir / "manifest.json", manifest)
        return run_dir
    finally:
        if own_client:
            api.close()
