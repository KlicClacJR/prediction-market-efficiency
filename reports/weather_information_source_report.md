# Weather Forecast Updates and the 12h→6h Market Response

## Data and identification

The matched sample contains 826 KXHIGHNY events with archived ECMWF IFS HRES forecast runs and NOAA Central Park realized highs. Open-Meteo preserves exact model runs from March 14, 2024; this is an external numerical-model benchmark, not the official NWS/NDFD forecast seen by every trader.

Run initialization is not release time. The analysis uses the consistently archived 00Z/12Z cycles and assumes a conservative six-hour publication lag, consistent with the archive documentation's 4–6 hour global-model processing window. Thus the 12Z run is treated as available at 18Z, inside the market's 12h→6h interval.

## Forecast evolution

| As-of horizon | Mean absolute high-temperature error |
|---:|---:|
| 24h | 2.99°F |
| 12h | 2.67°F |
| 6h | 2.50°F |

ECMWF MAE falls by 0.32°F from 24h→12h and by 0.18°F from 12h→6h. The external model therefore does not show its largest forecast-error improvement in the market's dominant 12h→6h window.

## Market-versus-forecast revisions

| Interval | Pearson magnitude correlation (95% CI) | Regression slope (95% CI) |
|---|---:|---:|
| 24h_to_12h | 0.123 (0.030, 0.229) | 0.0090 (0.0021, 0.0173) |
| 12h_to_6h | -0.157 (-0.224, -0.085) | -0.0152 (-0.0216, -0.0089) |

## Event study around the assumed 12Z-run release

The post window is hours 0–3 after assumed availability; the pre window is hours -4 to -1. Differences are event-date cluster-bootstrap estimates.

- Across all events, hourly volume changes by 4719.2 contracts (95% CI 3955.6, 5549.3).
- For top-quartile forecast updates, hourly volume changes by 4087.1 contracts (95% CI 1860.0, 6437.1).
- The large-update post/pre volume change minus the small-update change is -844.8 contracts/hour (95% CI -3186.4, 1816.2).
- Mean absolute hourly probability movement changes by 0.0225 (95% CI 0.0195, 0.0256).

## Interpretation

The evidence supports timing alignment but not a forecast-update dose response. Market volume and probability movement rise after the assumed 18Z availability time, yet large ECMWF updates do not produce a larger volume increase than small updates. More importantly, 12h→6h forecast-revision magnitude is negatively, not positively, related to same-interval market-revision magnitude. Its positive correlation with the earlier 24h→12h market revision is more consistent with the market anticipating this benchmark or reacting to other information first.

Accordingly, the archived ECMWF updates do not explain the 70% concentration on their own. The clock-time coincidence is real, but the cross-event magnitude tests point away from a simple story in which larger 12Z model changes cause larger market changes.

Timing alignment is necessary but not sufficient for causality. A positive same-interval relationship would show that larger model updates coincide with larger market revisions; a post-release activity increase would strengthen that timing story. Neither establishes that ECMWF caused the trades because NWS forecasts, observations, private models, and time-of-day effects arrive concurrently.

The defensible conclusion is therefore graded: correlation describes co-movement; the event study describes alignment around an assumed availability time; causal attribution would require exact dissemination timestamps or a plausibly exogenous forecast shock.

## Limitations

- ECMWF model output is a benchmark, not archived official NWS point guidance.
- The six-hour release lag is conservative but approximate.
- Hourly market candles blur the ordering of forecasts and trades within each hour.
- Forecast highs are grid-cell 2 m temperature maxima, while settlement uses the Central Park station observation.
- The run archive begins in March 2024, so results do not cover the full market history.
- Multiple weather products and direct observations can confound lead/lag patterns.

## Sources

- [Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api)
- [NOAA NDFD overview](https://vlab.noaa.gov/web/mdl/ndfd)
- [NOAA NCEI Daily Summaries](https://www.ncei.noaa.gov/access/search/data-search/daily-summaries)

Study outputs: [forecast revisions](tables/weather_forecast_revisions.csv), [relationship estimates](tables/market_vs_forecast_relationship.csv), [update timeline](figures/forecast_update_timeline.png), and [market-versus-forecast revisions](figures/market_vs_forecast_revisions.png).
