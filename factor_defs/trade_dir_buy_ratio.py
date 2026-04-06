"""TradeDir buy ratio: fraction of trades flagged as buy by vendor proxy."""

from __future__ import annotations

from datetime import date as dt_date

import polars as pl

from factor_defs.change_support import (
    build_change_signal,
    build_change_signal_from_loader,
    collect_daily_frames_from_loader,
)

FACTOR_ID = "trade_dir_buy_ratio_v1"
FACTOR_FAMILY = "directional_proxy"
MECHANISM = (
    "Per-stock daily ratio of trades flagged as vendor-aggressor buy. "
    "This is NOT a true signed-side signal — it is a vendor-derived proxy "
    "that may capture asymmetric aggression patterns visible in the "
    "TradeDir field. Elevated buy ratios cross-sectionally may proxy "
    "accumulation or demand pressure under the vendor definition."
)
INPUT_DEPENDENCIES = ["date", "source_file", "Price", "Volume", "TradeDir"]
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level", "one_day_difference"]
EXPECTED_REGIME = "works better when directional interest varies across stocks"
FORBIDDEN_SEMANTIC_ASSUMPTIONS = [
    "no_signed_side_truth",
    "no_aggressor_truth",
    "no_broker_identity_truth",
    "no_queue_semantics",
]

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "trade_dir_buy_ratio_score"
SUPPORTED_TRANSFORMS = ["level", "one_day_difference"]
LOOKBACK_STEPS = 1
SOURCE_COLUMNS = ["date", "source_file", "Price", "Volume", "TradeDir"]

# Vendor convention: TradeDir == 1 is typically buy-side aggressor
_BUY_CODE = 1


def _daily_base(trades: pl.LazyFrame) -> pl.LazyFrame:
    """Build daily buy ratio from vendor TradeDir."""
    return (
        trades.group_by(["date", "instrument_key"])
        .agg(
            [
                pl.len().alias("trade_count"),
                (pl.col("TradeDir") == _BUY_CODE).sum().alias("buy_count"),
            ]
        )
        .with_columns(
            pl.when(pl.col("trade_count") > 0)
            .then(pl.col("buy_count").cast(pl.Float64) / pl.col("trade_count"))
            .otherwise(0.5)
            .alias("trade_dir_buy_ratio_level")
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
                pl.col("trade_dir_buy_ratio_level").alias(OUTPUT_COLUMN)
            )
            .sort(["date", OUTPUT_COLUMN], descending=[False, True])
        )
    if transform == "one_day_difference":
        return build_change_signal(
            base,
            base_score_column="trade_dir_buy_ratio_level",
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
                pl.col("trade_dir_buy_ratio_level").alias(OUTPUT_COLUMN)
            ).sort(["date", OUTPUT_COLUMN], descending=[False, True])
        )
    if transform == "one_day_difference":
        return build_change_signal_from_loader(
            table_loader=table_loader,
            source_columns=SOURCE_COLUMNS,
            daily_base_builder=_daily_base,
            base_score_column="trade_dir_buy_ratio_level",
            output_column=OUTPUT_COLUMN,
            target_dates=target_dates,
            previous_date_map=previous_date_map,
        )
    raise ValueError(f"Unsupported transform `{transform}` for {FACTOR_ID}.")
