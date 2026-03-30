"""Safe average trade notional bias factor for Phase A."""

from __future__ import annotations

from datetime import date as dt_date
import math

import polars as pl

from factor_defs.change_support import collect_daily_frames_from_loader

FACTOR_ID = "avg_trade_notional_bias_v1"
FACTOR_FAMILY = "trade_notional_composition"
MECHANISM = "Measure whether average trade notional suggests concentrated participation."
INPUT_DEPENDENCIES = ["date", "source_file", "Price", "Volume"]
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level"]
EXPECTED_REGIME = "works better when participation quality changes without explicit side labels"
FORBIDDEN_SEMANTIC_ASSUMPTIONS = [
    "no_trade_side_truth",
    "no_broker_identity_truth",
    "no_queue_semantics",
]

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "avg_trade_notional_bias_score"
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
        .with_columns(
            pl.col("avg_trade_notional").log1p().alias(OUTPUT_COLUMN)
        )
    )


def compute_signal(trades: pl.LazyFrame) -> pl.LazyFrame:
    return _daily_base(trades).sort(["date", OUTPUT_COLUMN], descending=[False, True])


def compute_signal_from_loader(
    *,
    table_loader,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
) -> pl.LazyFrame:
    del previous_date_map
    return collect_daily_frames_from_loader(
        table_loader=table_loader,
        source_columns=SOURCE_COLUMNS,
        daily_frame_builder=_daily_base,
        dates=list(target_dates or []),
    ).sort(["date", OUTPUT_COLUMN], descending=[False, True])


def compute_signal_from_daily(
    daily: pl.LazyFrame,
    *,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
) -> pl.LazyFrame:
    del previous_date_map
    frame = daily
    if target_dates:
        frame = frame.filter(pl.col("date").is_in([dt_date.fromisoformat(value) for value in target_dates]))
    return (
        frame.with_columns((pl.col("turnover") / pl.col("trade_count")).alias("avg_trade_notional"))
        .with_columns(pl.col("avg_trade_notional").log1p().alias(OUTPUT_COLUMN))
        .sort(["date", OUTPUT_COLUMN], descending=[False, True])
    )


def avg_trade_notional_bias(rows: list[dict[str, float]]) -> list[float]:
    """Compatibility helper for tiny in-memory examples."""
    scores: list[float] = []
    for row in rows:
        turnover = float(row["Price"]) * float(row["Volume"])
        scores.append(math.log1p(turnover))
    return scores
