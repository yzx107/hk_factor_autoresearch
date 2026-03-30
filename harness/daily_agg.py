"""Read-only loader for local daily aggregate cache tables."""

from __future__ import annotations

from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
DAILY_AGG_ROOT = ROOT / "cache" / "daily_agg"
VALID_DAILY_TABLES = {"verified_trades_daily", "verified_orders_daily"}


def _year_from_date(date: str) -> str:
    return date.split("-", 1)[0]


def daily_agg_partition_path(table_name: str, date: str) -> Path:
    if table_name not in VALID_DAILY_TABLES:
        raise ValueError(f"Unsupported daily agg table `{table_name}`.")
    return DAILY_AGG_ROOT / table_name / f"year={_year_from_date(date)}" / f"date={date}" / "part-00000.parquet"


def build_daily_agg_paths(table_name: str, dates: list[str]) -> list[Path]:
    if not dates:
        raise ValueError("At least one date is required.")
    paths: list[Path] = []
    for date in dates:
        path = daily_agg_partition_path(table_name, date)
        if not path.exists():
            raise FileNotFoundError(f"Daily agg partition not found: {path}")
        paths.append(path)
    return paths


def available_daily_agg_dates(table_name: str, year: str) -> list[str]:
    if table_name not in VALID_DAILY_TABLES:
        raise ValueError(f"Unsupported daily agg table `{table_name}`.")
    table_root = DAILY_AGG_ROOT / table_name / f"year={year}"
    if not table_root.exists():
        return []
    return sorted(
        path.name.split("=", 1)[1]
        for path in table_root.iterdir()
        if path.is_dir() and path.name.startswith("date=")
    )


def missing_daily_agg_dates(table_name: str, dates: list[str]) -> list[str]:
    return [date for date in dates if not daily_agg_partition_path(table_name, date).exists()]


def missing_named_daily_agg_dates(
    table_columns: dict[str, list[str]],
    dates: list[str],
) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    for table_name in table_columns:
        table_missing = missing_daily_agg_dates(table_name, dates)
        if table_missing:
            missing[table_name] = table_missing
    return missing


def has_daily_agg(table_name: str, dates: list[str]) -> bool:
    return not missing_daily_agg_dates(table_name, dates)


def load_daily_agg_lazy(
    table_name: str,
    dates: list[str],
    columns: list[str] | None = None,
) -> pl.LazyFrame:
    scan = pl.scan_parquet([str(path) for path in build_daily_agg_paths(table_name, dates)])
    if columns:
        scan = scan.select(list(dict.fromkeys(columns)))
    return scan


def build_daily_agg_cache_loader(default_columns: dict[str, list[str]] | None = None):
    column_map = dict(default_columns or {})

    def _load(
        table_name: str,
        dates: list[str],
        columns: list[str] | None = None,
    ) -> pl.LazyFrame:
        selected = columns if columns is not None else column_map.get(table_name)
        return load_daily_agg_lazy(table_name, dates, selected)

    return _load
