# KXHIGHNY Pilot Calibration Report

## Status

Completed pilot for events dated **March 1 through May 31, 2026**. This validates the
research pipeline and establishes baseline calibration evidence; it is not the final
full-history study.

## Provenance and sample

- Raw run: `data/raw/kalshi/KXHIGHNY/20260620T043500.751258Z`
- Retrieved: June 20, 2026 at 04:35 UTC
- Raw manifest: 564 contract files and 20,659 hourly candles across Kalshi's historical
  and live/recent partitions; every recorded SHA-256 hash verified.
- Processed pilot: 20,575 snapshots, 552 contracts, and 92 daily events.
- Event-date bounds: March 1–May 31, 2026, inclusive.
- Processed CSV hash matches `market_snapshots.manifest.json`.

The raw API query returned contracts whose trading windows crossed the requested UTC
boundaries. The build now filters explicitly on event date, preventing February 28 and
June 1 events from entering the canonical pilot dataset.

## Data-quality audit

- Missing bid, ask, or midpoint values: **0**
- Duplicate `(contract_id, timestamp)` rows: **0**
- Midpoints outside `[0, 1]`: **0**
- Crossed quotes: **0**
- Resolution labels: only `yes` and `no`
- Missing-price exclusions while creating the snapshot CSV: **0**
- The full metadata universe contained 12 unresolved/exceptional contracts; these were
  excluded before resolved-outcome analysis.

Cleaning the real metadata initially exposed scalar timestamp parsing as a bottleneck.
Vectorized market and candle parsing reduced normalization to approximately eight seconds.
The pilot also exposed mixed millisecond/microsecond Parquet timestamps; as-of join keys
are now normalized to nanosecond UTC.

## Horizon coverage and event probability sums

| Horizon | Observations | Events represented | Events with all 6 buckets | Mean probability sum | Range | Max staleness |
|---:|---:|---:|---:|---:|---:|---:|
| 24h | 552 | 92 | 92 / 92 | 1.032 | 0.945–1.105 | 1.98h |
| 12h | 552 | 92 | 92 / 92 | 1.024 | 0.935–1.110 | 0.98h |
| 6h | 551 | 92 | 91 / 92 | 1.019 | 0.960–1.050 | 1.98h |
| 1h | 532 | 91 | 82 / 92 | 1.020 | 1.005–1.075 | 1.98h |

Incomplete coverage:

- 6h: `KXHIGHNY-26MAY08` is missing one eligible bucket quote.
- 1h: `KXHIGHNY-26MAY31` has no eligible quotes within the two-hour staleness limit.
- 1h partial events: `KXHIGHNY-26APR20`, `KXHIGHNY-26APR22`,
  `KXHIGHNY-26MAY07`, `KXHIGHNY-26MAY14`, `KXHIGHNY-26MAY16`,
  `KXHIGHNY-26MAY21`, `KXHIGHNY-26MAY28`, `KXHIGHNY-26MAY29`, and
  `KXHIGHNY-26MAY30`.

Raw midpoint sums average slightly above one, consistent with quote spreads and the fact
that raw bucket midpoints are not normalized event probabilities. The incomplete 1h panel
must remain disclosed in downstream comparisons.

## Calibration results

Confidence intervals are percentile intervals from 1,000 bootstrap resamples clustered by
`event_id`. Log loss clips probabilities at `1e-6`.

| Horizon | Brier score (95% CI) | Log loss (95% CI) | ECE (95% CI) |
|---:|---:|---:|---:|
| 24h | 0.0977 (0.0872–0.1084) | 0.3097 (0.2817–0.3393) | 0.0410 (0.0289–0.0675) |
| 12h | 0.0722 (0.0596–0.0850) | 0.2303 (0.1928–0.2695) | 0.0266 (0.0205–0.0537) |
| 6h | 0.0169 (0.0058–0.0301) | 0.0633 (0.0269–0.1078) | 0.0108 (0.0069–0.0264) |
| 1h | 0.0038 (0.0000–0.0115) | 0.0195 (0.0051–0.0485) | 0.0045 (0.0033–0.0092) |

Scores improve sharply as resolution approaches. That pattern is expected in daily weather
markets because forecast and observed-temperature information accumulates throughout the
day; it is not, by itself, evidence for or against market efficiency. Decile reliability
curves are visually noisy where bins contain few observations, so the decile count table
must accompany the figure.

## Reproduction

```bash
pm-efficiency clean
pm-efficiency build
python scripts/descriptive_summary.py
python scripts/calibration_analysis.py
```

Primary artifacts:

- `data/processed/market_snapshots.csv`
- `reports/tables/descriptive_summary.csv`
- `reports/tables/calibration_metrics.csv`
- `reports/tables/calibration_deciles.csv`
- `reports/figures/reliability_diagram.png`

The operational horizon anchor is `close_time`. Expanding to full history and running the
efficiency/martingale study should follow only after retaining these coverage diagnostics
as robustness filters.
