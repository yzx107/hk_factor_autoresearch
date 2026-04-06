"""Fixed forward-return pre-evaluation for Phase A factor outputs."""

from __future__ import annotations

from collections import Counter
from math import fsum, log
from typing import Any

import polars as pl

from diagnostics.regime_slices import build_regime_slice_summary

LABEL_NAME = "forward_return_1d_close_like"
LABEL_SOURCE = "verified_trades_last_print_close_like_v1"
TOP_FRACTION = 0.1
MI_BIN_COUNT = 8
MI_BINNING = "equal_frequency_rank_bins_v1"


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return fsum(values) / len(values)


def _records(frame: pl.DataFrame) -> list[dict[str, Any]]:
    records = frame.to_dicts()
    for record in records:
        if "date" in record and record["date"] is not None:
            record["date"] = str(record["date"])
        if "next_date" in record and record["next_date"] is not None:
            record["next_date"] = str(record["next_date"])
    return records


def _effective_bin_count(row_count: int, requested_bins: int) -> int:
    if row_count <= 1:
        return 1
    return max(2, min(requested_bins, row_count))


def _equal_frequency_bins(values: list[float], requested_bins: int) -> tuple[list[int], int]:
    effective_bins = _effective_bin_count(len(values), requested_bins)
    if effective_bins <= 1:
        return [0 for _ in values], effective_bins
    order = sorted(range(len(values)), key=lambda idx: (values[idx], idx))
    bins = [0 for _ in values]
    for rank, idx in enumerate(order):
        bins[idx] = min((rank * effective_bins) // len(values), effective_bins - 1)
    return bins, effective_bins


def _entropy(counts: Counter[int], total: int) -> float:
    if total <= 0:
        return 0.0
    return -fsum((count / total) * log(count / total) for count in counts.values() if count > 0)


def _mutual_information_metrics(
    score_values: list[float],
    label_values: list[float],
    *,
    requested_bins: int = MI_BIN_COUNT,
) -> tuple[float | None, float | None, int]:
    if len(score_values) != len(label_values):
        raise ValueError("score_values and label_values must have the same length.")
    if len(score_values) <= 1:
        return None, None, 1

    score_bins, score_effective = _equal_frequency_bins(score_values, requested_bins)
    label_bins, label_effective = _equal_frequency_bins(label_values, requested_bins)
    effective_bins = min(score_effective, label_effective)
    total = len(score_values)

    score_counts = Counter(score_bins)
    label_counts = Counter(label_bins)
    joint_counts = Counter(zip(score_bins, label_bins))

    score_entropy = _entropy(score_counts, total)
    label_entropy = _entropy(label_counts, total)
    if score_entropy <= 0.0 or label_entropy <= 0.0:
        return 0.0, 0.0, effective_bins

    mutual_info = fsum(
        (joint_count / total)
        * log((joint_count * total) / (score_counts[score_bin] * label_counts[label_bin]))
        for (score_bin, label_bin), joint_count in joint_counts.items()
        if joint_count > 0
    )
    normalized_mutual_info = mutual_info / max(score_entropy, label_entropy)
    return mutual_info, normalized_mutual_info, effective_bins


def build_close_like_frame(trades: pl.LazyFrame) -> pl.DataFrame:
    return (
        trades.sort(["date", "instrument_key", "Time", "row_num_in_file"])
        .group_by(["date", "instrument_key"], maintain_order=True)
        .agg(pl.col("Price").last().alias("close_like_price"))
        .sort(["date", "instrument_key"])
        .collect()
    )


def build_forward_return_labels(
    close_like_df: pl.DataFrame,
    *,
    next_date_map: dict[str, str],
    label_name: str = LABEL_NAME,
    label_source: str = LABEL_SOURCE,
) -> pl.DataFrame:
    if close_like_df.is_empty() or not next_date_map:
        return pl.DataFrame(
            {
                "date": [],
                "next_date": [],
                "instrument_key": [],
                "close_like_price": [],
                "next_close_like_price": [],
                label_name: [],
                "label_source": [],
            },
            schema={
                "date": pl.Date,
                "next_date": pl.Date,
                "instrument_key": pl.String,
                "close_like_price": pl.Float64,
                "next_close_like_price": pl.Float64,
                label_name: pl.Float64,
                "label_source": pl.String,
            },
        )

    date_map = pl.DataFrame(
        {
            "date": list(next_date_map.keys()),
            "next_date": list(next_date_map.values()),
        }
    ).with_columns([pl.col("date").str.to_date(), pl.col("next_date").str.to_date()])

    current_prices = close_like_df.select(["date", "instrument_key", "close_like_price"])
    next_prices = close_like_df.select(
        [
            pl.col("date").alias("next_date"),
            "instrument_key",
            pl.col("close_like_price").alias("next_close_like_price"),
        ]
    )

    return (
        current_prices.join(date_map, on="date", how="inner")
        .join(next_prices, on=["next_date", "instrument_key"], how="inner")
        .filter(pl.col("close_like_price") > 0)
        .with_columns(
            [
                ((pl.col("next_close_like_price") / pl.col("close_like_price")) - 1.0).alias(label_name),
                pl.lit(label_source).alias("label_source"),
            ]
        )
        .sort(["date", "instrument_key"])
    )


def build_pre_eval_summary(
    factor_df: pl.DataFrame,
    *,
    score_column: str,
    labels_df: pl.DataFrame,
    date_annotations: pl.DataFrame | None = None,
    label_column: str = LABEL_NAME,
    top_fraction: float = TOP_FRACTION,
    mi_bin_count: int = MI_BIN_COUNT,
) -> dict[str, Any]:
    if score_column not in factor_df.columns:
        raise ValueError(f"Missing score column `{score_column}` in factor output.")
    if label_column not in labels_df.columns:
        raise ValueError(f"Missing label column `{label_column}` in label frame.")
    if "date" not in factor_df.columns or "instrument_key" not in factor_df.columns:
        raise ValueError("Factor output must include `date` and `instrument_key`.")
    if top_fraction <= 0 or top_fraction > 0.5:
        raise ValueError("top_fraction must be in (0, 0.5].")
    if mi_bin_count < 2:
        raise ValueError("mi_bin_count must be >= 2.")

    factor_dates = sorted({str(value) for value in factor_df["date"].to_list()})
    labeled_dates = sorted({str(value) for value in labels_df["date"].to_list()})
    skipped_dates = [date for date in factor_dates if date not in labeled_dates]

    factor_counts = factor_df.group_by("date").agg(pl.len().alias("factor_rows"))
    joined = factor_df.select(["date", "instrument_key", score_column]).join(
        labels_df.select(["date", "next_date", "instrument_key", label_column]),
        on=["date", "instrument_key"],
        how="inner",
    )

    if joined.is_empty():
        per_date_rows: list[dict[str, Any]] = []
        joined_preview: list[dict[str, Any]] = []
        mean_rank_ic = None
        mean_abs_rank_ic = None
        mean_mutual_info = None
        mean_normalized_mutual_info = None
        mean_top_bottom_spread = None
        mean_coverage_ratio = None
    else:
        ranked = (
            joined.with_columns(
                [
                    pl.len().over("date").alias("labeled_rows"),
                    pl.col(score_column).rank("average").over("date").alias("score_rank"),
                    pl.col(label_column).rank("average").over("date").alias("label_rank"),
                    pl.col(score_column).rank("ordinal", descending=True).over("date").alias("score_rank_desc"),
                    pl.col(score_column).rank("ordinal").over("date").alias("score_rank_asc"),
                ]
            )
            .with_columns(
                (pl.col("labeled_rows") * top_fraction).ceil().clip(lower_bound=1).cast(pl.Int64).alias(
                    "bucket_size"
                )
            )
        )

        per_date = (
            ranked.group_by("date")
            .agg(
                [
                    pl.first("next_date").alias("next_date"),
                    pl.first("labeled_rows").alias("labeled_rows"),
                    pl.first("bucket_size").alias("bucket_size"),
                    pl.corr("score_rank", "label_rank").alias("rank_ic"),
                    pl.corr(score_column, label_column).alias("pearson_corr"),
                    pl.col(label_column).mean().alias("mean_forward_return"),
                ]
            )
            .join(factor_counts, on="date", how="left")
            .with_columns((pl.col("labeled_rows") / pl.col("factor_rows")).alias("coverage_ratio"))
            .sort("date")
        )

        top_returns = (
            ranked.filter(pl.col("score_rank_desc") <= pl.col("bucket_size"))
            .group_by("date")
            .agg(pl.col(label_column).mean().alias("top_bucket_mean_return"))
        )
        bottom_returns = (
            ranked.filter(pl.col("score_rank_asc") <= pl.col("bucket_size"))
            .group_by("date")
            .agg(pl.col(label_column).mean().alias("bottom_bucket_mean_return"))
        )

        per_date = (
            per_date.join(top_returns, on="date", how="left")
            .join(bottom_returns, on="date", how="left")
            .with_columns(
                (pl.col("top_bucket_mean_return") - pl.col("bottom_bucket_mean_return")).alias(
                    "top_bottom_spread"
                )
            )
            .sort("date")
        )
        per_date_rows = _records(per_date)
        mutual_info_by_date: dict[str, dict[str, float | int | None]] = {}
        for date_value, subset in joined.partition_by("date", as_dict=True).items():
            date_key = str(date_value[0] if isinstance(date_value, tuple) else date_value)
            score_values = [float(value) for value in subset[score_column].to_list()]
            label_values = [float(value) for value in subset[label_column].to_list()]
            mutual_info, normalized_mutual_info, effective_bins = _mutual_information_metrics(
                score_values,
                label_values,
                requested_bins=mi_bin_count,
            )
            mutual_info_by_date[date_key] = {
                "mutual_info": mutual_info,
                "normalized_mutual_info": normalized_mutual_info,
                "mi_bin_count": effective_bins,
            }

        for row in per_date_rows:
            metrics = mutual_info_by_date.get(str(row["date"]), {})
            row["mutual_info"] = metrics.get("mutual_info")
            row["normalized_mutual_info"] = metrics.get("normalized_mutual_info")
            row["mi_bin_count"] = metrics.get("mi_bin_count")
            row["mi"] = metrics.get("mutual_info")
            row["nmi"] = metrics.get("normalized_mutual_info")

        joined_preview = _records(joined.sort(["date", score_column], descending=[False, True]).head(10))
        rank_ic_values = [float(item["rank_ic"]) for item in per_date_rows if item["rank_ic"] is not None]
        mutual_info_values = [
            float(item["mutual_info"]) for item in per_date_rows if item.get("mutual_info") is not None
        ]
        normalized_mutual_info_values = [
            float(item["normalized_mutual_info"])
            for item in per_date_rows
            if item.get("normalized_mutual_info") is not None
        ]
        spread_values = [
            float(item["top_bottom_spread"]) for item in per_date_rows if item["top_bottom_spread"] is not None
        ]
        coverage_values = [float(item["coverage_ratio"]) for item in per_date_rows if item["coverage_ratio"] is not None]
        mean_rank_ic = _average(rank_ic_values)
        mean_abs_rank_ic = _average([abs(value) for value in rank_ic_values])
        mean_mutual_info = _average(mutual_info_values)
        mean_normalized_mutual_info = _average(normalized_mutual_info_values)
        mean_top_bottom_spread = _average(spread_values)
        mean_coverage_ratio = _average(coverage_values)

    regime_slices = build_regime_slice_summary(per_date_rows, date_annotations)
    aggregate_metrics = {
        "rank_ic": mean_rank_ic,
        "abs_rank_ic": mean_abs_rank_ic,
        "mi": mean_mutual_info,
        "nmi": mean_normalized_mutual_info,
        "top_bottom_spread": mean_top_bottom_spread,
        "coverage_ratio": mean_coverage_ratio,
    }

    return {
        "label_name": label_column,
        "label_source": labels_df["label_source"][0] if not labels_df.is_empty() else LABEL_SOURCE,
        "score_column": score_column,
        "mi_binning": MI_BINNING,
        "mi_bin_count": mi_bin_count,
        "aggregate_metrics": aggregate_metrics,
        "factor_date_count": len(factor_dates),
        "factor_dates": factor_dates,
        "labeled_date_count": len(labeled_dates),
        "labeled_dates": labeled_dates,
        "skipped_dates": skipped_dates,
        "joined_rows": int(joined.height),
        "rank_ic": mean_rank_ic,
        "abs_rank_ic": mean_abs_rank_ic,
        "mi": mean_mutual_info,
        "nmi": mean_normalized_mutual_info,
        "top_bottom_spread": mean_top_bottom_spread,
        "coverage_ratio": mean_coverage_ratio,
        "mean_rank_ic": mean_rank_ic,
        "mean_abs_rank_ic": mean_abs_rank_ic,
        "mean_mutual_info": mean_mutual_info,
        "mean_normalized_mutual_info": mean_normalized_mutual_info,
        "mean_top_bottom_spread": mean_top_bottom_spread,
        "mean_coverage_ratio": mean_coverage_ratio,
        "regime_slices": regime_slices,
        "per_date": per_date_rows,
        "joined_preview": joined_preview,
    }
