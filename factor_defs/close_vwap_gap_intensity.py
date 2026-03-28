"""Safe close-to-VWAP gap intensity factor for Phase A."""

from __future__ import annotations

import math

import polars as pl

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "close_vwap_gap_intensity_score"


def compute_signal(trades: pl.LazyFrame) -> pl.LazyFrame:
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
            ).alias(OUTPUT_COLUMN)
        )
        .sort(["date", OUTPUT_COLUMN], descending=[False, True])
    )


def close_vwap_gap_intensity(rows: list[dict[str, float]]) -> list[float]:
    """Compatibility helper for tiny in-memory examples."""
    scores: list[float] = []
    for row in rows:
        close_like = float(row["close_like_price"])
        vwap = float(row["vwap"])
        trade_count = float(row["trade_count"])
        scores.append(((close_like / vwap) - 1.0) * math.log1p(trade_count))
    return scores
