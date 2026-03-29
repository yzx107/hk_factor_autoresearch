"""Read-only loader for upstream verified layer partitions."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import polars as pl

VERIFIED_ROOT = Path("/Volumes/Data/港股Tick数据/verified")
VALID_TABLES = {"verified_trades", "verified_orders"}


def _year_from_date(date: str) -> str:
    return date.split("-", 1)[0]


def build_partition_paths(table_name: str, dates: list[str]) -> list[Path]:
    if table_name not in VALID_TABLES:
        raise ValueError(f"Unsupported verified table `{table_name}`.")
    if not dates:
        raise ValueError("At least one date is required.")

    paths: list[Path] = []
    for date in dates:
        path = VERIFIED_ROOT / table_name / f"year={_year_from_date(date)}" / f"date={date}" / "part-00000.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Verified partition not found: {path}")
        paths.append(path)
    return paths


def verified_manifest_path(year: str) -> Path:
    return VERIFIED_ROOT / "manifests" / f"year={year}" / "summary.json"


def load_verified_manifest(year: str) -> dict[str, Any]:
    path = verified_manifest_path(year)
    if not path.exists():
        raise FileNotFoundError(f"Verified manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def available_dates(table_name: str, year: str) -> list[str]:
    dates: set[str] = set()

    try:
        manifest = load_verified_manifest(year)
        table_payload = manifest.get("tables", {}).get(table_name)
        if table_payload:
            dates.update(str(date) for date in table_payload.get("dates", []))
    except FileNotFoundError:
        pass

    table_root = VERIFIED_ROOT / table_name / f"year={year}"
    if table_root.exists():
        for path in table_root.iterdir():
            if path.is_dir() and path.name.startswith("date="):
                dates.add(path.name.split("=", 1)[1])

    if not dates:
        raise ValueError(f"No verified dates found for table `{table_name}` in year `{year}`.")
    return sorted(dates)


def next_available_dates(
    table_name: str,
    dates: list[str],
    *,
    step: int = 1,
) -> dict[str, str]:
    if step < 1:
        raise ValueError("step must be >= 1")
    if not dates:
        return {}

    per_year: dict[str, list[str]] = {}
    for date in dates:
        per_year.setdefault(_year_from_date(date), []).append(date)

    mapping: dict[str, str] = {}
    for year, year_dates in per_year.items():
        available = available_dates(table_name, year)
        index = {date: idx for idx, date in enumerate(available)}
        for date in year_dates:
            pos = index.get(date)
            if pos is None:
                continue
            next_pos = pos + step
            if next_pos < len(available):
                mapping[date] = available[next_pos]
    return mapping


def instrument_key_expr() -> pl.Expr:
    return pl.col("source_file").str.extract(r"([^/]+)\.csv$", 1).alias("instrument_key")


def load_verified_lazy(
    table_name: str,
    dates: list[str],
    columns: list[str] | None = None,
) -> pl.LazyFrame:
    paths = build_partition_paths(table_name, dates)
    scan = pl.scan_parquet([str(path) for path in paths])
    if columns:
        base_columns = list(dict.fromkeys(columns))
        scan = scan.select(base_columns)
    return scan.with_columns(instrument_key_expr())


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    if len(args) < 2:
        print("usage: python3 harness/verified_reader.py <table> <date> [<date>...]")
        return 1
    table_name, *dates = args
    frame = load_verified_lazy(table_name, dates).limit(5).collect()
    print(frame)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
