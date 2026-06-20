import httpx

from pm_efficiency.config import PathsConfig, ProjectConfig
from pm_efficiency.data.ingest import fetch_series_history, verify_raw_manifest
from pm_efficiency.data.kalshi import KalshiClient


def test_current_and_historical_candles_use_distinct_routes():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"candlesticks": []})

    client = KalshiClient(transport=httpx.MockTransport(handler), max_retries=0)
    client.get_candlesticks("M1", 1, 2, series_ticker="KXHIGHNY", historical=False)
    client.get_candlesticks("M2", 1, 2, series_ticker="KXHIGHNY", historical=True)
    client.close()
    assert paths == [
        "/trade-api/v2/series/KXHIGHNY/markets/M1/candlesticks",
        "/trade-api/v2/historical/markets/M2/candlesticks",
    ]


def test_market_listing_follows_cursor_pagination():
    cursors = []

    def handler(request):
        cursor = request.url.params.get("cursor", "")
        cursors.append(cursor)
        if not cursor:
            return httpx.Response(200, json={"markets": [{"ticker": "M1"}], "cursor": "next"})
        return httpx.Response(200, json={"markets": [{"ticker": "M2"}], "cursor": ""})

    client = KalshiClient(transport=httpx.MockTransport(handler), max_retries=0)
    markets = client.list_series_markets("KXHIGHNY")
    client.close()
    assert [market["ticker"] for market in markets] == ["M1", "M2"]
    assert cursors == ["", "next"]


def test_ingestion_routes_markets_around_historical_cutoff(tmp_path):
    class FakeClient:
        calls = []
        ranges = {}

        def get_historical_cutoff(self):
            return {"market_settled_ts": "2026-01-15T00:00:00Z"}

        def list_series_markets(self, *args, **kwargs):
            return [
                {
                    "ticker": "NEW",
                    "open_time": "2026-01-20T00:00:00Z",
                    "close_time": "2026-02-01T04:59:00Z",
                    "settlement_ts": "2026-02-01T12:00:00Z",
                }
            ]

        def list_historical_series_markets(self, *args, **kwargs):
            return [
                {
                    "ticker": "OLD",
                    "open_time": "2026-01-01T00:00:00Z",
                    "close_time": "2026-01-02T00:00:00Z",
                    "settlement_ts": "2026-01-03T00:00:00Z",
                }
            ]

        def get_candlesticks(self, ticker, start, end, interval, **kwargs):
            self.calls.append((ticker, kwargs["historical"]))
            self.ranges[ticker] = (start, end)
            return []

    config = ProjectConfig(
        project_name="test",
        fetch={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        paths=PathsConfig(
            raw=tmp_path / "raw",
            interim=tmp_path / "interim",
            processed=tmp_path / "processed",
            figures=tmp_path / "figures",
            tables=tmp_path / "tables",
        ),
    )
    fake = FakeClient()
    run = fetch_series_history(config, client=fake)
    assert (run / "manifest.json").exists()
    verify_raw_manifest(run)
    assert fake.calls == [("OLD", True), ("NEW", False)]
    assert fake.ranges["NEW"][1].isoformat() == "2026-02-01T04:59:00+00:00"

    (run / "markets.json").write_text("tampered")
    try:
        verify_raw_manifest(run)
    except ValueError as exc:
        assert "hash mismatch: markets.json" in str(exc)
    else:
        raise AssertionError("tampered raw data should fail hash verification")
