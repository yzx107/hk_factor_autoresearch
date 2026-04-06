"""TradeDir imbalance intensity: volume-weighted |buy - sell| normalized."""

from __future__ import annotations

import polars as pl

from factor_defs.change_support import (
    build_change_signal,
    build_change_signal_from_loader,
    collect_daily_frames_from_loader,
)

FACTOR_ID = "trade_dir_imbalance_intensity_v1"
FACTOR_FAMILY = "directional_proxy"
MECHANISM = (
    "Compute the absolute volume-weighted imbalance between vendor-flagged "
    "buy and sell trades per stock-day. This captures the magnitude of "
    "directional aggression regardless of sign under the vendor proxy. "
    "High imbalance may indicate one-sided pressure or informed flow. "
    "This is NOT a signed-side truth claim — see TradeDir admissibility rules."
)
INPUT_DEPENDENCIES = ["date", "source_file", "Price", "Volume", "TradeDir"]
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level", "one_day_difference"]
EXPECTED_REGIME = "works better when buy-sell imbalance proxies directional urgency"
FORBIDDEN_SEMANTIC_ASSUMPTIONS = [
    "no_signed_side_truth",
    "no_aggressor_truth",
    "no_broker_identity_truth",
    "no_queue_semantics",
]

INPUT_TABLE = "verified_trades"
OUTPUT_COLUMN = "trade_dir_imbalance_intensity_score"
SUPPORTED_TRANSFORMS = ["level", "one_day_difference"]
LOOKBACK_STEPS = 1
SOURCE_COLUMNS = ["date", "source_file", "Price", "Volume", "TradeDir"]

_BUY_CODE = 1
_SELL_CODE = 2


def _daily_base(trades: pl.LazyFrame) -> pl.LazyFrame:
    """Build daily volume-weighted buy-sell imbalance."""
    with_notional = trades.with_columns(
        (pl.col("Price") * pl.col("Volume")).alias("notional"),
    )

    buy_vol = (
        with_notional.filter(pl.col("TradeDir") == _BUY_CODE)
        .group_by(["date", "instrument_key"])
        .agg(pl.col("notional").sum().alias("buy_notional"))
    )

    sell_vol = (
        with_notional.filter(pl.col("TradeDir") == _SELL_CODE)
        .group_by(["date", "instrument_key"])
        .agg(pl.col("notional").sum().alias("sell_notional"))
    )

    total = (
        with_notional.group_by(["date", "instrument_key"])
        .agg(pl.col("notional").sum().alias("total_notional"))
    )

    return (
        total.join(buy_vol, on=["date", "instrument_key"], how="left")
        .join(sell_vol, on=["date", "instrument_key"], how="left")
        .with_columns(
            [
                pl.col("buy_notional").fill_null(0.0),
                pl.col("sell_notional").fill_null(0.0),
            ]
        )
        .with_columns(
            pl.when(pl.col("total_notional") > 0)
            .then(
                (pl.col("buy_notional") - pl.col("sell_notional")).abs()
                / pl.col("total_notional")
            )
            .otherwise(0.0)
            .alias("trade_dir_imbalance_intensity_level")
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
                pl.col("trade_dir_imbalance_intensity_level").alias(OUTPUT_COLUMN)
            )
            .sort(["date", OUTPUT_COLUMN], descending=[False, True])
        )
    if transform == "one_day_difference":
        return build_change_signal(
            base,
            base_score_column="trade_dir_imbalance_intensity_level",
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
                pl.col("trade_dir_imbalance_intensity_level").alias(OUTPUT_COLUMN)
            ).sort(["date", OUTPUT_COLUMN], descending=[False, True])
        )
    if transform == "one_day_difference":
        return build_change_signal_from_loader(
            table_loader=table_loader,
            source_columns=SOURCE_COLUMNS,
            daily_base_builder=_daily_base,
            base_score_column="trade_dir_imbalance_intensity_level",
            output_column=OUTPUT_COLUMN,
            target_dates=target_dates,
            previous_date_map=previous_date_map,
        )
    raise ValueError(f"Unsupported transform `{transform}` for {FACTOR_ID}.")
