"""Safe close-to-VWAP gap intensity factor for Phase A."""

from __future__ import annotations

from datetime import date as dt_date
import math

import polars as pl

from factor_defs.change_support import collect_daily_frames_from_loader

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "close_vwap_gap_intensity_score"
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
            ).alias(OUTPUT_COLUMN)
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
        frame.with_columns(
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
