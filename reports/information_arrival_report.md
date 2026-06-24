# Information Arrival Across Forecast Horizons

## Design

To avoid compositional changes across horizons, this study uses a balanced panel of 4,281 contracts from 1,299 events with eligible quotes at all four horizons. Brier and clipped log-loss changes are therefore paired within the same contract. Confidence intervals use 1,000 event-date cluster bootstrap draws.

An interval's error reduction is the earlier-horizon loss minus the later-horizon loss. Positive values indicate that prices became more accurate. Shares divide each interval reduction by the total matched-sample reduction from 24h to 1h.

## Matched-sample calibration

| Horizon | Brier score (95% CI) | Log loss (95% CI) |
|---:|---:|---:|
| 24h | 0.1536 (0.1484, 0.1587) | 0.4568 (0.4429, 0.4718) |
| 12h | 0.1343 (0.1280, 0.1407) | 0.4028 (0.3868, 0.4212) |
| 6h | 0.0344 (0.0301, 0.0390) | 0.1183 (0.1037, 0.1319) |
| 1h | 0.0115 (0.0091, 0.0144) | 0.0432 (0.0365, 0.0504) |

## Error-reduction decomposition

| Interval | Brier reduction (95% CI) | Share of total | Log-loss reduction (95% CI) | Share of total |
|---|---:|---:|---:|---:|
| 24h→12h | 0.0193 (0.0147, 0.0238) | 13.6% | 0.0540 (0.0423, 0.0652) | 13.1% |
| 12h→6h | 0.0999 (0.0935, 0.1067) | 70.3% | 0.2845 (0.2660, 0.3026) | 68.8% |
| 6h→1h | 0.0229 (0.0192, 0.0267) | 16.1% | 0.0751 (0.0643, 0.0871) | 18.2% |

All three paired intervals have positive confidence intervals, but the dominant information-arrival window is 12h→6h before close. It accounts for about 70% of the total Brier reduction and 69% of the total log-loss reduction. The result is not an artifact of changing contract coverage because the decomposition uses the same 4,281 contracts throughout.

This identifies when forecast errors fall, not why. For NYC daily highs, the 12h→6h interval often overlaps the transition from an overnight forecast to same-day observations and updated weather guidance. The later [weather-information study](weather_information_source_report.md) compares this timing with archived ECMWF runs and NOAA observations but does not establish a causal source.

## Limitations

- The balanced panel excludes contracts without all four quotes and therefore describes the better-covered 1,299 events.
- Close time is the operational anchor; exchange settlement occurs later.
- Error reduction near resolution is mechanically expected as uncertainty resolves. It does not establish a market inefficiency.
- Hourly candles and a two-hour staleness tolerance blur the exact minute of information arrival.
- The decomposition is an average across seasons and contract vintages; it can conceal heterogeneous arrival patterns.

The underlying tables are [information_arrival_scores.csv](tables/information_arrival_scores.csv) and [information_arrival_decomposition.csv](tables/information_arrival_decomposition.csv); the figure is [information_arrival.png](figures/information_arrival.png).
