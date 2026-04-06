"""Trade size concentration: Gini coefficient of per-trade notional values."""

from __future__ import annotations

from math import fsum

import polars as pl

from factor_defs.change_support import (
    build_change_signal,
    build_change_signal_from_loader,
    collect_daily_frames_from_loader,
)

FACTOR_ID = "trade_size_concentration_v1"
FACTOR_FAMILY = "intraday_distribution"
MECHANISM = (
    "Compute Gini coefficient of individual trade notional values per stock-day. "
    "High concentration indicates a few large trades dominating daily turnover, "
    "which may proxy institutional activity or block-trade pressure."
)
INPUT_DEPENDENCIES = ["date", "source_file", "Price", "Volume"]
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level", "one_day_difference"]
EXPECTED_REGIME = "works better when large-trade vs small-trade composition varies"
FORBIDDEN_SEMANTIC_ASSUMPTIONS = [
    "no_trade_side_truth",
    "no_broker_identity_truth",
    "no_queue_semantics",
]

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "trade_size_concentration_score"
SUPPORTED_TRANSFORMS = ["level", "one_day_difference"]
LOOKBACK_STEPS = 1
SOURCE_COLUMNS = ["date", "source_file", "Price", "Volume"]


def _gini(values: list[float]) -> float:
    """Compute the Gini coefficient for a list of non-negative values."""
    n = len(values)
    if n <= 1:
        return 0.0
    sorted_values = sorted(values)
    total = fsum(sorted_values)
    if total <= 0.0:
        return 0.0
    cumulative = fsum(
        (2 * (i + 1) - n - 1) * v for i, v in enumerate(sorted_values)
    )
    return cumulative / (n * total)


def _daily_base(trades: pl.LazyFrame) -> pl.LazyFrame:
    """Build per-stock-day Gini of trade notional from raw tick data."""
    with_notional = trades.with_columns(
        (pl.col("Price") * pl.col("Volume")).alias("notional"),
    )

    daily = (
        with_notional.group_by(["date", "instrument_key"])
        .agg(
            [
                pl.col("notional").alias("notional_list"),
                pl.len().alias("trade_count"),
            ]
        )
    )

    # Compute Gini per group using map_elements
    return daily.with_columns(
        pl.col("notional_list")
        .map_elements(
            lambda arr: _gini(arr.to_list()),
            return_dtype=pl.Float64,
        )
        .alias("trade_size_concentration_level"),
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
                pl.col("trade_size_concentration_level").alias(OUTPUT_COLUMN)
            )
            .sort(["date", OUTPUT_COLUMN], descending=[False, True])
        )
    if transform == "one_day_difference":
        return build_change_signal(
            base,
            base_score_column="trade_size_concentration_level",
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
                pl.col("trade_size_concentration_level").alias(OUTPUT_COLUMN)
            ).sort(["date", OUTPUT_COLUMN], descending=[False, True])
        )
    if transform == "one_day_difference":
        return build_change_signal_from_loader(
            table_loader=table_loader,
            source_columns=SOURCE_COLUMNS,
            daily_base_builder=_daily_base,
            base_score_column="trade_size_concentration_level",
            output_column=OUTPUT_COLUMN,
            target_dates=target_dates,
            previous_date_map=previous_date_map,
        )
    raise ValueError(f"Unsupported transform `{transform}` for {FACTOR_ID}.")
