"""Regime-slice helpers for Phase A pre-eval diagnostics."""

from __future__ import annotations

from datetime import date as dt_date
from pathlib import Path
from typing import Any

import polars as pl

from harness.daily_agg import load_daily_agg_lazy


YEAR_GRADE_MAP = {
    2025: "coarse_only",
    2026: "fine_ok",
}

DEFAULT_SLICE_COLUMNS = [
    "year_grade",
    "market_turnover_regime",
    "market_volatility_regime",
]

ROOT = Path(__file__).resolve().parents[1]


def _previous_date_map(dates: list[str]) -> dict[str, str]:
    ordered = sorted(dates)
    return {ordered[index]: ordered[index - 1] for index in range(1, len(ordered))}


def apply_regime_labels(stats: pl.DataFrame) -> pl.DataFrame:
    if stats.is_empty():
        return stats

    turnover_median = stats["market_total_turnover"].median()
    volatility_values = stats["market_abs_close_return"].drop_nulls()
    volatility_median = volatility_values.median() if len(volatility_values) else None

    year_grade_expr = (
        pl.col("date")
        .dt.year()
        .replace_strict(YEAR_GRADE_MAP, default="unknown_year")
        .alias("year_grade")
    )
    turnover_expr = (
        pl.when(pl.col("market_total_turnover") >= turnover_median)
        .then(pl.lit("high_turnover"))
        .otherwise(pl.lit("low_turnover"))
        .alias("market_turnover_regime")
    )
    if volatility_median is None:
        volatility_expr = pl.lit("insufficient_history").alias("market_volatility_regime")
    else:
        volatility_expr = (
            pl.when(pl.col("market_abs_close_return").is_null())
            .then(pl.lit("insufficient_history"))
            .when(pl.col("market_abs_close_return") >= volatility_median)
            .then(pl.lit("high_vol"))
            .otherwise(pl.lit("low_vol"))
            .alias("market_volatility_regime")
        )

    return stats.with_columns([year_grade_expr, turnover_expr, volatility_expr])


def build_regime_slice_frame(dates: list[str]) -> pl.DataFrame:
    if not dates:
        return pl.DataFrame(
            schema={
                "date": pl.Date,
                "year_grade": pl.String,
                "market_total_turnover": pl.Float64,
                "market_abs_close_return": pl.Float64,
                "market_turnover_regime": pl.String,
                "market_volatility_regime": pl.String,
            }
        )

    year_only = pl.DataFrame({"date": dates}).with_columns(pl.col("date").str.to_date()).with_columns(
        pl.col("date").dt.year().replace_strict(YEAR_GRADE_MAP, default="unknown_year").alias("year_grade")
    )

    previous_map = _previous_date_map(dates)
    all_dates = sorted(set(dates) | set(previous_map.values()))
    try:
        daily = (
            load_daily_agg_lazy(
                "verified_trades_daily",
                all_dates,
                ["date", "instrument_key", "turnover", "close_like_price"],
            )
            .collect()
            .sort(["date", "instrument_key"])
        )
    except FileNotFoundError:
        return year_only

    turnover_stats = (
        daily.group_by("date")
        .agg(pl.col("turnover").sum().alias("market_total_turnover"))
        .filter(pl.col("date").is_in([dt_date.fromisoformat(value) for value in dates]))
    )

    current_prices = daily.select(["date", "instrument_key", "close_like_price"])
    prev_prices = daily.select(
        [
            pl.col("date").alias("prev_date"),
            "instrument_key",
            pl.col("close_like_price").alias("prev_close_like_price"),
        ]
    )
    prev_map_frame = pl.DataFrame(
        {
            "date": list(previous_map.keys()),
            "prev_date": list(previous_map.values()),
        }
    ).with_columns([pl.col("date").str.to_date(), pl.col("prev_date").str.to_date()])

    return_stats = (
        current_prices.join(prev_map_frame, on="date", how="left")
        .join(prev_prices, on=["prev_date", "instrument_key"], how="left")
        .filter(pl.col("prev_close_like_price").is_not_null() & (pl.col("prev_close_like_price") > 0))
        .with_columns(
            ((pl.col("close_like_price") / pl.col("prev_close_like_price")) - 1.0)
            .abs()
            .alias("abs_close_return")
        )
        .group_by("date")
        .agg(pl.col("abs_close_return").mean().alias("market_abs_close_return"))
    )

    date_frame = pl.DataFrame({"date": dates}).with_columns(pl.col("date").str.to_date())
    stats = (
        year_only.join(turnover_stats, on="date", how="left")
        .join(return_stats, on="date", how="left")
        .sort("date")
    )
    return apply_regime_labels(stats)


def build_regime_slice_summary(
    per_date_rows: list[dict[str, Any]],
    date_annotations: pl.DataFrame | None,
) -> dict[str, list[dict[str, Any]]]:
    if not per_date_rows or date_annotations is None or date_annotations.is_empty():
        return {}

    per_date = pl.DataFrame(per_date_rows).with_columns(pl.col("date").str.to_date())
    annotations = date_annotations.sort("date")
    slice_columns = [column for column in DEFAULT_SLICE_COLUMNS if column in annotations.columns]
    if not slice_columns:
        return {}

    joined = per_date.join(annotations, on="date", how="left")
    summary: dict[str, list[dict[str, Any]]] = {}
    for slice_name in slice_columns:
        grouped = (
            joined.filter(pl.col(slice_name).is_not_null())
            .group_by(slice_name)
            .agg(
                [
                    pl.len().alias("date_count"),
                    pl.col("labeled_rows").sum().alias("labeled_rows"),
                    pl.col("rank_ic").mean().alias("mean_rank_ic"),
                    pl.col("rank_ic").abs().mean().alias("mean_abs_rank_ic"),
                    pl.col("normalized_mutual_info").mean().alias("mean_normalized_mutual_info"),
                    pl.col("top_bottom_spread").mean().alias("mean_top_bottom_spread"),
                    pl.col("coverage_ratio").mean().alias("mean_coverage_ratio"),
                ]
            )
            .sort(slice_name)
        )
        summary[slice_name] = [
            {
                "slice_value": row[slice_name],
                "date_count": int(row["date_count"]),
                "labeled_rows": int(row["labeled_rows"]),
                "mean_rank_ic": None if row["mean_rank_ic"] is None else float(row["mean_rank_ic"]),
                "mean_abs_rank_ic": None if row["mean_abs_rank_ic"] is None else float(row["mean_abs_rank_ic"]),
                "mean_normalized_mutual_info": (
                    None
                    if row["mean_normalized_mutual_info"] is None
                    else float(row["mean_normalized_mutual_info"])
                ),
                "mean_top_bottom_spread": (
                    None if row["mean_top_bottom_spread"] is None else float(row["mean_top_bottom_spread"])
                ),
                "mean_coverage_ratio": (
                    None if row["mean_coverage_ratio"] is None else float(row["mean_coverage_ratio"])
                ),
            }
            for row in grouped.to_dicts()
        ]
    return summary
