# KXHIGHNY Pilot Calibration Report

## Status and provenance

This is an exploratory audit of New York daily-high-temperature events dated **March 1
through May 31, 2026**. It validates the research pipeline and estimates spring-sample
calibration; it does not establish general calibration or weak-form efficiency.

- Raw run: `data/raw/kalshi/KXHIGHNY/20260620T210850.724188Z`
- Retrieved: June 20, 2026 at 21:08 UTC
- Raw manifest: 564 contract files and 20,760 hourly candles across Kalshi's historical
  and live/recent partitions; every recorded SHA-256 hash verified.
- Processed sample: 20,604 snapshots, 552 contracts, and 92 daily events.
- Processed CSV hash matches `market_snapshots.manifest.json`.
- Horizon anchor: `close_time`; the latest quote at or before the target is accepted only
  when no more than two hours stale.

The fetch includes a 12-hour post-event buffer because the May 31 event closes at 04:59
UTC on June 1. Without that buffer, its 1h observations were mechanically truncated. The
build separately filters on event date, so adjacent February 28 and June 1 events cannot
enter the pilot.

## 1. Data audit

### Integrity and event structure

- Missing bid, ask, or midpoint values: **0**
- Duplicate `(contract_id, timestamp)` rows: **0**
- Duplicate `(contract_id, horizon)` selections: **0**
- Midpoints outside `[0, 1]`: **0**
- Crossed quotes: **0**
- Resolution labels: only `yes` and `no`
- Every event has exactly **six distinct mutually exclusive bucket contracts** and exactly
  **one resolved-YES contract**.
- The full metadata universe contained 12 unresolved/exceptional contracts; none enter the
  resolved pilot sample.

Contracts are therefore not literally double-counted: each contract appears once at each
horizon. The same underlying weather event intentionally contributes six binary records.
Treating those six records as independent would be pseudo-replication, so inference must
operate on the event cluster.

### Unit of calibration

The reported Brier score, log loss, decile table, and ECE are **contract-level binary
metrics**, not event-level multiclass metrics. At a complete horizon, each event contributes
one positive and five negative binary outcomes. Consequently:

- the outcome prevalence is mechanically `1/6 = 0.1667`;
- low-probability losing buckets dominate the observation count; and
- the mean binary Brier score is exactly one-sixth of the event-summed vector Brier score
  when all six contracts are observed.

The raw bucket midpoints do not necessarily sum to one, so the current analysis does not
score a coherent six-outcome probability vector. Claims about event-level or multiclass
calibration require a separate analysis using complete events and an explicitly disclosed
normalization rule.

### Are 92 events enough?

Ninety-two event clusters are adequate for an exploratory estimate of aggregate Brier
score, log loss, and ECE: all four horizons have 92 clusters and finite event-bootstrap
intervals. They are not enough to support a detailed ten-bin reliability curve or broad
claims across seasons.

| Horizon | Decile counts from 0–10% through 90–100% | Sparse-bin assessment |
|---:|---|---|
| 24h | 264, 89, 74, 62, 41, 10, 4, 3, 4, 1 | Four bins have fewer than 10 events; the top bin has one. |
| 12h | 345, 45, 28, 34, 25, 33, 17, 6, 6, 13 | Two bins have only six events. |
| 6h | 447, 8, 3, 1, 0, 0, 3, 1, 9, 79 | Two bins are empty and six have fewer than 10 events. |
| 1h | 444, 2, 0, 0, 0, 0, 0, 1, 0, 91 | Six bins are empty; only the endpoint bins are estimable. |

Thus the 24h and 12h aggregate results are moderately supported, while individual extreme
deciles remain unstable. At 6h and 1h, ECE mostly measures calibration near zero and one;
it does not identify calibration across the interior of the probability range. The sample
also covers one spring season in one city, and adjacent weather days may be serially
dependent.

### Coverage and probability sums

| Horizon | Contracts | Events | Events with all 6 buckets | Mean raw sum | Range | Max staleness |
|---:|---:|---:|---:|---:|---:|---:|
| 24h | 552 | 92 | 92 / 92 | 1.032 | 0.945–1.105 | 1.98h |
| 12h | 552 | 92 | 92 / 92 | 1.024 | 0.935–1.110 | 0.98h |
| 6h | 551 | 92 | 91 / 92 | 1.019 | 0.960–1.050 | 1.98h |
| 1h | 538 | 92 | 83 / 92 | 1.020 | 1.005–1.075 | 1.98h |

The 6h panel omits one losing contract in `KXHIGHNY-26MAY08`. The 1h panel omits
14 losing contracts across nine events: `KXHIGHNY-26APR20`, `KXHIGHNY-26APR22`,
`KXHIGHNY-26MAY07`, `KXHIGHNY-26MAY14`, `KXHIGHNY-26MAY16`,
`KXHIGHNY-26MAY21`, `KXHIGHNY-26MAY28`, `KXHIGHNY-26MAY29`, and
`KXHIGHNY-26MAY30`.

For every omitted contract, the latest quote before the target was 2.98–5.98 hours stale
and its midpoint was 0.005. In most cases a new candle appears one minute after the target,
but using it would violate the no-lookahead rule. The missingness is therefore caused by
sparse updates in nearly settled losing buckets plus the strict timestamp rule—not by a
missing winning bucket or an unresolved event.

Incomplete bucket coverage biases event probability sums downward. The 1h raw sum averages
1.0122 for the nine partial events versus 1.0206 for the 83 complete events, consistent with
omitting one or more 0.005 buckets. It also raises the contract-level outcome prevalence
from 0.1667 to 0.1710 and omits easy correct negatives, which should slightly worsen rather
than improve the reported 1h proper scores. Probability sums are additionally approximate
because component quotes can have different timestamps within the two-hour tolerance.

## 2. Interpretation of 24h/12h/6h/1h calibration results

Confidence intervals are percentile intervals from 1,000 bootstrap resamples of complete
`event_id` clusters. Log loss clips probabilities at `1e-6`.

| Horizon | Brier score (95% CI) | Log loss (95% CI) | ECE (95% CI) |
|---:|---:|---:|---:|
| 24h | 0.0977 (0.0872–0.1084) | 0.3097 (0.2817–0.3393) | 0.0410 (0.0289–0.0675) |
| 12h | 0.0722 (0.0596–0.0850) | 0.2303 (0.1928–0.2695) | 0.0266 (0.0205–0.0537) |
| 6h | 0.0169 (0.0058–0.0301) | 0.0633 (0.0269–0.1078) | 0.0108 (0.0069–0.0264) |
| 1h | 0.0038 (0.0000–0.0110) | 0.0193 (0.0051–0.0462) | 0.0044 (0.0033–0.0091) |

### 24h

The 24h panel has complete event coverage and the broadest useful spread of probabilities.
Its ECE of 0.041 indicates a weighted average absolute bin gap of about four percentage
points, but the apparent behavior above 60% is based on only 12 contracts across the final
four bins. This is the best pilot horizon for studying non-extreme calibration, subject to
the spring-only sample.

### 12h

All 92 events and 552 contracts remain present. Brier score, log loss, and ECE are lower
than at 24h, and the reliability table still has observations in every decile. The two
80%-adjacent bins have only six observations each, so local deviations there should not be
treated as stable bias.

### 6h

The aggregate scores improve sharply, but 526 of 551 contracts (95.5%) are already below
10% or at least 90%. Two interior deciles are empty and most others contain fewer than ten
events. The low ECE therefore supports good endpoint calibration in this sample, not a
general six-hour calibration function. One omitted 0.005 losing bucket has negligible
numerical influence but should remain disclosed.

### 1h

At 1h, 535 of 538 contracts (99.4%) are in the endpoint deciles. Six deciles are empty,
and the only interior observations comprise two contracts in 10–20% and one in 70–80%.
The very low Brier score and ECE mostly say that nearly resolved contracts are priced near
their realized endpoints. They provide little information about calibration at intermediate
probabilities.

### Why scores improve near resolution

The monotonic score improvement is mechanically expected as uncertainty resolves. Updated
forecasts, model runs, and observed temperatures arrive during the day; a rational forecast
should approach zero or one and receive a better proper score. This pattern is not evidence
of weak-form efficiency and does not show that earlier prices were biased.

Sample attrition is not the explanation: restricting every horizon to the same 537 contracts
across all 92 events still yields Brier scores of 0.1004, 0.0742, 0.0174, and 0.0038 from
24h to 1h. A formal horizon comparison would nevertheless require paired event-clustered
confidence intervals for score differences, not a visual comparison of separate marginal
intervals.

## 3. Limitations

1. **Calibration is not efficiency.** Proper scores evaluate forecast accuracy and
   calibration; weak-form efficiency concerns whether future price revisions are
   predictable from information already in the market.
2. **Contract-level weighting.** Six dependent binary buckets represent one event. Event
   clustering fixes the standard-error unit but does not convert the estimand into
   event-level multiclass calibration.
3. **Cluster bootstrap scope.** Resampling `event_id` correctly keeps all buckets from a
   sampled day together, including partially observed events. It assumes event clusters are
   exchangeable and does not handle serial weather dependence across adjacent days.
4. **Sparse deciles.** Equal-width decile ECE is unstable at 24h extremes and is largely an
   endpoint statistic at 6h and 1h. Empty or singleton bins cannot support range-specific
   bias claims.
5. **Asynchronous and incomplete vectors.** A two-hour staleness tolerance permits bucket
   prices from different timestamps in one event sum. Missing 0.005 losing buckets bias
   partial sums downward and change contract-level weighting.
6. **Raw probabilities are incoherent as a vector.** Midpoint sums average above one, so
   raw contract probabilities cannot be interpreted directly as a normalized multinomial
   forecast.
7. **Limited external validity.** Ninety-two spring days in New York do not establish
   performance in other seasons, cities, market categories, or exchanges.
8. **Market-price convention.** Hourly candle closing midpoints are not necessarily
   executable prices, and the candle immediately after a target cannot be used without
   lookahead.

## 4. Next steps before making research claims

1. Extend the sample to the full available history and report results by season; retain the
   event-date filter and post-event fetch buffer.
2. Pre-register primary estimands: contract-level binary calibration as the baseline and a
   complete-event, normalized multiclass sensitivity analysis using event-level Brier and
   log scores.
3. Repeat calibration on complete events only, on the 537-contract common-horizon panel,
   and under alternative staleness limits. Report how inclusion of stale 0.005 contracts
   changes 1h results.
4. Replace unsupported decile claims with bins that meet a minimum event count, while
   retaining fixed deciles as the pre-specified headline ECE. Add event-clustered intervals
   to each reliability-bin rate.
5. Use paired event-cluster bootstrap estimates for score changes between horizons. Add a
   weekly block-bootstrap sensitivity analysis for serial weather dependence.
6. Test weak-form efficiency directly: predict non-overlapping 1h and 6h future midpoint
   revisions using only lagged public price, momentum, volatility, volume, open interest,
   spread, and time-to-close features. Use chronological event-level train/test splits,
   compare against the zero-revision martingale forecast, and adjust multiple tests.
7. Separate statistical predictability from tradability by evaluating revisions against
   contemporaneous spreads, fees, and feasible execution prices.

## Reproduction and artifacts

```bash
pm-efficiency clean
pm-efficiency build
python scripts/descriptive_summary.py
python scripts/calibration_analysis.py
```

- `data/processed/market_snapshots.csv`
- `reports/tables/descriptive_summary.csv`
- `reports/tables/calibration_metrics.csv`
- `reports/tables/calibration_deciles.csv`
- `reports/figures/reliability_diagram.png`
