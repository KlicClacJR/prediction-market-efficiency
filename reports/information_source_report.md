# Sources of the 12h→6h Information-Arrival Concentration

## Design

The study uses the same balanced 4,281-contract, 1,299-event panel at all four horizons. Between-quote volume is reconstructed from hourly candle volume and divided by interval length. Liquidity quartiles are fixed at 24h using trailing volume and open interest, before any later revision. All intervals and subgroup confidence intervals use 1,000 event-date cluster bootstrap draws.

## Main mechanism results

The 12h→6h interval contains 70.3% of total Brier reduction and 55.7% of total absolute probability movement.

| Interval | Volume/hour | OI growth/hour | Mean absolute revision | Movement share | Brier-reduction share |
|---|---:|---:|---:|---:|---:|
| 24h_to_12h | 574.60 | 396.00 | 0.1089 | 29.6% | 13.6% |
| 12h_to_6h | 1957.71 | 1118.25 | 0.2050 | 55.7% | 70.3% |
| 6h_to_1h | 784.70 | 527.17 | 0.0544 | 14.8% | 16.1% |

Relative to the average of the adjacent intervals, the middle window differs by 1278.06 contracts/hour in volume (95% CI 1125.39, 1439.48), 656.67 contracts/hour in open-interest growth (95% CI 545.66, 781.92), and 0.1233 in absolute probability revision (95% CI 0.1155, 0.1308).

Average trailing activity rises sharply into the middle window:

| Horizon | Mean trailing 6h volume | Mean trailing 24h volume | Mean open interest |
|---:|---:|---:|---:|
| 24h | 1351 | 2272 | 1639 |
| 12h | 4867 | 8996 | 6391 |
| 6h | 11765 | 19993 | 13101 |
| 1h | 6084 | 22899 | 15737 |

## Seasonal concentration

The 12h→6h Brier-reduction and movement shares are:

| Season | Brier-reduction share | Absolute-movement share |
|---|---:|---:|
| Winter | 58.4% | 52.6% |
| Spring | 68.5% | 53.8% |
| Summer | 78.2% | 58.2% |
| Fall | 74.5% | 58.5% |

The concentration is present in every season, but is largest in summer and fall and smallest in winter.

## Temperature regimes

Cold, mild, and hot regimes use pre-test training-period terciles of the realized temperature proxy, so later outcomes do not redefine the cutoffs.

| Temperature regime | Brier-reduction share in 12h→6h | Absolute-movement share in 12h→6h |
|---|---:|---:|
| Cold | 64.4% | 53.3% |
| Mild | 66.2% | 53.0% |
| Hot | 76.3% | 59.1% |

## Liquidity-conditioned concentration

Liquidity is measured at 24h, so later trading cannot move a contract into a different stratum.

| 24h liquidity quartile | Brier-reduction share in 12h→6h | Absolute-movement share in 12h→6h |
|---|---:|---:|
| Q1_low | 66.4% | 50.2% |
| Q2 | 69.8% | 53.7% |
| Q3 | 77.5% | 59.5% |
| Q4_high | 67.3% | 58.7% |

## Interpretation

The timing evidence lines up across three observables: the middle interval has the highest hourly volume, the highest open-interest growth per hour, and the largest absolute revisions. This supports an activity-and-updating mechanism for the error drop, although it does not identify which public weather signal caused the trades.

High-liquidity contracts appear faster at the margins: Q4 assigns more Brier improvement to 24h→12h and less to 6h→1h than Q1. The middle interval remains dominant in every quartile, so liquidity changes the speed profile without creating the concentration by itself.

A mechanism is supported only when timing, activity, and revisions align; these results remain descriptive rather than causal. A volume spike can accompany public weather information without proving that trades caused price discovery. Likewise, open interest can fall when positions close even as information arrives.

The combined evidence should be read as locating the market response window. Attributing it to specific forecast releases or observations requires an external, timestamped meteorological-news dataset.

## Limitations

- Hourly candles blur within-hour sequencing and do not reveal order-book depth.
- Volume counts contracts, not informed traders; open interest is a stock, not flow.
- The balanced sample excludes events without all four usable horizon quotes.
- Seasonal and liquidity results are multiple descriptive comparisons without a causal treatment design.
- Absolute-temperature and contract-design regimes remain possible confounders.
