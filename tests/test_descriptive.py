import pandas as pd

from pm_efficiency.analysis.descriptive import (
    SUMMARY_COLUMNS,
    build_descriptive_summary,
    write_descriptive_summary,
)


def _snapshots():
    return pd.DataFrame(
        {
            "event_id": ["E1", "E1", "E1", "E1", "E2"],
            "contract_id": ["C1", "C2", "C1", "C2", "C3"],
            "event_date": ["2026-06-18"] * 4 + ["2026-06-19"],
            "timestamp": [
                "2026-06-18T12:00:00Z",
                "2026-06-18T12:00:00Z",
                "2026-06-18T13:00:00Z",
                "2026-06-18T13:00:00Z",
                "2026-06-19T12:00:00Z",
            ],
            "yes_bid": [0.35, 0.55, 0.40, 0.50, 0.60],
            "yes_ask": [0.39, 0.59, 0.44, 0.54, 0.64],
            "midpoint_probability": [0.37, 0.57, 0.42, 0.52, 0.62],
            "volume": [10.0, 20.0, 15.0, 25.0, None],
            "open_interest": [100.0, 80.0, 105.0, 85.0, 90.0],
            "close_time": ["2026-06-19T05:00:00Z"] * 4 + ["2026-06-20T05:00:00Z"],
            "resolution": ["yes", "no", "yes", "no", "yes"],
            "resolved_yes": [True, False, True, False, True],
            "bucket_label": ["A", "B", "A", "B", "C"],
        }
    )


def test_descriptive_summary_contains_requested_sections_and_event_sums():
    summary = build_descriptive_summary(_snapshots())
    assert summary.columns.tolist() == SUMMARY_COLUMNS
    metrics = summary.set_index("metric")["value"]
    assert metrics.loc["event_count"] == 2
    assert metrics.loc["contract_count"] == 3
    assert metrics.loc["first_event_date"] == "2026-06-18"
    assert metrics.loc["last_event_date"] == "2026-06-19"
    assert {
        "missingness",
        "midpoint_probability_summary",
        "spread_summary",
        "activity_summary",
        "event_probability_sums",
    }.issubset(summary["section"])
    event_sums = summary.loc[summary["section"] == "event_probability_sums"]
    first_sum = event_sums.loc[event_sums["timestamp"].str.contains("12:00:00")].iloc[0]
    assert first_sum["value"] == 0.94
    assert first_sum["contracts_observed"] == 2


def test_writes_default_shape_to_requested_path(tmp_path):
    input_path = tmp_path / "market_snapshots.csv"
    output_path = tmp_path / "reports" / "tables" / "descriptive_summary.csv"
    _snapshots().to_csv(input_path, index=False)
    result = write_descriptive_summary(input_path, output_path)
    assert result == output_path
    assert pd.read_csv(result).columns.tolist() == SUMMARY_COLUMNS
