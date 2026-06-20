"""Canonical columns and typed records for persisted research data."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

MARKET_COLUMNS = [
    "source",
    "series_id",
    "event_id",
    "event_date",
    "market_id",
    "title",
    "subtitle",
    "category",
    "market_type",
    "strike_type",
    "floor_strike",
    "cap_strike",
    "created_at",
    "open_at",
    "close_at",
    "resolved_at",
    "status",
    "result",
    "settlement_value",
    "rules_primary",
    "retrieved_at",
]

OUTCOME_COLUMNS = [
    "market_id",
    "event_id",
    "result",
    "outcome",
    "settlement_value",
    "resolved_at",
    "resolution_source",
    "is_valid_resolution",
]

PRICE_COLUMNS = [
    "market_id",
    "timestamp",
    "interval_minutes",
    "yes_bid_open",
    "yes_bid_low",
    "yes_bid_high",
    "yes_bid_close",
    "yes_ask_open",
    "yes_ask_low",
    "yes_ask_high",
    "yes_ask_close",
    "trade_price_open",
    "trade_price_low",
    "trade_price_high",
    "trade_price_close",
    "trade_price_mean",
    "trade_price_previous",
    "probability_mid",
    "bid_ask_spread",
    "volume_interval",
    "open_interest",
    "liquidity_dollars",
    "retrieved_at",
]


class CanonicalModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class MarketRecord(CanonicalModel):
    source: str = "kalshi"
    series_id: str
    event_id: str
    event_date: date | None = None
    market_id: str
    title: str = ""
    subtitle: str = ""
    category: str = "Weather"
    market_type: str = "binary"
    strike_type: str | None = None
    floor_strike: float | None = None
    cap_strike: float | None = None
    created_at: datetime | None = None
    open_at: datetime | None = None
    close_at: datetime
    resolved_at: datetime | None = None
    status: str
    result: str | None = None
    settlement_value: float | None = None
    rules_primary: str = ""
    retrieved_at: datetime


class OutcomeRecord(CanonicalModel):
    market_id: str
    event_id: str
    result: str
    outcome: int = Field(ge=0, le=1)
    settlement_value: float | None = None
    resolved_at: datetime | None = None
    resolution_source: str = "NWS Daily Climate Report"
    is_valid_resolution: bool = True


class PriceRecord(CanonicalModel):
    market_id: str
    timestamp: datetime
    interval_minutes: int
    probability_mid: float | None = Field(default=None, ge=0, le=1)
    bid_ask_spread: float | None = Field(default=None, ge=0, le=1)
    volume_interval: float | None = Field(default=None, ge=0)
    open_interest: float | None = Field(default=None, ge=0)
    liquidity_dollars: float | None = Field(default=None, ge=0)
    retrieved_at: datetime
