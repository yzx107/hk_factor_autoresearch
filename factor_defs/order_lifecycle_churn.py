"""Safe order lifecycle churn factor for Phase A."""

from __future__ import annotations

import math

import polars as pl

INPUT_TABLE = "verified_orders"
OUTPUT_COLUMN = "order_lifecycle_churn_score"


def compute_signal(orders: pl.LazyFrame) -> pl.LazyFrame:
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
            ).alias(OUTPUT_COLUMN)
        )
        .sort(["date", OUTPUT_COLUMN], descending=[False, True])
    )


def order_lifecycle_churn(rows: list[dict[str, float]]) -> list[float]:
    """Compatibility helper for tiny in-memory examples."""
    scores: list[float] = []
    for row in rows:
        churn_ratio = float(row["order_event_count"]) / max(float(row["unique_order_ids"]), 1.0)
        scores.append(math.log1p(churn_ratio))
    return scores
