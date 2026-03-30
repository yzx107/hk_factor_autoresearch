"""Auto-generated Gate A factor from factor_specs."""

from __future__ import annotations

import polars as pl

from factor_defs.order_trade_interaction_support import DAILY_AGG_TABLES, build_interaction_daily_from_cache_loader

FACTOR_ID = "close_vwap_churn_interaction_v1"
FACTOR_FAMILY = "order_trade_interaction_pressure"
MECHANISM = '把尾盘价格偏离和订单生命周期 churn 放在一起，捕捉“价格压力 × 订单摩擦”的联合状态。'
INPUT_DEPENDENCIES = ['date', 'source_file', 'OrderId', 'Time', 'Price', 'Volume', 'row_num_in_file']
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level"]
EXPECTED_REGIME = 'works better when end-of-day dislocation and order churn rise together'
FORBIDDEN_SEMANTIC_ASSUMPTIONS = ['no_trade_side_truth', 'no_broker_identity_truth', 'no_ordertype_truth', 'no_queue_semantics']

INPUT_TABLE = "verified_trades"
INPUT_TABLES = ['verified_trades', 'verified_orders']
OUTPUT_COLUMN = "close_vwap_churn_interaction_score"


def _with_level_score(daily: pl.LazyFrame) -> pl.LazyFrame:
    return daily.with_columns(
        ((((pl.col("close_like_price") / pl.col("vwap")) - 1.0) * pl.col("churn_ratio").log1p())).alias(OUTPUT_COLUMN)
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
