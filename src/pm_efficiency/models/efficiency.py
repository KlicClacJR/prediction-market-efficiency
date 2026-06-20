"""Interpretable market-efficiency and martingale diagnostics."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import combine_pvalues
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.stats.multitest import multipletests

DEFAULT_PREDICTORS = [
    "probability_mid",
    "delta_p_1h",
    "delta_p_6h",
    "momentum_6h",
    "volatility_6h",
    "volume_6h",
    "open_interest",
    "bid_ask_spread",
    "time_to_resolution_hours",
]


def _model_data(
    panel: pd.DataFrame,
    horizon_hours: int,
    predictors: Sequence[str],
) -> tuple[pd.DataFrame, str]:
    target = f"future_revision_{horizon_hours}h"
    required = [target, "event_id", *predictors]
    missing = set(required) - set(panel.columns)
    if missing:
        raise ValueError(f"efficiency panel missing columns: {sorted(missing)}")
    data = panel[required].replace([np.inf, -np.inf], np.nan).dropna().copy()
    if data.empty:
        raise ValueError("no complete observations for the efficiency model")
    return data, target


def fit_revision_model(
    panel: pd.DataFrame,
    horizon_hours: int = 1,
    predictors: Sequence[str] | None = None,
):
    """Fit OLS with event-clustered covariance whenever at least two events exist."""
    predictors = list(predictors or DEFAULT_PREDICTORS)
    data, target = _model_data(panel, horizon_hours, predictors)
    design = sm.add_constant(data[predictors].astype(float), has_constant="add")
    model = sm.OLS(data[target].astype(float), design)
    if data["event_id"].nunique() >= 2:
        return model.fit(cov_type="cluster", cov_kwds={"groups": data["event_id"]})
    return model.fit(cov_type="HC1")


def evaluate_revision_predictions(
    panel: pd.DataFrame,
    horizon_hours: int = 1,
    predictors: Sequence[str] | None = None,
    minimum_training_events: int = 60,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Expanding-window predictions in strict event-date order."""
    predictors = list(predictors or DEFAULT_PREDICTORS)
    data, target = _model_data(panel, horizon_hours, predictors)
    ordering_column = "close_at" if "close_at" in panel.columns else "timestamp"
    order = (
        panel[["event_id", ordering_column]]
        .dropna()
        .groupby("event_id")[ordering_column]
        .min()
        .sort_values()
    )
    events = order.index.tolist()
    rows = []
    for position in range(minimum_training_events, len(events)):
        train_events = events[:position]
        test_event = events[position]
        train = data.loc[data["event_id"].isin(train_events)]
        test = data.loc[data["event_id"] == test_event]
        if train.empty or test.empty:
            continue
        estimator = make_pipeline(StandardScaler(), LinearRegression())
        estimator.fit(train[predictors], train[target])
        prediction = estimator.predict(test[predictors])
        batch = pd.DataFrame(
            {
                "event_id": test_event,
                "actual_revision": test[target].to_numpy(),
                "predicted_revision": prediction,
                "martingale_prediction": 0.0,
            }
        )
        rows.append(batch)
    predictions = (
        pd.concat(rows, ignore_index=True)
        if rows
        else pd.DataFrame(
            columns=["event_id", "actual_revision", "predicted_revision", "martingale_prediction"]
        )
    )
    if predictions.empty:
        return predictions, {
            "n": 0,
            "events": 0,
            "oos_r2_vs_zero": np.nan,
            "mae": np.nan,
            "zero_mae": np.nan,
        }
    residual = predictions["actual_revision"] - predictions["predicted_revision"]
    baseline_residual = predictions["actual_revision"]
    baseline_sse = float(np.square(baseline_residual).sum())
    metrics = {
        "n": int(len(predictions)),
        "events": int(predictions["event_id"].nunique()),
        "oos_r2_vs_zero": (
            float(1 - np.square(residual).sum() / baseline_sse) if baseline_sse else np.nan
        ),
        "mae": float(np.abs(residual).mean()),
        "zero_mae": float(np.abs(baseline_residual).mean()),
    }
    return predictions, metrics


def test_martingale_difference(
    panel: pd.DataFrame,
    horizon_hours: int = 1,
    predictors: Sequence[str] | None = None,
    ljung_box_lags: int = 10,
) -> dict[str, float]:
    """Test zero conditional mean plus serial correlation in probability revisions."""
    predictors = list(predictors or DEFAULT_PREDICTORS)
    model = fit_revision_model(panel, horizon_hours, predictors)
    joint = model.wald_test(np.eye(len(model.params)), scalar=True)
    target = f"future_revision_{horizon_hours}h"
    grouping = "market_id" if "market_id" in panel else "event_id"
    ljung_box_pvalues = []
    for _, group in panel.groupby(grouping):
        revisions = group.sort_values("timestamp")[target].dropna()
        effective_lags = min(ljung_box_lags, max(1, len(revisions) // 5))
        if len(revisions) > effective_lags + 1:
            ljung_box = acorr_ljungbox(revisions, lags=[effective_lags], return_df=True)
            ljung_box_pvalues.append(float(ljung_box["lb_pvalue"].iloc[0]))
    lb_pvalue = (
        float(combine_pvalues(ljung_box_pvalues, method="fisher").pvalue)
        if ljung_box_pvalues
        else np.nan
    )
    return {
        "horizon_hours": horizon_hours,
        "n": int(model.nobs),
        "events": int(panel["event_id"].nunique()),
        "intercept": float(model.params.get("const", np.nan)),
        "intercept_pvalue": float(model.pvalues.get("const", np.nan)),
        "joint_zero_pvalue": float(np.asarray(joint.pvalue).squeeze()),
        "ljung_box_pvalue": lb_pvalue,
    }


def adjust_pvalues(
    values: Sequence[float],
    method: str = "fdr_bh",
) -> np.ndarray:
    """Benjamini-Hochberg adjustment by default, preserving missing entries."""
    array = np.asarray(values, dtype=float)
    output = np.full_like(array, np.nan)
    valid = np.isfinite(array)
    if valid.any():
        output[valid] = multipletests(array[valid], method=method)[1]
    return output
