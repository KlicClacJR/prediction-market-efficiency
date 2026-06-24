# KXHIGHNY Full-History Study

## Scope and reproducibility

This report compares the original March 1–May 31, 2026 pilot with the maximum resolved history returned by Kalshi on June 20, 2026. The full sample spans August 6, 2021 through June 19, 2026. The calibration horizons, two-hour staleness rule, feature definitions, 70/30 chronological split, model specifications, seven-event block bootstrap, and Benjamini–Hochberg adjustment were not changed.

The completed raw run is `data/raw/kalshi/KXHIGHNY/20260620T213956.167773Z`. Its manifest contains 9,046 candle files and 219,420 candle records. Every recorded SHA-256 hash was verified before cleaning. The processed snapshot table contains 219,294 rows from 9,040 resolved contracts and 1,775 event dates; the omitted raw rows belong to contracts that were not eligible resolved observations at the configured endpoint.

| Sample | Event dates | Contracts | Snapshot rows | Date range |
|---|---:|---:|---:|---|
| Pilot | 92 | 552 | 20,604 | 2026-03-01 to 2026-05-31 |
| Full history | 1,775 | 9,040 | 219,294 | 2021-08-06 to 2026-06-19 |

The full sample has 19.3 times as many event dates, 16.4 times as many contracts, and 10.6 times as many snapshots as the pilot. All processed resolution labels are `yes` or `no`; there are no duplicate contract timestamps, missing midpoint probabilities, out-of-bound probabilities, or crossed bid/ask quotes.

## Calibration comparison

Intervals are 95% event-cluster bootstrap intervals. Scores are contract-level binary scores; they are not event-level multiclass scores.

| Horizon | Sample | Events | Brier score (95% CI) | Log loss (95% CI) | ECE (95% CI) |
|---:|---|---:|---:|---:|---:|
| 24h | Pilot | 92 | 0.0977 (0.0872, 0.1084) | 0.3097 (0.2817, 0.3393) | 0.0410 (0.0289, 0.0675) |
| 24h | Full | 1,731 | 0.1361 (0.1326, 0.1394) | 0.4151 (0.4058, 0.4240) | 0.0293 (0.0263, 0.0351) |
| 12h | Pilot | 92 | 0.0722 (0.0596, 0.0850) | 0.2303 (0.1928, 0.2695) | 0.0266 (0.0205, 0.0537) |
| 12h | Full | 1,765 | 0.1171 (0.1131, 0.1211) | 0.3568 (0.3462, 0.3672) | 0.0354 (0.0307, 0.0425) |
| 6h | Pilot | 92 | 0.0169 (0.0058, 0.0301) | 0.0633 (0.0269, 0.1078) | 0.0108 (0.0069, 0.0264) |
| 6h | Full | 1,690 | 0.0325 (0.0291, 0.0359) | 0.1128 (0.1030, 0.1232) | 0.0336 (0.0291, 0.0390) |
| 1h | Pilot | 92 | 0.0038 (0.0000, 0.0110) | 0.0193 (0.0051, 0.0462) | 0.0044 (0.0033, 0.0091) |
| 1h | Full | 1,399 | 0.0122 (0.0099, 0.0147) | 0.0456 (0.0387, 0.0526) | 0.0204 (0.0173, 0.0246) |

The full-history Brier score and log loss are higher at every horizon than in the spring pilot. This should not be read as proof that the market deteriorated: the pilot is a narrow seasonal slice, while the full series crosses exchange vintages, contract designs, weather seasons, and liquidity regimes. Prevalence also changes from about 0.167 in the six-bucket pilot to roughly 0.21–0.24 in the full contract-level samples. ECE is lower at 24h in the full sample but higher at 12h, 6h, and 1h. Because ECE depends on prevalence, bin occupancy, and sample composition, it is not directly comparable as a pure measure of market quality across these samples.

Both samples show lower Brier score and log loss nearer close. That pattern is mechanically expected when information accumulates and outcomes become less uncertain; it is not, by itself, an efficiency test. The much narrower full-history intervals mainly reflect the larger number of event clusters.

## Chronological efficiency comparison

Negative loss differences favor a fitted model; positive differences favor the zero-change forecast. The pilot used 64 training and 28 test dates. The full study uses the first 1,236 dates through January 4, 2025 for training and the final 531 dates through June 19, 2026 for testing. Pair-specific event counts are slightly smaller when one of the required horizon quotes is unavailable.

| Pair | Model | Pilot OOS R²; loss diff. (95% CI) | Full OOS R²; loss diff. (95% CI) | Full adjusted p |
|---|---|---:|---:|---:|
| 24h→12h | Linear | 0.0643; -0.00102 (-0.00271, 0.00120) | -0.2009; 0.00410 (0.00315, 0.00500) | 0.0007 |
| 24h→12h | Ridge | 0.0609; -0.00096 (-0.00221, 0.00086) | -0.1041; 0.00205 (0.00125, 0.00276) | 0.0007 |
| 24h→12h | Random forest | Not run | -0.0233; 0.00050 (0.00024, 0.00077) | 0.0019 |
| 12h→6h | Linear | -0.2307; 0.01105 (0.00287, 0.02004) | -0.1227; 0.00946 (0.00756, 0.01133) | 0.0007 |
| 12h→6h | Ridge | -0.0995; 0.00472 (-0.00099, 0.01056) | -0.0690; 0.00538 (0.00394, 0.00674) | 0.0007 |
| 12h→6h | Random forest | Not run | -0.0272; 0.00240 (0.00070, 0.00400) | 0.0084 |
| 6h→1h | Linear | 0.0052; -0.00014 (-0.00106, 0.00053) | -0.3149; 0.00402 (0.00326, 0.00484) | 0.0007 |
| 6h→1h | Ridge | 0.0156; -0.00030 (-0.00095, 0.00025) | -0.1350; 0.00172 (0.00116, 0.00236) | 0.0007 |
| 6h→1h | Random forest | Not run | -0.0122; 0.00015 (-0.00024, 0.00056) | 0.4598 |

No fitted model beats zero change in the full chronological test. All nine full-history OOS R² values are negative. Eight model/pair comparisons have positive loss-difference intervals or otherwise fail to favor the model; the 6h→1h random-forest interval includes zero. The small positive pilot R² values at 24h→12h and 6h→1h therefore do not persist in the broader test.

The statistically significant full-history comparisons above mostly establish that a fitted model is worse than zero change, not that the martingale null has been rejected in a profitable direction. The random forest now passes the pre-specified sample-size gate, but it also fails to beat the baseline. These results leave the study's conservative conclusion unchanged: the tested public features provide no demonstrated out-of-sample improvement over the zero-revision forecast, which is consistent with weak-form efficiency for this design. This is neither proof that prices are martingales nor evidence that every possible public signal is uninformative.

Pilot and full-history OOS metrics are not simple nested estimates. Expanding the data moves the chronological cutoff: the full model trains on 2021–2024 and tests on 2025–2026, whereas the pilot trains and tests only within spring 2026. Differences can therefore reflect seasonal composition, exchange evolution, or model transport across regimes as well as sampling error.

## Coverage and comparability issues

- Fixed-horizon event coverage is 1,731/1,775 at 24h, 1,765/1,775 at 12h, 1,690/1,775 at 6h, and 1,399/1,775 at 1h. Near-close coverage remains the principal gap.
- The contract design changes over history. Of 1,775 events, 108 have one contract, 153 have two, 227 have four, four have five, and 1,283 have six. Early threshold contracts are not equivalent to a complete six-bucket multiclass event.
- At 24h, only 753 events have all six selected contracts; at 12h, 827; at 6h, 479; and at 1h, 410. Event probability sums for partial or legacy threshold sets are not interpretable as exhaustive probability mass. The raw contract-level scores remain usable, but event-normalized results should not be pooled across designs without a separate restriction.
- Quote staleness averages about 1.0–1.3 hours under the unchanged two-hour tolerance. Later-horizon exclusions are therefore selective rather than random.
- For the 24h→12h model, the 24-hour lag is structurally unavailable and remains excluded. In the full 12h→6h pair, the six-hour change is missing for 67.8% of rows, largely because many historical contracts lack enough earlier quoted history. Training-only imputation preserves chronology but cannot create information that was never observed.
- The paired block bootstrap averages contracts within event date before resampling, preserving same-day bucket dependence. Seven-day blocks are still only an approximation to weather and market-regime dependence.
- Midpoints are not executable prices, and no fees, slippage, or fill uncertainty are modeled.

## Conclusion and subsequent evidence

The full-history expansion increases precision and enables the pre-specified random forest, but it does not uncover robust revision predictability. The weak-form-efficiency conclusion remains unchanged in the limited sense supported by this experiment: none of the tested models improves on zero revision out of sample.

Subsequent liquidity, information-arrival, extreme-weather, and external-forecast studies hold these core results fixed. They identify heterogeneity in late-stage calibration and the timing of information arrival, but do not uncover a subgroup in which the tested models beat zero revision. Executable-price and fee analysis remains outside this repository, so no result should be described as tradable alpha.
