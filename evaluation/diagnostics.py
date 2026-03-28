"""Fixed lightweight diagnostics for Phase A factor outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import polars as pl


@dataclass(frozen=True)
class ScoreSummary:
    row_count: int
    mean: float
    min: float
    max: float


def _score_summary(frame: pl.DataFrame, score_column: str) -> ScoreSummary:
    if frame.is_empty():
        return ScoreSummary(row_count=0, mean=0.0, min=0.0, max=0.0)
    summary = frame.select(
        [
            pl.len().alias("row_count"),
            pl.col(score_column).mean().alias("mean"),
            pl.col(score_column).min().alias("min"),
            pl.col(score_column).max().alias("max"),
        ]
    ).to_dicts()[0]
    return ScoreSummary(
        row_count=int(summary["row_count"]),
        mean=float(summary["mean"]),
        min=float(summary["min"]),
        max=float(summary["max"]),
    )


def _records(frame: pl.DataFrame) -> list[dict[str, Any]]:
    records = frame.to_dicts()
    for record in records:
        if "date" in record:
            record["date"] = str(record["date"])
    return records


def build_signal_diagnostics(
    signal_df: pl.DataFrame,
    *,
    score_column: str,
    top_n: int = 5,
) -> dict[str, Any]:
    if score_column not in signal_df.columns:
        raise ValueError(f"Missing score column `{score_column}` in signal output.")
    if "date" not in signal_df.columns:
        raise ValueError("Signal output must include `date`.")

    dates = sorted({str(value) for value in signal_df["date"].to_list()})
    distinct_instruments = signal_df["instrument_key"].n_unique() if "instrument_key" in signal_df.columns else 0
    per_date = (
        signal_df.group_by("date")
        .agg(
            [
                pl.len().alias("row_count"),
                pl.col(score_column).mean().alias("score_mean"),
                pl.col(score_column).min().alias("score_min"),
                pl.col(score_column).max().alias("score_max"),
            ]
        )
        .sort("date")
    )

    top_rows = (
        signal_df.sort(["date", score_column], descending=[False, True])
        .group_by("date")
        .head(top_n)
    )
    bottom_rows = (
        signal_df.sort(["date", score_column], descending=[False, False])
        .group_by("date")
        .head(top_n)
    )

    diagnostics = {
        "score_column": score_column,
        "row_count": signal_df.height,
        "date_count": len(dates),
        "dates": dates,
        "distinct_instruments": int(distinct_instruments),
        "overall_score_summary": asdict(_score_summary(signal_df, score_column)),
        "per_date": _records(per_date),
        "top_by_date": _records(top_rows),
        "bottom_by_date": _records(bottom_rows),
    }
    return diagnostics
