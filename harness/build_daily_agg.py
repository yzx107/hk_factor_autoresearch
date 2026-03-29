"""Build low-memory daily aggregate cache tables from upstream verified partitions."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Callable

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.daily_agg import DAILY_AGG_ROOT, daily_agg_partition_path
from harness.verified_reader import available_dates, load_verified_lazy


SOURCE_TABLE_BY_DAILY_TABLE = {
    "verified_trades_daily": "verified_trades",
    "verified_orders_daily": "verified_orders",
}

SOURCE_COLUMNS_BY_DAILY_TABLE = {
    "verified_trades_daily": ["date", "source_file", "Time", "Price", "Volume", "row_num_in_file"],
    "verified_orders_daily": ["date", "source_file", "OrderId", "Price", "Volume"],
}


def build_trades_daily_agg(trades: pl.LazyFrame) -> pl.DataFrame:
    turnover = (pl.col("Price") * pl.col("Volume")).sum().alias("turnover")
    share_volume = pl.col("Volume").sum().alias("share_volume")
    trade_count = pl.len().alias("trade_count")
    avg_trade_size = pl.col("Volume").mean().alias("avg_trade_size")
    return (
        trades.sort(["date", "instrument_key", "Time", "row_num_in_file"])
        .group_by(["date", "instrument_key"], maintain_order=True)
        .agg([trade_count, turnover, share_volume, avg_trade_size, pl.col("Price").last().alias("close_like_price")])
        .filter(pl.col("share_volume") > 0)
        .with_columns(
            [
                (pl.col("turnover") / pl.col("share_volume")).alias("vwap"),
                pl.lit("file_derived_instrument_key").alias("instrument_key_source"),
            ]
        )
        .sort(["date", "instrument_key"])
        .collect()
    )


def build_orders_daily_agg(orders: pl.LazyFrame) -> pl.DataFrame:
    event_count = pl.len().alias("order_event_count")
    unique_orders = pl.col("OrderId").n_unique().alias("unique_order_ids")
    total_order_notional = (pl.col("Price") * pl.col("Volume")).sum().alias("total_order_notional")
    return (
        orders.group_by(["date", "instrument_key"])
        .agg([event_count, unique_orders, total_order_notional])
        .with_columns(
            [
                (pl.col("order_event_count") / pl.col("unique_order_ids")).alias("churn_ratio"),
                pl.lit("file_derived_instrument_key").alias("instrument_key_source"),
            ]
        )
        .sort(["date", "instrument_key"])
        .collect()
    )


BUILDERS: dict[str, Callable[[pl.LazyFrame], pl.DataFrame]] = {
    "verified_trades_daily": build_trades_daily_agg,
    "verified_orders_daily": build_orders_daily_agg,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build daily aggregate cache tables.")
    parser.add_argument(
        "--table",
        required=True,
        choices=["verified_trades_daily", "verified_orders_daily", "all"],
        help="Daily aggregate table to build.",
    )
    parser.add_argument("--year", required=True, help="Verified year like 2026.")
    parser.add_argument("--dates", nargs="*", default=[], help="Optional explicit dates to build.")
    parser.add_argument("--date-from", default="", help="Optional lower date bound like 2026-01-02.")
    parser.add_argument("--date-to", default="", help="Optional upper date bound like 2026-01-30.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing cache files.")
    parser.add_argument("--notes", default="", help="Short build note.")
    return parser.parse_args()


def _resolve_dates(
    daily_table: str,
    year: str,
    explicit_dates: list[str],
    *,
    date_from: str,
    date_to: str,
) -> list[str]:
    if explicit_dates:
        return explicit_dates
    source_table = SOURCE_TABLE_BY_DAILY_TABLE[daily_table]
    dates = available_dates(source_table, year)
    if date_from:
        dates = [date for date in dates if date >= date_from]
    if date_to:
        dates = [date for date in dates if date <= date_to]
    return dates


def build_daily_agg_for_date(
    *,
    daily_table: str,
    date: str,
    force: bool = False,
) -> dict[str, object]:
    path = daily_agg_partition_path(daily_table, date)
    if path.exists() and not force:
        cached = pl.read_parquet(path)
        return {
            "date": date,
            "table_name": daily_table,
            "status": "skipped_existing",
            "row_count": cached.height,
            "path": str(path),
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    source_table = SOURCE_TABLE_BY_DAILY_TABLE[daily_table]
    source_columns = SOURCE_COLUMNS_BY_DAILY_TABLE[daily_table]
    builder = BUILDERS[daily_table]
    lazy_frame = load_verified_lazy(source_table, [date], source_columns)
    frame = builder(lazy_frame)
    frame.write_parquet(path)
    return {
        "date": date,
        "table_name": daily_table,
        "status": "built",
        "row_count": frame.height,
        "path": str(path),
    }


def build_daily_agg_table(
    *,
    daily_table: str,
    year: str,
    dates: list[str],
    force: bool = False,
    notes: str = "",
) -> tuple[str, dict[str, object], Path]:
    results = [build_daily_agg_for_date(daily_table=daily_table, date=date, force=force) for date in dates]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    build_id = f"daily_agg_{daily_table}_{year}_{stamp}"
    summary_dir = DAILY_AGG_ROOT / "builds" / build_id
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / "build_summary.json"
    payload = {
        "build_id": build_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "table_name": daily_table,
        "year": year,
        "date_count": len(dates),
        "built_count": sum(1 for item in results if item["status"] == "built"),
        "skipped_count": sum(1 for item in results if item["status"] == "skipped_existing"),
        "notes": notes,
        "results": results,
    }
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return build_id, payload, summary_path


def main() -> int:
    args = parse_args()
    tables = (
        ["verified_trades_daily", "verified_orders_daily"]
        if args.table == "all"
        else [args.table]
    )
    outputs: list[tuple[str, dict[str, object], Path]] = []
    for table_name in tables:
        dates = _resolve_dates(
            table_name,
            args.year,
            args.dates,
            date_from=args.date_from,
            date_to=args.date_to,
        )
        outputs.append(
            build_daily_agg_table(
                daily_table=table_name,
                year=args.year,
                dates=dates,
                force=args.force,
                notes=args.notes,
            )
        )
    for build_id, payload, _ in outputs:
        print(
            f"{build_id} table={payload['table_name']} "
            f"date_count={payload['date_count']} built={payload['built_count']} skipped={payload['skipped_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
