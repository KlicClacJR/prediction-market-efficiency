"""Leakage-safe fixed-horizon and revision-prediction panels."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


def _asof_value(
    timestamps: pd.Series,
    values: pd.Series,
    targets: pd.Series,
    *,
    direction: str,
    tolerance: pd.Timedelta,
) -> np.ndarray:
    valid = timestamps.notna() & values.notna()
    if not valid.any():
        return np.full(len(targets), np.nan)
    right = pd.DataFrame({"timestamp": timestamps[valid], "value": values[valid]}).sort_values(
        "timestamp"
    )
    left = pd.DataFrame({"target": targets, "_order": np.arange(len(targets))}).sort_values(
        "target"
    )
    merged = pd.merge_asof(
        left,
        right,
        left_on="target",
        right_on="timestamp",
        direction=direction,
        tolerance=tolerance,
        allow_exact_matches=True,
    ).sort_values("_order")
    return merged["value"].to_numpy()


def engineer_market_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Create trailing features using only information available at each row timestamp."""
    if panel.empty:
        return panel.copy()
    required = {"market_id", "timestamp", "probability_mid", "volume_interval"}
    missing = required - set(panel.columns)
    if missing:
        raise ValueError(f"feature panel missing columns: {sorted(missing)}")
    result = panel.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    result = result.sort_values(["market_id", "timestamp"]).reset_index(drop=True)
    pieces = []
    for _, group in result.groupby("market_id", sort=False):
        group = group.copy().sort_values("timestamp")
        timestamp = group["timestamp"]
        probability = group["probability_mid"]
        for hours in (1, 6, 24):
            target = timestamp - pd.Timedelta(hours=hours)
            lagged = _asof_value(
                timestamp,
                probability,
                target,
                direction="backward",
                tolerance=pd.Timedelta(minutes=15),
            )
            group[f"delta_p_{hours}h"] = probability.to_numpy() - lagged

        indexed = group.set_index("timestamp")
        hourly_change = indexed["delta_p_1h"]
        group["momentum_6h"] = hourly_change.rolling("6h", min_periods=2).mean().to_numpy()
        group["volatility_6h"] = hourly_change.rolling("6h", min_periods=2).std(ddof=1).to_numpy()
        group["volatility_24h"] = hourly_change.rolling("24h", min_periods=3).std(ddof=1).to_numpy()
        volume = pd.to_numeric(indexed["volume_interval"], errors="coerce")
        group["volume_6h"] = volume.rolling("6h", min_periods=1).sum().to_numpy()
        group["volume_24h"] = volume.rolling("24h", min_periods=1).sum().to_numpy()
        pieces.append(group)
    result = pd.concat(pieces, ignore_index=True)
    if "close_at" in result:
        result["close_at"] = pd.to_datetime(result["close_at"], utc=True)
        result["time_to_resolution_hours"] = (
            result["close_at"] - result["timestamp"]
        ).dt.total_seconds() / 3600
    result["quote_missing"] = result["probability_mid"].isna()
    result["spread_missing"] = result.get(
        "bid_ask_spread", pd.Series(np.nan, index=result.index)
    ).isna()
    return result


def build_efficiency_panel(
    candles: pd.DataFrame,
    markets: pd.DataFrame,
    future_horizons_hours: Iterable[int] = (1, 6),
) -> pd.DataFrame:
    """Build an hourly panel with future revisions as targets, never as predictors."""
    metadata = markets[["market_id", "event_id", "close_at"]].drop_duplicates("market_id")
    panel = candles.merge(metadata, on="market_id", how="inner", validate="many_to_one")
    panel = panel.loc[panel["timestamp"] <= panel["close_at"]].copy()
    panel = engineer_market_features(panel)
    pieces = []
    for _, group in panel.groupby("market_id", sort=False):
        group = group.copy().sort_values("timestamp")
        for horizon in future_horizons_hours:
            target = group["timestamp"] + pd.Timedelta(hours=horizon)
            future = _asof_value(
                group["timestamp"],
                group["probability_mid"],
                target,
                direction="forward",
                tolerance=pd.Timedelta(minutes=15),
            )
            group[f"future_probability_{horizon}h"] = future
            group[f"future_revision_{horizon}h"] = future - group["probability_mid"].to_numpy()
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True) if pieces else panel


def build_fixed_horizon_panel(
    candles: pd.DataFrame,
    markets: pd.DataFrame,
    outcomes: pd.DataFrame,
    horizons: Iterable[int] = (24, 12, 6, 1),
    max_staleness_hours: float = 2,
) -> pd.DataFrame:
    """Select the final quote at or before each fixed pre-close horizon."""
    valid_outcomes = outcomes.loc[outcomes["is_valid_resolution"].fillna(False)].copy()
    metadata = markets[["market_id", "event_id", "close_at"]].merge(
        valid_outcomes[["market_id", "outcome", "resolved_at"]],
        on="market_id",
        how="inner",
        validate="one_to_one",
    )
    enriched = candles.merge(
        metadata[["market_id", "event_id", "close_at"]],
        on="market_id",
        how="inner",
        validate="many_to_one",
    )
    enriched = engineer_market_features(enriched)
    rows = []
    for market in metadata.itertuples(index=False):
        history = enriched.loc[
            (enriched["market_id"] == market.market_id) & enriched["probability_mid"].notna()
        ].sort_values("timestamp")
        if history.empty:
            continue
        for horizon in horizons:
            target = market.close_at - pd.Timedelta(hours=horizon)
            eligible = history.loc[history["timestamp"] <= target]
            if eligible.empty:
                continue
            selected = eligible.iloc[-1].copy()
            staleness = (target - selected["timestamp"]).total_seconds() / 3600
            if staleness > max_staleness_hours:
                continue
            selected["forecast_horizon_hours"] = int(horizon)
            selected["target_asof"] = target
            selected["staleness_hours"] = staleness
            selected["quote_stale"] = staleness > 1
            selected["outcome"] = int(market.outcome)
            selected["resolved_at"] = market.resolved_at
            rows.append(selected)
    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame(rows).reset_index(drop=True)
    return normalize_event_probabilities(result)


def normalize_event_probabilities(panel: pd.DataFrame) -> pd.DataFrame:
    """Add event-normalized probabilities without replacing raw midpoint probabilities."""
    if panel.empty:
        return panel.copy()
    result = panel.copy()
    group_columns = ["event_id"]
    if "forecast_horizon_hours" in result:
        group_columns.append("forecast_horizon_hours")
    event_sum = result.groupby(group_columns, dropna=False)["probability_mid"].transform("sum")
    result["event_probability_sum"] = event_sum
    result["probability_normalized"] = np.where(
        event_sum > 0, result["probability_mid"] / event_sum, np.nan
    )
    return result
