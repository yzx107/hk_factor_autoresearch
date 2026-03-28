"""Safe structural activity proxy example for Phase A."""

from __future__ import annotations

import math

import polars as pl

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "structural_activity_score"


def compute_signal(trades: pl.LazyFrame) -> pl.LazyFrame:
    """Build a file-derived per-instrument activity proxy from verified trades."""
    turnover = (pl.col("Price") * pl.col("Volume")).sum().alias("turnover")
    trade_count = pl.len().alias("trade_count")
    share_volume = pl.col("Volume").sum().alias("share_volume")
    avg_trade_size = pl.col("Volume").mean().alias("avg_trade_size")

    return (
        trades.group_by(["date", "instrument_key"])
        .agg([trade_count, turnover, share_volume, avg_trade_size])
        .with_columns(
            [
                (
                    pl.col("turnover").log1p() + 0.25 * pl.col("trade_count").log1p()
                ).alias(OUTPUT_COLUMN),
                pl.lit("file_derived_instrument_key").alias("instrument_key_source"),
            ]
        )
        .sort(["date", OUTPUT_COLUMN], descending=[False, True])
    )


def structural_activity_proxy(rows: list[dict[str, float]]) -> list[float]:
    """Compatibility helper for tiny in-memory examples."""
    return [
        math.log1p(float(row["Price"]) * float(row["Volume"]))
        for row in rows
    ]
