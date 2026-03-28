"""Safe average trade notional bias factor for Phase A."""

from __future__ import annotations

import math

import polars as pl

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "avg_trade_notional_bias_score"


def compute_signal(trades: pl.LazyFrame) -> pl.LazyFrame:
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
        .sort(["date", OUTPUT_COLUMN], descending=[False, True])
    )


def avg_trade_notional_bias(rows: list[dict[str, float]]) -> list[float]:
    """Compatibility helper for tiny in-memory examples."""
    scores: list[float] = []
    for row in rows:
        turnover = float(row["Price"]) * float(row["Volume"])
        scores.append(math.log1p(turnover))
    return scores
