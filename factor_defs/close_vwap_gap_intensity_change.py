"""One-day change version of the close-to-VWAP gap intensity factor."""

from __future__ import annotations

import polars as pl

from factor_defs.change_support import build_change_signal, build_change_signal_from_loader

FACTOR_ID = "close_vwap_gap_intensity_change_v1"
FACTOR_FAMILY = "close_vwap_pressure"
MECHANISM = "Measure day-over-day acceleration in close-like versus VWAP dislocation."
INPUT_DEPENDENCIES = ["date", "source_file", "Time", "row_num_in_file", "Price", "Volume"]
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level", "one_day_difference"]
EXPECTED_REGIME = "works better when end-of-day price pressure is not fully resolved"
FORBIDDEN_SEMANTIC_ASSUMPTIONS = [
    "no_trade_side_truth",
    "no_broker_identity_truth",
    "no_queue_semantics",
]

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "close_vwap_gap_intensity_change_score"
LOOKBACK_STEPS = 1
SOURCE_COLUMNS = ["date", "source_file", "Time", "Price", "Volume", "row_num_in_file"]
DAILY_AGG_TABLE = "verified_trades_daily"
DAILY_SOURCE_COLUMNS = [
    "date",
    "instrument_key",
    "trade_count",
    "close_like_price",
    "vwap",
    "instrument_key_source",
]


def _daily_base(trades: pl.LazyFrame) -> pl.LazyFrame:
    turnover = (pl.col("Price") * pl.col("Volume")).sum().alias("turnover")
    share_volume = pl.col("Volume").sum().alias("share_volume")
    trade_count = pl.len().alias("trade_count")
    return (
        trades.sort(["date", "instrument_key", "Time", "row_num_in_file"])
        .group_by(["date", "instrument_key"], maintain_order=True)
        .agg([trade_count, turnover, share_volume, pl.col("Price").last().alias("close_like_price")])
        .filter(pl.col("share_volume") > 0)
        .with_columns(
            [
                (pl.col("turnover") / pl.col("share_volume")).alias("vwap"),
                pl.lit("file_derived_instrument_key").alias("instrument_key_source"),
            ]
        )
        .with_columns(
            (
                ((pl.col("close_like_price") / pl.col("vwap")) - 1.0) * pl.col("trade_count").log1p()
            ).alias("close_vwap_gap_intensity_level")
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
        base_score_column="close_vwap_gap_intensity_level",
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
        base_score_column="close_vwap_gap_intensity_level",
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
            (
                ((pl.col("close_like_price") / pl.col("vwap")) - 1.0) * pl.col("trade_count").log1p()
            ).alias("close_vwap_gap_intensity_level")
        ),
        base_score_column="close_vwap_gap_intensity_level",
        output_column=OUTPUT_COLUMN,
        target_dates=target_dates,
        previous_date_map=previous_date_map,
    )
