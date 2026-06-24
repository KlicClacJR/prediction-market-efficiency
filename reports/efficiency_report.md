# KXHIGHNY Chronological Efficiency and Martingale Report

## Research question and design

The null is `E[p_later - p_now | public market information at now] = 0`. Targets pair 24h→12h, 12h→6h, and 6h→1h quotes. Features are timestamped at the now quote; no later-horizon field enters the feature matrix.

The first 1,236 event dates (2021-08-06 through 2025-01-04) form the training sample. The final 531 dates (2025-01-05 through 2026-06-19) form one untouched chronological test set. All contracts from an event remain on the same side of the split.

Numeric features are median-imputed and standardized using training data only. Bucket labels are one-hot encoded with rare training labels pooled. Linear and ridge models are compared with the martingale zero-change forecast. Random forest is run only when its pre-specified independent-event and row thresholds are met.

## Out-of-sample results

Negative loss differences favor the fitted model. P-values use paired circular seven-event block bootstraps of event-date mean squared-loss differences; adjusted p-values control the tested model/pair family with Benjamini-Hochberg.

| Pair | Model | Test events | OOS R² vs zero | RMSE / zero | MAE / zero | Sign acc. / zero | Bound violations | Squared-loss diff. (95% CI) | Adjusted p |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 24h_to_12h | zero_change_baseline | 530 | 0.0000 | 0.1455 / 0.1455 | 0.0914 / 0.0914 | 0.1069 / 0.1069 | 0.0000 | 0.000000 (0.000000, 0.000000) | NA |
| 24h_to_12h | linear_regression | 530 | -0.2009 | 0.1595 / 0.1455 | 0.1152 / 0.0914 | 0.3601 / 0.1069 | 0.0466 | 0.004105 (0.003154, 0.004996) | 0.0007 |
| 24h_to_12h | ridge_regression | 530 | -0.1041 | 0.1529 / 0.1455 | 0.1079 / 0.0914 | 0.3333 / 0.1069 | 0.0068 | 0.002051 (0.001248, 0.002763) | 0.0007 |
| 24h_to_12h | random_forest | 530 | -0.0233 | 0.1472 / 0.1455 | 0.0986 / 0.0914 | 0.3047 / 0.1069 | 0.0013 | 0.000496 (0.000242, 0.000772) | 0.0019 |
| 12h_to_6h | zero_change_baseline | 531 | 0.0000 | 0.2777 / 0.2777 | 0.1680 / 0.1680 | 0.3027 / 0.3027 | 0.0000 | 0.000000 (0.000000, 0.000000) | NA |
| 12h_to_6h | linear_regression | 531 | -0.1227 | 0.2943 / 0.2777 | 0.2218 / 0.1680 | 0.2051 / 0.3027 | 0.0559 | 0.009464 (0.007558, 0.011327) | 0.0007 |
| 12h_to_6h | ridge_regression | 531 | -0.0690 | 0.2871 / 0.2777 | 0.2121 / 0.1680 | 0.1736 / 0.3027 | 0.0122 | 0.005379 (0.003938, 0.006739) | 0.0007 |
| 12h_to_6h | random_forest | 531 | -0.0272 | 0.2815 / 0.2777 | 0.1949 / 0.1680 | 0.1556 / 0.3027 | 0.0000 | 0.002398 (0.000701, 0.004003) | 0.0084 |
| 6h_to_1h | zero_change_baseline | 522 | 0.0000 | 0.1114 / 0.1114 | 0.0274 / 0.0274 | 0.7794 / 0.7794 | 0.0000 | 0.000000 (0.000000, 0.000000) | NA |
| 6h_to_1h | linear_regression | 522 | -0.3149 | 0.1278 / 0.1114 | 0.0599 / 0.0274 | 0.3146 / 0.7794 | 0.3858 | 0.004024 (0.003262, 0.004836) | 0.0007 |
| 6h_to_1h | ridge_regression | 522 | -0.1350 | 0.1187 / 0.1114 | 0.0457 / 0.0274 | 0.3547 / 0.7794 | 0.3888 | 0.001722 (0.001160, 0.002356) | 0.0007 |
| 6h_to_1h | random_forest | 522 | -0.0122 | 0.1121 / 0.1114 | 0.0300 / 0.0274 | 0.7292 / 0.7794 | 0.0094 | 0.000148 (-0.000235, 0.000561) | 0.4598 |

## Interpretation

No evaluated model beats the zero-change forecast after the paired weekly-block bootstrap and Benjamini-Hochberg adjustment. Within this sample, the evidence is consistent with weak-form efficiency; this is not proof of efficiency.

A positive OOS R² here means lower squared revision error than predicting zero, not explanatory power relative to a test-set mean. Sign accuracy uses a ±0.005 no-change band, matching the midpoint grid. Separate marginal model metrics are not treated as evidence unless the paired block comparison also survives adjustment.

### Pair-level reading

- **24h_to_12h:** all evaluated fitted models have non-positive OOS R² versus zero.
- **12h_to_6h:** all evaluated fitted models have non-positive OOS R² versus zero.
- **6h_to_1h:** all evaluated fitted models have non-positive OOS R² versus zero.

## Feature and sample audit

- **24h_to_12h:** 7471 paired contracts across 1723 events; largest numeric-feature missing rate is 100.0% (delta_p_24h); partially missing features are imputed from training data only. Test observations with bucket labels unseen in training: 3.8%. Structurally unavailable and excluded: delta_p_24h.
- **12h_to_6h:** 6381 paired contracts across 1685 events; largest numeric-feature missing rate is 67.8% (delta_p_6h); partially missing features are imputed from training data only. Test observations with bucket labels unseen in training: 6.4%.
- **6h_to_1h:** 4481 paired contracts across 1346 events; largest numeric-feature missing rate is 7.4% (delta_p_24h); partially missing features are imputed from training data only. Test observations with bucket labels unseen in training: 12.9%.

`efficiency_coefficients.csv` contains standardized linear/ridge coefficients from the training sample. They are descriptive and neither causal nor a substitute for out-of-sample performance.

## Limitations

1. The test set contains the final 531 event dates (2025-01-05 through 2026-06-19). It is chronologically honest, but regime and season composition can still affect external validity.
2. Weekly event blocks address short-run date dependence only approximately. The six mutually exclusive contracts within a day are averaged before resampling.
3. Bucket labels are high-cardinality and partially unseen chronologically; ridge is more defensible than unregularized linear coefficients in this sample. Unknown test labels map to the pooled infrequent category learned from training only.
4. Unconstrained linear predictions can imply later probabilities outside `[0, 1]`; the reported bound-violation rate is a model diagnostic and predictions are not silently clipped.
5. Hourly candle midpoints are not executable prices. This study tests statistical revision predictability, not net profitability.
6. Model and preprocessing choices are fixed for this run but still need seasonal, alternate-staleness, and alternate-block-length checks.

## Interpretation safeguards

- Seasonal, liquidity, and extreme-weather follow-ups are reported separately and do not overturn the full-sample result.
- Executable bid/ask prices, fees, slippage, and fill uncertainty remain unmodeled; the results do not support a claim of tradable alpha.
- Any future detected relationship should remain framed as predictability unless it survives chronological robustness and execution-cost checks.
