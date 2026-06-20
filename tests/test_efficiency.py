import numpy as np
import pandas as pd

from pm_efficiency.models.efficiency import fit_revision_model
from pm_efficiency.models.efficiency import test_martingale_difference as martingale_test


def test_predictable_revisions_are_detected():
    rng = np.random.default_rng(7)
    n = 500
    signal = rng.normal(size=n)
    panel = pd.DataFrame(
        {
            "event_id": np.repeat([f"E{i}" for i in range(50)], 10),
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC"),
            "delta_p_1h": signal,
            "future_revision_1h": 0.25 * signal + rng.normal(scale=0.1, size=n),
        }
    )
    model = fit_revision_model(panel, 1, predictors=["delta_p_1h"])
    assert model.params["delta_p_1h"] > 0.2
    assert model.pvalues["delta_p_1h"] < 1e-6
    diagnostics = martingale_test(panel, 1, predictors=["delta_p_1h"], ljung_box_lags=5)
    assert diagnostics["joint_zero_pvalue"] < 1e-6
