"""Run a minimal event study for operator gossip cases."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.daily_agg import available_daily_agg_dates, load_daily_agg_lazy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a minimal event study on operator gossip cases.")
    parser.add_argument(
        "--cases",
        default="operator_gossip/labels/gossip_cases_template.csv",
        help="Path to the gossip ledger CSV.",
    )
    parser.add_argument(
        "--year",
        required=True,
        help="Daily agg year to load, such as 2026.",
    )
    parser.add_argument(
        "--horizons",
        nargs="*",
        type=int,
        default=[1, 3, 5, 10],
        help="Forward return horizons in trading days.",
    )
    return parser.parse_args()


def load_cases(path: Path) -> pl.DataFrame:
    frame = pl.read_csv(path, try_parse_dates=True).with_columns(
        [
            pl.col("asof_date").cast(pl.Date, strict=False),
            pl.col("ticker").cast(pl.String, strict=False).str.zfill(5),
            pl.col("operator_guess").cast(pl.String, strict=False),
            pl.col("seat_guess").cast(pl.String, strict=False),
            pl.col("style_guess").cast(pl.String, strict=False),
            pl.col("direction").cast(pl.String, strict=False),
            pl.col("confidence").cast(pl.String, strict=False),
            pl.col("expected_horizon_days").cast(pl.Int64, strict=False),
        ]
    )
    if frame.is_empty():
        raise ValueError("No gossip cases found.")
    return frame


def load_price_panel(year: str, dates: list[str]) -> pl.DataFrame:
    frame = (
        load_daily_agg_lazy("verified_trades_daily", dates, ["date", "instrument_key", "close_like_price", "turnover"])
        .collect()
        .with_columns(pl.col("instrument_key").cast(pl.String, strict=False).str.zfill(5).alias("ticker"))
        .sort(["ticker", "date"])
    )
    return frame


def enrich_forward_metrics(cases: pl.DataFrame, prices: pl.DataFrame, horizons: list[int]) -> pl.DataFrame:
    lookup = prices.select(["ticker", "date", "close_like_price"]).rename({"date": "asof_date", "close_like_price": "entry_close"})
    result = cases.join(lookup, on=["ticker", "asof_date"], how="left")

    for horizon in horizons:
        shifted = prices.select(
            [
                "ticker",
                pl.col("date").alias("asof_date"),
                pl.col("close_like_price").shift(-horizon).over("ticker").alias(f"close_tplus_{horizon}"),
            ]
        )
        result = result.join(shifted, on=["ticker", "asof_date"], how="left").with_columns(
            pl.when((pl.col("entry_close").is_not_null()) & (pl.col(f"close_tplus_{horizon}").is_not_null()) & (pl.col("entry_close") != 0))
            .then(pl.col(f"close_tplus_{horizon}") / pl.col("entry_close") - 1.0)
            .otherwise(None)
            .alias(f"fwd_return_{horizon}d")
        )
    return result


def summarize_by_bucket(frame: pl.DataFrame, horizons: list[int]) -> pl.DataFrame:
    aggregations: list[pl.Expr] = [pl.len().alias("case_count")]
    for horizon in horizons:
        aggregations.extend(
            [
                pl.col(f"fwd_return_{horizon}d").mean().alias(f"avg_fwd_return_{horizon}d"),
                pl.col(f"fwd_return_{horizon}d").median().alias(f"median_fwd_return_{horizon}d"),
                (pl.col(f"fwd_return_{horizon}d") > 0).mean().alias(f"win_rate_{horizon}d"),
            ]
        )
    return frame.group_by(["operator_guess", "style_guess", "confidence", "direction"]).agg(aggregations).sort(
        ["case_count", "avg_fwd_return_5d"], descending=[True, True]
    )


def main() -> int:
    args = parse_args()
    case_path = Path(args.cases)
    if not case_path.is_absolute():
        case_path = (ROOT / case_path).resolve()
    cases = load_cases(case_path)
    dates = available_daily_agg_dates("verified_trades_daily", args.year)
    prices = load_price_panel(args.year, dates)
    enriched = enrich_forward_metrics(cases, prices, args.horizons)
    summary = summarize_by_bucket(enriched, args.horizons)

    print("== enriched cases preview ==")
    print(enriched.head(10))
    print("== grouped summary ==")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
