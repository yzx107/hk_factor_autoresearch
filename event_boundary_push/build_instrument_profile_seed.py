"""Build a fillable instrument profile seed for event_boundary_push."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from event_boundary_push._core import _preview_rows, build_event_universe_frame, load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fillable instrument_profile_csv seed for event_boundary_push.")
    parser.add_argument(
        "--config",
        default="event_boundary_push/configs/boundary_push_event_v0.toml",
        help="Path to the event module config TOML.",
    )
    parser.add_argument(
        "--output",
        default="event_boundary_push/outputs/instrument_profile_seed.csv",
        help="Path to the output CSV seed.",
    )
    parser.add_argument(
        "--included-only",
        action="store_true",
        help="Only export instruments currently included in the event universe.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config))
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (ROOT / output_path).resolve()
    summary_path = output_path.with_suffix('.summary.json')

    universe = build_event_universe_frame(config)
    if args.included_only:
        universe = universe.filter(pl.col("event_universe_included"))

    seed = universe.select(
        [
            "instrument_key",
            "ticker",
            "event_universe_included",
            "first_seen_date",
            "last_seen_date",
            "observed_days",
            pl.col("listing_date_effective").alias("listing_date_seed"),
            pl.col("listing_date_source").alias("listing_date_seed_source"),
            pl.col("float_mktcap_effective").alias("float_mktcap_seed"),
            pl.col("southbound_eligible_effective").alias("southbound_seed"),
            pl.col("southbound_source").alias("southbound_seed_source"),
            "boundary_proxy_reference_value",
            "boundary_proxy_reference_percentile",
        ]
    ).with_columns(
        [
            pl.lit(None, dtype=pl.String).alias("listing_date"),
            pl.lit(None, dtype=pl.Float64).alias("float_mktcap"),
            pl.lit(None, dtype=pl.Boolean).alias("southbound_eligible"),
            pl.lit("").alias("profile_notes"),
        ]
    ).select(
        [
            "instrument_key",
            "ticker",
            "event_universe_included",
            "listing_date",
            "float_mktcap",
            "southbound_eligible",
            "listing_date_seed",
            "listing_date_seed_source",
            "float_mktcap_seed",
            "southbound_seed",
            "southbound_seed_source",
            "first_seen_date",
            "last_seen_date",
            "observed_days",
            "boundary_proxy_reference_value",
            "boundary_proxy_reference_percentile",
            "profile_notes",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    seed.write_csv(output_path)
    payload = {
        "path": str(output_path),
        "row_count": seed.height,
        "included_only": bool(args.included_only),
        "columns": seed.columns,
        "preview": _preview_rows(seed),
        "config_path": str(config.config_path),
        "instructions": [
            "fill listing_date / float_mktcap / southbound_eligible when true values are available",
            "then point instrument_profile_csv in boundary_push_event_v0.toml to the enriched CSV",
        ],
    }
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    print(f"instrument_profile_seed rows={seed.height} output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
