"""Export fixed forward-return labels for a full verified year."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.pre_eval import LABEL_NAME, build_close_like_frame, build_forward_return_labels
from factor_defs.change_support import collect_daily_frames_from_loader
from harness.daily_agg import load_daily_agg_lazy, missing_daily_agg_dates
from harness.instrument_universe import (
    DEFAULT_SOURCE_INSTRUMENT_UNIVERSE,
    DEFAULT_TARGET_INSTRUMENT_UNIVERSE,
    UNIVERSE_FILTER_VERSION,
)
from harness.verified_reader import available_dates, load_verified_lazy, next_available_dates

RUN_ROOT = ROOT / "runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export shared forward-return labels for a verified year.")
    parser.add_argument("--year", required=True, help="Verified year like 2026.")
    parser.add_argument(
        "--target-instrument-universe",
        default="stock_research_candidate",
        help="Target instrument universe label, defaulting to the stock research candidate lane.",
    )
    parser.add_argument("--notes", default="", help="Short export note.")
    return parser.parse_args()


def export_forward_labels(
    *,
    year: str,
    target_instrument_universe: str = "stock_research_candidate",
    notes: str = "",
) -> tuple[str, dict[str, object], Path]:
    dates = available_dates("verified_trades", year)
    next_map = next_available_dates("verified_trades", dates, step=1)
    label_dates = sorted(set(dates) | set(next_map.values()))
    if not missing_daily_agg_dates("verified_trades_daily", label_dates):
        close_like = (
            load_daily_agg_lazy(
                "verified_trades_daily",
                label_dates,
                ["date", "instrument_key", "close_like_price"],
                target_instrument_universe=target_instrument_universe,
            )
            .collect()
            .sort(["date", "instrument_key"])
        )
    else:
        close_like = collect_daily_frames_from_loader(
            table_loader=lambda load_dates, columns: load_verified_lazy(
                "verified_trades",
                load_dates,
                columns,
                target_instrument_universe=target_instrument_universe,
            ),
            source_columns=["date", "source_file", "Time", "Price", "row_num_in_file"],
            daily_frame_builder=build_close_like_frame,
            dates=label_dates,
        )
    labels_df = build_forward_return_labels(close_like, next_date_map=next_map, label_name=LABEL_NAME)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    export_id = f"labels_{year}_{stamp}"
    run_dir = RUN_ROOT / export_id
    run_dir.mkdir(parents=True, exist_ok=True)
    labels_path = run_dir / "forward_labels.parquet"
    summary_path = run_dir / "labels_summary.json"

    labels_df.write_parquet(labels_path)
    payload = {
        "export_id": export_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "year": year,
        "label_name": LABEL_NAME,
        "target_instrument_universe": target_instrument_universe,
        "source_instrument_universe": DEFAULT_SOURCE_INSTRUMENT_UNIVERSE,
        "contains_cross_security_source": False,
        "universe_filter_version": UNIVERSE_FILTER_VERSION,
        "dates": dates,
        "date_count": len(dates),
        "row_count": labels_df.height,
        "columns": labels_df.columns,
        "labels_path": str(labels_path),
        "notes": notes,
    }
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return export_id, payload, labels_path


def main() -> int:
    args = parse_args()
    export_id, payload, _ = export_forward_labels(
        year=args.year,
        target_instrument_universe=args.target_instrument_universe,
        notes=args.notes,
    )
    print(
        f"{export_id} year={payload['year']} date_count={payload['date_count']} "
        f"row_count={payload['row_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
