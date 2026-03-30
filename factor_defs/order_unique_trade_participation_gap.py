"""Auto-generated Gate A factor from factor_specs."""

from __future__ import annotations

import polars as pl

from factor_defs.order_trade_interaction_support import DAILY_AGG_TABLES, build_interaction_daily_from_cache_loader

FACTOR_ID = "order_unique_trade_participation_gap_v1"
FACTOR_FAMILY = "order_trade_interaction_pressure"
MECHANISM = '比较唯一订单参与广度与成交笔广度，捕捉“挂单参与”和“实际成交实现”之间的落差。'
INPUT_DEPENDENCIES = ['date', 'source_file', 'OrderId', 'Price', 'Volume']
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level"]
EXPECTED_REGIME = 'works better when displayed participation broadens faster than matched execution breadth'
FORBIDDEN_SEMANTIC_ASSUMPTIONS = ['no_trade_side_truth', 'no_broker_identity_truth', 'no_ordertype_truth', 'no_queue_semantics']

INPUT_TABLE = "verified_trades"
INPUT_TABLES = ['verified_trades', 'verified_orders']
OUTPUT_COLUMN = "order_unique_trade_participation_gap_score"


def _with_level_score(daily: pl.LazyFrame) -> pl.LazyFrame:
    return daily.with_columns(
        ((pl.col("unique_order_ids").log1p() - pl.col("trade_count").log1p())).alias(OUTPUT_COLUMN)
    )


def compute_signal(daily: pl.LazyFrame) -> pl.LazyFrame:
    return _with_level_score(daily).sort(["date", OUTPUT_COLUMN], descending=[False, True])


def compute_signal_from_cache_loader(
    *,
    cache_loader,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
) -> pl.LazyFrame:
    del previous_date_map
    daily = build_interaction_daily_from_cache_loader(cache_loader=cache_loader, dates=list(target_dates or []))
    return compute_signal(daily)
