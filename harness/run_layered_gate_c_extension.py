"""Extend promoted broad candidates to cached dates, then rerun Gate C."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tomllib
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.daily_agg import missing_daily_agg_dates
from harness.run_layered_gate_c import (
    DEFAULT_DECISION_LOG,
    DEFAULT_GATE_C_LOG,
    build_layered_gate_c_summary,
    select_gate_c_candidates,
)
from harness.run_verified_factor import run_verified_factor_experiment
from harness.verified_reader import available_dates, previous_available_dates

RUN_ROOT = ROOT / "runs"
DEFAULT_CONFIG = ROOT / "configs" / "autoresearch_phase_a.toml"
DEFAULT_LABEL_COLUMN = "forward_return_1d_close_like"


def parse_args() -> argparse.Namespace:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    parser = argparse.ArgumentParser(description="Extend broad Gate C candidates across cached dates.")
    parser.add_argument("--layered-board", required=True, help="Source layered_factor_board.json.")
    parser.add_argument("--decision-log", default=str(DEFAULT_DECISION_LOG), help="Layered decision TSV.")
    parser.add_argument("--gate-log", default=str(DEFAULT_GATE_C_LOG), help="Append-only Gate C TSV.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Candidate config with card/module mapping.")
    parser.add_argument("--triage-id", default="", help="Optional triage_id filter. Defaults to latest in TSV.")
    parser.add_argument("--year", default="2026", help="Verified year to extend.")
    parser.add_argument("--dates", nargs="*", default=[], help="Optional explicit dates. Defaults to daily-agg cached dates.")
    parser.add_argument("--factors", nargs="*", default=[], help="Optional factor subset.")
    parser.add_argument("--label-column", default=DEFAULT_LABEL_COLUMN)
    parser.add_argument("--top-fraction", type=float, default=0.1)
    parser.add_argument("--cost-bps", type=float, default=15.0)
    parser.add_argument("--min-evaluated-dates", type=int, default=8)
    parser.add_argument("--min-hit-rate", type=float, default=0.52)
    parser.add_argument("--min-stability", type=float, default=0.55)
    parser.add_argument("--max-turnover-proxy", type=float, default=0.9)
    parser.add_argument("--min-primary-pass-layers", type=int, default=2)
    parser.add_argument(
        "--doc-path",
        default=str(ROOT / "docs" / f"layered_gate_c_extended_summary_{month}.md"),
        help="Tracked extended Gate C summary markdown path.",
    )
    parser.add_argument("--notes", default="extended cached-date gate c stress")
    parser.add_argument("--json", action="store_true", help="Emit JSON payload.")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSON artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing TSV artifact: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def cached_daily_dates(year: str) -> list[str]:
    dates = available_dates("verified_trades", year)
    missing = set(missing_daily_agg_dates("verified_trades_daily", dates))
    missing.update(missing_daily_agg_dates("verified_orders_daily", dates))
    cached = [date for date in dates if date not in missing]
    previous_map = previous_available_dates("verified_trades", cached, step=1)
    return [date for date in cached if date in previous_map and previous_map[date] not in missing]


def load_candidate_config(path: Path) -> dict[str, dict[str, str]]:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict[str, str]] = {}
    for row in payload.get("candidates", []):
        factor = str(row["factor"])
        result[factor] = {
            "factor": factor,
            "card": str(row["card"]),
            "module": str(row.get("module", "")),
            "transform": str(row.get("transform", "level")),
        }
    return result


def write_extended_decision_rows(
    *,
    rows: list[dict[str, str]],
    extension_id: str,
    run_dir_by_factor: dict[str, str],
    path: Path,
) -> None:
    fieldnames = list(rows[0].keys())
    for name in ["triage_id", "created_at", "run_dir", "primary_decision"]:
        if name not in fieldnames:
            fieldnames.append(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            updated = dict(row)
            updated["triage_id"] = extension_id
            updated["created_at"] = created_at
            updated["primary_decision"] = "promote_broad_candidate"
            updated["run_dir"] = run_dir_by_factor[str(row["factor_name"])]
            writer.writerow(updated)


def annotate_extension_doc(path: Path, *, target_dates: list[str]) -> None:
    if not path.exists() or not target_dates:
        return
    text = path.read_text(encoding="utf-8")
    if "extension_date_count" in text:
        return
    marker = next((line for line in text.splitlines() if line.startswith("- cost_bps:")), "")
    if not marker:
        return
    addition = "\n".join(
        [
            f"- extension_date_count: `{len(target_dates)}`",
            f"- extension_date_range: `{target_dates[0]}` to `{target_dates[-1]}`",
            "- extension_policy: cached daily-aggregate dates with cached previous trading day for change factors",
        ]
    )
    path.write_text(text.replace(marker, f"{marker}\n{addition}", 1), encoding="utf-8")


def build_layered_gate_c_extension(
    *,
    layered_board_path: Path,
    decision_log_path: Path = DEFAULT_DECISION_LOG,
    gate_log_path: Path = DEFAULT_GATE_C_LOG,
    config_path: Path = DEFAULT_CONFIG,
    doc_path: Path | None = None,
    run_root: Path = RUN_ROOT,
    triage_id: str = "",
    year: str = "2026",
    dates: list[str] | None = None,
    factors: list[str] | None = None,
    label_column: str = DEFAULT_LABEL_COLUMN,
    top_fraction: float = 0.1,
    cost_bps: float = 15.0,
    min_evaluated_dates: int = 8,
    min_hit_rate: float = 0.52,
    min_stability: float = 0.55,
    max_turnover_proxy: float = 0.9,
    min_primary_pass_layers: int = 2,
    notes: str = "extended cached-date gate c stress",
) -> tuple[str, dict[str, Any], Path]:
    board = _load_json(layered_board_path)
    decision_rows = _read_tsv(decision_log_path)
    candidates = select_gate_c_candidates(decision_rows, triage_id=triage_id, factors=factors)
    target_dates = list(dates or cached_daily_dates(year))
    if not target_dates:
        raise ValueError("No extension dates available.")
    config = load_candidate_config(config_path)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    extension_id = f"layered_gate_c_ext_{stamp}_{board['board_id']}"
    extension_dir = run_root / extension_id
    extension_dir.mkdir(parents=True, exist_ok=True)
    extension_decision_path = extension_dir / "extended_layered_factor_decisions.tsv"

    materialized: list[dict[str, Any]] = []
    run_dir_by_factor: dict[str, str] = {}
    for row in candidates:
        factor_name = str(row["factor_name"])
        spec = config.get(factor_name)
        if spec is None:
            raise ValueError(f"Missing candidate config for `{factor_name}`.")
        parent_summary = _load_json(Path(row["run_dir"]) / "data_run_summary.json")
        record, summary = run_verified_factor_experiment(
            card_path=ROOT / spec["card"],
            factor_name=factor_name,
            module_name=spec["module"] or None,
            transform_name=spec["transform"],
            dates=target_dates,
            owner="agent",
            notes=notes,
            parent_experiment_id=str(parent_summary.get("experiment_id", "")),
            allow_with_caveat=False,
        )
        if summary is None:
            raise RuntimeError(f"Factor `{factor_name}` did not materialize; gate={record.gate_a_decision}.")
        run_dir_by_factor[factor_name] = str(record.run_dir)
        materialized.append(
            {
                "factor_name": factor_name,
                "experiment_id": record.experiment_id,
                "parent_experiment_id": record.parent_experiment_id,
                "run_dir": record.run_dir,
                "output_rows": summary["output_rows"],
                "date_count": len(summary["dates"]),
                "module": spec["module"],
                "transform": spec["transform"],
                "card": spec["card"],
            }
        )

    write_extended_decision_rows(
        rows=candidates,
        extension_id=extension_id,
        run_dir_by_factor=run_dir_by_factor,
        path=extension_decision_path,
    )
    gate_c_id, gate_payload, gate_summary_path = build_layered_gate_c_summary(
        layered_board_path=layered_board_path,
        decision_log_path=extension_decision_path,
        gate_log_path=gate_log_path,
        doc_path=doc_path,
        run_root=run_root,
        triage_id=extension_id,
        factors=factors,
        label_column=label_column,
        top_fraction=top_fraction,
        cost_bps=cost_bps,
        min_evaluated_dates=min_evaluated_dates,
        min_hit_rate=min_hit_rate,
        min_stability=min_stability,
        max_turnover_proxy=max_turnover_proxy,
        min_primary_pass_layers=min_primary_pass_layers,
        notes=notes,
    )
    if doc_path is not None:
        annotate_extension_doc(doc_path, target_dates=target_dates)
    payload = {
        "extension_id": extension_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_board_id": str(board["board_id"]),
        "source_triage_id": str(candidates[0]["triage_id"]),
        "extension_decision_path": str(extension_decision_path),
        "target_dates": target_dates,
        "target_date_count": len(target_dates),
        "materialized": materialized,
        "gate_c_id": gate_c_id,
        "gate_c_summary_path": str(gate_summary_path),
        "gate_c_decision_counts": gate_payload["decision_counts"],
        "notes": notes,
    }
    summary_path = extension_dir / "layered_gate_c_extension_summary.json"
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return extension_id, payload, summary_path


def main() -> int:
    args = parse_args()
    extension_id, payload, summary_path = build_layered_gate_c_extension(
        layered_board_path=Path(args.layered_board),
        decision_log_path=Path(args.decision_log),
        gate_log_path=Path(args.gate_log),
        config_path=Path(args.config),
        doc_path=Path(args.doc_path),
        triage_id=args.triage_id,
        year=args.year,
        dates=args.dates or None,
        factors=args.factors or None,
        label_column=args.label_column,
        top_fraction=args.top_fraction,
        cost_bps=args.cost_bps,
        min_evaluated_dates=args.min_evaluated_dates,
        min_hit_rate=args.min_hit_rate,
        min_stability=args.min_stability,
        max_turnover_proxy=args.max_turnover_proxy,
        min_primary_pass_layers=args.min_primary_pass_layers,
        notes=args.notes,
    )
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(
            f"{extension_id} dates={payload['target_date_count']} "
            f"factors={len(payload['materialized'])} "
            f"gate_c={payload['gate_c_decision_counts']} summary={summary_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
