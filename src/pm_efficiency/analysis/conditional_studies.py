"""Liquidity, information-arrival, and extreme-event robustness studies."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from zlib import crc32

import numpy as np
import pandas as pd

from pm_efficiency.metrics.calibration import calibration_table, expected_calibration_error
from pm_efficiency.metrics.scoring import binary_log_loss, brier_score

HORIZONS = (24, 12, 6, 1)
LIQUIDITY_LABELS = ("Q1_low", "Q2", "Q3", "Q4_high")


def _metric(name: str, y: pd.Series, p: pd.Series, bins: int = 10) -> float:
    if name == "brier_score":
        return brier_score(y, p)
    if name == "log_loss":
        return binary_log_loss(y, p)
    if name == "ece":
        return expected_calibration_error(y, p, bins)
    raise ValueError(f"unknown metric: {name}")


def _cluster_draws(
    frame: pd.DataFrame,
    statistic: Callable[[pd.DataFrame], float],
    *,
    iterations: int,
    seed: int,
    cluster: str = "event_id",
) -> tuple[float, float, float]:
    cluster_codes, clusters = pd.factorize(frame[cluster], sort=False)
    cluster_count = len(clusters)
    if cluster_count < 2:
        raise ValueError("cluster inference requires at least two event clusters")
    rng = np.random.default_rng(seed)
    draws = np.empty(iterations)
    row_positions = np.arange(len(frame))
    for index in range(iterations):
        selected = rng.integers(0, cluster_count, cluster_count)
        multiplicity = np.bincount(selected, minlength=cluster_count)[cluster_codes]
        sample = frame.iloc[np.repeat(row_positions, multiplicity)]
        draws[index] = statistic(sample)
    return (
        float(statistic(frame)),
        float(np.quantile(draws, 0.025)),
        float(np.quantile(draws, 0.975)),
    )


def assign_liquidity_quartiles(panel: pd.DataFrame) -> pd.DataFrame:
    """Assign horizon-specific quartiles from trailing volume and open interest."""
    data = panel.copy()
    data["volume_24h"] = pd.to_numeric(data["volume_24h"], errors="coerce").fillna(0)
    data["open_interest"] = pd.to_numeric(data["open_interest"], errors="coerce").fillna(0)
    data["volume_rank"] = data.groupby("forecast_horizon_hours")["volume_24h"].rank(pct=True)
    data["open_interest_rank"] = data.groupby("forecast_horizon_hours")["open_interest"].rank(
        pct=True
    )
    data["liquidity_score"] = (data["volume_rank"] + data["open_interest_rank"]) / 2
    data["liquidity_quartile"] = data.groupby("forecast_horizon_hours", group_keys=False)[
        "liquidity_score"
    ].transform(
        lambda values: pd.qcut(values.rank(method="first"), 4, labels=LIQUIDITY_LABELS).astype(str)
    )
    return data


def run_liquidity_study(
    forecast_panel: pd.DataFrame,
    *,
    iterations: int = 1000,
    bins: int = 10,
    seed: int = 20260619,
) -> dict[str, pd.DataFrame]:
    data = assign_liquidity_quartiles(forecast_panel).rename(
        columns={"probability_mid": "probability"}
    )
    metrics = []
    reliability = []
    comparisons = []
    for horizon in HORIZONS:
        horizon_data = data[data.forecast_horizon_hours == horizon]
        for quartile_index, quartile in enumerate(LIQUIDITY_LABELS):
            sample = horizon_data[horizon_data.liquidity_quartile == quartile]
            row = {
                "forecast_horizon_hours": horizon,
                "liquidity_quartile": quartile,
                "observations": len(sample),
                "events": sample.event_id.nunique(),
                "median_volume_24h": sample.volume_24h.median(),
                "median_open_interest": sample.open_interest.median(),
            }
            for metric_index, metric_name in enumerate(("brier_score", "log_loss", "ece")):
                estimate, lower, upper = _cluster_draws(
                    sample,
                    lambda x, name=metric_name: _metric(name, x.outcome, x.probability, bins),
                    iterations=iterations,
                    seed=seed + horizon * 100 + quartile_index * 10 + metric_index,
                )
                row[metric_name] = estimate
                row[f"{metric_name}_ci_lower"] = lower
                row[f"{metric_name}_ci_upper"] = upper
            metrics.append(row)
            table = calibration_table(sample.outcome, sample.probability, bins)
            table.insert(0, "liquidity_quartile", quartile)
            table.insert(0, "forecast_horizon_hours", horizon)
            reliability.append(table)

        for metric_index, metric_name in enumerate(("brier_score", "log_loss", "ece")):
            subset = horizon_data[horizon_data.liquidity_quartile.isin(["Q1_low", "Q4_high"])]

            def difference(x: pd.DataFrame, name: str = metric_name) -> float:
                low = x[x.liquidity_quartile == "Q1_low"]
                high = x[x.liquidity_quartile == "Q4_high"]
                return _metric(name, low.outcome, low.probability, bins) - _metric(
                    name, high.outcome, high.probability, bins
                )

            estimate, lower, upper = _cluster_draws(
                subset,
                difference,
                iterations=iterations,
                seed=seed + 5000 + horizon * 10 + metric_index,
            )
            comparisons.append(
                {
                    "forecast_horizon_hours": horizon,
                    "metric": metric_name,
                    "low_minus_high": estimate,
                    "ci_lower": lower,
                    "ci_upper": upper,
                    "low_significantly_worse": bool(lower > 0),
                    "bootstrap_iterations": iterations,
                }
            )
    return {
        "metrics": pd.DataFrame(metrics),
        "reliability": pd.concat(reliability, ignore_index=True),
        "comparisons": pd.DataFrame(comparisons),
        "panel": data,
    }


def run_information_arrival_study(
    forecast_panel: pd.DataFrame,
    *,
    iterations: int = 1000,
    seed: int = 20260619,
) -> dict[str, pd.DataFrame]:
    keys = ["event_id", "market_id"]
    data = forecast_panel[forecast_panel.forecast_horizon_hours.isin(HORIZONS)].copy()
    complete = data.groupby(keys).forecast_horizon_hours.nunique()
    complete_keys = complete[complete == len(HORIZONS)].index
    data = data.set_index(keys).loc[complete_keys].reset_index()
    data["brier_loss"] = np.square(data.probability_mid - data.outcome)
    clipped = data.probability_mid.clip(1e-6, 1 - 1e-6)
    data["log_loss_value"] = -(
        data.outcome * np.log(clipped) + (1 - data.outcome) * np.log(1 - clipped)
    )

    score_rows = []
    for horizon in HORIZONS:
        sample = data[data.forecast_horizon_hours == horizon]
        row = {
            "forecast_horizon_hours": horizon,
            "observations": len(sample),
            "events": sample.event_id.nunique(),
        }
        for metric_index, column in enumerate(("brier_loss", "log_loss_value")):
            estimate, lower, upper = _cluster_draws(
                sample,
                lambda x, col=column: float(x[col].mean()),
                iterations=iterations,
                seed=seed + horizon * 10 + metric_index,
            )
            name = "brier_score" if column == "brier_loss" else "log_loss"
            row[name] = estimate
            row[f"{name}_ci_lower"] = lower
            row[f"{name}_ci_upper"] = upper
        score_rows.append(row)

    wide = data.pivot(index=keys, columns="forecast_horizon_hours")
    event_ids = wide.index.get_level_values("event_id")
    decomposition = []
    intervals = ((24, 12), (12, 6), (6, 1))
    total_brier = float((wide["brier_loss"][24] - wide["brier_loss"][1]).mean())
    total_log = float((wide["log_loss_value"][24] - wide["log_loss_value"][1]).mean())
    for interval_index, (earlier, later) in enumerate(intervals):
        interval_frame = pd.DataFrame(
            {
                "event_id": event_ids,
                "brier_reduction": wide["brier_loss"][earlier].to_numpy()
                - wide["brier_loss"][later].to_numpy(),
                "log_loss_reduction": wide["log_loss_value"][earlier].to_numpy()
                - wide["log_loss_value"][later].to_numpy(),
            }
        )
        row = {"interval": f"{earlier}h_to_{later}h", "earlier": earlier, "later": later}
        for metric_index, column in enumerate(("brier_reduction", "log_loss_reduction")):
            estimate, lower, upper = _cluster_draws(
                interval_frame,
                lambda x, col=column: float(x[col].mean()),
                iterations=iterations,
                seed=seed + 1000 + interval_index * 10 + metric_index,
            )
            row[column] = estimate
            row[f"{column}_ci_lower"] = lower
            row[f"{column}_ci_upper"] = upper
        row["share_total_brier_reduction"] = row["brier_reduction"] / total_brier
        row["share_total_log_loss_reduction"] = row["log_loss_reduction"] / total_log
        decomposition.append(row)
    return {
        "scores": pd.DataFrame(score_rows),
        "decomposition": pd.DataFrame(decomposition),
        "balanced_panel": data,
    }


def derive_temperature_events(
    markets: pd.DataFrame, training_end: object
) -> tuple[pd.DataFrame, dict]:
    """Reconstruct a conservative realized-temperature proxy from winning bucket strikes."""
    winners = markets[(markets.result == "yes") & markets.strike_type.notna()].copy()
    counts = winners.groupby("event_id").size()
    winners = winners[winners.event_id.isin(counts[counts == 1].index)].copy()
    winners["temperature_proxy"] = np.select(
        [
            winners.strike_type.eq("between"),
            winners.strike_type.eq("less"),
            winners.strike_type.eq("greater"),
        ],
        [
            (winners.floor_strike + winners.cap_strike) / 2,
            winners.cap_strike - 1,
            winners.floor_strike + 1,
        ],
        default=np.nan,
    )
    events = winners[["event_id", "event_date", "temperature_proxy", "strike_type"]].dropna()
    events["event_date"] = pd.to_datetime(events.event_date).dt.date
    cutoff = pd.Timestamp(training_end).date()
    training = events[events.event_date <= cutoff]
    lower = float(training.temperature_proxy.quantile(0.10))
    upper = float(training.temperature_proxy.quantile(0.90))
    events["extreme_group"] = np.where(
        (events.temperature_proxy <= lower) | (events.temperature_proxy >= upper),
        "extreme",
        "normal",
    )
    return events, {
        "training_end": str(cutoff),
        "training_events": len(training),
        "lower_percentile": lower,
        "upper_percentile": upper,
        "events_with_temperature_proxy": len(events),
        "censored_tail_winners": int(events.strike_type.isin(["less", "greater"]).sum()),
    }


def run_extreme_study(
    forecast_panel: pd.DataFrame,
    markets: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    iterations: int = 1000,
    bins: int = 10,
    seed: int = 20260619,
) -> dict[str, pd.DataFrame | dict]:
    test_start = pd.to_datetime(predictions.event_date).min().date()
    events, thresholds = derive_temperature_events(
        markets, pd.Timestamp(test_start) - pd.Timedelta(days=1)
    )
    event_groups = events[["event_id", "extreme_group"]]
    calibration = forecast_panel.merge(event_groups, on="event_id", how="inner")
    calibration_rows = []
    calibration_tests = []
    for horizon in HORIZONS:
        horizon_data = calibration[calibration.forecast_horizon_hours == horizon]
        for group_index, group in enumerate(("normal", "extreme")):
            sample = horizon_data[horizon_data.extreme_group == group]
            row = {
                "forecast_horizon_hours": horizon,
                "extreme_group": group,
                "observations": len(sample),
                "events": sample.event_id.nunique(),
            }
            for metric_index, metric_name in enumerate(("brier_score", "log_loss", "ece")):
                estimate, lower, upper = _cluster_draws(
                    sample,
                    lambda x, name=metric_name: _metric(name, x.outcome, x.probability_mid, bins),
                    iterations=iterations,
                    seed=seed + horizon * 100 + group_index * 10 + metric_index,
                )
                row[metric_name] = estimate
                row[f"{metric_name}_ci_lower"] = lower
                row[f"{metric_name}_ci_upper"] = upper
            calibration_rows.append(row)
        for metric_index, metric_name in enumerate(("brier_score", "log_loss", "ece")):

            def difference(x: pd.DataFrame, name: str = metric_name) -> float:
                extreme = x[x.extreme_group == "extreme"]
                normal = x[x.extreme_group == "normal"]
                return _metric(name, extreme.outcome, extreme.probability_mid, bins) - _metric(
                    name, normal.outcome, normal.probability_mid, bins
                )

            estimate, lower, upper = _cluster_draws(
                horizon_data,
                difference,
                iterations=iterations,
                seed=seed + 4000 + horizon * 10 + metric_index,
            )
            calibration_tests.append(
                {
                    "forecast_horizon_hours": horizon,
                    "metric": metric_name,
                    "extreme_minus_normal": estimate,
                    "ci_lower": lower,
                    "ci_upper": upper,
                    "extreme_significantly_worse": bool(lower > 0),
                }
            )

    efficiency = predictions.merge(event_groups, on="event_id", how="inner")
    efficiency_rows = []
    for (pair, model, group), sample in efficiency.groupby(
        ["pair", "model", "extreme_group"], sort=False
    ):
        actual = sample.actual_revision.to_numpy()
        predicted = sample.predicted_revision.to_numpy()
        baseline_mse = float(np.mean(np.square(actual)))
        loss = sample[["event_id"]].copy()
        loss["loss_difference"] = np.square(actual - predicted) - np.square(actual)
        estimate, lower, upper = _cluster_draws(
            loss,
            lambda x: float(x.loss_difference.mean()),
            iterations=iterations,
            seed=seed + crc32(f"{pair}|{model}|{group}".encode()) % 10000,
        )
        efficiency_rows.append(
            {
                "pair": pair,
                "model": model,
                "extreme_group": group,
                "observations": len(sample),
                "events": sample.event_id.nunique(),
                "oos_r2_vs_zero": 1 - np.mean(np.square(actual - predicted)) / baseline_mse
                if baseline_mse > 0
                else np.nan,
                "rmse": np.sqrt(np.mean(np.square(actual - predicted))),
                "baseline_rmse": np.sqrt(baseline_mse),
                "squared_loss_difference": estimate,
                "ci_lower": lower,
                "ci_upper": upper,
            }
        )
    return {
        "temperature_events": events,
        "thresholds": thresholds,
        "calibration_metrics": pd.DataFrame(calibration_rows),
        "calibration_tests": pd.DataFrame(calibration_tests),
        "efficiency_metrics": pd.DataFrame(efficiency_rows),
    }


def write_frame(frame: pd.DataFrame, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination, index=False)
