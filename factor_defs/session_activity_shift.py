"""Intraday session activity shift: afternoon turnover share vs morning."""

from __future__ import annotations

from datetime import date as dt_date, time as dt_time

import polars as pl

from factor_defs.change_support import (
    build_change_signal,
    build_change_signal_from_loader,
    collect_daily_frames_from_loader,
)

FACTOR_ID = "session_activity_shift_v1"
FACTOR_FAMILY = "intraday_distribution"
MECHANISM = (
    "Compare afternoon vs morning turnover share to capture within-day "
    "attention migration. Stocks where activity shifts toward the close "
    "may face closing auction pressure or late informed flow."
)
INPUT_DEPENDENCIES = ["date", "source_file", "Time", "Price", "Volume"]
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level", "one_day_difference"]
EXPECTED_REGIME = "works better when session structure varies across stocks"
FORBIDDEN_SEMANTIC_ASSUMPTIONS = [
    "no_trade_side_truth",
    "no_broker_identity_truth",
    "no_queue_semantics",
]

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "session_activity_shift_score"
SUPPORTED_TRANSFORMS = ["level", "one_day_difference"]
LOOKBACK_STEPS = 1
SOURCE_COLUMNS = ["date", "source_file", "Time", "Price", "Volume"]

# HK market sessions: morning 09:30-12:00, afternoon 13:00-16:00
_MORNING_START = dt_time(9, 30)
_MORNING_END = dt_time(12, 0)
_AFTERNOON_START = dt_time(13, 0)
_AFTERNOON_END = dt_time(16, 0)


def _daily_base(trades: pl.LazyFrame) -> pl.LazyFrame:
    """Build daily session ratios from raw tick data."""
    trades_with_notional = trades.with_columns(
        (pl.col("Price") * pl.col("Volume")).alias("notional"),
    )

    morning = (
        trades_with_notional
        .filter(
            (pl.col("Time") >= _MORNING_START)
            & (pl.col("Time") < _MORNING_END)
        )
        .group_by(["date", "instrument_key"])
        .agg(pl.col("notional").sum().alias("morning_turnover"))
    )

    afternoon = (
        trades_with_notional
        .filter(
            (pl.col("Time") >= _AFTERNOON_START)
            & (pl.col("Time") < _AFTERNOON_END)
        )
        .group_by(["date", "instrument_key"])
        .agg(pl.col("notional").sum().alias("afternoon_turnover"))
    )

    total = (
        trades_with_notional
        .group_by(["date", "instrument_key"])
        .agg(pl.col("notional").sum().alias("total_turnover"))
    )

    return (
        total.join(morning, on=["date", "instrument_key"], how="left")
        .join(afternoon, on=["date", "instrument_key"], how="left")
        .with_columns(
            [
                pl.col("morning_turnover").fill_null(0.0),
                pl.col("afternoon_turnover").fill_null(0.0),
            ]
        )
        .with_columns(
            pl.when(pl.col("total_turnover") > 0)
            .then(
                (pl.col("afternoon_turnover") - pl.col("morning_turnover"))
                / pl.col("total_turnover")
            )
            .otherwise(0.0)
            .alias("session_activity_shift_level")
        )
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
                pl.col("session_activity_shift_level").alias(OUTPUT_COLUMN)
            )
            .sort(["date", OUTPUT_COLUMN], descending=[False, True])
        )
    if transform == "one_day_difference":
        return build_change_signal(
            base,
            base_score_column="session_activity_shift_level",
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
                pl.col("session_activity_shift_level").alias(OUTPUT_COLUMN)
            ).sort(["date", OUTPUT_COLUMN], descending=[False, True])
        )
    if transform == "one_day_difference":
        return build_change_signal_from_loader(
            table_loader=table_loader,
            source_columns=SOURCE_COLUMNS,
            daily_base_builder=_daily_base,
            base_score_column="session_activity_shift_level",
            output_column=OUTPUT_COLUMN,
            target_dates=target_dates,
            previous_date_map=previous_date_map,
        )
    raise ValueError(f"Unsupported transform `{transform}` for {FACTOR_ID}.")
