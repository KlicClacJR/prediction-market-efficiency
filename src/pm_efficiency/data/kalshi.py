"""Small, unauthenticated client for Kalshi's public market-data API."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import httpx


class KalshiAPIError(RuntimeError):
    """Raised after a Kalshi request exhausts its retry budget."""


class KalshiClient:
    BASE_URL = "https://external-api.kalshi.com/trade-api/v2"

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30,
        max_retries: int = 4,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=base_url or self.BASE_URL,
            timeout=timeout,
            transport=transport,
            headers={"User-Agent": "pm-efficiency/0.1 (academic research)"},
        )

    def __enter__(self) -> KalshiClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.get(path, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                retryable = not isinstance(
                    exc, httpx.HTTPStatusError
                ) or exc.response.status_code in {429, 500, 502, 503, 504}
                if not retryable or attempt == self.max_retries:
                    break
                retry_after = 0.5 * (2**attempt)
                if isinstance(exc, httpx.HTTPStatusError):
                    retry_after = float(exc.response.headers.get("Retry-After", retry_after))
                time.sleep(retry_after)
        raise KalshiAPIError(f"GET {path} failed after retries: {last_error}") from last_error

    def _list_markets(
        self,
        series_ticker: str,
        status: str | None,
        page_size: int,
        historical: bool,
    ) -> list[dict[str, Any]]:
        path = "/historical/markets" if historical else "/markets"
        cursor = ""
        records: list[dict[str, Any]] = []
        while True:
            params: dict[str, Any] = {"series_ticker": series_ticker, "limit": page_size}
            if status and not historical:
                params["status"] = status
            if cursor:
                params["cursor"] = cursor
            payload = self._request(path, params)
            records.extend(payload.get("markets", []))
            cursor = payload.get("cursor") or ""
            if not cursor:
                return records

    def list_series_markets(
        self,
        series_ticker: str,
        status: str | None = None,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """List markets still present in Kalshi's live/recent partition."""
        return self._list_markets(series_ticker, status, page_size, historical=False)

    def list_historical_series_markets(
        self, series_ticker: str, page_size: int = 1000
    ) -> list[dict[str, Any]]:
        """List settled markets moved to Kalshi's historical partition."""
        return self._list_markets(series_ticker, None, page_size, historical=True)

    def get_historical_cutoff(self) -> dict[str, Any]:
        return self._request("/historical/cutoff")

    def get_market(self, market_ticker: str, historical: bool = False) -> dict[str, Any]:
        prefix = "/historical/markets" if historical else "/markets"
        return self._request(f"{prefix}/{market_ticker}").get("market", {})

    def get_candlesticks(
        self,
        market_ticker: str,
        start: int | datetime,
        end: int | datetime,
        interval: int = 60,
        *,
        series_ticker: str = "KXHIGHNY",
        historical: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch candles through the correct current or historical route."""
        if interval not in {1, 60, 1440}:
            raise ValueError("interval must be 1, 60, or 1440 minutes")
        start_ts = int(start.timestamp()) if isinstance(start, datetime) else int(start)
        end_ts = int(end.timestamp()) if isinstance(end, datetime) else int(end)
        if historical:
            path = f"/historical/markets/{market_ticker}/candlesticks"
        else:
            path = f"/series/{series_ticker}/markets/{market_ticker}/candlesticks"
        payload = self._request(
            path,
            {"start_ts": start_ts, "end_ts": end_ts, "period_interval": interval},
        )
        return payload.get("candlesticks", [])
