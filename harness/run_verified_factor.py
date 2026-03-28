"""Run a safe Phase A factor on upstream verified partitions."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib
import json
from pathlib import Path
import sys

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gatekeeper.gate_a_data import load_research_card
from harness.run_phase_a import build_record, append_experiment_log, append_lineage
from harness.verified_reader import load_verified_lazy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a verified-layer factor on one or more dates.")
    parser.add_argument("--card", required=True, help="Research card path.")
    parser.add_argument("--factor", required=True, help="Factor module name under factor_defs/ .")
    parser.add_argument("--dates", nargs="+", required=True, help="Trading dates like 2026-03-13.")
    parser.add_argument("--owner", default="agent", help="Experiment owner.")
    parser.add_argument("--notes", default="", help="Short run note.")
    parser.add_argument("--parent", default="", help="Optional parent experiment id.")
    parser.add_argument(
        "--allow-with-caveat",
        action="store_true",
        help="Allow materialization when Gate A returns allow_with_caveat.",
    )
    return parser.parse_args()


def _load_factor_module(factor_name: str):
    return importlib.import_module(f"factor_defs.{factor_name}")


def _required_columns(card: dict[str, object]) -> list[str]:
    fields = [str(field) for field in card["required_fields"]]
    required = ["date", "source_file"] + fields
    return list(dict.fromkeys(required))


def main() -> int:
    args = parse_args()
    card_path = ROOT / args.card
    card = load_research_card(card_path)

    record, artifact = build_record(
        card_path=card_path,
        factor_name=args.factor,
        owner=args.owner,
        notes=args.notes,
        parent_experiment_id=args.parent,
    )
    append_experiment_log(record)
    append_lineage(record, artifact)

    if record.gate_a_decision == "fail":
        print(f"{record.experiment_id} decision=fail status=discard factor={args.factor}")
        return 1
    if record.gate_a_decision == "allow_with_caveat" and not args.allow_with_caveat:
        print(
            f"{record.experiment_id} decision=allow_with_caveat status=manual_review "
            f"factor={args.factor} data_run=skipped"
        )
        return 0

    module = _load_factor_module(args.factor)
    table_name = getattr(module, "INPUT_TABLE")
    lazy_frame = load_verified_lazy(table_name, args.dates, _required_columns(card))
    signal_lazy = module.compute_signal(lazy_frame)
    signal_df = signal_lazy.collect()

    run_dir = Path(record.run_dir)
    signal_path = run_dir / "factor_output.parquet"
    preview_path = run_dir / "preview.json"
    summary_path = run_dir / "data_run_summary.json"

    signal_df.write_parquet(signal_path)
    preview_rows = signal_df.head(10).to_dicts()
    preview_path.write_text(json.dumps(preview_rows, indent=2, default=str), encoding="utf-8")
    summary = {
        "experiment_id": record.experiment_id,
        "factor_name": args.factor,
        "table_name": table_name,
        "dates": args.dates,
        "input_columns": _required_columns(card),
        "output_rows": signal_df.height,
        "output_columns": signal_df.columns,
        "artifacts": {
            "factor_output": str(signal_path),
            "preview": str(preview_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(
        f"{record.experiment_id} decision={record.gate_a_decision} "
        f"status={record.status} factor={args.factor} output_rows={signal_df.height}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
