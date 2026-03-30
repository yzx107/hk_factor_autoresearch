"""Shared daily-cache helpers for order x trade interaction families."""

from __future__ import annotations

import polars as pl


TRADES_DAILY_COLUMNS = [
    "date",
    "instrument_key",
    "trade_count",
    "turnover",
    "share_volume",
    "close_like_price",
    "vwap",
    "instrument_key_source",
]

ORDERS_DAILY_COLUMNS = [
    "date",
    "instrument_key",
    "order_event_count",
    "unique_order_ids",
    "total_order_notional",
    "churn_ratio",
    "instrument_key_source",
]

DAILY_AGG_TABLES = {
    "verified_trades_daily": TRADES_DAILY_COLUMNS,
    "verified_orders_daily": ORDERS_DAILY_COLUMNS,
}


def build_interaction_daily_frame(
    trades_daily: pl.LazyFrame,
    orders_daily: pl.LazyFrame,
) -> pl.LazyFrame:
    return (
        trades_daily.join(
            orders_daily,
            on=["date", "instrument_key"],
            how="inner",
            suffix="_orders",
        )
        .with_columns(
            pl.coalesce(
                [
                    pl.col("instrument_key_source"),
                    pl.col("instrument_key_source_orders"),
                ]
            ).alias("instrument_key_source")
        )
        .drop("instrument_key_source_orders")
    )


def build_interaction_daily_from_cache_loader(
    *,
    cache_loader,
    dates: list[str],
) -> pl.LazyFrame:
    if not dates:
        return pl.DataFrame().lazy()
    trades_daily = cache_loader("verified_trades_daily", dates, TRADES_DAILY_COLUMNS)
    orders_daily = cache_loader("verified_orders_daily", dates, ORDERS_DAILY_COLUMNS)
    return build_interaction_daily_frame(trades_daily, orders_daily)

