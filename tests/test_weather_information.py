import pandas as pd

from pm_efficiency.analysis.weather_information import build_weather_revision_table
from pm_efficiency.data.weather_forecasts import latest_available_run


def test_latest_available_run_uses_main_cycle_and_publication_lag():
    as_of = pd.Timestamp("2025-05-01T17:00:00Z")
    assert latest_available_run(as_of, publication_lag_hours=6) == pd.Timestamp(
        "2025-05-01T00:00:00Z"
    )
    as_of_later = pd.Timestamp("2025-05-01T23:00:00Z")
    assert latest_available_run(as_of_later, publication_lag_hours=6) == pd.Timestamp(
        "2025-05-01T12:00:00Z"
    )


def test_weather_revision_table_uses_only_complete_vintages():
    rows = []
    for event, realized, forecasts in (
        ("E1", 70.0, {24: 66.0, 12: 68.0, 6: 69.0}),
        ("E2", 80.0, {24: 76.0, 12: 79.0}),
    ):
        for horizon, forecast in forecasts.items():
            rows.append(
                {
                    "event_id": event,
                    "event_date": pd.Timestamp("2025-05-01").date(),
                    "realized_high_f": realized,
                    "forecast_horizon_hours": horizon,
                    "forecast_high_f": forecast,
                    "run_initialization": pd.Timestamp("2025-04-30T12:00:00Z"),
                    "assumed_available_at": pd.Timestamp("2025-04-30T18:00:00Z"),
                }
            )
    result = build_weather_revision_table(pd.DataFrame(rows))
    assert result.event_id.tolist() == ["E1"]
    row = result.iloc[0]
    assert row.forecast_revision_24h_to_12h_f == 2
    assert row.forecast_revision_12h_to_6h_f == 1
    assert row.forecast_error_reduction_24h_to_12h_f == 2
    assert row.forecast_error_reduction_12h_to_6h_f == 1
