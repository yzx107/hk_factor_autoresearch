"""Trade arrival burstiness: coefficient of variation of inter-trade intervals."""

from __future__ import annotations

from math import fsum, sqrt

import polars as pl

from factor_defs.change_support import (
    build_change_signal,
    build_change_signal_from_loader,
    collect_daily_frames_from_loader,
)

FACTOR_ID = "trade_arrival_burstiness_v1"
FACTOR_FAMILY = "intraday_distribution"
MECHANISM = (
    "Compute the coefficient of variation (CV) of inter-trade time intervals "
    "per stock-day. High burstiness (high CV) indicates clustered, "
    "event-driven trading patterns; low burstiness indicates steady, "
    "noise-like flow. Bursty patterns may indicate information arrival."
)
INPUT_DEPENDENCIES = ["date", "source_file", "Time", "Price", "Volume"]
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level", "one_day_difference"]
EXPECTED_REGIME = "works better when trade rhythms carry information about urgency"
FORBIDDEN_SEMANTIC_ASSUMPTIONS = [
    "no_trade_side_truth",
    "no_broker_identity_truth",
    "no_queue_semantics",
]

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "trade_arrival_burstiness_score"
SUPPORTED_TRANSFORMS = ["level", "one_day_difference"]
LOOKBACK_STEPS = 1
SOURCE_COLUMNS = ["date", "source_file", "Time", "Price", "Volume"]


def _cv(values: list[float]) -> float:
    """Coefficient of variation: std / mean. Returns 0 if insufficient data."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = fsum(values) / n
    if mean <= 0.0:
        return 0.0
    variance = fsum((v - mean) ** 2 for v in values) / (n - 1)
    return sqrt(variance) / mean


def _daily_base(trades: pl.LazyFrame) -> pl.LazyFrame:
    """Build per-stock-day burstiness (CV of inter-trade seconds)."""
    # Sort by time and compute time as seconds-from-midnight
    sorted_trades = trades.sort(["date", "instrument_key", "Time", "row_num_in_file"])

    with_seconds = sorted_trades.with_columns(
        (
            pl.col("Time").dt.hour() * 3600
            + pl.col("Time").dt.minute() * 60
            + pl.col("Time").dt.second()
        )
        .cast(pl.Float64)
        .alias("time_seconds"),
    )

    grouped = (
        with_seconds.group_by(["date", "instrument_key"])
        .agg(
            [
                pl.col("time_seconds").alias("time_list"),
                pl.len().alias("trade_count"),
            ]
        )
    )

    def _interval_cv(times_series) -> float:
        times = sorted(times_series.to_list())
        if len(times) < 3:
            return 0.0
        intervals = [times[i + 1] - times[i] for i in range(len(times) - 1)]
        positive_intervals = [iv for iv in intervals if iv > 0]
        if len(positive_intervals) < 2:
            return 0.0
        return _cv(positive_intervals)

    return grouped.with_columns(
        pl.col("time_list")
        .map_elements(_interval_cv, return_dtype=pl.Float64)
        .alias("trade_arrival_burstiness_level"),
    )


def compute_signal(
    trades: pl.LazyFrame,
    *,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
    transform: str = "level",
) -> pl.LazyFrame:
    base = _daily_base(trades)
    if transform == "level":
        return (
            base.with_columns(
                pl.col("trade_arrival_burstiness_level").alias(OUTPUT_COLUMN)
            )
            .sort(["date", OUTPUT_COLUMN], descending=[False, True])
        )
    if transform == "one_day_difference":
        return build_change_signal(
            base,
            base_score_column="trade_arrival_burstiness_level",
            output_column=OUTPUT_COLUMN,
            target_dates=target_dates,
            previous_date_map=previous_date_map,
        )
    raise ValueError(f"Unsupported transform `{transform}` for {FACTOR_ID}.")


def compute_signal_from_loader(
    *,
    table_loader,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
    transform: str = "level",
) -> pl.LazyFrame:
    target_dates = list(target_dates or [])
    previous_date_map = dict(previous_date_map or {})
    if transform == "level":
        return collect_daily_frames_from_loader(
            table_loader=table_loader,
            source_columns=SOURCE_COLUMNS,
            daily_frame_builder=_daily_base,
            dates=target_dates,
        ).pipe(
            lambda df: df.with_columns(
                pl.col("trade_arrival_burstiness_level").alias(OUTPUT_COLUMN)
            ).sort(["date", OUTPUT_COLUMN], descending=[False, True])
        )
    if transform == "one_day_difference":
        return build_change_signal_from_loader(
            table_loader=table_loader,
            source_columns=SOURCE_COLUMNS,
            daily_base_builder=_daily_base,
            base_score_column="trade_arrival_burstiness_level",
            output_column=OUTPUT_COLUMN,
            target_dates=target_dates,
            previous_date_map=previous_date_map,
        )
    raise ValueError(f"Unsupported transform `{transform}` for {FACTOR_ID}.")
