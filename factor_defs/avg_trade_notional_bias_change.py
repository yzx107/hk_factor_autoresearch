"""One-day change version of the average trade notional bias factor."""

from __future__ import annotations

import polars as pl

from factor_defs.change_support import build_change_signal, build_change_signal_from_loader

FACTOR_ID = "avg_trade_notional_bias_change_v1"
FACTOR_FAMILY = "trade_notional_composition"
MECHANISM = "Measure day-over-day acceleration in average trade notional composition."
INPUT_DEPENDENCIES = ["date", "source_file", "Price", "Volume"]
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level", "one_day_difference"]
EXPECTED_REGIME = "works better when participation quality changes without explicit side labels"
FORBIDDEN_SEMANTIC_ASSUMPTIONS = [
    "no_trade_side_truth",
    "no_broker_identity_truth",
    "no_queue_semantics",
]

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "avg_trade_notional_bias_change_score"
LOOKBACK_STEPS = 1
SOURCE_COLUMNS = ["date", "source_file", "Price", "Volume"]
DAILY_AGG_TABLE = "verified_trades_daily"
DAILY_SOURCE_COLUMNS = [
    "date",
    "instrument_key",
    "trade_count",
    "turnover",
    "share_volume",
    "instrument_key_source",
]


def _daily_base(trades: pl.LazyFrame) -> pl.LazyFrame:
    trade_count = pl.len().alias("trade_count")
    turnover = (pl.col("Price") * pl.col("Volume")).sum().alias("turnover")
    share_volume = pl.col("Volume").sum().alias("share_volume")
    return (
        trades.group_by(["date", "instrument_key"])
        .agg([trade_count, turnover, share_volume])
        .with_columns(
            [
                (pl.col("turnover") / pl.col("trade_count")).alias("avg_trade_notional"),
                pl.lit("file_derived_instrument_key").alias("instrument_key_source"),
            ]
        )
        .with_columns(pl.col("avg_trade_notional").log1p().alias("avg_trade_notional_bias_level"))
    )


def compute_signal(
    trades: pl.LazyFrame,
    *,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
) -> pl.LazyFrame:
    return build_change_signal(
        _daily_base(trades),
        base_score_column="avg_trade_notional_bias_level",
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
        base_score_column="avg_trade_notional_bias_level",
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
        daily.with_columns((pl.col("turnover") / pl.col("trade_count")).alias("avg_trade_notional"))
        .with_columns(pl.col("avg_trade_notional").log1p().alias("avg_trade_notional_bias_level")),
        base_score_column="avg_trade_notional_bias_level",
        output_column=OUTPUT_COLUMN,
        target_dates=target_dates,
        previous_date_map=previous_date_map,
    )
