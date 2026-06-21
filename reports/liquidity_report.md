# Liquidity-Stratified Calibration

## Design

This study uses the existing full-history fixed-horizon panel. At each 24h, 12h, 6h, and 1h horizon, contracts are ranked separately on trailing 24-hour volume and contemporaneous open interest. The mean of those two percentile ranks defines four equally sized liquidity strata. This horizon-specific construction prevents the mechanically larger cumulative volume near close from determining quartile membership.

Calibration remains contract-level. Confidence intervals and low-minus-high comparisons use 1,000 event-date cluster bootstrap draws, preserving dependence among contracts from the same daily event. Positive low-minus-high differences mean worse performance in the least-liquid quartile.

## Results

| Horizon | Metric | Q1 low | Q4 high | Low minus high (95% CI) |
|---:|---|---:|---:|---:|
| 24h | Brier | 0.1107 | 0.1416 | -0.0309 (-0.0423, -0.0200) |
| 24h | Log loss | 0.3484 | 0.4302 | -0.0818 (-0.1114, -0.0530) |
| 24h | ECE | 0.0600 | 0.0142 | 0.0458 (0.0207, 0.0527) |
| 12h | Brier | 0.0970 | 0.1148 | -0.0178 (-0.0293, -0.0068) |
| 12h | Log loss | 0.2997 | 0.3506 | -0.0508 (-0.0827, -0.0217) |
| 12h | ECE | 0.0695 | 0.0137 | 0.0558 (0.0338, 0.0652) |
| 6h | Brier | 0.0580 | 0.0228 | 0.0353 (0.0251, 0.0450) |
| 6h | Log loss | 0.1921 | 0.0800 | 0.1121 (0.0811, 0.1401) |
| 6h | ECE | 0.0854 | 0.0082 | 0.0772 (0.0635, 0.0877) |
| 1h | Brier | 0.0246 | 0.0091 | 0.0155 (0.0079, 0.0227) |
| 1h | Log loss | 0.0872 | 0.0332 | 0.0539 (0.0305, 0.0753) |
| 1h | ECE | 0.0611 | 0.0112 | 0.0499 (0.0382, 0.0591) |

Low-liquidity contracts have significantly larger ECE at every horizon. They also have materially worse proper scores at 6h and 1h, when Q1 Brier score is roughly 2.6–2.7 times Q4. However, the proper-score ordering reverses at 24h and 12h: Q1 has lower Brier score and log loss despite worse ECE.

This mixed pattern matters. ECE isolates average bin-level probability gaps, whereas Brier score and log loss also reflect outcome uncertainty and the probability distribution presented to each stratum. The results support a specific conditional deviation—late-horizon calibration is weaker in the least-liquid quartile—but not a blanket claim that low liquidity always produces worse forecasts.

## Limitations

- Quartiles are observational and mix contract vintages, strikes, probabilities, and event difficulty. They do not identify a causal effect of liquidity.
- Volume is trailing and open interest is point-in-time, so both are public at the forecast timestamp; neither uses future trading.
- Historical order-book depth is unavailable. Volume and open interest are proxies, not executable depth.
- Equal-sized contract quartiles do not imply equal numbers of independent events; inference therefore clusters by event date.
- ECE depends on fixed decile bins and probability mix. The proper scoring rules should receive at least equal weight in interpretation.

The underlying tables are `liquidity_calibration_metrics.csv`, `liquidity_comparisons.csv`, and `liquidity_reliability.csv`; the reliability figure is `reports/figures/liquidity_reliability.png`.
