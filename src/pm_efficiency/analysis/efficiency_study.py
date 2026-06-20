"""End-to-end revision-predictability study tables."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import pandas as pd

from pm_efficiency.models.efficiency import (
    DEFAULT_PREDICTORS,
    adjust_pvalues,
    evaluate_revision_predictions,
    fit_revision_model,
    test_martingale_difference,
)


def run_efficiency_analysis(
    panel: pd.DataFrame,
    *,
    horizons: Iterable[int] = (1, 6),
    predictors: Sequence[str] | None = None,
    minimum_training_events: int = 60,
    output_dir: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    predictors = list(predictors or DEFAULT_PREDICTORS)
    coefficient_rows = []
    test_rows = []
    prediction_rows = []
    performance_rows = []
    for horizon in horizons:
        model = fit_revision_model(panel, horizon, predictors)
        confidence = model.conf_int()
        for term in model.params.index:
            coefficient_rows.append(
                {
                    "horizon_hours": horizon,
                    "term": term,
                    "coefficient": model.params[term],
                    "std_error": model.bse[term],
                    "pvalue": model.pvalues[term],
                    "ci_lower": confidence.loc[term, 0],
                    "ci_upper": confidence.loc[term, 1],
                    "n": int(model.nobs),
                }
            )
        test_rows.append(test_martingale_difference(panel, horizon, predictors))
        predictions, performance = evaluate_revision_predictions(
            panel, horizon, predictors, minimum_training_events
        )
        predictions.insert(0, "horizon_hours", horizon)
        prediction_rows.append(predictions)
        performance_rows.append({"horizon_hours": horizon, **performance})
    coefficients = pd.DataFrame(coefficient_rows)
    if not coefficients.empty:
        coefficients["pvalue_adjusted_bh"] = adjust_pvalues(coefficients["pvalue"])
    tests = pd.DataFrame(test_rows)
    if not tests.empty:
        tests["joint_zero_pvalue_adjusted_bh"] = adjust_pvalues(tests["joint_zero_pvalue"])
    outputs = {
        "coefficients": coefficients,
        "martingale_tests": tests,
        "oos_predictions": pd.concat(prediction_rows, ignore_index=True),
        "oos_performance": pd.DataFrame(performance_rows),
    }
    if output_dir is not None:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        for name, frame in outputs.items():
            frame.to_csv(target / f"{name}.csv", index=False)
    return outputs
