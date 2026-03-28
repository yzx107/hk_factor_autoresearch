"""Minimal autoresearch-style harness runner for Phase A."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest_engine.fixed_engine import load_baseline_config
from gatekeeper.gate_a_data import evaluate_card, load_research_card
DEFAULT_CONFIG = ROOT / "configs" / "baseline_phase_a.toml"
DEFAULT_LOG = ROOT / "registry" / "experiment_log.tsv"
DEFAULT_LINEAGE = ROOT / "registry" / "lineage.json"
DEFAULT_RUN_ROOT = ROOT / "runs"


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    created_at: str
    owner: str
    factor_name: str
    card_path: str
    config_version: str
    harness_version: str
    gate_a_decision: str
    result_summary: str
    status: str
    parent_experiment_id: str
    run_dir: str
    notes: str


def slugify(text: str) -> str:
    value = text.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "experiment"


def build_record(
    *,
    card_path: Path,
    factor_name: str,
    owner: str,
    notes: str,
    parent_experiment_id: str,
    config_path: Path = DEFAULT_CONFIG,
    run_root: Path = DEFAULT_RUN_ROOT,
) -> tuple[ExperimentRecord, dict[str, Any]]:
    config = load_baseline_config(config_path)
    card = load_research_card(card_path)
    gate = evaluate_card(card_path)
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    experiment_id = f"exp_{timestamp}_{slugify(card['card_id'])}"
    run_dir = run_root / experiment_id
    run_dir.mkdir(parents=True, exist_ok=True)

    if gate.decision == "pass":
        status = "keep"
    elif gate.decision == "allow_with_caveat":
        status = "manual_review"
    else:
        status = "discard"

    result_summary = "; ".join(gate.reasons[:3])
    if len(gate.reasons) > 3:
        result_summary += "; ..."

    record = ExperimentRecord(
        experiment_id=experiment_id,
        created_at=now.isoformat(),
        owner=owner,
        factor_name=factor_name,
        card_path=str(card_path),
        config_version=config.version,
        harness_version=config.harness_version,
        gate_a_decision=gate.decision,
        result_summary=result_summary,
        status=status,
        parent_experiment_id=parent_experiment_id,
        run_dir=str(run_dir),
        notes=notes,
    )

    artifact = {
        "record": asdict(record),
        "card_id": card["card_id"],
        "card_name": card["name"],
        "years": card["years"],
        "universe": card["universe"],
        "required_fields": card["required_fields"],
        "gate_a": gate.as_dict(),
    }
    (run_dir / "result.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return record, artifact


def append_experiment_log(record: ExperimentRecord, log_path: Path = DEFAULT_LOG) -> None:
    with log_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                record.experiment_id,
                record.created_at,
                record.owner,
                record.factor_name,
                record.card_path,
                record.config_version,
                record.harness_version,
                record.gate_a_decision,
                record.result_summary,
                record.status,
                record.parent_experiment_id,
                record.run_dir,
                record.notes,
            ]
        )


def append_lineage(record: ExperimentRecord, artifact: dict[str, Any], lineage_path: Path = DEFAULT_LINEAGE) -> None:
    payload = json.loads(lineage_path.read_text(encoding="utf-8"))
    payload.setdefault("experiments", []).append(
        {
            "experiment_id": record.experiment_id,
            "parent_experiment_id": record.parent_experiment_id,
            "factor_name": record.factor_name,
            "card_path": record.card_path,
            "gate_a_decision": record.gate_a_decision,
            "status": record.status,
            "run_dir": record.run_dir,
            "card_id": artifact["card_id"],
        }
    )
    lineage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_experiment(
    *,
    card_path: Path,
    factor_name: str,
    owner: str,
    notes: str,
    parent_experiment_id: str,
    config_path: Path = DEFAULT_CONFIG,
    log_path: Path = DEFAULT_LOG,
    lineage_path: Path = DEFAULT_LINEAGE,
    run_root: Path = DEFAULT_RUN_ROOT,
) -> ExperimentRecord:
    record, artifact = build_record(
        card_path=card_path,
        factor_name=factor_name,
        owner=owner,
        notes=notes,
        parent_experiment_id=parent_experiment_id,
        config_path=config_path,
        run_root=run_root,
    )
    append_experiment_log(record, log_path)
    append_lineage(record, artifact, lineage_path)
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one Phase A harness experiment.")
    parser.add_argument("--card", required=True, help="Research card path.")
    parser.add_argument("--factor", required=True, help="Factor name for registry logging.")
    parser.add_argument("--owner", default="agent", help="Experiment owner.")
    parser.add_argument("--notes", default="", help="Short registry note.")
    parser.add_argument("--parent", default="", help="Optional parent experiment id.")
    parser.add_argument("--verbose", action="store_true", help="Emit full JSON instead of a compact line.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    record = run_experiment(
        card_path=ROOT / args.card,
        factor_name=args.factor,
        owner=args.owner,
        notes=args.notes,
        parent_experiment_id=args.parent,
    )
    if args.verbose:
        print(json.dumps(asdict(record), indent=2))
    else:
        print(
            f"{record.experiment_id} "
            f"decision={record.gate_a_decision} "
            f"status={record.status} "
            f"factor={record.factor_name}"
        )
    return 0 if record.gate_a_decision != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
