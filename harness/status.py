"""Compact project status view for harness-style progress tracking."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_LOG = ROOT / "registry" / "experiment_log.tsv"
LINEAGE_PATH = ROOT / "registry" / "lineage.json"
COMPARISON_LOG = ROOT / "registry" / "comparison_log.tsv"


@dataclass(frozen=True)
class StatusSnapshot:
    experiment_count: int
    keep_count: int
    manual_review_count: int
    discard_count: int
    latest_experiment: dict[str, Any] | None
    latest_data_run: dict[str, Any] | None
    latest_comparison: dict[str, Any] | None


def read_experiment_log(path: Path = EXPERIMENT_LOG) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader)


def read_lineage(path: Path = LINEAGE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"version": "missing", "experiments": []}
    return json.loads(path.read_text(encoding="utf-8"))


def read_comparison_log(path: Path = COMPARISON_LOG) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader)


def _latest_data_run(entries: list[dict[str, str]]) -> dict[str, Any] | None:
    for entry in reversed(entries):
        summary_path = Path(entry["run_dir"]) / "data_run_summary.json"
        if summary_path.exists():
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            return {
                "experiment_id": entry["experiment_id"],
                "factor_name": payload["factor_name"],
                "dates": payload["dates"],
                "output_rows": payload["output_rows"],
                "table_name": payload["table_name"],
                "summary_path": str(summary_path),
            }
    return None


def build_status_snapshot(entries: list[dict[str, str]]) -> StatusSnapshot:
    keep_count = sum(1 for entry in entries if entry["status"] == "keep")
    manual_review_count = sum(1 for entry in entries if entry["status"] == "manual_review")
    discard_count = sum(1 for entry in entries if entry["status"] == "discard")
    latest_experiment = entries[-1] if entries else None
    latest_data_run = _latest_data_run(entries)
    comparisons = read_comparison_log()
    latest_comparison = comparisons[-1] if comparisons else None
    return StatusSnapshot(
        experiment_count=len(entries),
        keep_count=keep_count,
        manual_review_count=manual_review_count,
        discard_count=discard_count,
        latest_experiment=latest_experiment,
        latest_data_run=latest_data_run,
        latest_comparison=latest_comparison,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show compact harness progress status.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--limit", type=int, default=5, help="Recent experiment rows to show in text mode.")
    return parser.parse_args()


def _text_status(snapshot: StatusSnapshot, entries: list[dict[str, str]], lineage: dict[str, Any], limit: int) -> str:
    lines: list[str] = []
    lines.append(
        "summary "
        f"experiments={snapshot.experiment_count} "
        f"keep={snapshot.keep_count} "
        f"manual_review={snapshot.manual_review_count} "
        f"discard={snapshot.discard_count}"
    )
    lines.append(f"lineage version={lineage.get('version', 'unknown')} nodes={len(lineage.get('experiments', []))}")
    if snapshot.latest_experiment:
        latest = snapshot.latest_experiment
        lines.append(
            "latest_experiment "
            f"id={latest['experiment_id']} "
            f"factor={latest['factor_name']} "
            f"decision={latest['gate_a_decision']} "
            f"status={latest['status']}"
        )
    if snapshot.latest_data_run:
        data_run = snapshot.latest_data_run
        lines.append(
            "latest_data_run "
            f"id={data_run['experiment_id']} "
            f"factor={data_run['factor_name']} "
            f"table={data_run['table_name']} "
            f"dates={','.join(data_run['dates'])} "
            f"output_rows={data_run['output_rows']}"
        )
    if snapshot.latest_comparison:
        comparison = snapshot.latest_comparison
        lines.append(
            "latest_comparison "
            f"id={comparison['comparison_id']} "
            f"left={comparison['left_factor']} "
            f"right={comparison['right_factor']} "
            f"common_rows={comparison['common_rows']}"
        )
    if entries:
        lines.append("recent")
        for entry in entries[-limit:]:
            lines.append(
                f"  {entry['experiment_id']} "
                f"factor={entry['factor_name']} "
                f"decision={entry['gate_a_decision']} "
                f"status={entry['status']} "
                f"notes={entry['notes']}"
            )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    entries = read_experiment_log()
    lineage = read_lineage()
    snapshot = build_status_snapshot(entries)
    comparisons = read_comparison_log()
    if args.json:
        print(
            json.dumps(
                {
                    "snapshot": {
                        "experiment_count": snapshot.experiment_count,
                        "keep_count": snapshot.keep_count,
                        "manual_review_count": snapshot.manual_review_count,
                        "discard_count": snapshot.discard_count,
                        "latest_experiment": snapshot.latest_experiment,
                        "latest_data_run": snapshot.latest_data_run,
                        "latest_comparison": snapshot.latest_comparison,
                    },
                    "lineage": lineage,
                    "comparisons": comparisons[-args.limit :],
                    "recent": entries[-args.limit :],
                },
                indent=2,
            )
        )
    else:
        print(_text_status(snapshot, entries, lineage, args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
