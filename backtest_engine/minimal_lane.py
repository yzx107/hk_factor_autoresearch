"""Minimal formal backtest lane for shortlisted factors.

This is intentionally low-freedom:
- standardized factor score + label join
- daily top/bottom spread
- simple turnover proxy
- hit-rate and sign-stability proxy
- optional conservative cost-adjusted spread
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import fsum
from statistics import mean
from typing import Any

import polars as pl

from evaluation.robustness import summarize_signs
from harness.instrument_universe import (
    DEFAULT_SOURCE_INSTRUMENT_UNIVERSE,
    DEFAULT_TARGET_INSTRUMENT_UNIVERSE,
    UNIVERSE_FILTER_VERSION,
)

DEFAULT_LABEL_COLUMN = "forward_return_1d_close_like"
DEFAULT_SCORE_COLUMN = "score"
DEFAULT_TOP_FRACTION = 0.1
DEFAULT_COST_BPS = 0.0
POLICY_VERSION = "minimal_backtest_lane_v1"


@dataclass(frozen=True)
class MinimalBacktestResult:
    backtest_id: str
    policy_version: str
    factor_name: str
    score_column: str
    label_column: str
    target_instrument_universe: str
    source_instrument_universe: str
    contains_cross_security_source: bool
    universe_filter_version: str
    horizon: str
    top_fraction: float
    cost_bps: float
    joined_rows: int
    evaluated_dates: int
    coverage_ratio: float | None
    gross_long_return: float | None
    gross_short_return: float | None
    spread_return: float | None
    cost_adjusted_spread_return: float | None
    turnover_proxy: float | None
    hit_rate: float | None
    stability_proxy: float | None
    sign_switch_count: int
    per_date: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ensure_frame(frame: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame:
    return frame.collect() if isinstance(frame, pl.LazyFrame) else frame


def _normalize_columns(frame: pl.DataFrame, *, date_column: str = "date") -> pl.DataFrame:
    columns = list(frame.columns)
    if date_column in columns:
        frame = frame.with_columns(pl.col(date_column).cast(pl.Utf8))
    if "instrument_key" in columns:
        frame = frame.with_columns(pl.col("instrument_key").cast(pl.Utf8))
    return frame


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return fsum(values) / len(values)


def run_minimal_backtest(
    factor_scores: pl.DataFrame | pl.LazyFrame,
    labels: pl.DataFrame | pl.LazyFrame,
    *,
    factor_name: str,
    score_column: str = DEFAULT_SCORE_COLUMN,
    label_column: str = DEFAULT_LABEL_COLUMN,
    target_instrument_universe: str = DEFAULT_TARGET_INSTRUMENT_UNIVERSE,
    source_instrument_universe: str = DEFAULT_SOURCE_INSTRUMENT_UNIVERSE,
    contains_cross_security_source: bool = False,
    universe_filter_version: str = UNIVERSE_FILTER_VERSION,
    horizon: str = "1d",
    top_fraction: float = DEFAULT_TOP_FRACTION,
    cost_bps: float = DEFAULT_COST_BPS,
) -> MinimalBacktestResult:
    if top_fraction <= 0.0 or top_fraction > 0.5:
        raise ValueError("top_fraction must be in (0, 0.5].")
    if cost_bps < 0.0:
        raise ValueError("cost_bps must be >= 0.")

    factor_frame = _normalize_columns(_ensure_frame(factor_scores))
    label_frame = _normalize_columns(_ensure_frame(labels))

    if score_column not in factor_frame.columns:
        raise ValueError(f"Missing score column `{score_column}` in factor scores.")
    if label_column not in label_frame.columns:
        raise ValueError(f"Missing label column `{label_column}` in labels.")
    if "date" not in factor_frame.columns or "instrument_key" not in factor_frame.columns:
        raise ValueError("Factor scores must include `date` and `instrument_key`.")
    if "date" not in label_frame.columns or "instrument_key" not in label_frame.columns:
        raise ValueError("Labels must include `date` and `instrument_key`.")

    joined = (
        factor_frame.select(["date", "instrument_key", score_column])
        .join(label_frame.select(["date", "instrument_key", label_column]), on=["date", "instrument_key"], how="inner")
        .drop_nulls([score_column, label_column])
        .sort(["date", score_column], descending=[False, True])
    )

    per_date: list[dict[str, Any]] = []
    prev_selected: set[str] | None = None
    prev_spread_signs: list[float] = []
    total_factor_rows = factor_frame.height
    total_joined_rows = joined.height

    for date_key, date_frame in joined.group_by("date", maintain_order=True):
        date_value = str(date_key[0] if isinstance(date_key, tuple) else date_key)
        ordered = date_frame.sort(score_column, descending=True)
        row_count = ordered.height
        bucket_size = max(1, int(row_count * top_fraction))
        long_bucket = ordered.head(bucket_size)
        short_bucket = ordered.tail(bucket_size).sort(score_column)

        long_return = _mean_or_none(long_bucket[label_column].to_list())
        short_return = _mean_or_none(short_bucket[label_column].to_list())
        spread_return = None if long_return is None or short_return is None else long_return - short_return
        long_keys = set(long_bucket["instrument_key"].to_list())
        short_keys = set(short_bucket["instrument_key"].to_list())
        selected_keys = long_keys | short_keys
        if prev_selected is None:
            turnover_proxy = 0.0
        else:
            union = selected_keys | prev_selected
            turnover_proxy = 0.0 if not union else 1.0 - (len(selected_keys & prev_selected) / len(union))

        per_date.append(
            {
                "date": date_value,
                "row_count": row_count,
                "bucket_size": bucket_size,
                "long_return": long_return,
                "short_return": short_return,
                "spread_return": spread_return,
                "turnover_proxy": turnover_proxy,
                "selected_count": len(selected_keys),
            }
        )
        prev_selected = selected_keys

    spread_values = [row["spread_return"] for row in per_date if row["spread_return"] is not None]
    long_values = [row["long_return"] for row in per_date if row["long_return"] is not None]
    short_values = [row["short_return"] for row in per_date if row["short_return"] is not None]
    turnover_values = [row["turnover_proxy"] for row in per_date if row["turnover_proxy"] is not None]
    sign_summary = summarize_signs(spread_values)
    hit_rate = None if not spread_values else sum(1 for value in spread_values if value > 0.0) / len(spread_values)
    spread_return = _mean_or_none(spread_values)
    turnover_proxy = _mean_or_none(turnover_values)
    cost_adjusted = None
    if spread_return is not None:
        cost_adjusted = spread_return - ((cost_bps / 10_000.0) * (turnover_proxy or 0.0))

    result = MinimalBacktestResult(
        backtest_id="",
        policy_version=POLICY_VERSION,
        factor_name=factor_name,
        score_column=score_column,
        label_column=label_column,
        target_instrument_universe=target_instrument_universe,
        source_instrument_universe=source_instrument_universe,
        contains_cross_security_source=contains_cross_security_source,
        universe_filter_version=universe_filter_version,
        horizon=horizon,
        top_fraction=top_fraction,
        cost_bps=cost_bps,
        joined_rows=total_joined_rows,
        evaluated_dates=len(per_date),
        coverage_ratio=(None if total_factor_rows == 0 else total_joined_rows / total_factor_rows),
        gross_long_return=_mean_or_none(long_values),
        gross_short_return=_mean_or_none(short_values),
        spread_return=spread_return,
        cost_adjusted_spread_return=cost_adjusted,
        turnover_proxy=turnover_proxy,
        hit_rate=hit_rate,
        stability_proxy=sign_summary.sign_consistency,
        sign_switch_count=sign_summary.sign_switch_count,
        per_date=per_date,
    )
    return result

