"""Shared helpers for first-difference factor variants."""

from __future__ import annotations

import polars as pl


def build_change_signal(
    daily_base: pl.LazyFrame,
    *,
    base_score_column: str,
    output_column: str,
    target_dates: list[str] | None,
    previous_date_map: dict[str, str] | None,
) -> pl.LazyFrame:
    target_dates = list(target_dates or [])
    previous_date_map = dict(previous_date_map or {})
    effective_dates = [date for date in target_dates if date in previous_date_map]
    if not effective_dates:
        return (
            daily_base
            .limit(0)
            .with_columns(pl.lit(0.0).alias("previous_" + base_score_column))
            .with_columns(pl.lit(0.0).alias(output_column))
        )

    date_map = (
        pl.DataFrame(
            {
                "date": effective_dates,
                "previous_date": [previous_date_map[date] for date in effective_dates],
            }
        )
        .with_columns([pl.col("date").str.to_date(), pl.col("previous_date").str.to_date()])
        .lazy()
    )

    current = daily_base.join(date_map, on="date", how="inner")
    previous = daily_base.select(
        [
            pl.col("date").alias("previous_date"),
            "instrument_key",
            pl.col(base_score_column).alias("previous_" + base_score_column),
        ]
    )

    return (
        current.join(previous, on=["previous_date", "instrument_key"], how="inner")
        .with_columns(
            (
                pl.col(base_score_column) - pl.col("previous_" + base_score_column)
            ).alias(output_column)
        )
        .sort(["date", output_column], descending=[False, True])
    )


def collect_daily_frames_from_loader(
    *,
    table_loader,
    source_columns: list[str],
    daily_frame_builder,
    dates: list[str],
) -> pl.LazyFrame:
    daily_frames: list[pl.DataFrame] = []
    for date in dates:
        built = daily_frame_builder(table_loader([date], source_columns))
        if isinstance(built, pl.LazyFrame):
            daily_frames.append(built.collect())
        else:
            daily_frames.append(built)
    if not daily_frames:
        return pl.DataFrame().lazy()
    return pl.concat(daily_frames, how="vertical_relaxed").lazy()


def build_change_signal_from_loader(
    *,
    table_loader,
    source_columns: list[str],
    daily_base_builder,
    base_score_column: str,
    output_column: str,
    target_dates: list[str] | None,
    previous_date_map: dict[str, str] | None,
) -> pl.LazyFrame:
    target_dates = list(target_dates or [])
    previous_date_map = dict(previous_date_map or {})
    effective_dates = [date for date in target_dates if date in previous_date_map]
    if not effective_dates:
        return build_change_signal(
            pl.DataFrame(
                {
                    "date": [],
                    "instrument_key": [],
                    base_score_column: [],
                },
                schema={"date": pl.Date, "instrument_key": pl.String, base_score_column: pl.Float64},
            ).lazy(),
            base_score_column=base_score_column,
            output_column=output_column,
            target_dates=target_dates,
            previous_date_map=previous_date_map,
        )

    context_dates = sorted(set(effective_dates) | {previous_date_map[date] for date in effective_dates})
    daily_base = collect_daily_frames_from_loader(
        table_loader=table_loader,
        source_columns=source_columns,
        daily_frame_builder=daily_base_builder,
        dates=context_dates,
    )
    return build_change_signal(
        daily_base,
        base_score_column=base_score_column,
        output_column=output_column,
        target_dates=target_dates,
        previous_date_map=previous_date_map,
    )
