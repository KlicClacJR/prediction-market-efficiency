# KXHIGHNY Chronological Efficiency and Martingale Report

## Research question and design

The null is `E[p_later - p_now | public market information at now] = 0`. Targets pair 24h→12h, 12h→6h, and 6h→1h quotes. Features are timestamped at the now quote; no later-horizon field enters the feature matrix.

The first 64 event dates (2026-03-01 through 2026-05-03) form the training sample. The final 28 dates (2026-05-04 through 2026-05-31) form one untouched chronological test set. All six contracts from an event remain on the same side of the split.

Numeric features are median-imputed and standardized using training data only. Bucket labels are one-hot encoded with rare training labels pooled. Linear and ridge models are compared with the martingale zero-change forecast. Random forest is run only when its pre-specified independent-event and row thresholds are met.

## Out-of-sample results

Negative loss differences favor the fitted model. P-values use paired circular seven-event block bootstraps of event-date mean squared-loss differences; adjusted p-values control the tested model/pair family with Benjamini-Hochberg.

| Pair | Model | Test events | OOS R² vs zero | RMSE / zero | MAE / zero | Sign acc. / zero | Bound violations | Squared-loss diff. (95% CI) | Adjusted p |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 24h_to_12h | zero_change_baseline | 28 | 0.0000 | 0.1258 / 0.1258 | 0.0805 / 0.0805 | 0.1607 / 0.1607 | 0.0000 | 0.000000 (0.000000, 0.000000) | NA |
| 24h_to_12h | linear_regression | 28 | 0.0643 | 0.1217 / 0.1258 | 0.0822 / 0.0805 | 0.4464 / 0.1607 | 0.1964 | -0.001018 (-0.002714, 0.001195) | 0.4576 |
| 24h_to_12h | ridge_regression | 28 | 0.0609 | 0.1219 / 0.1258 | 0.0777 / 0.0805 | 0.5000 / 0.1607 | 0.2024 | -0.000964 (-0.002212, 0.000860) | 0.4576 |
| 24h_to_12h | random_forest (skipped) | 28 | NA | NA | NA | NA | NA | requires >= 100 train events and >= 1000 rows; observed 64 events and 384 rows | NA |
| 12h_to_6h | zero_change_baseline | 28 | 0.0000 | 0.2176 / 0.2176 | 0.1197 / 0.1197 | 0.4192 / 0.4192 | 0.0000 | 0.000000 (0.000000, 0.000000) | NA |
| 12h_to_6h | linear_regression | 28 | -0.2307 | 0.2414 / 0.2176 | 0.1570 / 0.1197 | 0.3234 / 0.4192 | 0.2216 | 0.011045 (0.002865, 0.020040) | 0.0570 |
| 12h_to_6h | ridge_regression | 28 | -0.0995 | 0.2282 / 0.2176 | 0.1356 / 0.1197 | 0.3293 / 0.4192 | 0.1737 | 0.004719 (-0.000992, 0.010560) | 0.3673 |
| 12h_to_6h | random_forest (skipped) | 28 | NA | NA | NA | NA | NA | requires >= 100 train events and >= 1000 rows; observed 64 events and 384 rows | NA |
| 6h_to_1h | zero_change_baseline | 28 | 0.0000 | 0.1286 / 0.1286 | 0.0295 / 0.0295 | 0.8544 / 0.8544 | 0.0000 | 0.000000 (0.000000, 0.000000) | NA |
| 6h_to_1h | linear_regression | 28 | 0.0051 | 0.1283 / 0.1286 | 0.0384 / 0.0295 | 0.5127 / 0.8544 | 0.2405 | -0.000140 (-0.001064, 0.000534) | 0.7331 |
| 6h_to_1h | ridge_regression | 28 | 0.0156 | 0.1276 / 0.1286 | 0.0352 / 0.0295 | 0.6076 / 0.8544 | 0.0696 | -0.000302 (-0.000949, 0.000246) | 0.4576 |
| 6h_to_1h | random_forest (skipped) | 28 | NA | NA | NA | NA | NA | requires >= 100 train events and >= 1000 rows; observed 64 events and 379 rows | NA |

## Interpretation

No evaluated model beats the zero-change forecast after the paired weekly-block bootstrap and Benjamini-Hochberg adjustment. Within this pilot, the evidence is consistent with weak-form efficiency; this is not proof of efficiency.

A positive OOS R² here means lower squared revision error than predicting zero, not explanatory power relative to a test-set mean. Sign accuracy uses a ±0.005 no-change band, matching the midpoint grid. Separate marginal model metrics are not treated as evidence unless the paired block comparison also survives adjustment.

### Pair-level reading

- **24h_to_12h:** linear_regression has a small positive OOS R² (0.0643), but its block interval includes zero and the adjusted comparison is not significant.
- **12h_to_6h:** all evaluated fitted models have non-positive OOS R² versus zero.
- **6h_to_1h:** ridge_regression has a small positive OOS R² (0.0156), but its block interval includes zero and the adjusted comparison is not significant.

## Feature and sample audit

- **24h_to_12h:** 552 paired contracts across 92 events; largest numeric-feature missing rate is 100.0% (delta_p_24h); partially missing features are imputed from training data only. Test observations with bucket labels unseen in training: 13.1%. Structurally unavailable and excluded: delta_p_24h.
- **12h_to_6h:** 551 paired contracts across 92 events; largest numeric-feature missing rate is 2.4% (delta_p_6h); partially missing features are imputed from training data only. Test observations with bucket labels unseen in training: 13.2%.
- **6h_to_1h:** 537 paired contracts across 92 events; largest numeric-feature missing rate is 1.1% (delta_p_24h); partially missing features are imputed from training data only. Test observations with bucket labels unseen in training: 12.7%.

`efficiency_coefficients.csv` contains standardized linear/ridge coefficients from the training sample. They are descriptive and neither causal nor a substitute for out-of-sample performance.

## Limitations

1. The test set contains only the final 28 spring event dates; power and seasonal external validity are limited.
2. Weekly event blocks address short-run date dependence only approximately. The six mutually exclusive contracts within a day are averaged before resampling.
3. Bucket labels are high-cardinality and partially unseen chronologically; ridge is more defensible than unregularized linear coefficients in this sample. Unknown test labels map to the pooled infrequent category learned from training only.
4. Unconstrained linear predictions can imply later probabilities outside `[0, 1]`; the reported bound-violation rate is a model diagnostic and predictions are not silently clipped.
5. Hourly candle midpoints are not executable prices. This study tests statistical revision predictability, not net profitability.
6. Model and preprocessing choices are pre-specified for this pilot but still need full-history, seasonal, alternate-staleness, and alternate-block-length checks.

## Required next checks

- Repeat on the full available history with the chronological split fixed before examining results.
- Report seasonal subsamples and weekly/monthly block-bootstrap sensitivity.
- Test predictions against feasible bid/ask execution and fees before discussing alpha.
- Keep any detected relationship framed as predictability unless it survives those checks.
