import numpy as np
import pandas as pd

from pm_efficiency.analysis.paired_efficiency_study import run_paired_efficiency_study
from pm_efficiency.features.revision_pairs import NUMERIC_FEATURES
from pm_efficiency.models.revision_prediction import (
    chronological_event_split,
    paired_event_block_bootstrap,
)


def _predictable_panel(events=80, contracts_per_event=4):
    rng = np.random.default_rng(17)
    rows = []
    for event_number in range(events):
        event_date = (pd.Timestamp("2025-01-01") + pd.Timedelta(days=event_number)).date()
        for contract_number in range(contracts_per_event):
            signal = rng.normal()
            probability = rng.uniform(0.1, 0.9)
            delta = 0.08 * signal + rng.normal(scale=0.015)
            row = {
                "event_id": f"E{event_number:03d}",
                "event_date": event_date,
                "contract_id": f"E{event_number:03d}-C{contract_number}",
                "pair": "24h_to_12h",
                "now_horizon_hours": 24,
                "later_horizon_hours": 12,
                "probability_now": probability,
                "probability_later": probability + delta,
                "delta_p": delta,
                "bucket_label": f"bucket-{contract_number % 2}",
                "midpoint_probability": probability,
                "bid_ask_spread": 0.02,
                "volume": 10 + contract_number,
                "open_interest": 100 + event_number,
                "delta_p_1h": signal,
                "delta_p_6h": signal / 2,
                "delta_p_24h": np.nan if event_number % 9 == 0 else signal / 3,
                "volatility_6h": 0.02,
                "volatility_24h": 0.03,
                "volume_6h": 60.0,
                "volume_24h": 240.0,
                "time_to_close": 24.0,
            }
            rows.append(row)
    return pd.DataFrame(rows)


def test_chronological_split_keeps_dates_and_events_disjoint():
    panel = _predictable_panel(events=20)
    split = chronological_event_split(panel, train_fraction=0.7, minimum_training_events=10)
    assert len(split.train_dates) == 14
    assert len(split.test_dates) == 6
    assert max(split.train_dates) < min(split.test_dates)
    assert set(split.train_dates).isdisjoint(split.test_dates)


def test_predictable_public_signal_beats_zero_out_of_sample(tmp_path):
    panel = _predictable_panel()
    split = chronological_event_split(panel, train_fraction=0.75, minimum_training_events=50)
    outputs = run_paired_efficiency_study(
        panel,
        split,
        bootstrap_iterations=200,
        block_length_events=5,
        random_forest_min_events=1000,
        random_forest_min_observations=10000,
        metrics_path=tmp_path / "efficiency_metrics.csv",
        coefficients_path=tmp_path / "efficiency_coefficients.csv",
        predictions_path=tmp_path / "efficiency_predictions.csv",
        report_path=tmp_path / "efficiency_report.md",
    )
    metrics = outputs["metrics"].set_index("model")
    assert metrics.loc["linear_regression", "oos_r2_vs_zero"] > 0.8
    assert metrics.loc["ridge_regression", "oos_r2_vs_zero"] > 0.8
    assert metrics.loc["linear_regression", "squared_loss_difference"] < 0
    assert metrics.loc["random_forest", "model_status"] == "skipped"
    assert set(NUMERIC_FEATURES).issubset(panel.columns)
    assert not outputs["coefficients"].empty
    assert (tmp_path / "efficiency_report.md").is_file()


def test_weekly_block_bootstrap_detects_lower_paired_loss():
    losses = pd.DataFrame(
        {
            "event_date": np.repeat(pd.date_range("2025-01-01", periods=28), 3),
            "loss_diff": -0.02 + np.tile([-0.001, 0, 0.001], 28),
        }
    )
    result = paired_event_block_bootstrap(
        losses,
        differential_column="loss_diff",
        iterations=500,
        block_length=7,
        seed=5,
    )
    assert result["mean_difference"] < 0
    assert result["ci_upper"] < 0
    assert result["pvalue"] < 0.05
