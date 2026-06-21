"""Relate archived meteorological forecast updates to market information arrival."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

from pm_efficiency.analysis.conditional_studies import _cluster_draws

WEATHER_INTERVALS = ((24, 12), (12, 6))
MARKET_INTERVALS = ("24h_to_12h", "12h_to_6h", "6h_to_1h")


def build_weather_revision_table(vintages: pd.DataFrame) -> pd.DataFrame:
    """Create one event row with forecast vintages, revisions, and error reductions."""
    values = ["forecast_high_f", "run_initialization", "assumed_available_at"]
    wide = vintages.pivot(
        index=["event_id", "event_date", "realized_high_f"],
        columns="forecast_horizon_hours",
        values=values,
    )
    rows = []
    for index, record in wide.iterrows():
        event_id, event_date, realized = index
        row = {"event_id": event_id, "event_date": event_date, "realized_high_f": realized}
        complete = True
        for horizon in (24, 12, 6):
            forecast = record.get(("forecast_high_f", horizon), np.nan)
            row[f"forecast_high_{horizon}h_f"] = forecast
            row[f"forecast_error_{horizon}h_f"] = forecast - realized
            row[f"absolute_forecast_error_{horizon}h_f"] = abs(forecast - realized)
            row[f"run_initialization_{horizon}h"] = record.get(("run_initialization", horizon))
            row[f"assumed_available_at_{horizon}h"] = record.get(("assumed_available_at", horizon))
            complete &= pd.notna(forecast) and pd.notna(realized)
        if not complete:
            continue
        for earlier, later in WEATHER_INTERVALS:
            label = f"{earlier}h_to_{later}h"
            revision = row[f"forecast_high_{later}h_f"] - row[f"forecast_high_{earlier}h_f"]
            row[f"forecast_revision_{label}_f"] = revision
            row[f"absolute_forecast_revision_{label}_f"] = abs(revision)
            row[f"forecast_error_reduction_{label}_f"] = (
                row[f"absolute_forecast_error_{earlier}h_f"]
                - row[f"absolute_forecast_error_{later}h_f"]
            )
        rows.append(row)
    return pd.DataFrame(rows).sort_values("event_date").reset_index(drop=True)


def aggregate_market_intervals(intervals: pd.DataFrame) -> pd.DataFrame:
    return intervals.groupby(["event_id", "event_date", "interval"], as_index=False).agg(
        market_absolute_revision=("absolute_revision", "mean"),
        market_brier_reduction=("brier_reduction", "mean"),
        market_volume_per_hour=("volume_per_hour", "sum"),
        market_open_interest_growth_per_hour=("open_interest_growth_per_hour", "sum"),
    )


def _bootstrap_pair_stat(
    frame: pd.DataFrame,
    statistic,
    *,
    iterations: int,
    seed: int,
) -> tuple[float, float, float]:
    return _cluster_draws(
        frame.dropna(), statistic, iterations=iterations, seed=seed, cluster="event_id"
    )


def market_forecast_relationships(
    weather: pd.DataFrame,
    market_intervals: pd.DataFrame,
    *,
    iterations: int = 1000,
    seed: int = 20260619,
) -> pd.DataFrame:
    rows = []
    for weather_index, (earlier, later) in enumerate(WEATHER_INTERVALS):
        weather_label = f"{earlier}h_to_{later}h"
        weather_column = f"absolute_forecast_revision_{weather_label}_f"
        weather_error_column = f"forecast_error_reduction_{weather_label}_f"
        source = weather[["event_id", weather_column, weather_error_column]]
        for market_index, market_label in enumerate(MARKET_INTERVALS):
            market = market_intervals[market_intervals.interval == market_label]
            joined = market.merge(source, on="event_id", how="inner")
            for stat_index, (name, function) in enumerate(
                (
                    (
                        "pearson_magnitude_correlation",
                        lambda x, wc=weather_column: float(
                            pearsonr(x[wc], x.market_absolute_revision).statistic
                        ),
                    ),
                    (
                        "spearman_magnitude_correlation",
                        lambda x, wc=weather_column: float(
                            spearmanr(x[wc], x.market_absolute_revision).statistic
                        ),
                    ),
                )
            ):
                estimate, lower, upper = _bootstrap_pair_stat(
                    joined[["event_id", weather_column, "market_absolute_revision"]],
                    function,
                    iterations=iterations,
                    seed=seed + weather_index * 100 + market_index * 10 + stat_index,
                )
                rows.append(
                    {
                        "analysis": "lead_lag_correlation",
                        "weather_interval": weather_label,
                        "market_interval": market_label,
                        "metric": name,
                        "estimate": estimate,
                        "ci_lower": lower,
                        "ci_upper": upper,
                        "events": joined.event_id.nunique(),
                    }
                )
        same_market = market_intervals[market_intervals.interval == weather_label]
        same = same_market.merge(source, on="event_id", how="inner")

        def slope_stat(x: pd.DataFrame, wc: str = weather_column) -> float:
            return float(np.polyfit(x[wc], x.market_absolute_revision, 1)[0])

        estimate, lower, upper = _bootstrap_pair_stat(
            same[["event_id", weather_column, "market_absolute_revision"]],
            slope_stat,
            iterations=iterations,
            seed=seed + 1000 + weather_index,
        )
        rows.append(
            {
                "analysis": "same_interval_regression",
                "weather_interval": weather_label,
                "market_interval": weather_label,
                "metric": "market_abs_revision_per_degree_abs_forecast_revision",
                "estimate": estimate,
                "ci_lower": lower,
                "ci_upper": upper,
                "events": same.event_id.nunique(),
            }
        )

        def error_corr(x: pd.DataFrame, ec: str = weather_error_column) -> float:
            return float(pearsonr(x[ec], x.market_brier_reduction).statistic)

        estimate, lower, upper = _bootstrap_pair_stat(
            same[["event_id", weather_error_column, "market_brier_reduction"]],
            error_corr,
            iterations=iterations,
            seed=seed + 1100 + weather_index,
        )
        rows.append(
            {
                "analysis": "error_reduction_correlation",
                "weather_interval": weather_label,
                "market_interval": weather_label,
                "metric": "weather_vs_market_error_reduction_pearson",
                "estimate": estimate,
                "ci_lower": lower,
                "ci_upper": upper,
                "events": same.event_id.nunique(),
            }
        )
    return pd.DataFrame(rows)


def build_forecast_update_event_study(
    weather: pd.DataFrame,
    price_history: pd.DataFrame,
    markets: pd.DataFrame,
    *,
    iterations: int = 1000,
    seed: int = 20260619,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Measure market activity around the assumed release of the 12Z model run."""
    releases = weather[
        ["event_id", "assumed_available_at_6h", "absolute_forecast_revision_12h_to_6h_f"]
    ].copy()
    releases["assumed_available_at_6h"] = pd.to_datetime(releases.assumed_available_at_6h, utc=True)
    cutoff = releases.absolute_forecast_revision_12h_to_6h_f.quantile(0.75)
    releases["forecast_update_group"] = np.where(
        releases.absolute_forecast_revision_12h_to_6h_f >= cutoff,
        "large_update",
        "small_update",
    )
    market_map = markets[["market_id", "event_id"]].drop_duplicates("market_id")
    history = price_history[
        ["market_id", "timestamp", "probability_mid", "volume_interval", "open_interest"]
    ].copy()
    history["timestamp"] = pd.to_datetime(history.timestamp, utc=True)
    history = history.sort_values(["market_id", "timestamp"])
    history["absolute_probability_change"] = (
        history.groupby("market_id").probability_mid.diff().abs()
    )
    history["open_interest_change"] = history.groupby("market_id").open_interest.diff()
    history = history.merge(market_map, on="market_id", how="inner", validate="many_to_one")
    history = history.merge(releases, on="event_id", how="inner", validate="many_to_one")
    history["relative_hour"] = np.floor(
        (history.timestamp - history.assumed_available_at_6h).dt.total_seconds() / 3600
    ).astype(int)
    history = history[history.relative_hour.between(-6, 6)]
    event_hour = history.groupby(
        ["event_id", "relative_hour", "forecast_update_group"], as_index=False
    ).agg(
        volume=("volume_interval", "sum"),
        mean_absolute_probability_change=("absolute_probability_change", "mean"),
        open_interest_change=("open_interest_change", "sum"),
    )
    timeline_rows = []
    for group_index, group in enumerate(("small_update", "large_update")):
        group_data = event_hour[event_hour.forecast_update_group == group]
        for offset in range(-6, 7):
            sample = group_data[group_data.relative_hour == offset]
            row = {
                "analysis": "forecast_update_event_study",
                "forecast_update_group": group,
                "relative_hour": offset,
                "events": sample.event_id.nunique(),
            }
            for metric_index, column in enumerate(
                ("volume", "mean_absolute_probability_change", "open_interest_change")
            ):
                if sample.event_id.nunique() < 2:
                    continue
                estimate, lower, upper = _cluster_draws(
                    sample.dropna(subset=[column]),
                    lambda x, col=column: float(x[col].mean()),
                    iterations=iterations,
                    seed=seed + group_index * 1000 + (offset + 6) * 10 + metric_index,
                )
                row[column] = estimate
                row[f"{column}_ci_lower"] = lower
                row[f"{column}_ci_upper"] = upper
            timeline_rows.append(row)
    timeline = pd.DataFrame(timeline_rows)

    pre = (
        event_hour[event_hour.relative_hour.between(-4, -1)]
        .groupby("event_id")
        .agg(
            pre_volume=("volume", "mean"),
            pre_abs_change=("mean_absolute_probability_change", "mean"),
        )
    )
    post = (
        event_hour[event_hour.relative_hour.between(0, 3)]
        .groupby("event_id")
        .agg(
            post_volume=("volume", "mean"),
            post_abs_change=("mean_absolute_probability_change", "mean"),
        )
    )
    paired = (
        pre.join(post, how="inner")
        .reset_index()
        .merge(releases[["event_id", "forecast_update_group"]], on="event_id", how="left")
    )
    paired["volume_post_minus_pre"] = paired.post_volume - paired.pre_volume
    paired["abs_change_post_minus_pre"] = paired.post_abs_change - paired.pre_abs_change
    tests = []
    for group_index, group in enumerate(("all", "small_update", "large_update")):
        sample = paired if group == "all" else paired[paired.forecast_update_group == group]
        for metric_index, column in enumerate(
            ("volume_post_minus_pre", "abs_change_post_minus_pre")
        ):
            estimate, lower, upper = _cluster_draws(
                sample[["event_id", column]],
                lambda x, col=column: float(x[col].mean()),
                iterations=iterations,
                seed=seed + 5000 + group_index * 10 + metric_index,
            )
            tests.append(
                {
                    "analysis": "post_vs_pre_release",
                    "forecast_update_group": group,
                    "metric": column,
                    "estimate": estimate,
                    "ci_lower": lower,
                    "ci_upper": upper,
                    "events": sample.event_id.nunique(),
                }
            )
    return timeline, pd.DataFrame(tests)


def write_weather_report(
    weather: pd.DataFrame,
    relationships: pd.DataFrame,
    release_tests: pd.DataFrame,
    output_path: str | Path,
) -> None:
    same = relationships[
        (relationships.analysis == "lead_lag_correlation")
        & (relationships.metric == "pearson_magnitude_correlation")
        & (relationships.weather_interval == relationships.market_interval)
    ].set_index("weather_interval")
    slopes = relationships[relationships.analysis == "same_interval_regression"].set_index(
        "weather_interval"
    )
    release = release_tests.set_index(["forecast_update_group", "metric"])
    mae = {
        horizon: weather[f"absolute_forecast_error_{horizon}h_f"].mean() for horizon in (24, 12, 6)
    }
    lines = [
        "# Weather Forecast Updates and the 12h→6h Market Response",
        "",
        "## Data and identification",
        "",
        f"The matched sample contains {len(weather):,} KXHIGHNY events with archived ECMWF IFS "
        "HRES forecast runs and NOAA Central Park realized highs. Open-Meteo preserves exact "
        "model runs from March 14, 2024; this is an external numerical-model benchmark, not the "
        "official NWS/NDFD forecast seen by every trader.",
        "",
        "Run initialization is not release time. The analysis uses the consistently archived "
        "00Z/12Z cycles and assumes a conservative six-hour "
        "publication lag, consistent with the archive documentation's 4–6 hour global-model "
        "processing window. Thus the 12Z run is treated as available at 18Z, inside the market's "
        "12h→6h interval.",
        "",
        "## Forecast evolution",
        "",
        "| As-of horizon | Mean absolute high-temperature error |",
        "|---:|---:|",
        f"| 24h | {mae[24]:.2f}°F |",
        f"| 12h | {mae[12]:.2f}°F |",
        f"| 6h | {mae[6]:.2f}°F |",
        "",
        "## Market-versus-forecast revisions",
        "",
        "| Interval | Pearson magnitude correlation (95% CI) | Regression slope (95% CI) |",
        "|---|---:|---:|",
    ]
    for label in ("24h_to_12h", "12h_to_6h"):
        corr = same.loc[label]
        slope = slopes.loc[label]
        lines.append(
            f"| {label} | {corr.estimate:.3f} ({corr.ci_lower:.3f}, {corr.ci_upper:.3f}) | "
            f"{slope.estimate:.4f} ({slope.ci_lower:.4f}, {slope.ci_upper:.4f}) |"
        )
    all_volume = release.loc[("all", "volume_post_minus_pre")]
    large_volume = release.loc[("large_update", "volume_post_minus_pre")]
    all_change = release.loc[("all", "abs_change_post_minus_pre")]
    lines.extend(
        [
            "",
            "## Event study around the assumed 12Z-run release",
            "",
            "The post window is hours 0–3 after assumed availability; the pre window is hours "
            "-4 to -1. Differences are event-date cluster-bootstrap estimates.",
            "",
            f"- Across all events, hourly volume changes by {all_volume.estimate:.1f} contracts "
            f"(95% CI {all_volume.ci_lower:.1f}, {all_volume.ci_upper:.1f}).",
            f"- For top-quartile forecast updates, hourly volume changes by "
            f"{large_volume.estimate:.1f} contracts (95% CI {large_volume.ci_lower:.1f}, "
            f"{large_volume.ci_upper:.1f}).",
            f"- Mean absolute hourly probability movement changes by {all_change.estimate:.4f} "
            f"(95% CI {all_change.ci_lower:.4f}, {all_change.ci_upper:.4f}).",
            "",
            "## Interpretation",
            "",
            "Timing alignment is necessary but not sufficient for causality. A positive same-"
            "interval relationship would show that larger model updates coincide with larger "
            "market revisions; a post-release activity increase would strengthen that timing "
            "story. Neither establishes that ECMWF caused the trades because NWS forecasts, "
            "observations, private models, and time-of-day effects arrive concurrently.",
            "",
            "The defensible conclusion is therefore graded: correlation describes co-movement; "
            "the event study describes alignment around an assumed availability time; causal "
            "attribution would require exact dissemination timestamps or a plausibly exogenous "
            "forecast shock.",
            "",
            "## Limitations",
            "",
            "- ECMWF model output is a benchmark, not archived official NWS point guidance.",
            "- The six-hour release lag is conservative but approximate.",
            "- Hourly market candles blur the ordering of forecasts and trades within each hour.",
            "- Forecast highs are grid-cell 2 m temperature maxima, while settlement uses the "
            "Central Park station observation.",
            "- The run archive begins in March 2024, so results do not cover the full market "
            "history.",
            "- Multiple weather products and direct observations can confound lead/lag patterns.",
            "",
            "## Sources",
            "",
            "- [Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api)",
            "- [NOAA NDFD overview](https://vlab.noaa.gov/web/mdl/ndfd)",
            "- [NOAA NCEI Daily Summaries](https://www.ncei.noaa.gov/access/search/data-search/daily-summaries)",
            "",
        ]
    )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines))
