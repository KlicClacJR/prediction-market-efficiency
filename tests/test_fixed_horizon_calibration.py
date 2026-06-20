import matplotlib
import numpy as np
import pandas as pd

from pm_efficiency.analysis.fixed_horizon_calibration import (
    run_fixed_horizon_calibration,
    select_fixed_horizon_quotes,
)

matplotlib.use("Agg")


def _snapshots():
    rows = []
    horizons = (24, 12, 6, 1)
    for event_number in range(4):
        event_id = f"E{event_number}"
        close = pd.Timestamp("2026-06-10T12:00:00Z") + pd.Timedelta(days=event_number)
        for contract_number in range(2):
            resolved_yes = contract_number == event_number % 2
            resolution = "yes" if resolved_yes else "no"
            for horizon in horizons:
                probability = 0.7 if resolved_yes else 0.3
                probability -= 0.005 * horizon
                target = close - pd.Timedelta(hours=horizon)
                for timestamp, midpoint in (
                    (target, probability),
                    (target + pd.Timedelta(minutes=30), 0.99),
                ):
                    rows.append(
                        {
                            "event_id": event_id,
                            "contract_id": f"{event_id}-C{contract_number}",
                            "event_date": close.date().isoformat(),
                            "timestamp": timestamp,
                            "yes_bid": midpoint - 0.01,
                            "yes_ask": midpoint + 0.01,
                            "midpoint_probability": midpoint,
                            "volume": 10 + event_number,
                            "open_interest": 100 + contract_number,
                            "close_time": close,
                            "resolution": resolution,
                            "resolved_yes": resolved_yes,
                            "bucket_label": f"bucket {contract_number}",
                        }
                    )
    return pd.DataFrame(rows)


def test_selects_latest_quote_before_each_horizon_without_lookahead():
    panel = select_fixed_horizon_quotes(_snapshots())
    assert len(panel) == 4 * 2 * 4
    assert set(panel["forecast_horizon_hours"]) == {24, 12, 6, 1}
    assert (panel["quote_timestamp"] == panel["target_time"]).all()
    assert not np.isclose(panel["probability"], 0.99).any()
    assert (panel["staleness_hours"] == 0).all()


def test_writes_metrics_deciles_and_reliability_diagram(tmp_path):
    metrics_path = tmp_path / "tables" / "calibration_metrics.csv"
    deciles_path = tmp_path / "tables" / "calibration_deciles.csv"
    figure_path = tmp_path / "figures" / "reliability_diagram.png"
    outputs = run_fixed_horizon_calibration(
        _snapshots(),
        bootstrap_iterations=25,
        seed=11,
        metrics_path=metrics_path,
        deciles_path=deciles_path,
        figure_path=figure_path,
    )
    metrics = outputs["metrics"]
    assert metrics["forecast_horizon_hours"].tolist() == [24, 12, 6, 1]
    assert {
        "brier_score",
        "brier_score_ci_lower",
        "brier_score_ci_upper",
        "log_loss",
        "log_loss_ci_lower",
        "log_loss_ci_upper",
        "ece",
        "ece_ci_lower",
        "ece_ci_upper",
    }.issubset(metrics.columns)
    assert np.isfinite(metrics[["brier_score", "log_loss", "ece"]]).all().all()
    deciles = outputs["calibration_deciles"]
    assert len(deciles) == 4 * 10
    assert deciles.groupby("forecast_horizon_hours")["count"].sum().eq(8).all()
    assert metrics_path.is_file() and deciles_path.is_file()
    assert figure_path.is_file() and figure_path.stat().st_size > 0
