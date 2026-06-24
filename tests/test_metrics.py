import numpy as np

from pm_efficiency.metrics.calibration import calibration_table, expected_calibration_error
from pm_efficiency.metrics.inference import adjust_pvalues
from pm_efficiency.metrics.scoring import binary_log_loss, brier_score
from pm_efficiency.models.bayesian import beta_binomial_smooth


def test_proper_scores_match_hand_calculation():
    y = np.array([0, 1])
    p = np.array([0.25, 0.75])
    assert brier_score(y, p) == 0.0625
    assert np.isclose(binary_log_loss(y, p), -np.log(0.75))


def test_calibration_bins_and_ece_include_probability_one():
    y = [0, 1, 1, 1]
    p = [0.1, 0.4, 0.8, 1.0]
    table = calibration_table(y, p, bins=2)
    assert table["count"].sum() == 4
    expected = 0.5 * abs(0.5 - 0.25) + 0.5 * abs(1.0 - 0.9)
    assert np.isclose(expected_calibration_error(y, p, bins=2), expected)


def test_beta_binomial_smoothing():
    posterior = beta_binomial_smooth(8, 10, alpha=2, beta=2)
    assert np.isclose(posterior.mean, 10 / 14)
    assert 0 < posterior.lower < posterior.mean < posterior.upper < 1


def test_benjamini_hochberg_adjustment_preserves_order_and_missing_values():
    adjusted = adjust_pvalues([0.01, 0.04, np.nan, 0.03])
    assert np.allclose(adjusted[[0, 1, 3]], [0.03, 0.04, 0.04])
    assert np.isnan(adjusted[2])
