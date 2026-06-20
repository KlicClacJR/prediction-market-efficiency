import numpy as np
import pandas as pd

from pm_efficiency.features.revision_pairs import (
    NUMERIC_FEATURES,
    build_paired_revision_panel,
)


def _paired_inputs(events=3, contracts_per_event=2):
    snapshot_rows = []
    feature_rows = []
    horizons = (24, 12, 6, 1)
    for event_number in range(events):
        event_id = f"E{event_number:02d}"
        event_date = pd.Timestamp("2026-01-01") + pd.Timedelta(days=event_number)
        close = event_date.tz_localize("UTC") + pd.Timedelta(days=1, hours=5)
        for contract_number in range(contracts_per_event):
            contract_id = f"{event_id}-C{contract_number}"
            for horizon in horizons:
                timestamp = close - pd.Timedelta(hours=horizon)
                probability = (
                    0.2 + 0.02 * event_number + 0.01 * contract_number + 0.001 * (24 - horizon)
                )
                snapshot_rows.append(
                    {
                        "event_id": event_id,
                        "contract_id": contract_id,
                        "event_date": event_date.date().isoformat(),
                        "timestamp": timestamp,
                        "yes_bid": probability - 0.01,
                        "yes_ask": probability + 0.01,
                        "midpoint_probability": probability,
                        "volume": 10.0,
                        "open_interest": 100.0,
                        "close_time": close,
                        "resolution": "yes" if contract_number == 0 else "no",
                        "resolved_yes": contract_number == 0,
                        "bucket_label": f"bucket-{contract_number}",
                    }
                )
                feature_rows.append(
                    {
                        "event_id": event_id,
                        "market_id": contract_id,
                        "timestamp": timestamp,
                        "probability_mid": probability,
                        "bid_ask_spread": 0.02,
                        "volume_interval": 10.0,
                        "open_interest": 100.0,
                        "delta_p_1h": 0.01,
                        "delta_p_6h": 0.02,
                        "delta_p_24h": 0.03,
                        "volatility_6h": 0.01,
                        "volatility_24h": 0.02,
                        "volume_6h": 60.0,
                        "volume_24h": 240.0,
                        "time_to_resolution_hours": float(horizon),
                    }
                )
    return pd.DataFrame(snapshot_rows), pd.DataFrame(feature_rows)


def test_paired_targets_and_features_are_timestamped_at_now_quote():
    snapshots, features = _paired_inputs()
    panel = build_paired_revision_panel(snapshots, features)
    assert set(panel["pair"]) == {"24h_to_12h", "12h_to_6h", "6h_to_1h"}
    assert len(panel) == 3 * 2 * 3
    sample = panel.loc[panel["pair"] == "24h_to_12h"].iloc[0]
    assert sample["midpoint_probability"] == sample["probability_now"]
    assert np.isclose(sample["delta_p"], 0.012)
    assert sample["feature_timestamp"] <= sample["target_time_now"]
    assert sample["quote_timestamp_later"] > sample["feature_timestamp"]
    assert not panel.duplicated(["pair", "contract_id"]).any()
    assert set(NUMERIC_FEATURES).issubset(panel.columns)


def test_later_feature_changes_cannot_modify_earlier_pair_features():
    snapshots, features = _paired_inputs()
    original = build_paired_revision_panel(snapshots, features)
    contract = snapshots["contract_id"].iloc[0]
    close = pd.to_datetime(snapshots.loc[snapshots.contract_id == contract, "close_time"].iloc[0])
    later_timestamp = close - pd.Timedelta(hours=12)
    features.loc[
        (features.market_id == contract) & (features.timestamp == later_timestamp),
        "volume_interval",
    ] = 99999
    changed = build_paired_revision_panel(snapshots, features)
    before = original.loc[
        (original.contract_id == contract) & (original.pair == "24h_to_12h"), "volume"
    ].iloc[0]
    after = changed.loc[
        (changed.contract_id == contract) & (changed.pair == "24h_to_12h"), "volume"
    ].iloc[0]
    assert before == after == 10
