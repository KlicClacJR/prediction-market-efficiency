# Prediction Market Efficiency and Bayesian Information Aggregation

> Status: research-report template. Replace bracketed fields only with outputs produced from a versioned raw-data manifest.

## Abstract

We evaluate the calibration and weak-form informational efficiency of Kalshi's daily New York City high-temperature markets. Using fixed pre-resolution horizons and event-clustered inference, we test whether quoted probabilities correspond to empirical frequencies and whether public market state predicts subsequent probability revisions. [Insert dated sample, principal estimates, uncertainty, and a restrained conclusion.]

## 1. Hypotheses

- **H1 — Calibration:** Among contracts quoted near probability \(p\), approximately proportion \(p\) resolve YES.
- **H2 — Martingale difference:** Conditional on public market features at time \(t\), expected future probability revision is zero.
- **H3 — Range bias:** Calibration residuals do not differ systematically across probability ranges.
- **H4 — Bayesian smoothing:** A prior estimated solely from training events does not improve held-out proper scores over raw prices.

## 2. Market and resolution process

Describe `KXHIGHNY`, mutually exclusive temperature buckets, trading hours, quote mechanics, and the NWS Daily Climate Report resolution source. Distinguish quoted midpoints from executable prices.

## 3. Data and sample construction

Report the raw manifest path and hash, retrieval date, first/last event, market and event counts, exclusions, quote coverage, staleness, and exceptional resolutions. Include the data-flow diagram and canonical schemas.

## 4. Methodology

Define midpoint probability, 24/12/6/1-hour snapshots, Brier score, clipped log loss, decile ECE, event-cluster bootstrap, raw versus normalized buckets, efficiency predictors, rolling-origin evaluation, clustered covariance, Ljung-Box diagnostics, and Benjamini-Hochberg correction.

## 5. Descriptive evidence

Include event/contract counts, price and spread distributions, volume/open-interest summaries, missingness, event probability sums, and representative probability paths.

## 6. Calibration results

Insert `calibration_metrics.csv`, a reliability diagram, and range-bias tables. Interpret effect sizes and confidence intervals separately at every horizon. Compare raw prices, normalized prices, expanding prevalence, and the 0.5 reference where useful.

## 7. Efficiency and martingale tests

Insert coefficient tables, joint tests, autocorrelation diagnostics, and adjusted p-values. Separate in-sample inference from the out-of-sample economic question.

## 8. Out-of-sample prediction

Report forecast count, event count, revision MAE, zero-benchmark MAE, and out-of-sample \(R^2\). Discuss whether any statistical predictability survives chronological evaluation.

## 9. Robustness

- Raw midpoint versus event-normalized probabilities
- Alternate staleness thresholds and calibration bins
- Trade price versus midpoint, clearly labeled
- Excluding the final hour
- Seasonal subsamples
- Non-overlapping revision targets
- Event-cluster versus alternative uncertainty estimates

## 10. Bayesian extension

Describe category/horizon/bin Beta priors, training-only hyperparameter estimation, posterior means and credible intervals, and held-out score comparisons. Do not present in-sample shrinkage as evidence of improvement.

## 11. Limitations

Discuss dependent buckets, summarized rather than complete order books, non-executable midpoints, API coverage, near-resolution observations, selection effects, multiple testing, weather-specific information arrival, and limited external validity.

## 12. Conclusion

[State what the data support, what they do not support, and the next falsifiable study.]

## Reproducibility appendix

Record the Git commit, Python/package versions, configuration file, raw manifest, exact CLI command, random seed, generated table/figure paths, and any deviations from the preregistered workflow.

