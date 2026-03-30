"""Auto-generated Gate A factor from factor_specs."""

from __future__ import annotations

import polars as pl

from factor_defs.change_support import build_change_signal
from factor_defs.order_trade_interaction_support import DAILY_AGG_TABLES, build_interaction_daily_from_cache_loader

FACTOR_ID = "close_vwap_churn_interaction_v1"
FACTOR_FAMILY = "order_trade_interaction_pressure"
MECHANISM = '把尾盘价格偏离和订单生命周期 churn 放在一起，捕捉“价格压力 × 订单摩擦”的联合状态。'
INPUT_DEPENDENCIES = ['date', 'source_file', 'OrderId', 'Time', 'Price', 'Volume', 'row_num_in_file']
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level", "one_day_difference"]
EXPECTED_REGIME = 'works better when end-of-day dislocation and order churn rise together'
FORBIDDEN_SEMANTIC_ASSUMPTIONS = ['no_trade_side_truth', 'no_broker_identity_truth', 'no_ordertype_truth', 'no_queue_semantics']

INPUT_TABLE = "verified_trades"
INPUT_TABLES = ['verified_trades', 'verified_orders']
OUTPUT_COLUMN = "close_vwap_churn_interaction_score"
SUPPORTED_TRANSFORMS = ["level", "one_day_difference"]
LOOKBACK_STEPS = 1


def _level_frame(daily: pl.LazyFrame) -> pl.LazyFrame:
    return daily.with_columns(
        ((((pl.col("close_like_price") / pl.col("vwap")) - 1.0) * pl.col("churn_ratio").log1p())).alias("close_vwap_churn_interaction_level")
    )


def compute_signal(
    daily: pl.LazyFrame,
    *,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
    transform: str = "level",
) -> pl.LazyFrame:
    if transform == "level":
        return (
            _level_frame(daily)
            .with_columns(pl.col("close_vwap_churn_interaction_level").alias(OUTPUT_COLUMN))
            .sort(["date", OUTPUT_COLUMN], descending=[False, True])
        )
    if transform == "one_day_difference":
        return build_change_signal(
            _level_frame(daily),
            base_score_column="close_vwap_churn_interaction_level",
            output_column=OUTPUT_COLUMN,
            target_dates=target_dates,
            previous_date_map=previous_date_map,
        )
    raise ValueError(f"Unsupported transform `{transform}` for {FACTOR_ID}.")


def compute_signal_from_cache_loader(
    *,
    cache_loader,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
    transform: str = "level",
) -> pl.LazyFrame:
    target_dates = list(target_dates or [])
    previous_date_map = dict(previous_date_map or {})
    context_dates = (
        target_dates
        if transform == "level"
        else sorted(set(target_dates) | set(previous_date_map.values()))
    )
    daily = build_interaction_daily_from_cache_loader(cache_loader=cache_loader, dates=context_dates)
    return compute_signal(
        daily,
        target_dates=target_dates,
        previous_date_map=previous_date_map,
        transform=transform,
    )
