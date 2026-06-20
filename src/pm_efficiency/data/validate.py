"""Data-contract checks with machine-readable diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_for_errors(self) -> None:
        if self.errors:
            raise ValueError("Data validation failed: " + "; ".join(self.errors))


def _required(frame: pd.DataFrame, names: set[str], report: ValidationReport) -> bool:
    missing = sorted(names - set(frame.columns))
    if missing:
        report.errors.append(f"missing columns: {missing}")
    return not missing


def validate_markets(markets: pd.DataFrame) -> ValidationReport:
    report = ValidationReport()
    required = {"market_id", "event_id", "market_type", "close_at", "status"}
    if not _required(markets, required, report):
        return report
    if markets["market_id"].duplicated().any():
        report.errors.append("market_id is not unique")
    if markets["market_id"].isna().any() or markets["event_id"].isna().any():
        report.errors.append("market/event identifiers contain null values")
    if markets["close_at"].isna().any():
        report.errors.append("close_at contains null values")
    non_binary = markets.loc[markets["market_type"] != "binary", "market_id"]
    if not non_binary.empty:
        report.warnings.append(f"{len(non_binary)} non-binary markets will be excluded")
    return report


def validate_candles(candles: pd.DataFrame) -> ValidationReport:
    report = ValidationReport()
    required = {
        "market_id",
        "timestamp",
        "probability_mid",
        "yes_bid_close",
        "yes_ask_close",
        "bid_ask_spread",
        "volume_interval",
        "open_interest",
    }
    if not _required(candles, required, report):
        return report
    if candles.duplicated(["market_id", "timestamp"]).any():
        report.errors.append("(market_id, timestamp) is not unique")
    valid_quotes = candles[["yes_bid_close", "yes_ask_close"]].notna().all(axis=1)
    crossed = valid_quotes & (candles["yes_bid_close"] > candles["yes_ask_close"])
    if crossed.any():
        report.errors.append(f"{int(crossed.sum())} candles have crossed quotes")
    probability = candles["probability_mid"].dropna()
    if not probability.between(0, 1).all():
        report.errors.append("probability_mid lies outside [0, 1]")
    if candles["timestamp"].isna().any():
        report.errors.append("timestamp contains null values")
    missing_quote_share = 1 - valid_quotes.mean() if len(candles) else 1.0
    if missing_quote_share:
        report.warnings.append(f"{missing_quote_share:.1%} of candles lack two-sided quotes")
    for column in ("volume_interval", "open_interest"):
        if (candles[column].dropna() < 0).any():
            report.errors.append(f"{column} contains negative values")
    return report


def validate_outcomes(outcomes: pd.DataFrame) -> ValidationReport:
    report = ValidationReport()
    required = {"market_id", "event_id", "outcome", "is_valid_resolution", "resolved_at"}
    if not _required(outcomes, required, report):
        return report
    if outcomes["market_id"].duplicated().any():
        report.errors.append("outcome market_id is not unique")
    valid = outcomes["is_valid_resolution"].fillna(False)
    if not outcomes.loc[valid, "outcome"].isin([0, 1]).all():
        report.errors.append("valid resolutions must map to binary outcomes")
    invalid_count = int((~valid).sum())
    if invalid_count:
        report.warnings.append(f"{invalid_count} unresolved/exceptional outcomes will be excluded")
    return report


def validate_market_snapshots(snapshots: pd.DataFrame) -> ValidationReport:
    """Validate the public processed snapshot contract before CSV persistence."""
    report = ValidationReport()
    required = {
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
    }
    if not _required(snapshots, required, report):
        return report
    missing_prices = snapshots[["yes_bid", "yes_ask", "midpoint_probability"]].isna().any(axis=1)
    if missing_prices.any():
        report.errors.append(f"{int(missing_prices.sum())} snapshots have missing prices")
    duplicates = snapshots.duplicated(["contract_id", "timestamp"])
    if duplicates.any():
        report.errors.append(f"{int(duplicates.sum())} duplicate contract timestamps")
    for column in ("yes_bid", "yes_ask", "midpoint_probability"):
        values = snapshots[column].dropna()
        if not values.between(0, 1).all():
            report.errors.append(f"{column} lies outside [0, 1]")
    crossed = snapshots["yes_bid"].notna() & (snapshots["yes_bid"] > snapshots["yes_ask"])
    if crossed.any():
        report.errors.append(f"{int(crossed.sum())} snapshots have crossed quotes")
    labels = snapshots["resolution"].astype("string").str.lower()
    invalid_labels = ~labels.isin(["yes", "no"])
    if invalid_labels.any():
        report.errors.append(f"{int(invalid_labels.sum())} invalid resolution labels")
    expected_yes = labels.eq("yes")
    resolved_yes = snapshots["resolved_yes"].astype("boolean")
    inconsistent = resolved_yes.isna() | resolved_yes.ne(expected_yes)
    if inconsistent.any():
        report.errors.append(f"{int(inconsistent.sum())} inconsistent resolved_yes values")
    return report
