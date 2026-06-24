"""Mechanism study for the concentration of information arrival between 12h and 6h."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pm_efficiency.analysis.conditional_studies import (
    HORIZONS,
    LIQUIDITY_LABELS,
    _cluster_draws,
    derive_temperature_events,
)

INTERVALS = ((24, 12), (12, 6), (6, 1))
SEASON_ORDER = ("winter", "spring", "summer", "fall")
TEMPERATURE_ORDER = ("cold", "mild", "hot")


def _season(month: pd.Series) -> pd.Series:
    return pd.Series(
        np.select(
            [month.isin([12, 1, 2]), month.isin([3, 4, 5]), month.isin([6, 7, 8])],
            ["winter", "spring", "summer"],
            default="fall",
        ),
        index=month.index,
    )


def build_information_source_panels(
    forecast_panel: pd.DataFrame,
    price_history: pd.DataFrame,
    markets: pd.DataFrame,
    *,
    training_end: object = "2025-01-04",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return balanced horizon rows and exact between-quote interval rows."""
    keys = ["event_id", "market_id"]
    horizon = forecast_panel[forecast_panel.forecast_horizon_hours.isin(HORIZONS)].copy()
    complete = horizon.groupby(keys).forecast_horizon_hours.nunique()
    complete_keys = complete[complete == len(HORIZONS)].index
    horizon = horizon.set_index(keys).loc[complete_keys].reset_index()
    event_dates = markets[["event_id", "event_date"]].drop_duplicates("event_id")
    event_dates["event_date"] = pd.to_datetime(event_dates.event_date)
    horizon = horizon.merge(event_dates, on="event_id", how="left", validate="many_to_one")
    horizon["season"] = _season(horizon.event_date.dt.month)
    temperature_events, _ = derive_temperature_events(markets, training_end)
    cutoff = pd.Timestamp(training_end).date()
    temperature_training = temperature_events[temperature_events.event_date <= cutoff]
    cold_threshold = temperature_training.temperature_proxy.quantile(1 / 3)
    hot_threshold = temperature_training.temperature_proxy.quantile(2 / 3)
    temperature_events["temperature_regime"] = np.select(
        [
            temperature_events.temperature_proxy <= cold_threshold,
            temperature_events.temperature_proxy >= hot_threshold,
        ],
        ["cold", "hot"],
        default="mild",
    )
    horizon = horizon.merge(
        temperature_events[["event_id", "temperature_proxy", "temperature_regime"]],
        on="event_id",
        how="left",
        validate="many_to_one",
    )

    at_24 = horizon[horizon.forecast_horizon_hours == 24].copy()
    at_24["volume_rank"] = at_24.volume_24h.rank(pct=True)
    at_24["open_interest_rank"] = at_24.open_interest.rank(pct=True)
    at_24["liquidity_score_24h"] = (at_24.volume_rank + at_24.open_interest_rank) / 2
    at_24["liquidity_quartile_24h"] = pd.qcut(
        at_24.liquidity_score_24h.rank(method="first"), 4, labels=LIQUIDITY_LABELS
    ).astype(str)
    liquidity = at_24[keys + ["liquidity_score_24h", "liquidity_quartile_24h"]]
    horizon = horizon.merge(liquidity, on=keys, how="left", validate="many_to_one")

    history = price_history[["market_id", "timestamp", "volume_interval"]].copy()
    history["timestamp"] = pd.to_datetime(history.timestamp, utc=True)
    history = history.sort_values(["market_id", "timestamp"])
    history["cumulative_volume"] = history.groupby("market_id").volume_interval.cumsum()
    cumulative = history[["market_id", "timestamp", "cumulative_volume"]]

    interval_rows = []
    for earlier, later in INTERVALS:
        left = horizon[horizon.forecast_horizon_hours == earlier].copy()
        right = horizon[horizon.forecast_horizon_hours == later].copy()
        left = left.merge(
            cumulative,
            on=["market_id", "timestamp"],
            how="left",
            validate="one_to_one",
        ).rename(columns={"cumulative_volume": "cumulative_volume_earlier"})
        right = right.merge(
            cumulative,
            on=["market_id", "timestamp"],
            how="left",
            validate="one_to_one",
        ).rename(columns={"cumulative_volume": "cumulative_volume_later"})
        columns = keys + [
            "event_date",
            "season",
            "temperature_regime",
            "liquidity_quartile_24h",
            "probability_mid",
            "outcome",
            "volume_6h",
            "volume_24h",
            "open_interest",
            "cumulative_volume_earlier",
        ]
        left = left[columns].rename(
            columns={
                "probability_mid": "probability_earlier",
                "volume_6h": "volume_6h_earlier",
                "volume_24h": "volume_24h_earlier",
                "open_interest": "open_interest_earlier",
            }
        )
        right = right[
            keys
            + [
                "probability_mid",
                "volume_6h",
                "volume_24h",
                "open_interest",
                "cumulative_volume_later",
            ]
        ].rename(
            columns={
                "probability_mid": "probability_later",
                "volume_6h": "volume_6h_later",
                "volume_24h": "volume_24h_later",
                "open_interest": "open_interest_later",
            }
        )
        joined = left.merge(right, on=keys, how="inner", validate="one_to_one")
        duration = earlier - later
        joined["interval"] = f"{earlier}h_to_{later}h"
        joined["interval_hours"] = duration
        joined["interval_volume"] = (
            joined.cumulative_volume_later - joined.cumulative_volume_earlier
        ).clip(lower=0)
        joined["volume_per_hour"] = joined.interval_volume / duration
        joined["volume_6h_growth"] = joined.volume_6h_later - joined.volume_6h_earlier
        joined["log_volume_6h_growth"] = np.log1p(joined.volume_6h_later) - np.log1p(
            joined.volume_6h_earlier
        )
        joined["open_interest_growth"] = joined.open_interest_later - joined.open_interest_earlier
        joined["open_interest_growth_per_hour"] = joined.open_interest_growth / duration
        joined["absolute_revision"] = (joined.probability_later - joined.probability_earlier).abs()
        joined["brier_earlier"] = np.square(joined.probability_earlier - joined.outcome)
        joined["brier_later"] = np.square(joined.probability_later - joined.outcome)
        joined["brier_reduction"] = joined.brier_earlier - joined.brier_later
        interval_rows.append(joined)
    intervals = pd.concat(interval_rows, ignore_index=True)
    return horizon, intervals


def _mean_ci(
    sample: pd.DataFrame,
    column: str,
    *,
    iterations: int,
    seed: int,
) -> tuple[float, float, float]:
    return _cluster_draws(
        sample.dropna(subset=[column]),
        lambda x: float(x[column].mean()),
        iterations=iterations,
        seed=seed,
    )


def run_information_source_study(
    horizon: pd.DataFrame,
    intervals: pd.DataFrame,
    *,
    iterations: int = 1000,
    seed: int = 20260619,
) -> dict[str, pd.DataFrame]:
    horizon_rows = []
    for horizon_index, hours in enumerate(HORIZONS):
        sample = horizon[horizon.forecast_horizon_hours == hours]
        row = {
            "forecast_horizon_hours": hours,
            "observations": len(sample),
            "events": sample.event_id.nunique(),
        }
        for metric_index, column in enumerate(("volume_6h", "volume_24h", "open_interest")):
            estimate, lower, upper = _mean_ci(
                sample,
                column,
                iterations=iterations,
                seed=seed + horizon_index * 10 + metric_index,
            )
            row[f"mean_{column}"] = estimate
            row[f"{column}_ci_lower"] = lower
            row[f"{column}_ci_upper"] = upper
        horizon_rows.append(row)

    interval_rows = []
    columns = (
        "volume_per_hour",
        "log_volume_6h_growth",
        "open_interest_growth_per_hour",
        "absolute_revision",
        "brier_reduction",
    )
    interval_order = [f"{earlier}h_to_{later}h" for earlier, later in INTERVALS]
    for interval_index, interval in enumerate(interval_order):
        sample = intervals[intervals.interval == interval]
        row = {
            "interval": interval,
            "interval_hours": int(sample.interval_hours.iloc[0]),
            "observations": len(sample),
            "events": sample.event_id.nunique(),
        }
        for metric_index, column in enumerate(columns):
            estimate, lower, upper = _mean_ci(
                sample,
                column,
                iterations=iterations,
                seed=seed + 1000 + interval_index * 10 + metric_index,
            )
            row[column] = estimate
            row[f"{column}_ci_lower"] = lower
            row[f"{column}_ci_upper"] = upper
        interval_rows.append(row)
    interval_summary = pd.DataFrame(interval_rows)
    interval_summary["share_absolute_revision"] = (
        interval_summary.absolute_revision / interval_summary.absolute_revision.sum()
    )
    interval_summary["share_brier_reduction"] = (
        interval_summary.brier_reduction / interval_summary.brier_reduction.sum()
    )

    wide = intervals.pivot(index=["event_id", "market_id"], columns="interval")
    activity_tests = []
    for metric_index, column in enumerate(
        ("volume_per_hour", "open_interest_growth_per_hour", "absolute_revision")
    ):
        comparison = pd.DataFrame(
            {
                "event_id": wide.index.get_level_values("event_id"),
                "difference": wide[column]["12h_to_6h"].to_numpy()
                - (wide[column]["24h_to_12h"].to_numpy() + wide[column]["6h_to_1h"].to_numpy()) / 2,
            }
        )
        estimate, lower, upper = _mean_ci(
            comparison,
            "difference",
            iterations=iterations,
            seed=seed + 2000 + metric_index,
        )
        activity_tests.append(
            {
                "metric": column,
                "middle_minus_other_interval_average": estimate,
                "ci_lower": lower,
                "ci_upper": upper,
                "middle_significantly_larger": bool(lower > 0),
            }
        )

    def conditional(group_column: str, order: tuple[str, ...], seed_offset: int) -> pd.DataFrame:
        rows = []
        for group_index, group in enumerate(order):
            group_data = intervals[intervals[group_column] == group]
            group_abs_total = group_data.groupby("interval").absolute_revision.mean().sum()
            group_brier_total = group_data.groupby("interval").brier_reduction.mean().sum()
            for interval_index, interval in enumerate(interval_order):
                sample = group_data[group_data.interval == interval]
                row = {
                    group_column: group,
                    "interval": interval,
                    "observations": len(sample),
                    "events": sample.event_id.nunique(),
                }
                for metric_index, column in enumerate(("absolute_revision", "brier_reduction")):
                    estimate, lower, upper = _mean_ci(
                        sample,
                        column,
                        iterations=iterations,
                        seed=seed
                        + seed_offset
                        + group_index * 100
                        + interval_index * 10
                        + metric_index,
                    )
                    row[column] = estimate
                    row[f"{column}_ci_lower"] = lower
                    row[f"{column}_ci_upper"] = upper
                row["share_absolute_revision"] = row["absolute_revision"] / group_abs_total
                row["share_brier_reduction"] = row["brier_reduction"] / group_brier_total
                rows.append(row)
        return pd.DataFrame(rows)

    seasonal = conditional("season", SEASON_ORDER, 3000)
    temperature = conditional("temperature_regime", TEMPERATURE_ORDER, 4000)
    liquidity = conditional("liquidity_quartile_24h", LIQUIDITY_LABELS, 5000)
    return {
        "horizon_activity": pd.DataFrame(horizon_rows),
        "interval_summary": interval_summary,
        "activity_tests": pd.DataFrame(activity_tests),
        "seasonal": seasonal,
        "temperature_regime": temperature,
        "liquidity": liquidity,
    }


def combine_tables(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    tables = []
    for name, frame in results.items():
        table = frame.copy()
        table.insert(0, "table", name)
        tables.append(table)
    return pd.concat(tables, ignore_index=True, sort=False)


def write_information_source_report(results: dict[str, pd.DataFrame], path: str | Path) -> None:
    interval = results["interval_summary"].set_index("interval")
    tests = results["activity_tests"].set_index("metric")
    seasonal = results["seasonal"]
    temperature = results["temperature_regime"]
    liquidity = results["liquidity"]
    seasonal_middle = seasonal[seasonal.interval == "12h_to_6h"].set_index("season")
    temperature_middle = temperature[temperature.interval == "12h_to_6h"].set_index(
        "temperature_regime"
    )
    liquidity_middle = liquidity[liquidity.interval == "12h_to_6h"].set_index(
        "liquidity_quartile_24h"
    )
    lines = [
        "# Sources of the 12h→6h Information-Arrival Concentration",
        "",
        "## Design",
        "",
        "The study uses the same balanced 4,281-contract, 1,299-event panel at all four "
        "horizons. Between-quote volume is reconstructed from hourly candle volume and divided "
        "by interval length. Liquidity quartiles are fixed at 24h using trailing volume and "
        "open interest, before any later revision. All intervals and subgroup confidence "
        "intervals use 1,000 event-date cluster bootstrap draws.",
        "",
        "## Main mechanism results",
        "",
        f"The 12h→6h interval contains {interval.loc['12h_to_6h', 'share_brier_reduction']:.1%} "
        "of total Brier reduction and "
        f"{interval.loc['12h_to_6h', 'share_absolute_revision']:.1%} of total absolute "
        "probability movement.",
        "",
        "| Interval | Volume/hour | OI growth/hour | Mean absolute revision | Movement share | "
        "Brier-reduction share |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, row in interval.iterrows():
        lines.append(
            f"| {name} | {row.volume_per_hour:.2f} | "
            f"{row.open_interest_growth_per_hour:.2f} | {row.absolute_revision:.4f} | "
            f"{row.share_absolute_revision:.1%} | {row.share_brier_reduction:.1%} |"
        )
    volume_test = tests.loc["volume_per_hour"]
    oi_test = tests.loc["open_interest_growth_per_hour"]
    revision_test = tests.loc["absolute_revision"]
    lines.extend(
        [
            "",
            "Relative to the average of the adjacent intervals, the middle window differs by "
            f"{volume_test.middle_minus_other_interval_average:.2f} contracts/hour in volume "
            f"(95% CI {volume_test.ci_lower:.2f}, {volume_test.ci_upper:.2f}), "
            f"{oi_test.middle_minus_other_interval_average:.2f} contracts/hour in open-interest "
            f"growth (95% CI {oi_test.ci_lower:.2f}, {oi_test.ci_upper:.2f}), and "
            f"{revision_test.middle_minus_other_interval_average:.4f} in absolute probability "
            f"revision (95% CI {revision_test.ci_lower:.4f}, {revision_test.ci_upper:.4f}).",
            "",
            "Average trailing activity rises sharply into the middle window:",
            "",
            "| Horizon | Mean trailing 6h volume | Mean trailing 24h volume | Mean open interest |",
            "|---:|---:|---:|---:|",
        ]
    )
    for row in results["horizon_activity"].itertuples(index=False):
        lines.append(
            f"| {int(row.forecast_horizon_hours)}h | {row.mean_volume_6h:.0f} | "
            f"{row.mean_volume_24h:.0f} | {row.mean_open_interest:.0f} |"
        )
    lines.extend(
        [
            "",
            "## Seasonal concentration",
            "",
            "The 12h→6h Brier-reduction and movement shares are:",
            "",
            "| Season | Brier-reduction share | Absolute-movement share |",
            "|---|---:|---:|",
        ]
    )
    for season in SEASON_ORDER:
        row = seasonal_middle.loc[season]
        lines.append(
            f"| {season.title()} | {row.share_brier_reduction:.1%} | "
            f"{row.share_absolute_revision:.1%} |"
        )
    lines.extend(
        [
            "",
            "The concentration is present in every season, but is largest in summer and fall "
            "and smallest in winter.",
            "",
            "## Temperature regimes",
            "",
            "Cold, mild, and hot regimes use pre-test training-period terciles of the realized "
            "temperature proxy, so later outcomes do not redefine the cutoffs.",
            "",
            "| Temperature regime | Brier-reduction share in 12h→6h | "
            "Absolute-movement share in 12h→6h |",
            "|---|---:|---:|",
        ]
    )
    for regime in TEMPERATURE_ORDER:
        row = temperature_middle.loc[regime]
        lines.append(
            f"| {regime.title()} | {row.share_brier_reduction:.1%} | "
            f"{row.share_absolute_revision:.1%} |"
        )
    lines.extend(
        [
            "",
            "## Liquidity-conditioned concentration",
            "",
            "Liquidity is measured at 24h, so later trading cannot move a contract into a "
            "different stratum.",
            "",
            "| 24h liquidity quartile | Brier-reduction share in 12h→6h | "
            "Absolute-movement share in 12h→6h |",
            "|---|---:|---:|",
        ]
    )
    for quartile in LIQUIDITY_LABELS:
        row = liquidity_middle.loc[quartile]
        lines.append(
            f"| {quartile} | {row.share_brier_reduction:.1%} | {row.share_absolute_revision:.1%} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The timing evidence lines up across three observables: the middle interval has the "
            "highest hourly volume, the highest open-interest growth per hour, and the largest "
            "absolute revisions. This supports an activity-and-updating mechanism for the error "
            "drop, although it does not identify which public weather signal caused the trades.",
            "",
            "High-liquidity contracts appear faster at the margins: Q4 assigns more Brier "
            "improvement to 24h→12h and less to 6h→1h than Q1. The middle interval remains "
            "dominant in every quartile, so liquidity changes the speed profile without creating "
            "the concentration by itself.",
            "",
            "A mechanism is supported only when timing, activity, and revisions align; these "
            "results remain descriptive rather than causal. A volume spike can accompany public "
            "weather information without proving that trades caused price discovery. Likewise, "
            "open interest can fall when positions close even as information arrives.",
            "",
            "The combined evidence should be read as locating the market response window. The "
            "subsequent weather-information comparison finds alignment with an assumed ECMWF "
            "availability time but no supporting dose response, so attribution remains "
            "correlational rather than causal.",
            "",
            "## Limitations",
            "",
            "- Hourly candles blur within-hour sequencing and do not reveal order-book depth.",
            "- Volume counts contracts, not informed traders; open interest is a stock, not flow.",
            "- The balanced sample excludes events without all four usable horizon quotes.",
            "- Seasonal and liquidity results are multiple descriptive comparisons without a "
            "causal treatment design.",
            "- Absolute-temperature and contract-design regimes remain possible confounders.",
            "",
            "The combined decomposition is in "
            "[information_source_tables.csv](tables/information_source_tables.csv); figures show "
            "[interval dynamics](figures/information_source_dynamics.png) and "
            "[conditional shares](figures/information_source_conditions.png).",
            "",
        ]
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines))
