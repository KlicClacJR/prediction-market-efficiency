# Prediction Market Efficiency and Information Aggregation

## Abstract

This study evaluates calibration and weak-form informational efficiency in Kalshi's daily
New York City high-temperature markets. The full-history dataset covers August 6, 2021
through June 19, 2026: 1,775 event dates, 9,040 resolved binary contracts, and 219,294
hourly market snapshots. Market probabilities become substantially more accurate as close
approaches, but the improvement is unevenly timed: 70.3% of the matched-sample 24h→1h
Brier-score reduction occurs between 12h and 6h. That interval also contains the greatest
trading activity, open-interest growth, and probability movement. In a chronological test
on the final 531 event dates, linear, ridge, and random-forest models all fail to improve
on a zero-revision forecast. Low-liquidity contracts exhibit weaker late-stage
calibration, while extreme temperatures do not reveal additional predictability.
Archived ECMWF updates coincide with the response window but do not provide causal or
cross-event magnitude evidence sufficient to explain it.

## 1. Questions and hypotheses

The study asks two primary questions:

1. Do market-implied probabilities correspond to observed contract frequencies?
2. Can future probability revisions be predicted from public market information?

The main efficiency null is

$$
E[p_{t+h}-p_t\mid\mathcal{F}_t]=0.
$$

The analysis also asks when information enters prices and whether calibration or
predictability differs with liquidity, temperature extremity, season, or external weather
forecast updates.

## 2. Data construction

The pipeline downloads market metadata, resolution labels, and hourly candles for
`KXHIGHNY`. Each raw run is immutable and accompanied by a manifest of retrieval metadata,
record counts, and SHA-256 hashes. Cleaning normalizes Kalshi's current and historical API
formats and validates timestamp uniqueness, probability bounds, bid/ask ordering, and
resolution labels.

The final canonical snapshot table contains 219,294 rows from 9,040 resolved contracts.
The first event is August 6, 2021 and the last is June 19, 2026. A quote must have both a
YES bid and ask; its probability is their midpoint. Fixed-horizon observations use the
last quote at or before 24h, 12h, 6h, or 1h before close and reject quotes more than two
hours stale.

Temperature contracts within a daily event are dependent and often mutually exclusive.
All uncertainty calculations therefore resample complete event dates. Calibration is
still evaluated at the binary-contract level, not as a multiclass event score. This
distinction is important because early event designs contain threshold contracts rather
than a complete set of six buckets.

## 3. Methods

Calibration is summarized with Brier score, log loss clipped at `1e-6`, fixed-decile
reliability, expected calibration error (ECE), and 95% event-cluster bootstrap intervals.
A balanced-panel decomposition restricts attention to 4,281 contracts from 1,299 events
that have usable quotes at all four horizons.

Efficiency targets are midpoint revisions for 24h→12h, 12h→6h, and 6h→1h. Predictors are
the current midpoint, bid/ask spread, volume, open interest, lagged probability changes,
trailing volatility and volume, bucket label, and time to close. The first 70% of event
dates train linear, ridge, and—when the sample-size gate is met—random-forest models. The
final 531 dates form one untouched test period. All preprocessing is fitted on training
data only. Models are compared with a zero-revision forecast using out-of-sample R²,
RMSE, MAE, sign accuracy, and paired circular seven-event block bootstraps; p-values are
adjusted with Benjamini–Hochberg.

## 4. Results

### 4.1 Calibration

| Horizon | Contracts | Events | Brier score (95% CI) | ECE (95% CI) |
|---:|---:|---:|---:|---:|
| 24h | 7,910 | 1,731 | 0.1361 (0.1326, 0.1394) | 0.0293 (0.0263, 0.0351) |
| 12h | 8,221 | 1,765 | 0.1171 (0.1131, 0.1211) | 0.0354 (0.0307, 0.0425) |
| 6h | 6,506 | 1,690 | 0.0325 (0.0291, 0.0359) | 0.0336 (0.0291, 0.0390) |
| 1h | 4,771 | 1,399 | 0.0122 (0.0099, 0.0146) | 0.0204 (0.0173, 0.0246) |

The forecasts are broadly meaningful, and proper scores improve sharply toward close.
That improvement is partly expected because outcome uncertainty resolves over time; it is
not evidence of inefficiency. Coverage also declines near close, so the unmatched scores
should not be treated as a pure within-contract time series. The balanced-panel analysis
addresses that composition issue.

### 4.2 Chronological efficiency

None of the nine fitted model/pair combinations achieves positive out-of-sample R²
against zero revision. Random forest comes closest for 6h→1h with R² of -0.012; its
squared-loss difference interval includes zero. In the other comparisons, fitted models
are measurably worse or fail to favor the model. Thus the tested public features do not
provide demonstrated out-of-sample revision predictability. This result is consistent
with weak-form efficiency under the study design, not proof that every public signal is
already incorporated.

![Predicted versus actual revisions](figures/predicted_vs_actual_revisions.png)

### 4.3 Timing of information arrival

On the balanced panel, Brier score falls from 0.1536 at 24h to 0.0115 at 1h. The 12h→6h
interval contributes 70.3% of that total reduction and 68.8% of the corresponding
log-loss reduction. It also contributes 55.7% of total absolute probability movement.
Trading volume per hour, open-interest growth per hour, and mean absolute revisions all
peak in the same interval.

![Information-arrival decomposition](figures/information_arrival.png)

The concentration appears in every season, temperature regime, and 24h liquidity
quartile. It is therefore not generated by one narrow subgroup, although its magnitude
varies across them.

### 4.4 Conditional results

The least-liquid quartile has significantly larger ECE at every horizon. Its proper
scores are not uniformly worse early, but at 6h and 1h its Brier score is roughly
2.6–2.7 times the highest-liquidity quartile. The defensible conclusion is specific:
low-liquidity contracts show weaker late-stage calibration, not universally worse
forecast quality.

An extreme-temperature label is estimated from training-period winning-bucket proxies.
Extreme-minus-normal confidence intervals do not establish worse calibration, and every
fitted model has negative subgroup out-of-sample R². Extreme weather therefore does not
identify a pocket of detectable additional predictability under this definition.

### 4.5 External weather information

Archived ECMWF model runs and NOAA observed highs are available for 826 overlapping
events beginning in March 2024. ECMWF high-temperature mean absolute error improves from
2.99°F at 24h to 2.67°F at 12h and 2.50°F at 6h. Its largest error reduction occurs before,
not during, the market's dominant 12h→6h interval.

Market activity increases around an assumed six-hour-lagged 12Z model availability time,
but larger ECMWF updates do not induce a larger activity increase. The same-interval
relationship between absolute ECMWF and market revisions is negative for 12h→6h. These
results support clock-time alignment while rejecting a simple dose-response explanation.
They do not establish causality because official NWS forecasts, observations, private
models, and time-of-day trading patterns overlap.

## 5. Limitations

- Contract designs change over time, and incomplete threshold sets make event-level
  probability sums non-comparable across vintages.
- Later-horizon quote coverage is selective; the 1h sample covers 1,399 of 1,775 events.
- Hourly candles blur within-hour sequencing and do not reconstruct order-book depth.
- Midpoint forecasts are not executable prices, and this study does not model fees,
  slippage, market impact, or fill uncertainty.
- Seven-day blocks approximate but cannot fully capture longer weather and market regimes.
- The extreme-temperature proxy is interval-valued and tail-censored.
- ECMWF is a benchmark rather than the official archived forecast available to every
  participant, and assumed availability times are approximate.
- One weather series cannot establish external validity for politics, economics, other
  exchanges, or prediction markets generally.

## 6. Conclusion

KXHIGHNY probabilities contain substantial information and become highly accurate near
close. Most of the measured improvement occurs in a narrow 12h→6h window accompanied by
intense trading and position growth. Yet public market-state features do not improve on a
zero-revision forecast out of sample, including among extreme events. Liquidity matters
for late-stage calibration, while the external weather comparison narrows—but does not
causally identify—the source of the information-arrival spike.

The evidence supports a restrained conclusion: this market is broadly informative and
the tested revision dynamics are consistent with weak-form efficiency, with meaningful
heterogeneity in when and where calibration improves.

## Reproducibility appendix

The exact sample configuration is in `config/mvp.yaml`. Core results are generated by
`pm-efficiency fetch`, `pm-efficiency clean`, `pm-efficiency build`, and the scripts in
`scripts/`. Detailed provenance and robustness results are in the
[full-history report](full_history_report.md), [efficiency report](efficiency_report.md),
[liquidity report](liquidity_report.md), [information-arrival report](information_arrival_report.md),
[extreme-weather report](extreme_weather_report.md), and
[weather-information report](weather_information_source_report.md).
