"""Leakage-safe paired-horizon revision targets and public feature rows."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from pm_efficiency.analysis.fixed_horizon_calibration import select_fixed_horizon_quotes

PAIR_DEFINITIONS = ((24, 12), (12, 6), (6, 1))

NUMERIC_FEATURES = [
    "midpoint_probability",
    "bid_ask_spread",
    "volume",
    "open_interest",
    "delta_p_1h",
    "delta_p_6h",
    "delta_p_24h",
    "volatility_6h",
    "volatility_24h",
    "volume_6h",
    "volume_24h",
    "time_to_close",
]

CATEGORICAL_FEATURES = ["bucket_label"]


def build_paired_revision_panel(
    snapshots: pd.DataFrame,
    efficiency_panel: pd.DataFrame,
    *,
    pairs: Iterable[tuple[int, int]] = PAIR_DEFINITIONS,
    max_staleness_hours: float = 2,
) -> pd.DataFrame:
    """Pair fixed-horizon quotes and attach only features timestamped at the now quote."""
    pair_definitions = tuple((int(now), int(later)) for now, later in pairs)
    if any(now <= later for now, later in pair_definitions):
        raise ValueError("each pair must move from a larger to a smaller pre-close horizon")
    horizons = sorted({horizon for pair in pair_definitions for horizon in pair}, reverse=True)
    selected = select_fixed_horizon_quotes(
        snapshots,
        horizons=horizons,
        max_staleness_hours=max_staleness_hours,
    )

    snapshot_metadata = snapshots[
        ["event_id", "contract_id", "event_date", "bucket_label"]
    ].drop_duplicates()
    if snapshot_metadata["contract_id"].duplicated().any():
        raise ValueError("contract metadata is not unique")
    snapshot_metadata["event_date"] = pd.to_datetime(
        snapshot_metadata["event_date"], errors="coerce"
    ).dt.date

    features = efficiency_panel.copy()
    features["timestamp"] = pd.to_datetime(features["timestamp"], utc=True).astype(
        "datetime64[ns, UTC]"
    )
    features = features.rename(
        columns={
            "market_id": "contract_id",
            "probability_mid": "midpoint_probability",
            "volume_interval": "volume",
            "time_to_resolution_hours": "time_to_close",
        }
    )
    feature_columns = [
        "contract_id",
        "timestamp",
        *NUMERIC_FEATURES,
    ]
    missing_features = sorted(set(feature_columns) - set(features.columns))
    if missing_features:
        raise ValueError(f"efficiency feature panel missing columns: {missing_features}")
    features = features[feature_columns]
    if features.duplicated(["contract_id", "timestamp"]).any():
        raise ValueError("efficiency features contain duplicate contract timestamps")

    outputs = []
    for now_horizon, later_horizon in pair_definitions:
        now = selected.loc[
            selected["forecast_horizon_hours"] == now_horizon,
            [
                "event_id",
                "contract_id",
                "target_time",
                "quote_timestamp",
                "staleness_hours",
                "probability",
            ],
        ].rename(
            columns={
                "target_time": "target_time_now",
                "quote_timestamp": "feature_timestamp",
                "staleness_hours": "now_staleness_hours",
                "probability": "probability_now",
            }
        )
        later = selected.loc[
            selected["forecast_horizon_hours"] == later_horizon,
            ["event_id", "contract_id", "target_time", "quote_timestamp", "probability"],
        ].rename(
            columns={
                "target_time": "target_time_later",
                "quote_timestamp": "quote_timestamp_later",
                "probability": "probability_later",
            }
        )
        paired = now.merge(
            later,
            on=["event_id", "contract_id"],
            how="inner",
            validate="one_to_one",
        )
        paired["feature_timestamp"] = pd.to_datetime(paired["feature_timestamp"], utc=True).astype(
            "datetime64[ns, UTC]"
        )
        paired = paired.merge(
            features,
            left_on=["contract_id", "feature_timestamp"],
            right_on=["contract_id", "timestamp"],
            how="left",
            validate="one_to_one",
        ).merge(
            snapshot_metadata,
            on=["event_id", "contract_id"],
            how="left",
            validate="many_to_one",
        )
        if paired["midpoint_probability"].isna().any():
            raise ValueError("selected now quotes did not match the public feature panel")
        if not np.allclose(
            paired["probability_now"], paired["midpoint_probability"], equal_nan=False
        ):
            raise ValueError("paired probability_now differs from the timestamped feature price")
        paired["now_horizon_hours"] = now_horizon
        paired["later_horizon_hours"] = later_horizon
        paired["pair"] = f"{now_horizon}h_to_{later_horizon}h"
        paired["delta_p"] = paired["probability_later"] - paired["probability_now"]
        paired["time_to_close"] = (
            pd.to_datetime(paired["target_time_now"], utc=True)
            + pd.to_timedelta(now_horizon, unit="h")
            - paired["feature_timestamp"]
        ).dt.total_seconds() / 3600
        if (paired["feature_timestamp"] > paired["target_time_now"]).any():
            raise ValueError("feature timestamp occurs after the now-horizon target")
        if (paired["quote_timestamp_later"] <= paired["feature_timestamp"]).any():
            raise ValueError("later quote does not occur after the public feature timestamp")
        outputs.append(paired)

    panel = pd.concat(outputs, ignore_index=True)
    if panel.duplicated(["pair", "contract_id"]).any():
        raise ValueError("paired panel contains duplicate contract/pair rows")
    return panel.sort_values(["event_date", "pair", "contract_id"]).reset_index(drop=True)
