import numpy as np
import pandas as pd

from pm_efficiency.features.market_features import (
    build_efficiency_panel,
    build_fixed_horizon_panel,
)


def _data():
    timestamps = pd.date_range("2026-01-01", periods=50, freq="h", tz="UTC")
    candles = pd.DataFrame(
        {
            "market_id": "M1",
            "timestamp": timestamps,
            "probability_mid": np.linspace(0.2, 0.7, len(timestamps)),
            "bid_ask_spread": 0.02,
            "volume_interval": 5.0,
            "open_interest": 100.0,
        }
    )
    markets = pd.DataFrame(
        {
            "market_id": ["M1"],
            "event_id": ["E1"],
            "close_at": [timestamps[-1] + pd.Timedelta(hours=1)],
        }
    )
    outcomes = pd.DataFrame(
        {
            "market_id": ["M1"],
            "outcome": [1],
            "resolved_at": [timestamps[-1] + pd.Timedelta(hours=2)],
            "is_valid_resolution": [True],
        }
    )
    return candles, markets, outcomes


def test_future_change_cannot_alter_past_features():
    candles, markets, _ = _data()
    original = build_efficiency_panel(candles, markets)
    changed = candles.copy()
    changed.loc[changed.index[-1], "probability_mid"] = 0.01
    perturbed = build_efficiency_panel(changed, markets)
    cutoff = candles.timestamp.iloc[-2]
    columns = ["delta_p_1h", "delta_p_6h", "momentum_6h", "volatility_6h", "volume_6h"]
    pd.testing.assert_frame_equal(
        original.loc[original.timestamp <= cutoff, columns].reset_index(drop=True),
        perturbed.loc[perturbed.timestamp <= cutoff, columns].reset_index(drop=True),
    )


def test_fixed_horizon_uses_last_quote_at_or_before_target():
    candles, markets, outcomes = _data()
    panel = build_fixed_horizon_panel(
        candles, markets, outcomes, horizons=[1], max_staleness_hours=2
    )
    assert len(panel) == 1
    assert panel.iloc[0].timestamp == candles.timestamp.iloc[-1]
    assert panel.iloc[0].outcome == 1


def test_features_accept_mixed_datetime_precision():
    candles, markets, _ = _data()
    candles["timestamp"] = candles["timestamp"].astype("datetime64[ms, UTC]")
    markets["close_at"] = markets["close_at"].astype("datetime64[us, UTC]")
    panel = build_efficiency_panel(candles, markets)
    assert panel["delta_p_1h"].notna().any()
