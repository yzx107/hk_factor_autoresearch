"""Safe structural activity proxy example for Phase A."""

from __future__ import annotations

import math

import polars as pl

from factor_defs.change_support import collect_daily_frames_from_loader

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "structural_activity_score"
SOURCE_COLUMNS = ["date", "source_file", "Price", "Volume"]

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
                (
                    pl.col("turnover").log1p() + 0.25 * pl.col("trade_count").log1p()
                ).alias(OUTPUT_COLUMN),
                pl.lit("file_derived_instrument_key").alias("instrument_key_source"),
            ]
        )
    )


def compute_signal(trades: pl.LazyFrame) -> pl.LazyFrame:
    """Build a file-derived per-instrument activity proxy from verified trades."""
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


def structural_activity_proxy(rows: list[dict[str, float]]) -> list[float]:
    """Compatibility helper for tiny in-memory examples."""
    return [
        math.log1p(float(row["Price"]) * float(row["Volume"]))
        for row in rows
    ]
