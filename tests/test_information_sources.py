import numpy as np
import pandas as pd

from pm_efficiency.analysis.information_sources import (
    HORIZONS,
    INTERVALS,
    run_information_source_study,
)


def test_information_source_shares_and_middle_interval_activity():
    seasons = ("winter", "spring", "summer", "fall")
    regimes = ("cold", "mild", "hot")
    quartiles = ("Q1_low", "Q2", "Q3", "Q4_high")
    horizon_rows = []
    interval_rows = []
    for event in range(24):
        event_id = f"E{event:02d}"
        for hours in HORIZONS:
            horizon_rows.append(
                {
                    "event_id": event_id,
                    "market_id": f"{event_id}-M",
                    "forecast_horizon_hours": hours,
                    "volume_6h": 100 * (25 - hours),
                    "volume_24h": 200 * (25 - hours),
                    "open_interest": 300 * (25 - hours),
                }
            )
        for earlier, later in INTERVALS:
            middle = (earlier, later) == (12, 6)
            interval_rows.append(
                {
                    "event_id": event_id,
                    "market_id": f"{event_id}-M",
                    "interval": f"{earlier}h_to_{later}h",
                    "interval_hours": earlier - later,
                    "volume_per_hour": 100 if middle else 20,
                    "log_volume_6h_growth": 1 if middle else 0.2,
                    "open_interest_growth_per_hour": 50 if middle else 10,
                    "absolute_revision": 0.20 if middle else 0.05,
                    "brier_reduction": 0.10 if middle else 0.02,
                    "season": seasons[event % 4],
                    "temperature_regime": regimes[event % 3],
                    "liquidity_quartile_24h": quartiles[event % 4],
                }
            )
    result = run_information_source_study(
        pd.DataFrame(horizon_rows), pd.DataFrame(interval_rows), iterations=20, seed=9
    )
    tests = result["activity_tests"].set_index("metric")
    assert tests["middle_significantly_larger"].all()
    assert np.isclose(result["interval_summary"].share_absolute_revision.sum(), 1)
    for key, group_column in (
        ("seasonal", "season"),
        ("temperature_regime", "temperature_regime"),
        ("liquidity", "liquidity_quartile_24h"),
    ):
        sums = result[key].groupby(group_column).share_brier_reduction.sum()
        assert np.allclose(sums, 1)
