# Extreme-Weather Calibration and Efficiency

## Definition and chronology

The canonical exchange data do not contain an exact realized temperature field. This study therefore reconstructs a conservative event-level proxy from the unique winning modern bucket: the midpoint for a bounded two-degree bucket, one degree below a lower-tail threshold, or one degree above an upper-tail threshold. It yields 1,250 events, including 187 censored tail winners.

Extreme cutoffs are estimated only from the 744 proxy events in the chronological efficiency training period ending January 4, 2025. The training-sample 10th and 90th percentiles are 42.5°F and 85.5°F. Events at or beyond either threshold are classified as extreme; later outcomes do not alter those cutoffs.

Calibration confidence intervals and extreme-minus-normal tests use 1,000 event-date cluster bootstrap draws. Efficiency results subgroup the already-fitted chronological test predictions; no realized-temperature label enters a predictor.

## Calibration

| Horizon | Normal Brier (95% CI) | Extreme Brier (95% CI) | Extreme minus normal (95% CI) |
|---:|---:|---:|---:|
| 24h | 0.1309 (0.1271, 0.1349) | 0.1233 (0.1166, 0.1297) | -0.0077 (-0.0154, 0.0001) |
| 12h | 0.1119 (0.1072, 0.1168) | 0.1062 (0.0991, 0.1138) | -0.0056 (-0.0149, 0.0026) |
| 6h | 0.0368 (0.0322, 0.0416) | 0.0294 (0.0225, 0.0369) | -0.0075 (-0.0161, 0.0011) |
| 1h | 0.0126 (0.0094, 0.0161) | 0.0121 (0.0074, 0.0179) | -0.0005 (-0.0061, 0.0057) |

None of the extreme-minus-normal confidence intervals for Brier score, log loss, or ECE establishes worse calibration for extreme events. Point estimates are generally slightly lower for extremes, but the paired cluster intervals include zero. The study therefore finds no robust extreme-weather calibration penalty under this definition.

## Chronological efficiency

The full-sample conclusion also survives the extreme-event split. Every linear and ridge OOS R² is negative for both normal and extreme test events. Random-forest OOS R² is also negative in all six subgroup/pair cells. Examples:

| Pair | Model | Extreme OOS R²; loss diff. CI | Normal OOS R²; loss diff. CI |
|---|---|---:|---:|
| 24h→12h | Ridge | -0.057; (-0.00004, 0.00248) | -0.127; (0.00186, 0.00306) |
| 12h→6h | Random forest | -0.004; (-0.00268, 0.00340) | -0.038; (0.00112, 0.00450) |
| 6h→1h | Random forest | -0.039; (-0.00006, 0.00096) | -0.005; (-0.00036, 0.00058) |

Negative OOS R² means the model loses to zero revision. A confidence interval containing zero is absence of a detected difference, not evidence that the losses are identical. No tested public-feature model shows conditional predictability concentrated in extreme events.

## Limitations

- The temperature proxy is interval-valued and tail-censored; it is not the exact NWS observation.
- Absolute percentiles identify very cold and very hot daily highs, not seasonally anomalous temperatures. A month- or day-of-year-normalized definition is a distinct robustness test.
- Legacy threshold-only events cannot be assigned a defensible exact proxy and are excluded, so this is not the entire 2021–2026 sample.
- Extreme status is known only after resolution. Subgroup results diagnose where errors occurred; they do not constitute an ex-ante tradable classifier.
- Weather regimes may persist longer than the seven-day bootstrap block.

Within these limits, extreme events do not identify a condition where the full-sample calibration or weak-form-efficiency conclusion breaks. The underlying outputs are `extreme_thresholds.csv`, `extreme_calibration_metrics.csv`, `extreme_calibration_tests.csv`, and `extreme_efficiency_metrics.csv`; the figure is `reports/figures/extreme_weather.png`.
