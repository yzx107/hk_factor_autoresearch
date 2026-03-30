"""Run the fixed Gate B statistical validity gate for Phase A factors."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gates.gate_b_stats import evaluate_gate_b

PRE_EVAL_LOG = ROOT / "registry" / "pre_eval_log.tsv"
GATE_B_LOG = ROOT / "registry" / "gate_b_log.tsv"
RUN_ROOT = ROOT / "runs"


def ensure_gate_b_log(path: Path = GATE_B_LOG) -> None:
    if path.exists():
        return
    path.write_text(
        "gate_b_id\tcreated_at\tpre_eval_id\texperiment_id\tfactor_name\tdecision\t"
        "direction_hint\tmean_abs_rank_ic\tmean_normalized_mutual_info\tmean_coverage_ratio\t"
        "sign_consistency\tsummary_path\tnotes\n",
        encoding="utf-8",
    )


def read_pre_eval_log(path: Path = PRE_EVAL_LOG) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader)


def _find_pre_eval(entries: list[dict[str, str]], factor_name: str, pre_eval_id: str) -> dict[str, str]:
    if pre_eval_id:
        for entry in entries:
            if entry["pre_eval_id"] == pre_eval_id:
                if factor_name and entry["factor_name"] != factor_name:
                    raise ValueError(
                        f"Pre-eval `{pre_eval_id}` belongs to `{entry['factor_name']}`, not `{factor_name}`."
                    )
                return entry
        raise ValueError(f"Pre-eval `{pre_eval_id}` not found.")

    for entry in reversed(entries):
        if entry["factor_name"] == factor_name:
            return entry
    raise ValueError(f"No pre-eval found for factor `{factor_name}`.")


def _load_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing pre-eval summary `{path}`.")
    return json.loads(path.read_text(encoding="utf-8"))


def _append_gate_b_log(
    *,
    gate_b_id: str,
    created_at: str,
    pre_eval_id: str,
    experiment_id: str,
    factor_name: str,
    decision: str,
    direction_hint: str,
    metrics: dict[str, Any],
    summary_path: Path,
    notes: str,
    path: Path = GATE_B_LOG,
) -> None:
    ensure_gate_b_log(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                gate_b_id,
                created_at,
                pre_eval_id,
                experiment_id,
                factor_name,
                decision,
                direction_hint,
                metrics.get("mean_abs_rank_ic"),
                metrics.get("mean_normalized_mutual_info"),
                metrics.get("mean_coverage_ratio"),
                metrics.get("sign_consistency"),
                str(summary_path),
                notes,
            ]
        )


def run_gate_b_for_factor(
    *,
    factor_name: str,
    pre_eval_id: str = "",
    notes: str = "",
    pre_eval_log_path: Path = PRE_EVAL_LOG,
    gate_b_log_path: Path = GATE_B_LOG,
    run_root: Path = RUN_ROOT,
) -> tuple[str, dict[str, Any], Path]:
    entries = read_pre_eval_log(pre_eval_log_path)
    entry = _find_pre_eval(entries, factor_name, pre_eval_id)
    pre_eval_summary_path = Path(entry["summary_path"])
    pre_eval_summary = _load_summary(pre_eval_summary_path)
    decision_payload = evaluate_gate_b(pre_eval_summary)

    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    gate_b_id = f"gateb_{stamp}_{entry['pre_eval_id']}"
    run_dir = run_root / gate_b_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "gate_b_summary.json"

    payload = {
        "gate_b_id": gate_b_id,
        "created_at": created_at,
        "notes": notes,
        "factor_name": entry["factor_name"],
        "experiment_id": entry["experiment_id"],
        "pre_eval_id": entry["pre_eval_id"],
        "pre_eval_summary_path": str(pre_eval_summary_path),
        **decision_payload,
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _append_gate_b_log(
        gate_b_id=gate_b_id,
        created_at=created_at,
        pre_eval_id=entry["pre_eval_id"],
        experiment_id=entry["experiment_id"],
        factor_name=entry["factor_name"],
        decision=decision_payload["decision"],
        direction_hint=decision_payload["direction_hint"],
        metrics=decision_payload["metrics"],
        summary_path=summary_path,
        notes=notes,
        path=gate_b_log_path,
    )
    return gate_b_id, payload, summary_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run fixed Gate B statistical validity checks.")
    parser.add_argument("--factor", nargs="+", required=True, help="Factor name(s) to evaluate.")
    parser.add_argument("--pre-eval-id", default="", help="Optional explicit pre_eval_id for single-factor runs.")
    parser.add_argument("--notes", default="", help="Short Gate B note.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.pre_eval_id and len(args.factor) != 1:
        raise SystemExit("--pre-eval-id can only be used with a single --factor value.")

    for factor_name in args.factor:
        gate_b_id, payload, _ = run_gate_b_for_factor(
            factor_name=factor_name,
            pre_eval_id=args.pre_eval_id,
            notes=args.notes,
        )
        metrics = payload["metrics"]
        print(
            f"{gate_b_id} factor={payload['factor_name']} "
            f"decision={payload['decision']} "
            f"mean_abs_rank_ic={metrics['mean_abs_rank_ic']} "
            f"mean_nmi={metrics['mean_normalized_mutual_info']} "
            f"sign_consistency={metrics['sign_consistency']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
