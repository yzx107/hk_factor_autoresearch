"""One-day change version of the structural activity proxy."""

from __future__ import annotations

import polars as pl

from factor_defs.change_support import build_change_signal, build_change_signal_from_loader

FACTOR_ID = "structural_activity_change_v1"
FACTOR_FAMILY = "activity_pressure"
MECHANISM = "Measure day-over-day acceleration in turnover and trade-count intensity."
INPUT_DEPENDENCIES = ["date", "source_file", "Price", "Volume", "TickID"]
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level", "one_day_difference"]
EXPECTED_REGIME = "works better when attention or activity pressure changes quickly"
FORBIDDEN_SEMANTIC_ASSUMPTIONS = [
    "no_trade_side_truth",
    "no_broker_identity_truth",
    "no_queue_semantics",
]

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "structural_activity_change_score"
LOOKBACK_STEPS = 1
SOURCE_COLUMNS = ["date", "source_file", "Price", "Volume", "TickID"]
DAILY_AGG_TABLE = "verified_trades_daily"
DAILY_SOURCE_COLUMNS = [
    "date",
    "instrument_key",
    "trade_count",
    "turnover",
    "share_volume",
    "avg_trade_size",
    "instrument_key_source",
]


def _daily_base(trades: pl.LazyFrame) -> pl.LazyFrame:
    turnover = (pl.col("Price") * pl.col("Volume")).sum().alias("turnover")
    trade_count = pl.len().alias("trade_count")
    share_volume = pl.col("Volume").sum().alias("share_volume")
    avg_trade_size = pl.col("Volume").mean().alias("avg_trade_size")
    return (
        trades.group_by(["date", "instrument_key"])
        .agg([trade_count, turnover, share_volume, avg_trade_size])
        .with_columns(
            [
                (pl.col("turnover").log1p() + 0.25 * pl.col("trade_count").log1p()).alias(
                    "structural_activity_level"
                ),
                pl.lit("file_derived_instrument_key").alias("instrument_key_source"),
            ]
        )
    )


def compute_signal(
    trades: pl.LazyFrame,
    *,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
) -> pl.LazyFrame:
    return build_change_signal(
        _daily_base(trades),
        base_score_column="structural_activity_level",
        output_column=OUTPUT_COLUMN,
        target_dates=target_dates,
        previous_date_map=previous_date_map,
    )


def compute_signal_from_loader(
    *,
    table_loader,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
) -> pl.LazyFrame:
    return build_change_signal_from_loader(
        table_loader=table_loader,
        source_columns=SOURCE_COLUMNS,
        daily_base_builder=_daily_base,
        base_score_column="structural_activity_level",
        output_column=OUTPUT_COLUMN,
        target_dates=target_dates,
        previous_date_map=previous_date_map,
    )


def compute_signal_from_daily(
    daily: pl.LazyFrame,
    *,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
) -> pl.LazyFrame:
    return build_change_signal(
        daily.with_columns(
            (pl.col("turnover").log1p() + 0.25 * pl.col("trade_count").log1p()).alias(
                "structural_activity_level"
            )
        ),
        base_score_column="structural_activity_level",
        output_column=OUTPUT_COLUMN,
        target_dates=target_dates,
        previous_date_map=previous_date_map,
    )
