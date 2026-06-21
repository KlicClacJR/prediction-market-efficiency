"""Archived forecast-run and NOAA observation acquisition for Central Park."""

from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

OPEN_METEO_URL = "https://single-runs-api.open-meteo.com/v1/forecast"
NCEI_URL = "https://www.ncei.noaa.gov/access/services/data/v1"
CENTRAL_PARK_LATITUDE = 40.7789
CENTRAL_PARK_LONGITUDE = -73.9692
CENTRAL_PARK_STATION = "USW00094728"
MODEL = "ecmwf_ifs"
ARCHIVE_START = pd.Timestamp("2024-03-14", tz="UTC")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def latest_available_run(as_of: object, publication_lag_hours: int = 6) -> pd.Timestamp:
    """Select the latest main 00Z/12Z ECMWF cycle public by an as-of time."""
    available_initialization = pd.Timestamp(as_of).tz_convert("UTC") - pd.Timedelta(
        hours=publication_lag_hours
    )
    return available_initialization.floor("12h")


def build_forecast_requests(
    markets: pd.DataFrame,
    *,
    horizons: tuple[int, ...] = (24, 12, 6),
    publication_lag_hours: int = 6,
) -> pd.DataFrame:
    resolved = markets[markets.result.isin(["yes", "no"])]
    events = resolved[["event_id", "event_date", "close_at"]].drop_duplicates("event_id").copy()
    events["event_date"] = pd.to_datetime(events.event_date).dt.date
    events["close_at"] = pd.to_datetime(events.close_at, utc=True)
    rows = []
    for event in events.itertuples(index=False):
        for horizon in horizons:
            as_of = event.close_at - pd.Timedelta(hours=horizon)
            run = latest_available_run(as_of, publication_lag_hours)
            if run < ARCHIVE_START:
                continue
            rows.append(
                {
                    "event_id": event.event_id,
                    "event_date": event.event_date,
                    "forecast_horizon_hours": horizon,
                    "market_as_of": as_of,
                    "run_initialization": run,
                    "assumed_available_at": run + pd.Timedelta(hours=publication_lag_hours),
                }
            )
    return pd.DataFrame(rows)


def _request_json(
    client: httpx.Client,
    url: str,
    params: dict[str, Any],
    *,
    retries: int = 5,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            last_error = exc
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            if status == 400 and isinstance(exc, httpx.HTTPStatusError):
                return exc.response.json()
            if status not in {429, 500, 502, 503, 504} or attempt == retries:
                break
            time.sleep(min(30, 1.5 * 2**attempt))
    raise RuntimeError(f"weather request failed: {last_error}") from last_error


def fetch_weather_archive(
    requests: pd.DataFrame,
    output_dir: str | Path,
    *,
    max_workers: int = 4,
) -> Path:
    """Fetch unique ECMWF runs and NOAA actuals into a hash-verified cache."""
    root = Path(output_dir)
    runs_dir = root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    unique_runs = sorted(pd.to_datetime(requests.run_initialization, utc=True).unique())
    client = httpx.Client(timeout=90, headers={"User-Agent": "pm-efficiency/0.1 research"})

    def fetch_run(run_value: object) -> dict[str, Any]:
        run = pd.Timestamp(run_value).tz_convert("UTC")
        name = run.strftime("%Y%m%dT%HZ.json")
        path = runs_dir / name
        if path.exists():
            try:
                payload = json.loads(path.read_text())
                if payload.get("hourly", {}).get("temperature_2m"):
                    return {
                        "path": str(path.relative_to(root)),
                        "cached": True,
                        "unavailable": False,
                    }
                if payload.get("error"):
                    return {
                        "path": str(path.relative_to(root)),
                        "cached": True,
                        "unavailable": True,
                    }
            except (json.JSONDecodeError, OSError):
                pass
        payload = _request_json(
            client,
            OPEN_METEO_URL,
            {
                "latitude": CENTRAL_PARK_LATITUDE,
                "longitude": CENTRAL_PARK_LONGITUDE,
                "run": run.strftime("%Y-%m-%dT%H:00"),
                "hourly": "temperature_2m",
                "models": MODEL,
                "temperature_unit": "fahrenheit",
                "timezone": "UTC",
                "forecast_hours": 48,
            },
        )
        path.write_text(json.dumps(payload, sort_keys=True))
        return {
            "path": str(path.relative_to(root)),
            "cached": False,
            "unavailable": bool(payload.get("error")),
        }

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            run_entries = list(executor.map(fetch_run, unique_runs))
        start = min(requests.event_date).isoformat()
        end = max(requests.event_date).isoformat()
        actual_path = root / "noaa_central_park_actuals.json"
        actuals = _request_json(
            client,
            NCEI_URL,
            {
                "dataset": "daily-summaries",
                "stations": CENTRAL_PARK_STATION,
                "startDate": start,
                "endDate": end,
                "format": "json",
                "units": "standard",
                "includeAttributes": "false",
            },
        )
        actual_path.write_text(json.dumps(actuals, sort_keys=True))
    finally:
        client.close()

    files = []
    for entry in run_entries:
        path = root / entry["path"]
        files.append(
            {
                "path": entry["path"],
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    files.append(
        {
            "path": actual_path.name,
            "sha256": sha256_file(actual_path),
            "bytes": actual_path.stat().st_size,
        }
    )
    manifest = {
        "retrieved_at": datetime.now(UTC).isoformat(),
        "forecast_source": OPEN_METEO_URL,
        "forecast_model": MODEL,
        "model_run_count": len(unique_runs),
        "unavailable_model_runs": sum(entry["unavailable"] for entry in run_entries),
        "observation_source": NCEI_URL,
        "station": CENTRAL_PARK_STATION,
        "files": files,
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest_path


def verify_weather_manifest(manifest_path: str | Path) -> None:
    path = Path(manifest_path)
    manifest = json.loads(path.read_text())
    errors = []
    for entry in manifest["files"]:
        target = path.parent / entry["path"]
        if not target.exists():
            errors.append(f"missing {entry['path']}")
        elif sha256_file(target) != entry["sha256"]:
            errors.append(f"hash mismatch {entry['path']}")
    if errors:
        raise ValueError("weather manifest verification failed: " + "; ".join(errors))


def load_forecast_vintages(
    requests: pd.DataFrame,
    archive_dir: str | Path,
) -> pd.DataFrame:
    root = Path(archive_dir)
    actuals = pd.DataFrame(json.loads((root / "noaa_central_park_actuals.json").read_text()))
    actuals["event_date"] = pd.to_datetime(actuals.DATE).dt.date
    actuals["realized_high_f"] = pd.to_numeric(actuals.TMAX, errors="coerce")
    actual_map = actuals.set_index("event_date").realized_high_f
    rows = []
    for request in requests.itertuples(index=False):
        run = pd.Timestamp(request.run_initialization).tz_convert("UTC")
        path = root / "runs" / run.strftime("%Y%m%dT%HZ.json")
        payload = json.loads(path.read_text())
        if payload.get("error") or not payload.get("hourly"):
            continue
        hourly = pd.DataFrame(payload["hourly"])
        hourly["time"] = pd.to_datetime(hourly.time, utc=True).dt.tz_convert("America/New_York")
        valid = hourly[hourly.time.dt.date == request.event_date]
        forecast_high = pd.to_numeric(valid.temperature_2m, errors="coerce").max()
        rows.append(
            {
                **request._asdict(),
                "forecast_high_f": forecast_high,
                "realized_high_f": actual_map.get(request.event_date, float("nan")),
                "source_model": MODEL,
                "grid_latitude": payload.get("latitude"),
                "grid_longitude": payload.get("longitude"),
            }
        )
    return pd.DataFrame(rows)
