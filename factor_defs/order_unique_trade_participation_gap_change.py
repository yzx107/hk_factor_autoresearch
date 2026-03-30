"""Auto-generated Gate A change factor from factor_specs."""

from __future__ import annotations

import polars as pl

from factor_defs.change_support import build_change_signal
from factor_defs.order_trade_interaction_support import DAILY_AGG_TABLES, build_interaction_daily_from_cache_loader

FACTOR_ID = "order_unique_trade_participation_gap_change_v1"
FACTOR_FAMILY = "order_trade_interaction_pressure"
MECHANISM = "Measure one-day acceleration in 订单-成交参与广度差."
INPUT_DEPENDENCIES = ['date', 'source_file', 'OrderId', 'Price', 'Volume']
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level", "one_day_difference"]
EXPECTED_REGIME = "change version of: works better when displayed participation broadens faster than matched execution breadth"
FORBIDDEN_SEMANTIC_ASSUMPTIONS = ['no_trade_side_truth', 'no_broker_identity_truth', 'no_ordertype_truth', 'no_queue_semantics']

INPUT_TABLE = "verified_trades"
INPUT_TABLES = ['verified_trades', 'verified_orders']
OUTPUT_COLUMN = "order_unique_trade_participation_gap_change_score"
LOOKBACK_STEPS = 1


def _daily_base(daily: pl.LazyFrame) -> pl.LazyFrame:
    return daily.with_columns(
        ((pl.col("unique_order_ids").log1p() - pl.col("trade_count").log1p())).alias("order_unique_trade_participation_gap_level")
    )


def compute_signal(
    daily: pl.LazyFrame,
    *,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
) -> pl.LazyFrame:
    return build_change_signal(
        _daily_base(daily),
        base_score_column="order_unique_trade_participation_gap_level",
        output_column=OUTPUT_COLUMN,
        target_dates=target_dates,
        previous_date_map=previous_date_map,
    )


def compute_signal_from_cache_loader(
    *,
    cache_loader,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
) -> pl.LazyFrame:
    target_dates = list(target_dates or [])
    previous_date_map = dict(previous_date_map or {})
    context_dates = sorted(set(target_dates) | set(previous_date_map.values()))
    daily = build_interaction_daily_from_cache_loader(cache_loader=cache_loader, dates=context_dates)
    return compute_signal(
        daily,
        target_dates=target_dates,
        previous_date_map=previous_date_map,
    )
