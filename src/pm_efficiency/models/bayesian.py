"""Beta-Binomial building blocks for the planned Bayesian calibration extension."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import beta as beta_distribution


@dataclass(frozen=True)
class BetaPosterior:
    alpha: float
    beta: float
    mean: float
    lower: float
    upper: float
    successes: float
    trials: float


def beta_binomial_smooth(
    successes: float,
    trials: float,
    *,
    alpha: float = 1,
    beta: float = 1,
    credible_level: float = 0.95,
) -> BetaPosterior:
    """Update a Beta prior and return a smoothed probability and credible interval."""
    if alpha <= 0 or beta <= 0:
        raise ValueError("Beta prior parameters must be positive")
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("Require 0 <= successes <= trials")
    if not 0 < credible_level < 1:
        raise ValueError("credible_level must lie in (0, 1)")
    posterior_alpha = alpha + successes
    posterior_beta = beta + trials - successes
    tail = (1 - credible_level) / 2
    lower, upper = beta_distribution.ppf([tail, 1 - tail], posterior_alpha, posterior_beta)
    return BetaPosterior(
        alpha=posterior_alpha,
        beta=posterior_beta,
        mean=posterior_alpha / (posterior_alpha + posterior_beta),
        lower=float(lower),
        upper=float(upper),
        successes=successes,
        trials=trials,
    )


def estimate_beta_prior(group_rates: object, minimum_precision: float = 2) -> tuple[float, float]:
    """Method-of-moments category prior from historical group-level success rates."""
    rates = np.asarray(group_rates, dtype=float)
    rates = rates[np.isfinite(rates)]
    if not len(rates):
        return 1.0, 1.0
    mean = float(np.clip(rates.mean(), 1e-6, 1 - 1e-6))
    variance = float(rates.var(ddof=1)) if len(rates) > 1 else 0
    precision = mean * (1 - mean) / variance - 1 if variance > 0 else minimum_precision
    precision = max(float(precision), minimum_precision)
    return mean * precision, (1 - mean) * precision
