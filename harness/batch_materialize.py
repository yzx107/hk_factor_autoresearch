"""Batch materialize configured candidates over a full verified year."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.autoresearch_cycle import DEFAULT_CONFIG, load_cycle_config
from harness.run_verified_factor import run_verified_factor_experiment
from harness.verified_reader import available_dates

RUN_ROOT = ROOT / "runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch materialize full-year factor outputs.")
    parser.add_argument("--year", required=True, help="Verified year like 2026.")
    parser.add_argument(
        "--table",
        default="",
        choices=["", "verified_trades", "verified_orders"],
        help="Optional table lane filter.",
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Candidate config TOML path.")
    parser.add_argument("--owner", default="agent", help="Owner for experiment records.")
    parser.add_argument("--notes", default="", help="Short batch note.")
    return parser.parse_args()


def run_batch_materialize(
    *,
    year: str,
    table_filter: str = "",
    config_path: Path = DEFAULT_CONFIG,
    owner: str = "agent",
    notes: str = "",
) -> tuple[str, dict[str, Any], Path]:
    config = load_cycle_config(config_path)
    candidates: list[dict[str, str]] = []
    for candidate in config.candidates:
        module_name = candidate.factor_name
        module = __import__(f"factor_defs.{module_name}", fromlist=["dummy"])
        table_name = getattr(module, "INPUT_TABLE")
        if table_filter and table_name != table_filter:
            continue
        candidates.append(
            {
                "factor_name": module_name,
                "card_path": str(candidate.card_path),
                "table_name": table_name,
            }
        )

    results: list[dict[str, Any]] = []
    for candidate in candidates:
        dates = available_dates(candidate["table_name"], year)
        try:
            record, summary = run_verified_factor_experiment(
                card_path=Path(candidate["card_path"]),
                factor_name=candidate["factor_name"],
                dates=dates,
                owner=owner,
                notes=notes or f"full-year materialize {year}",
            )
            results.append(
                {
                    "factor_name": candidate["factor_name"],
                    "table_name": candidate["table_name"],
                    "experiment_id": record.experiment_id,
                    "run_dir": record.run_dir,
                    "gate_a_decision": record.gate_a_decision,
                    "status": record.status,
                    "dates": dates,
                    "output_rows": None if summary is None else summary["output_rows"],
                    "factor_output": "" if summary is None else summary["artifacts"]["factor_output"],
                    "error": "",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "factor_name": candidate["factor_name"],
                    "table_name": candidate["table_name"],
                    "experiment_id": "",
                    "run_dir": "",
                    "gate_a_decision": "error",
                    "status": "error",
                    "dates": dates,
                    "output_rows": None,
                    "factor_output": "",
                    "error": str(exc),
                }
            )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_id = f"materialize_{year}_{table_filter or 'all'}_{stamp}"
    run_dir = RUN_ROOT / batch_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "materialize_manifest.json"
    payload = {
        "batch_id": batch_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "year": year,
        "table_filter": table_filter,
        "candidate_count": len(results),
        "notes": notes,
        "results": results,
    }
    manifest_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return batch_id, payload, manifest_path


def main() -> int:
    args = parse_args()
    config_path = ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config)
    batch_id, payload, _ = run_batch_materialize(
        year=args.year,
        table_filter=args.table,
        config_path=config_path,
        owner=args.owner,
        notes=args.notes,
    )
    print(
        f"{batch_id} year={payload['year']} table_filter={payload['table_filter'] or 'all'} "
        f"candidate_count={payload['candidate_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
