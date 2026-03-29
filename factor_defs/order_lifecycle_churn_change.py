"""One-day change version of the order lifecycle churn factor."""

from __future__ import annotations

import polars as pl

from factor_defs.change_support import build_change_signal, build_change_signal_from_loader

INPUT_TABLE = "verified_orders"
OUTPUT_COLUMN = "order_lifecycle_churn_change_score"
LOOKBACK_STEPS = 1
SOURCE_COLUMNS = ["date", "source_file", "OrderId", "Price", "Volume"]
DAILY_AGG_TABLE = "verified_orders_daily"
DAILY_SOURCE_COLUMNS = [
    "date",
    "instrument_key",
    "order_event_count",
    "unique_order_ids",
    "total_order_notional",
    "churn_ratio",
    "instrument_key_source",
]


def _daily_base(orders: pl.LazyFrame) -> pl.LazyFrame:
    event_count = pl.len().alias("order_event_count")
    unique_orders = pl.col("OrderId").n_unique().alias("unique_order_ids")
    total_order_notional = (pl.col("Price") * pl.col("Volume")).sum().alias("total_order_notional")
    return (
        orders.group_by(["date", "instrument_key"])
        .agg([event_count, unique_orders, total_order_notional])
        .with_columns(
            [
                (pl.col("order_event_count") / pl.col("unique_order_ids")).alias("churn_ratio"),
                pl.lit("file_derived_instrument_key").alias("instrument_key_source"),
            ]
        )
        .with_columns(
            (
                pl.col("churn_ratio").log1p() + 0.1 * pl.col("total_order_notional").log1p()
            ).alias("order_lifecycle_churn_level")
        )
    )


def compute_signal(
    orders: pl.LazyFrame,
    *,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
) -> pl.LazyFrame:
    return build_change_signal(
        _daily_base(orders),
        base_score_column="order_lifecycle_churn_level",
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
        base_score_column="order_lifecycle_churn_level",
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
                pl.col("churn_ratio").log1p() + 0.1 * pl.col("total_order_notional").log1p()
            ).alias("order_lifecycle_churn_level")
        ),
        base_score_column="order_lifecycle_churn_level",
        output_column=OUTPUT_COLUMN,
        target_dates=target_dates,
        previous_date_map=previous_date_map,
    )
