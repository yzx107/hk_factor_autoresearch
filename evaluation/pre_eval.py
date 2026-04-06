"""Fixed forward-return pre-evaluation for Phase A factor outputs."""

from __future__ import annotations

from math import fsum
from typing import Any

import polars as pl

from diagnostics.regime_slices import build_regime_metadata, build_regime_slice_summary
from evaluation.metrics import adaptive_bin_count, mutual_information_metrics
from evaluation.significance import mutual_information_permutation_test

LABEL_NAME = "forward_return_1d_close_like"
LABEL_SOURCE = "verified_trades_last_print_close_like_v1"
TOP_FRACTION = 0.1
MI_BIN_COUNT = 16
MI_MIN_BIN_COUNT = 4
MI_BINNING = "adaptive_equal_frequency_rank_bins_sturges_v1"
MI_PERMUTATION_COUNT = 100
MI_SIGNIFICANCE_THRESHOLD = 0.05


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
    mi_min_bin_count: int = MI_MIN_BIN_COUNT,
    mi_permutation_count: int = MI_PERMUTATION_COUNT,
    mi_significance_threshold: float = MI_SIGNIFICANCE_THRESHOLD,
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
    if mi_min_bin_count < 2:
        raise ValueError("mi_min_bin_count must be >= 2.")
    if mi_bin_count < mi_min_bin_count:
        raise ValueError("mi_bin_count must be >= mi_min_bin_count.")
    if mi_permutation_count < 1:
        raise ValueError("mi_permutation_count must be >= 1.")
    if mi_significance_threshold <= 0.0 or mi_significance_threshold >= 1.0:
        raise ValueError("mi_significance_threshold must be in (0, 1).")

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
        mean_nmi_ic_gap = None
        mean_mi_p_value = None
        mean_mi_excess_over_null = None
        mi_significant_date_ratio = None
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
        partitions = sorted(
            joined.partition_by("date", as_dict=True).items(),
            key=lambda item: item[0][0] if isinstance(item[0], tuple) else item[0],
        )
        for seed_offset, (date_value, subset) in enumerate(partitions):
            date_key = str(date_value[0] if isinstance(date_value, tuple) else date_value)
            score_values = [float(value) for value in subset[score_column].to_list()]
            label_values = [float(value) for value in subset[label_column].to_list()]
            requested_bins = adaptive_bin_count(
                len(score_values),
                minimum=mi_min_bin_count,
                maximum=mi_bin_count,
            )
            mi_summary = mutual_information_metrics(
                score_values,
                label_values,
                requested_bins=requested_bins,
            )
            mi_significance = mutual_information_permutation_test(
                score_values,
                label_values,
                requested_bins=requested_bins,
                permutations=mi_permutation_count,
                seed=seed_offset,
                p_value_threshold=mi_significance_threshold,
            )
            mutual_info = mi_summary.mutual_information
            normalized_mutual_info = mi_summary.normalized_mutual_information
            mi_null_mean = mi_significance.null_mean
            mutual_info_by_date[date_key] = {
                "mi": mutual_info,
                "nmi": normalized_mutual_info,
                "mi_bin_count": mi_summary.effective_bin_count,
                "mi_requested_bin_count": requested_bins,
                "mi_p_value": mi_significance.p_value,
                "mi_significant": mi_significance.passed,
                "mi_null_mean": mi_null_mean,
                "mi_null_std": mi_significance.null_std,
                "mi_excess_over_null": (
                    None if mutual_info is None or mi_null_mean is None else mutual_info - mi_null_mean
                ),
            }

        for row in per_date_rows:
            metrics = mutual_info_by_date.get(str(row["date"]), {})
            row["mi"] = metrics.get("mi")
            row["nmi"] = metrics.get("nmi")
            # Keep long-form aliases while downstream readers migrate to the canonical
            # per-date contract: `mi` / `nmi`.
            row["mutual_info"] = row["mi"]
            row["normalized_mutual_info"] = row["nmi"]
            row["mi_bin_count"] = metrics.get("mi_bin_count")
            row["mi_requested_bin_count"] = metrics.get("mi_requested_bin_count")
            row["mi_p_value"] = metrics.get("mi_p_value")
            row["mi_significant"] = metrics.get("mi_significant")
            row["mi_null_mean"] = metrics.get("mi_null_mean")
            row["mi_null_std"] = metrics.get("mi_null_std")
            row["mi_excess_over_null"] = metrics.get("mi_excess_over_null")
            row["nmi_ic_gap"] = (
                None
                if row["nmi"] is None or row["rank_ic"] is None
                else float(row["nmi"]) - abs(float(row["rank_ic"]))
            )

        joined_preview = _records(joined.sort(["date", score_column], descending=[False, True]).head(10))
        rank_ic_values = [float(item["rank_ic"]) for item in per_date_rows if item["rank_ic"] is not None]
        mutual_info_values = [float(item["mi"]) for item in per_date_rows if item.get("mi") is not None]
        normalized_mutual_info_values = [float(item["nmi"]) for item in per_date_rows if item.get("nmi") is not None]
        nmi_ic_gap_values = [float(item["nmi_ic_gap"]) for item in per_date_rows if item.get("nmi_ic_gap") is not None]
        mi_p_values = [float(item["mi_p_value"]) for item in per_date_rows if item.get("mi_p_value") is not None]
        mi_excess_values = [
            float(item["mi_excess_over_null"]) for item in per_date_rows if item.get("mi_excess_over_null") is not None
        ]
        mi_significance_values = [
            1.0 if bool(item["mi_significant"]) else 0.0
            for item in per_date_rows
            if item.get("mi_significant") is not None
        ]
        spread_values = [
            float(item["top_bottom_spread"]) for item in per_date_rows if item["top_bottom_spread"] is not None
        ]
        coverage_values = [float(item["coverage_ratio"]) for item in per_date_rows if item["coverage_ratio"] is not None]
        mean_rank_ic = _average(rank_ic_values)
        mean_abs_rank_ic = _average([abs(value) for value in rank_ic_values])
        mean_mutual_info = _average(mutual_info_values)
        mean_normalized_mutual_info = _average(normalized_mutual_info_values)
        mean_nmi_ic_gap = _average(nmi_ic_gap_values)
        mean_mi_p_value = _average(mi_p_values)
        mean_mi_excess_over_null = _average(mi_excess_values)
        mi_significant_date_ratio = _average(mi_significance_values)
        mean_top_bottom_spread = _average(spread_values)
        mean_coverage_ratio = _average(coverage_values)

    regime_slices = build_regime_slice_summary(per_date_rows, date_annotations)
    # Canonical summary contract lives under `aggregate_metrics`, with per-date
    # metrics exposed as `mi` / `nmi`. The legacy `mean_*` and long-form mutual
    # information aliases are kept for compatibility with existing readers.
    aggregate_metrics = {
        "rank_ic": mean_rank_ic,
        "abs_rank_ic": mean_abs_rank_ic,
        "mi": mean_mutual_info,
        "nmi": mean_normalized_mutual_info,
        "nmi_ic_gap": mean_nmi_ic_gap,
        "mi_p_value": mean_mi_p_value,
        "mi_excess_over_null": mean_mi_excess_over_null,
        "mi_significant_date_ratio": mi_significant_date_ratio,
        "top_bottom_spread": mean_top_bottom_spread,
        "coverage_ratio": mean_coverage_ratio,
    }

    return {
        "label_name": label_column,
        "label_source": labels_df["label_source"][0] if not labels_df.is_empty() else LABEL_SOURCE,
        "score_column": score_column,
        "mi_binning": MI_BINNING,
        "mi_bin_count": mi_bin_count,
        "mi_min_bin_count": mi_min_bin_count,
        "mi_permutation_count": mi_permutation_count,
        "mi_significance_threshold": mi_significance_threshold,
        "aggregate_metrics": aggregate_metrics,
        "factor_date_count": len(factor_dates),
        "factor_dates": factor_dates,
        "labeled_date_count": len(labeled_dates),
        "labeled_dates": labeled_dates,
        "skipped_dates": skipped_dates,
        "joined_rows": int(joined.height),
        "mean_rank_ic": mean_rank_ic,
        "mean_abs_rank_ic": mean_abs_rank_ic,
        "mean_mutual_info": mean_mutual_info,
        "mean_normalized_mutual_info": mean_normalized_mutual_info,
        "mean_nmi_ic_gap": mean_nmi_ic_gap,
        "mean_mi_p_value": mean_mi_p_value,
        "mean_mi_excess_over_null": mean_mi_excess_over_null,
        "mi_significant_date_ratio": mi_significant_date_ratio,
        "mean_top_bottom_spread": mean_top_bottom_spread,
        "mean_coverage_ratio": mean_coverage_ratio,
        "regime_metadata": build_regime_metadata(),
        "regime_slices": regime_slices,
        "per_date": per_date_rows,
        "joined_preview": joined_preview,
    }
