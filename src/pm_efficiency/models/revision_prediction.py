"""Chronological prediction and event-date block inference for probability revisions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from pm_efficiency.features.revision_pairs import CATEGORICAL_FEATURES, NUMERIC_FEATURES


@dataclass(frozen=True)
class ChronologicalSplit:
    train_dates: tuple[object, ...]
    test_dates: tuple[object, ...]

    @property
    def cutoff_date(self) -> object:
        return self.train_dates[-1]


def chronological_event_split(
    panel: pd.DataFrame,
    *,
    train_fraction: float = 0.70,
    minimum_training_events: int = 60,
) -> ChronologicalSplit:
    """Create one shared date split so no event appears in both train and test."""
    event_dates = (
        panel[["event_id", "event_date"]].drop_duplicates().sort_values(["event_date", "event_id"])
    )
    if event_dates["event_id"].duplicated().any():
        raise ValueError("an event_id maps to multiple event dates")
    dates = tuple(sorted(event_dates["event_date"].dropna().unique()))
    train_count = max(minimum_training_events, int(np.floor(len(dates) * train_fraction)))
    if train_count >= len(dates):
        raise ValueError(
            f"chronological split needs more than {train_count} event dates; found {len(dates)}"
        )
    return ChronologicalSplit(dates[:train_count], dates[train_count:])


def make_revision_pipeline(
    model_name: str,
    *,
    numeric_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
    ridge_alpha: float = 10.0,
    bucket_min_frequency: int = 3,
    random_seed: int = 20260619,
    random_forest_estimators: int = 300,
) -> Pipeline:
    """Build train-fitted preprocessing plus one requested regression model."""
    numeric_features = numeric_features or NUMERIC_FEATURES
    categorical_features = categorical_features or CATEGORICAL_FEATURES
    numeric = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler()),
        ]
    )
    categorical = OneHotEncoder(
        handle_unknown="infrequent_if_exist",
        min_frequency=bucket_min_frequency,
        drop="first",
        sparse_output=False,
    )
    preprocessor = ColumnTransformer(
        [
            ("numeric", numeric, numeric_features),
            ("bucket", categorical, categorical_features),
        ],
        verbose_feature_names_out=True,
    )
    if model_name == "linear_regression":
        model = LinearRegression()
    elif model_name == "ridge_regression":
        model = Ridge(alpha=ridge_alpha)
    elif model_name == "random_forest":
        model = RandomForestRegressor(
            n_estimators=random_forest_estimators,
            max_depth=5,
            min_samples_leaf=10,
            max_features=0.7,
            random_state=random_seed,
            n_jobs=-1,
        )
    else:
        raise ValueError(f"unknown revision model: {model_name}")
    return Pipeline([("preprocessor", preprocessor), ("model", model)])


def extract_model_effects(
    fitted_pipeline: Pipeline,
    *,
    pair: str,
    model_name: str,
    train_observations: int,
    train_events: int,
) -> pd.DataFrame:
    """Return standardized coefficients or feature importances from a fitted pipeline."""
    feature_names = fitted_pipeline.named_steps["preprocessor"].get_feature_names_out()
    estimator = fitted_pipeline.named_steps["model"]
    if hasattr(estimator, "coef_"):
        values = np.asarray(estimator.coef_).reshape(-1)
        estimate_type = "standardized_coefficient"
    else:
        values = np.asarray(estimator.feature_importances_).reshape(-1)
        estimate_type = "feature_importance"
    rows = pd.DataFrame(
        {
            "pair": pair,
            "model": model_name,
            "feature": feature_names,
            "estimate_type": estimate_type,
            "estimate": values,
            "train_observations": train_observations,
            "train_events": train_events,
        }
    )
    if hasattr(estimator, "intercept_"):
        intercept = pd.DataFrame(
            {
                "pair": [pair],
                "model": [model_name],
                "feature": ["intercept"],
                "estimate_type": ["intercept"],
                "estimate": [float(np.asarray(estimator.intercept_).squeeze())],
                "train_observations": [train_observations],
                "train_events": [train_events],
            }
        )
        rows = pd.concat([intercept, rows], ignore_index=True)
    return rows


def paired_event_block_bootstrap(
    losses: pd.DataFrame,
    *,
    differential_column: str,
    iterations: int = 2000,
    block_length: int = 7,
    seed: int = 20260619,
) -> dict[str, float]:
    """Bootstrap ordered event-date mean loss differentials in circular weekly blocks."""
    event_loss = (
        losses.groupby("event_date", as_index=False)[differential_column]
        .mean()
        .sort_values("event_date")[differential_column]
        .to_numpy(dtype=float)
    )
    if len(event_loss) < 2:
        raise ValueError("paired block bootstrap requires at least two test event dates")
    length = len(event_loss)
    block_length = min(block_length, length)
    blocks_needed = int(np.ceil(length / block_length))
    rng = np.random.default_rng(seed)
    draws = np.empty(iterations)
    null_values = event_loss - event_loss.mean()
    null_draws = np.empty(iterations)
    offsets = np.arange(block_length)
    for index in range(iterations):
        starts = rng.integers(0, length, size=blocks_needed)
        positions = ((starts[:, None] + offsets) % length).reshape(-1)[:length]
        draws[index] = event_loss[positions].mean()
        null_draws[index] = null_values[positions].mean()
    observed = float(event_loss.mean())
    pvalue = float((np.count_nonzero(np.abs(null_draws) >= abs(observed)) + 1) / (iterations + 1))
    return {
        "mean_difference": observed,
        "ci_lower": float(np.quantile(draws, 0.025)),
        "ci_upper": float(np.quantile(draws, 0.975)),
        "pvalue": pvalue,
        "test_event_dates": length,
        "block_length_events": block_length,
        "bootstrap_iterations": iterations,
    }


def revision_sign(values: object, tolerance: float = 0.005) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return np.where(array > tolerance, 1, np.where(array < -tolerance, -1, 0))
