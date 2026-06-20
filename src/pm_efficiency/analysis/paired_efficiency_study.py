"""Chronological paired-horizon tests of weak-form prediction-market efficiency."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pm_efficiency.features.revision_pairs import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_paired_revision_panel,
)
from pm_efficiency.models.efficiency import adjust_pvalues
from pm_efficiency.models.revision_prediction import (
    ChronologicalSplit,
    chronological_event_split,
    extract_model_effects,
    make_revision_pipeline,
    paired_event_block_bootstrap,
    revision_sign,
)

MODEL_ORDER = ["zero_change_baseline", "linear_regression", "ridge_regression", "random_forest"]
PAIR_ORDER = ["24h_to_12h", "12h_to_6h", "6h_to_1h"]


def _prediction_metrics(
    test: pd.DataFrame,
    prediction: np.ndarray,
    *,
    pair: str,
    model_name: str,
    train: pd.DataFrame,
    sign_tolerance: float,
    bootstrap_iterations: int,
    block_length_events: int,
    seed: int,
) -> tuple[dict[str, object], pd.DataFrame]:
    actual = test["delta_p"].to_numpy(dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    model_error = actual - prediction
    baseline_error = actual
    baseline_sse = float(np.square(baseline_error).sum())
    losses = test[["event_date", "event_id", "contract_id"]].copy()
    losses["squared_loss_difference"] = np.square(model_error) - np.square(baseline_error)
    losses["absolute_loss_difference"] = np.abs(model_error) - np.abs(baseline_error)
    squared_test = paired_event_block_bootstrap(
        losses,
        differential_column="squared_loss_difference",
        iterations=bootstrap_iterations,
        block_length=block_length_events,
        seed=seed,
    )
    absolute_test = paired_event_block_bootstrap(
        losses,
        differential_column="absolute_loss_difference",
        iterations=bootstrap_iterations,
        block_length=block_length_events,
        seed=seed + 1,
    )
    rmse = float(np.sqrt(np.mean(np.square(model_error))))
    baseline_rmse = float(np.sqrt(np.mean(np.square(baseline_error))))
    mae = float(np.mean(np.abs(model_error)))
    baseline_mae = float(np.mean(np.abs(baseline_error)))
    predicted_later = test["probability_now"].to_numpy(dtype=float) + prediction
    metrics = {
        "pair": pair,
        "now_horizon_hours": int(test["now_horizon_hours"].iloc[0]),
        "later_horizon_hours": int(test["later_horizon_hours"].iloc[0]),
        "model": model_name,
        "model_status": "evaluated",
        "status_reason": "",
        "train_observations": len(train),
        "train_events": train["event_id"].nunique(),
        "test_observations": len(test),
        "test_events": test["event_id"].nunique(),
        "train_start_date": str(min(train["event_date"])),
        "train_end_date": str(max(train["event_date"])),
        "test_start_date": str(min(test["event_date"])),
        "test_end_date": str(max(test["event_date"])),
        "oos_r2_vs_zero": (
            float(1 - np.square(model_error).sum() / baseline_sse) if baseline_sse > 0 else np.nan
        ),
        "rmse": rmse,
        "baseline_rmse": baseline_rmse,
        "rmse_improvement": baseline_rmse - rmse,
        "mae": mae,
        "baseline_mae": baseline_mae,
        "mae_improvement": baseline_mae - mae,
        "sign_accuracy": float(
            np.mean(
                revision_sign(prediction, sign_tolerance) == revision_sign(actual, sign_tolerance)
            )
        ),
        "baseline_sign_accuracy": float(np.mean(revision_sign(actual, sign_tolerance) == 0)),
        "sign_tolerance": sign_tolerance,
        "predicted_probability_bound_violation_fraction": float(
            np.mean((predicted_later < 0) | (predicted_later > 1))
        ),
        "squared_loss_difference": squared_test["mean_difference"],
        "squared_loss_ci_lower": squared_test["ci_lower"],
        "squared_loss_ci_upper": squared_test["ci_upper"],
        "squared_loss_pvalue": squared_test["pvalue"],
        "absolute_loss_difference": absolute_test["mean_difference"],
        "absolute_loss_ci_lower": absolute_test["ci_lower"],
        "absolute_loss_ci_upper": absolute_test["ci_upper"],
        "absolute_loss_pvalue": absolute_test["pvalue"],
        "block_length_events": block_length_events,
        "bootstrap_iterations": bootstrap_iterations,
    }
    predictions = test[
        [
            "event_date",
            "event_id",
            "contract_id",
            "pair",
            "probability_now",
            "probability_later",
            "delta_p",
        ]
    ].copy()
    predictions["model"] = model_name
    predictions["predicted_revision"] = prediction
    predictions = predictions.rename(columns={"delta_p": "actual_revision"})
    return metrics, predictions


def _baseline_metrics(
    test: pd.DataFrame,
    train: pd.DataFrame,
    *,
    pair: str,
    sign_tolerance: float,
    bootstrap_iterations: int,
    block_length_events: int,
) -> tuple[dict[str, object], pd.DataFrame]:
    metrics, predictions = _prediction_metrics(
        test,
        np.zeros(len(test)),
        pair=pair,
        model_name="zero_change_baseline",
        train=train,
        sign_tolerance=sign_tolerance,
        bootstrap_iterations=bootstrap_iterations,
        block_length_events=block_length_events,
        seed=0,
    )
    metrics.update(
        {
            "oos_r2_vs_zero": 0.0,
            "rmse_improvement": 0.0,
            "mae_improvement": 0.0,
            "squared_loss_difference": 0.0,
            "squared_loss_ci_lower": 0.0,
            "squared_loss_ci_upper": 0.0,
            "squared_loss_pvalue": 1.0,
            "absolute_loss_difference": 0.0,
            "absolute_loss_ci_lower": 0.0,
            "absolute_loss_ci_upper": 0.0,
            "absolute_loss_pvalue": 1.0,
        }
    )
    return metrics, predictions


def _skipped_model_row(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    pair: str,
    model_name: str,
    reason: str,
    sign_tolerance: float,
    bootstrap_iterations: int,
    block_length_events: int,
) -> dict[str, object]:
    return {
        "pair": pair,
        "now_horizon_hours": int(test["now_horizon_hours"].iloc[0]),
        "later_horizon_hours": int(test["later_horizon_hours"].iloc[0]),
        "model": model_name,
        "model_status": "skipped",
        "status_reason": reason,
        "train_observations": len(train),
        "train_events": train["event_id"].nunique(),
        "test_observations": len(test),
        "test_events": test["event_id"].nunique(),
        "train_start_date": str(min(train["event_date"])),
        "train_end_date": str(max(train["event_date"])),
        "test_start_date": str(min(test["event_date"])),
        "test_end_date": str(max(test["event_date"])),
        "sign_tolerance": sign_tolerance,
        "block_length_events": block_length_events,
        "bootstrap_iterations": bootstrap_iterations,
    }


def run_paired_efficiency_study(
    panel: pd.DataFrame,
    split: ChronologicalSplit,
    *,
    ridge_alpha: float = 10.0,
    sign_tolerance: float = 0.005,
    block_length_events: int = 7,
    bootstrap_iterations: int = 2000,
    bucket_min_frequency: int = 3,
    random_forest_min_events: int = 100,
    random_forest_min_observations: int = 1000,
    random_forest_estimators: int = 300,
    seed: int = 20260619,
    metrics_path: str | Path | None = None,
    coefficients_path: str | Path | None = None,
    predictions_path: str | Path | None = None,
    figure_path: str | Path | None = None,
    report_path: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Fit models on early events and evaluate them once on later event dates."""
    metric_rows = []
    coefficient_tables = []
    prediction_tables = []
    available_pairs = set(panel["pair"])
    ordered_pairs = [pair for pair in PAIR_ORDER if pair in available_pairs]
    ordered_pairs.extend(sorted(available_pairs - set(ordered_pairs)))
    for pair_index, pair in enumerate(ordered_pairs):
        sample = panel.loc[panel["pair"] == pair].copy()
        train = sample.loc[sample["event_date"].isin(split.train_dates)].copy()
        test = sample.loc[sample["event_date"].isin(split.test_dates)].copy()
        if train.empty or test.empty:
            raise ValueError(f"chronological split is empty for {pair}")
        available_numeric = [
            feature for feature in NUMERIC_FEATURES if train[feature].notna().any()
        ]
        unavailable_numeric = sorted(set(NUMERIC_FEATURES) - set(available_numeric))
        feature_columns = [*available_numeric, *CATEGORICAL_FEATURES]
        train_bucket_labels = set(train["bucket_label"].dropna())
        unseen_bucket_mask = ~test["bucket_label"].isin(train_bucket_labels)
        unseen_bucket_fraction = float(unseen_bucket_mask.mean())
        unseen_bucket_labels = int(test.loc[unseen_bucket_mask, "bucket_label"].nunique())
        baseline_metrics, baseline_predictions = _baseline_metrics(
            test,
            train,
            pair=pair,
            sign_tolerance=sign_tolerance,
            bootstrap_iterations=bootstrap_iterations,
            block_length_events=block_length_events,
        )
        baseline_metrics["numeric_features_used"] = "|".join(available_numeric)
        baseline_metrics["numeric_features_unavailable"] = "|".join(unavailable_numeric)
        baseline_metrics["unseen_bucket_observation_fraction"] = unseen_bucket_fraction
        baseline_metrics["unseen_bucket_labels"] = unseen_bucket_labels
        metric_rows.append(baseline_metrics)
        prediction_tables.append(baseline_predictions)

        for model_offset, model_name in enumerate(("linear_regression", "ridge_regression")):
            pipeline = make_revision_pipeline(
                model_name,
                numeric_features=available_numeric,
                categorical_features=CATEGORICAL_FEATURES,
                ridge_alpha=ridge_alpha,
                bucket_min_frequency=bucket_min_frequency,
                random_seed=seed,
                random_forest_estimators=random_forest_estimators,
            )
            pipeline.fit(train[feature_columns], train["delta_p"])
            prediction = pipeline.predict(test[feature_columns])
            metrics, predictions = _prediction_metrics(
                test,
                prediction,
                pair=pair,
                model_name=model_name,
                train=train,
                sign_tolerance=sign_tolerance,
                bootstrap_iterations=bootstrap_iterations,
                block_length_events=block_length_events,
                seed=seed + pair_index * 100 + model_offset * 10,
            )
            metrics["numeric_features_used"] = "|".join(available_numeric)
            metrics["numeric_features_unavailable"] = "|".join(unavailable_numeric)
            metrics["unseen_bucket_observation_fraction"] = unseen_bucket_fraction
            metrics["unseen_bucket_labels"] = unseen_bucket_labels
            metric_rows.append(metrics)
            prediction_tables.append(predictions)
            coefficient_tables.append(
                extract_model_effects(
                    pipeline,
                    pair=pair,
                    model_name=model_name,
                    train_observations=len(train),
                    train_events=train["event_id"].nunique(),
                )
            )

        train_events = train["event_id"].nunique()
        if (
            train_events >= random_forest_min_events
            and len(train) >= random_forest_min_observations
        ):
            model_name = "random_forest"
            pipeline = make_revision_pipeline(
                model_name,
                numeric_features=available_numeric,
                categorical_features=CATEGORICAL_FEATURES,
                ridge_alpha=ridge_alpha,
                bucket_min_frequency=bucket_min_frequency,
                random_seed=seed + pair_index,
                random_forest_estimators=random_forest_estimators,
            )
            pipeline.fit(train[feature_columns], train["delta_p"])
            prediction = pipeline.predict(test[feature_columns])
            metrics, predictions = _prediction_metrics(
                test,
                prediction,
                pair=pair,
                model_name=model_name,
                train=train,
                sign_tolerance=sign_tolerance,
                bootstrap_iterations=bootstrap_iterations,
                block_length_events=block_length_events,
                seed=seed + pair_index * 100 + 90,
            )
            metrics["numeric_features_used"] = "|".join(available_numeric)
            metrics["numeric_features_unavailable"] = "|".join(unavailable_numeric)
            metrics["unseen_bucket_observation_fraction"] = unseen_bucket_fraction
            metrics["unseen_bucket_labels"] = unseen_bucket_labels
            metric_rows.append(metrics)
            prediction_tables.append(predictions)
            coefficient_tables.append(
                extract_model_effects(
                    pipeline,
                    pair=pair,
                    model_name=model_name,
                    train_observations=len(train),
                    train_events=train_events,
                )
            )
        else:
            reason = (
                f"requires >= {random_forest_min_events} train events and >= "
                f"{random_forest_min_observations} rows; observed {train_events} events "
                f"and {len(train)} rows"
            )
            skipped = _skipped_model_row(
                train,
                test,
                pair=pair,
                model_name="random_forest",
                reason=reason,
                sign_tolerance=sign_tolerance,
                bootstrap_iterations=bootstrap_iterations,
                block_length_events=block_length_events,
            )
            skipped["numeric_features_used"] = "|".join(available_numeric)
            skipped["numeric_features_unavailable"] = "|".join(unavailable_numeric)
            skipped["unseen_bucket_observation_fraction"] = unseen_bucket_fraction
            skipped["unseen_bucket_labels"] = unseen_bucket_labels
            metric_rows.append(skipped)

    metrics = pd.DataFrame(metric_rows)
    evaluated = (metrics["model_status"] == "evaluated") & (
        metrics["model"] != "zero_change_baseline"
    )
    metrics["squared_loss_pvalue_adjusted_bh"] = np.nan
    metrics.loc[evaluated, "squared_loss_pvalue_adjusted_bh"] = adjust_pvalues(
        metrics.loc[evaluated, "squared_loss_pvalue"]
    )
    metrics["beats_zero_change_5pct"] = False
    metrics.loc[evaluated, "beats_zero_change_5pct"] = (
        (metrics.loc[evaluated, "oos_r2_vs_zero"] > 0)
        & (metrics.loc[evaluated, "squared_loss_difference"] < 0)
        & (metrics.loc[evaluated, "squared_loss_pvalue_adjusted_bh"] < 0.05)
    )
    model_rank = {model: index for index, model in enumerate(MODEL_ORDER)}
    metrics["_model_order"] = metrics["model"].map(model_rank)
    metrics = metrics.sort_values(["now_horizon_hours", "_model_order"], ascending=[False, True])
    metrics = metrics.drop(columns="_model_order").reset_index(drop=True)
    coefficients = (
        pd.concat(coefficient_tables, ignore_index=True) if coefficient_tables else pd.DataFrame()
    )
    predictions = pd.concat(prediction_tables, ignore_index=True)

    for path, frame in (
        (metrics_path, metrics),
        (coefficients_path, coefficients),
        (predictions_path, predictions),
    ):
        if path is not None:
            destination = Path(path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(destination, index=False)
    if figure_path is not None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        from pm_efficiency.visualization.plots import plot_predicted_vs_actual_revisions

        figure = plot_predicted_vs_actual_revisions(predictions, output_path=figure_path)
        plt.close(figure)
    if report_path is not None:
        write_efficiency_report(metrics, panel, split, report_path)
    return {"metrics": metrics, "coefficients": coefficients, "predictions": predictions}


def _format_number(value: object, digits: int = 4) -> str:
    return "NA" if pd.isna(value) else f"{float(value):.{digits}f}"


def write_efficiency_report(
    metrics: pd.DataFrame,
    panel: pd.DataFrame,
    split: ChronologicalSplit,
    output_path: str | Path,
) -> Path:
    """Write a conservative, reproducible interpretation of the OOS martingale tests."""
    evaluated = metrics.loc[
        (metrics["model_status"] == "evaluated") & (metrics["model"] != "zero_change_baseline")
    ]
    winners = evaluated.loc[evaluated["beats_zero_change_5pct"]]
    if winners.empty:
        conclusion = (
            "No evaluated model beats the zero-change forecast after the paired weekly-block "
            "bootstrap and Benjamini-Hochberg adjustment. Within this sample, the evidence is "
            "consistent with weak-form efficiency; this is not proof of efficiency."
        )
    else:
        labels = ", ".join(f"{row.model} on {row.pair}" for row in winners.itertuples(index=False))
        conclusion = (
            f"The adjusted predictive comparison identifies {labels}. This is evidence of "
            "out-of-sample predictability in the pilot, not automatic tradable alpha; prices, "
            "spreads, fees, and execution remain unmodeled."
        )
    lines = [
        "# KXHIGHNY Chronological Efficiency and Martingale Report",
        "",
        "## Research question and design",
        "",
        "The null is `E[p_later - p_now | public market information at now] = 0`. "
        "Targets pair 24h→12h, 12h→6h, and 6h→1h quotes. Features are timestamped "
        "at the now quote; no later-horizon field enters the feature matrix.",
        "",
        f"The first {len(split.train_dates)} event dates ({min(split.train_dates)} through "
        f"{max(split.train_dates)}) form the training sample. The final "
        f"{len(split.test_dates)} dates ({min(split.test_dates)} through "
        f"{max(split.test_dates)}) form one untouched chronological test set. All six "
        "contracts from an event remain on the same side of the split.",
        "",
        "Numeric features are median-imputed and standardized using training data only. "
        "Bucket labels are one-hot encoded with rare training labels pooled. Linear and "
        "ridge models are compared with the martingale zero-change forecast. Random forest "
        "is run only when its pre-specified independent-event and row thresholds are met.",
        "",
        "## Out-of-sample results",
        "",
        "Negative loss differences favor the fitted model. P-values use paired circular "
        "seven-event block bootstraps of event-date mean squared-loss differences; adjusted "
        "p-values control the tested model/pair family with Benjamini-Hochberg.",
        "",
        "| Pair | Model | Test events | OOS R² vs zero | RMSE / zero | MAE / zero | "
        "Sign acc. / zero | Bound violations | Squared-loss diff. (95% CI) | Adjusted p |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in metrics.itertuples(index=False):
        if row.model_status != "evaluated":
            lines.append(
                f"| {row.pair} | {row.model} (skipped) | {int(row.test_events)} | NA | NA | "
                f"NA | NA | NA | {row.status_reason} | NA |"
            )
            continue
        lines.append(
            f"| {row.pair} | {row.model} | {int(row.test_events)} | "
            f"{_format_number(row.oos_r2_vs_zero)} | {_format_number(row.rmse)} / "
            f"{_format_number(row.baseline_rmse)} | {_format_number(row.mae)} / "
            f"{_format_number(row.baseline_mae)} | {_format_number(row.sign_accuracy)} / "
            f"{_format_number(row.baseline_sign_accuracy)} | "
            f"{_format_number(row.predicted_probability_bound_violation_fraction)} | "
            f"{_format_number(row.squared_loss_difference, 6)} "
            f"({_format_number(row.squared_loss_ci_lower, 6)}, "
            f"{_format_number(row.squared_loss_ci_upper, 6)}) | "
            f"{_format_number(row.squared_loss_pvalue_adjusted_bh)} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            conclusion,
            "",
            "A positive OOS R² here means lower squared revision error than predicting zero, "
            "not explanatory power relative to a test-set mean. Sign accuracy uses a ±0.005 "
            "no-change band, matching the midpoint grid. Separate marginal model metrics are "
            "not treated as evidence unless the paired block comparison also survives adjustment.",
            "",
            "### Pair-level reading",
            "",
        ]
    )
    for pair in PAIR_ORDER:
        pair_models = evaluated.loc[evaluated["pair"] == pair]
        if pair_models.empty:
            continue
        best = pair_models.sort_values("oos_r2_vs_zero", ascending=False).iloc[0]
        if bool(best["beats_zero_change_5pct"]):
            reading = (
                f"{best['model']} beats zero under the adjusted primary test, indicating "
                "pilot predictability that still requires full-history and execution checks."
            )
        elif best["oos_r2_vs_zero"] > 0:
            reading = (
                f"{best['model']} has a small positive OOS R² "
                f"({_format_number(best['oos_r2_vs_zero'])}), but its block interval includes "
                "zero and the adjusted comparison is not significant."
            )
        else:
            reading = "all evaluated fitted models have non-positive OOS R² versus zero."
        lines.append(f"- **{pair}:** {reading}")
    lines.extend(
        [
            "",
            "## Feature and sample audit",
            "",
        ]
    )
    for pair in PAIR_ORDER:
        sample = panel.loc[panel["pair"] == pair]
        if sample.empty:
            continue
        missing = sample[NUMERIC_FEATURES].isna().mean()
        unavailable = [feature for feature in NUMERIC_FEATURES if missing[feature] == 1]
        train_labels = set(
            sample.loc[sample["event_date"].isin(split.train_dates), "bucket_label"].dropna()
        )
        test_labels = sample.loc[sample["event_date"].isin(split.test_dates), "bucket_label"]
        unseen_fraction = (~test_labels.isin(train_labels)).mean()
        availability_note = (
            f" Structurally unavailable and excluded: {', '.join(unavailable)}."
            if unavailable
            else ""
        )
        lines.append(
            f"- **{pair}:** {len(sample)} paired contracts across "
            f"{sample.event_id.nunique()} events; largest numeric-feature missing rate is "
            f"{missing.max():.1%} ({missing.idxmax()}); partially missing features are "
            f"imputed from training data only. Test observations with bucket labels unseen "
            f"in training: {unseen_fraction:.1%}."
            f"{availability_note}"
        )
    lines.extend(
        [
            "",
            "`efficiency_coefficients.csv` contains standardized linear/ridge coefficients "
            "from the training sample. They are descriptive and neither causal nor a substitute "
            "for out-of-sample performance.",
            "",
            "## Limitations",
            "",
            f"1. The test set contains the final {len(split.test_dates)} event dates "
            f"({min(split.test_dates)} through {max(split.test_dates)}). It is chronologically "
            "honest, but regime and season composition can still affect external validity.",
            "2. Weekly event blocks address short-run date dependence only approximately. The "
            "six mutually exclusive contracts within a day are averaged before resampling.",
            "3. Bucket labels are high-cardinality and partially unseen chronologically; ridge is "
            "more defensible than unregularized linear coefficients in this sample. Unknown test "
            "labels map to the pooled infrequent category learned from training only.",
            "4. Unconstrained linear predictions can imply later probabilities outside `[0, 1]`; "
            "the reported bound-violation rate is a model diagnostic and predictions are not "
            "silently clipped.",
            "5. Hourly candle midpoints are not executable prices. This study tests statistical "
            "revision predictability, not net profitability.",
            "6. Model and preprocessing choices are fixed for this run but still need seasonal, "
            "alternate-staleness, and alternate-block-length checks.",
            "",
            "## Required next checks",
            "",
            "- Report seasonal subsamples and weekly/monthly block-bootstrap sensitivity.",
            "- Test predictions against feasible bid/ask execution and fees before discussing "
            "alpha.",
            "- Keep any detected relationship framed as predictability unless it survives those "
            "checks.",
            "",
        ]
    )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines))
    return destination


def run_paired_efficiency_from_files(
    snapshots_path: str | Path = "data/processed/market_snapshots.csv",
    efficiency_panel_path: str | Path = "data/processed/efficiency_panel.parquet",
    *,
    train_fraction: float = 0.70,
    minimum_training_events: int = 60,
    max_staleness_hours: float = 2,
    **kwargs: object,
) -> dict[str, pd.DataFrame]:
    snapshots = pd.read_csv(snapshots_path)
    efficiency_panel = pd.read_parquet(efficiency_panel_path)
    paired_panel = build_paired_revision_panel(
        snapshots,
        efficiency_panel,
        max_staleness_hours=max_staleness_hours,
    )
    split = chronological_event_split(
        paired_panel,
        train_fraction=train_fraction,
        minimum_training_events=minimum_training_events,
    )
    return run_paired_efficiency_study(paired_panel, split, **kwargs)
