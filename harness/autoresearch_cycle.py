"""Run a fixed Phase A autoresearch cycle across configured candidates."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import itertools
from pathlib import Path
import sys
import tomllib
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.compare_factors import COMPARISON_LOG, run_factor_comparison
from harness.run_pre_eval import PRE_EVAL_LOG, run_pre_eval_for_factor
from harness.run_verified_factor import run_verified_factor_experiment
from harness.scoreboard import build_scoreboard
from harness.status import read_experiment_log

DEFAULT_CONFIG = ROOT / "configs" / "autoresearch_phase_a.toml"
CYCLE_LOG = ROOT / "registry" / "autoresearch_cycle_log.tsv"
RUN_ROOT = ROOT / "runs"


@dataclass(frozen=True)
class CandidateSpec:
    factor_name: str
    card_path: Path
    module_name: str
    transform_name: str


@dataclass(frozen=True)
class SelectionPolicy:
    min_abs_rank_ic_keep: float
    min_abs_rank_ic_review: float
    min_normalized_mi_keep: float
    min_normalized_mi_review: float
    max_mean_abs_peer_corr: float


@dataclass(frozen=True)
class CycleConfig:
    version: str
    name: str
    owner: str
    anchor_dates: tuple[str, ...]
    selection: SelectionPolicy
    candidates: tuple[CandidateSpec, ...]


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_cycle_config(path: Path = DEFAULT_CONFIG) -> CycleConfig:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    selection = raw["selection"]
    candidates = tuple(
        CandidateSpec(
            factor_name=str(item["factor"]),
            card_path=ROOT / str(item["card"]),
            module_name=str(item.get("module", item["factor"])),
            transform_name=str(item.get("transform", "level")),
        )
        for item in raw["candidates"]
    )
    return CycleConfig(
        version=str(raw["version"]),
        name=str(raw["name"]),
        owner=str(raw["owner"]),
        anchor_dates=tuple(str(item) for item in raw["anchor_dates"]),
        selection=SelectionPolicy(
            min_abs_rank_ic_keep=float(selection["min_abs_rank_ic_keep"]),
            min_abs_rank_ic_review=float(selection["min_abs_rank_ic_review"]),
            min_normalized_mi_keep=float(selection["min_normalized_mi_keep"]),
            min_normalized_mi_review=float(selection["min_normalized_mi_review"]),
            max_mean_abs_peer_corr=float(selection["max_mean_abs_peer_corr"]),
        ),
        candidates=candidates,
    )


def ensure_cycle_log(path: Path = CYCLE_LOG) -> None:
    if path.exists():
        return
    path.write_text(
        "cycle_id\tcreated_at\tconfig_version\tfactor_count\texperiment_count\tpre_eval_count\t"
        "comparison_count\tscoreboard_id\tbest_factor\tbest_action\tsummary_path\tnotes\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_experiment_for_factor(entries: list[dict[str, str]], factor_name: str) -> dict[str, str] | None:
    for entry in reversed(entries):
        summary_path = Path(entry["run_dir"]) / "data_run_summary.json"
        if entry["factor_name"] == factor_name and summary_path.exists():
            return entry
    return None


def _matching_run(entry: dict[str, str] | None, *, card_path: Path, anchor_dates: tuple[str, ...]) -> bool:
    if not entry:
        return False
    if Path(entry["card_path"]) != card_path:
        return False
    summary_path = Path(entry["run_dir"]) / "data_run_summary.json"
    if not summary_path.exists():
        return False
    summary = _load_json(summary_path)
    return list(anchor_dates) == [str(date) for date in summary.get("dates", [])]


def _latest_pre_eval_for_experiment(experiment_id: str) -> dict[str, str] | None:
    entries = _read_tsv(PRE_EVAL_LOG)
    for entry in reversed(entries):
        if entry["experiment_id"] == experiment_id:
            return entry
    return None


def _latest_comparison(
    left_experiment_id: str,
    right_experiment_id: str,
) -> dict[str, str] | None:
    entries = _read_tsv(COMPARISON_LOG)
    targets = {left_experiment_id, right_experiment_id}
    for entry in reversed(entries):
        pair = {entry["left_experiment_id"], entry["right_experiment_id"]}
        if pair == targets:
            return entry
    return None


def _recommendation(row: dict[str, Any], policy: SelectionPolicy) -> tuple[str, str]:
    abs_ic = row["mean_abs_rank_ic"]
    signed_ic = row["mean_rank_ic"]
    normalized_mi = row.get("mean_normalized_mutual_info")
    mean_corr = float(row["mean_abs_peer_corr"])
    strong_linear = abs_ic is not None and float(abs_ic) >= policy.min_abs_rank_ic_keep
    review_linear = abs_ic is not None and float(abs_ic) >= policy.min_abs_rank_ic_review
    strong_nonlinear = normalized_mi is not None and float(normalized_mi) >= policy.min_normalized_mi_keep
    review_nonlinear = normalized_mi is not None and float(normalized_mi) >= policy.min_normalized_mi_review

    if abs_ic is None and normalized_mi is None:
        return "missing_pre_eval", "No pre-eval summary is available for this factor."
    if strong_linear and signed_ic is not None and float(signed_ic) < 0:
        return "consider_inverse", "Signed rank IC is negative while absolute IC clears the keep threshold."
    if (strong_linear or strong_nonlinear) and mean_corr <= policy.max_mean_abs_peer_corr:
        reason = (
            "Non-linear dependence clears the fixed MI keep threshold without looking crowded."
            if strong_nonlinear and not strong_linear
            else "Absolute rank IC or MI clears the keep threshold without looking crowded."
        )
        return "keep_candidate", reason
    if strong_linear or strong_nonlinear:
        return "keep_but_crowded", "Signal is strong on IC or MI but peer correlation is elevated."
    if review_linear or review_nonlinear:
        reason = (
            "Signal is above the MI review floor but below the keep threshold."
            if review_nonlinear and not review_linear
            else "Signal is above the review floor but below the keep threshold."
        )
        return "monitor", reason
    return "discard_candidate", "Absolute rank IC stays below the fixed review floor."


def _render_report(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Autoresearch Cycle")
    lines.append("")
    lines.append(f"- cycle_id: `{payload['cycle_id']}`")
    lines.append(f"- config_version: `{payload['config_version']}`")
    lines.append(f"- scoreboard_id: `{payload['scoreboard']['scoreboard_id']}`")
    lines.append(f"- factor_count: `{payload['factor_count']}`")
    lines.append("")
    lines.append("## Candidate Actions")
    lines.append("")
    for item in payload["recommendations"]:
        lines.append(
            "- "
            f"`{item['factor_name']}` action=`{item['action']}` "
            f"mean_rank_ic=`{item['mean_rank_ic']}` "
            f"mean_abs_rank_ic=`{item['mean_abs_rank_ic']}` "
            f"mean_nmi=`{item['mean_normalized_mutual_info']}` "
            f"peer_corr=`{item['mean_abs_peer_corr']}`"
        )
    lines.append("")
    lines.append("## Inventory")
    lines.append("")
    for item in payload["inventory"]:
        lines.append(
            "- "
            f"`{item['factor_name']}` "
            f"experiment=`{item['experiment_id']}` "
            f"experiment_mode=`{item['experiment_mode']}` "
            f"pre_eval_mode=`{item['pre_eval_mode']}`"
        )
    return "\n".join(lines) + "\n"


def append_cycle_log(
    *,
    cycle_id: str,
    created_at: str,
    config_version: str,
    factor_count: int,
    experiment_count: int,
    pre_eval_count: int,
    comparison_count: int,
    scoreboard_id: str,
    best_factor: str,
    best_action: str,
    summary_path: Path,
    notes: str,
    path: Path = CYCLE_LOG,
) -> None:
    ensure_cycle_log(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                cycle_id,
                created_at,
                config_version,
                factor_count,
                experiment_count,
                pre_eval_count,
                comparison_count,
                scoreboard_id,
                best_factor,
                best_action,
                str(summary_path),
                notes,
            ]
        )


def run_autoresearch_cycle(
    *,
    config_path: Path = DEFAULT_CONFIG,
    owner: str = "",
    notes: str = "",
    reuse_latest: bool = True,
) -> tuple[str, dict[str, Any], Path]:
    config = load_cycle_config(config_path)
    resolved_owner = owner or config.owner
    experiment_entries = read_experiment_log()
    inventory: list[dict[str, Any]] = []

    for candidate in config.candidates:
        latest = _latest_experiment_for_factor(experiment_entries, candidate.factor_name)
        if reuse_latest and _matching_run(latest, card_path=candidate.card_path, anchor_dates=config.anchor_dates):
            experiment_entry = latest
            experiment_mode = "reused"
        else:
            record, summary = run_verified_factor_experiment(
                card_path=candidate.card_path,
                factor_name=candidate.factor_name,
                module_name=candidate.module_name,
                transform_name=candidate.transform_name,
                dates=list(config.anchor_dates),
                owner=resolved_owner,
                notes="autoresearch cycle verified run",
            )
            experiment_entry = {
                "experiment_id": record.experiment_id,
                "factor_name": record.factor_name,
                "card_path": record.card_path,
                "run_dir": record.run_dir,
            }
            experiment_mode = "new"
            if summary is None:
                raise RuntimeError(f"Failed to materialize factor `{candidate.factor_name}` inside cycle.")

        pre_eval_entry = _latest_pre_eval_for_experiment(experiment_entry["experiment_id"])
        if reuse_latest and pre_eval_entry:
            pre_eval_mode = "reused"
        else:
            _, pre_eval_payload, pre_eval_path = run_pre_eval_for_factor(
                factor_name=candidate.factor_name,
                experiment_id=experiment_entry["experiment_id"],
                notes="autoresearch cycle pre-eval",
            )
            pre_eval_entry = {
                "pre_eval_id": pre_eval_payload["pre_eval_id"],
                "summary_path": str(pre_eval_path),
            }
            pre_eval_mode = "new"

        inventory.append(
            {
                "factor_name": candidate.factor_name,
                "card_path": str(candidate.card_path),
                "experiment_id": experiment_entry["experiment_id"],
                "experiment_mode": experiment_mode,
                "pre_eval_id": pre_eval_entry["pre_eval_id"],
                "pre_eval_mode": pre_eval_mode,
            }
        )

    comparisons: list[dict[str, str]] = []
    for left, right in itertools.combinations(inventory, 2):
        comparison_entry = _latest_comparison(left["experiment_id"], right["experiment_id"])
        if reuse_latest and comparison_entry:
            comparisons.append(comparison_entry)
            continue
        _, comparison_payload, comparison_path = run_factor_comparison(
            left_factor=left["factor_name"],
            right_factor=right["factor_name"],
            left_experiment=left["experiment_id"],
            right_experiment=right["experiment_id"],
            notes="autoresearch cycle comparison",
        )
        comparisons.append(
            {
                "comparison_id": comparison_payload["comparison_id"],
                "summary_path": str(comparison_path),
            }
        )

    scoreboard_id, scoreboard_payload, scoreboard_path = build_scoreboard(
        [candidate.factor_name for candidate in config.candidates],
        notes=f"autoresearch cycle {config.version}",
    )
    recommendations: list[dict[str, Any]] = []
    for row in scoreboard_payload["factor_board"]:
        action, reason = _recommendation(row, config.selection)
        recommendations.append(
            {
                "factor_name": row["factor_name"],
                "action": action,
                "reason": reason,
                "mean_rank_ic": row["mean_rank_ic"],
                "mean_abs_rank_ic": row["mean_abs_rank_ic"],
                "mean_normalized_mutual_info": row.get("mean_normalized_mutual_info"),
                "mean_abs_peer_corr": row["mean_abs_peer_corr"],
            }
        )

    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cycle_id = f"auto_{stamp}"
    run_dir = RUN_ROOT / cycle_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "cycle_summary.json"
    report_path = run_dir / "cycle_report.md"
    best = recommendations[0] if recommendations else {"factor_name": "none", "action": "none"}
    payload = {
        "cycle_id": cycle_id,
        "created_at": created_at,
        "config_version": config.version,
        "config_name": config.name,
        "owner": resolved_owner,
        "notes": notes,
        "anchor_dates": list(config.anchor_dates),
        "factor_count": len(config.candidates),
        "inventory": inventory,
        "comparison_count": len(comparisons),
        "scoreboard": {
            "scoreboard_id": scoreboard_id,
            "summary_path": str(scoreboard_path),
            "factor_board": scoreboard_payload["factor_board"],
        },
        "recommendations": recommendations,
    }
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    report_path.write_text(_render_report(payload), encoding="utf-8")
    append_cycle_log(
        cycle_id=cycle_id,
        created_at=created_at,
        config_version=config.version,
        factor_count=len(config.candidates),
        experiment_count=len(inventory),
        pre_eval_count=len(inventory),
        comparison_count=len(comparisons),
        scoreboard_id=scoreboard_id,
        best_factor=best["factor_name"],
        best_action=best["action"],
        summary_path=summary_path,
        notes=notes or f"autoresearch cycle {config.version}",
    )
    return cycle_id, payload, summary_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a fixed Phase A autoresearch cycle.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Cycle config TOML path.")
    parser.add_argument("--owner", default="", help="Optional owner override.")
    parser.add_argument("--notes", default="", help="Short cycle note.")
    parser.add_argument("--no-reuse", action="store_true", help="Force fresh runs instead of reusing latest artifacts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cycle_id, payload, _ = run_autoresearch_cycle(
        config_path=ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config),
        owner=args.owner,
        notes=args.notes,
        reuse_latest=not args.no_reuse,
    )
    best = payload["recommendations"][0] if payload["recommendations"] else {"factor_name": "none", "action": "none"}
    print(
        f"{cycle_id} scoreboard={payload['scoreboard']['scoreboard_id']} "
        f"best_factor={best['factor_name']} action={best['action']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
