# Prediction Market Efficiency and Bayesian Information Aggregation

This repository studies whether prediction-market prices are calibrated and whether their revisions are predictable. The MVP uses Kalshi's `KXHIGHNY` series: daily contracts on the highest temperature recorded in Central Park.

Weather is a useful first laboratory because events repeat frequently, contract language is comparatively stable, and the outcome is resolved against the National Weather Service Daily Climate Report. The project deliberately begins with one series before attempting broader claims about politics, economics, or culture.

## Research questions

1. Do market-implied probabilities match observed event frequencies?
2. How do Brier score, log loss, and calibration change as resolution approaches?
3. Can public market information predict subsequent probability revisions?
4. Are midpoint probabilities consistent with a martingale-difference process?
5. Can category-level Beta priors improve held-out calibration without erasing information in prices?

The main null for efficiency is

$$
E[p_{t+h}-p_t\mid\mathcal{F}_t]=0.
$$

Rejecting a coefficient test is not, by itself, evidence of a tradable strategy. Spreads, fees, fill uncertainty, dependence, and multiple testing all matter.

## Repository and data flow

```text
Kalshi public API
  -> data/raw/kalshi/KXHIGHNY/<timestamp>/  immutable JSON + manifest
  -> data/interim/                         canonical Parquet tables
  -> data/processed/                       forecast and efficiency panels
  -> reports/tables + reports/figures      reproducible results
```

Research logic lives under `src/pm_efficiency`. Notebooks are intentionally thin consumers of package functions; they are not hidden production pipelines.

## Installation

Python 3.12 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,notebooks]'
pytest
```

## Reproducible commands

```bash
# Create a new immutable API snapshot.
pm-efficiency fetch

# Normalize the latest snapshot and enforce data contracts.
pm-efficiency clean

# Build leakage-safe panels.
pm-efficiency build

# Write coverage, missingness, distribution, and event probability-sum tables.
python scripts/descriptive_summary.py

# Score 24h/12h/6h/1h forecasts and write the reliability diagram.
python scripts/calibration_analysis.py

# Produce statistical tables and the reliability figure.
pm-efficiency analyze

# Reproduce everything downstream from a particular cached raw run.
pm-efficiency pipeline --run-dir data/raw/kalshi/KXHIGHNY/<run-id>
```

All defaults are in `config/mvp.yaml`. The raw run manifest records retrieval time, source partition, record counts, and SHA-256 hashes. Raw responses are never overwritten.

## Canonical datasets

- `markets.parquet`: one row per binary temperature bucket, including event, strike, lifecycle timestamps, rules, and settlement metadata.
- `outcomes.parquet`: explicit binary mapping plus a validity flag for unresolved or exceptional outcomes.
- `price_history.parquet`: hourly quotes and trades normalized across Kalshi's current and historical response formats.
- `forecast_panel.parquet`: one row per market at 24, 12, 6, and 1 hour before close.
- `efficiency_panel.parquet`: hourly trailing features and one-/six-hour future revisions.
- `market_snapshots.csv`: resolved `KXHIGHNY` hourly snapshots with the canonical public
  columns requested for downstream research. Its adjacent manifest records the output hash,
  source retrieval dates, row counts, and missing-price exclusions.

The primary implied probability is the midpoint of the closing YES bid and ask in an hourly candle. A missing two-sided quote remains missing; it is not silently replaced with a last trade. `liquidity_dollars` is nullable because historical point-in-time liquidity cannot be reconstructed safely from candle data.

## Metrics and inference

- Brier score: mean squared probability error.
- Binary log loss: probabilities clipped to `[1e-6, 1 - 1e-6]`, with clipping disclosed in output methodology.
- Calibration: fixed-width deciles and expected calibration error (ECE).
- Uncertainty: complete daily events are resampled in a cluster bootstrap, preserving dependence among mutually exclusive buckets.
- Efficiency: OLS with event-clustered covariance and expanding-window out-of-sample predictions against a zero-revision benchmark.
- Multiple tests: Benjamini-Hochberg adjusted p-values.

Fixed-horizon rows use the final quote at or before the target timestamp and reject quotes more than two hours stale. Trailing features are timestamp-aware. Outcomes, post-target candles, and information from later events are never used as predictors.

Raw bucket midpoints are the primary forecasts. Since the buckets within a daily event are mutually exclusive, the pipeline also records their probability sum and a normalized probability. Normalization is a robustness check rather than a replacement for the prices participants actually faced.

## Expected outputs

- Calibration metrics and clustered confidence intervals by horizon
- Reliability bins and diagram
- Probability-range bias estimates
- Revision-model coefficients and adjusted p-values
- Martingale joint tests and Ljung-Box diagnostics
- Rolling out-of-sample performance versus zero predicted revision

The notebooks cover data auditing, calibration interpretation, and efficiency interpretation. `reports/final_report.md` is the manuscript skeleton and records the claims that require populated evidence.

## Limitations

- Temperature buckets inside an event are dependent and should not be treated as independent resolutions.
- Hourly candles summarize quotes; they are not a complete order-book history.
- A midpoint is not necessarily executable.
- Near-close weather prices may reflect observations rather than forecasts.
- Results from NYC temperature contracts do not automatically generalize to other categories or exchanges.
- Exchange APIs and archived schemas can change; raw manifests and fixture tests make those changes detectable, not impossible.

This is an academic research project, not investment advice.

## Roadmap

1. Validate a complete `KXHIGHNY` history and publish the first calibration/efficiency report.
2. Add other city-temperature series through configuration.
3. Estimate category/horizon/bin Beta priors on training events and evaluate posterior-smoothed probabilities out of sample.
4. Add richer timestamped order-book depth prospectively.
5. Only then compare weather with economics, politics, and culture.

## Sources

- [Kalshi public market-data quick start](https://docs.kalshi.com/getting_started/quick_start_market_data)
- [Kalshi historical-data partitioning](https://docs.kalshi.com/getting_started/historical_data)
- [Kalshi weather settlement overview](https://help.kalshi.com/markets/popular-markets/weather-markets)
