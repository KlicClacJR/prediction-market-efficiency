import numpy as np
import pandas as pd

from pm_efficiency.analysis.conditional_studies import (
    HORIZONS,
    assign_liquidity_quartiles,
    derive_temperature_events,
    run_information_arrival_study,
)


def test_liquidity_quartiles_are_horizon_specific_and_balanced():
    rows = []
    for horizon in HORIZONS:
        for index in range(8):
            rows.append(
                {
                    "forecast_horizon_hours": horizon,
                    "volume_24h": index * (25 - horizon),
                    "open_interest": index,
                }
            )
    result = assign_liquidity_quartiles(pd.DataFrame(rows))
    counts = result.groupby(["forecast_horizon_hours", "liquidity_quartile"]).size()
    assert (counts == 2).all()


def test_information_arrival_decomposition_telescopes_on_matched_contracts():
    rows = []
    for event in range(12):
        outcome = event % 2
        for contract in range(2):
            for horizon, error in zip(HORIZONS, (0.30, 0.20, 0.10, 0.05), strict=True):
                probability = outcome - error if outcome else error
                rows.append(
                    {
                        "event_id": f"E{event}",
                        "market_id": f"E{event}-C{contract}",
                        "forecast_horizon_hours": horizon,
                        "probability_mid": probability,
                        "outcome": outcome,
                    }
                )
    result = run_information_arrival_study(pd.DataFrame(rows), iterations=20)
    decomposition = result["decomposition"]
    scores = result["scores"].set_index("forecast_horizon_hours")
    assert len(result["balanced_panel"]) == 12 * 2 * 4
    assert np.isclose(
        decomposition.brier_reduction.sum(),
        scores.loc[24, "brier_score"] - scores.loc[1, "brier_score"],
    )
    assert np.isclose(decomposition.share_total_brier_reduction.sum(), 1)


def test_extreme_thresholds_use_training_events_only():
    rows = []
    for index in range(24):
        date = pd.Timestamp("2024-01-01") + pd.Timedelta(days=index)
        floor = 30 + index
        rows.append(
            {
                "event_id": f"E{index}",
                "event_date": date.date(),
                "result": "yes",
                "strike_type": "between",
                "floor_strike": floor,
                "cap_strike": floor + 1,
            }
        )
    markets = pd.DataFrame(rows)
    _, original = derive_temperature_events(markets, "2024-01-20")
    markets.loc[markets.event_date > pd.Timestamp("2024-01-20").date(), "floor_strike"] = 200
    markets.loc[markets.event_date > pd.Timestamp("2024-01-20").date(), "cap_strike"] = 201
    _, changed = derive_temperature_events(markets, "2024-01-20")
    assert original["lower_percentile"] == changed["lower_percentile"]
    assert original["upper_percentile"] == changed["upper_percentile"]
