"""Build a fixed candidate scoreboard from latest factor runs and comparisons."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import itertools
import json
from math import fsum
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPERIMENT_LOG = ROOT / "registry" / "experiment_log.tsv"
COMPARISON_LOG = ROOT / "registry" / "comparison_log.tsv"
PRE_EVAL_LOG = ROOT / "registry" / "pre_eval_log.tsv"
SCOREBOARD_LOG = ROOT / "registry" / "scoreboard_log.tsv"
RUN_ROOT = ROOT / "runs"


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _latest_runs(entries: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for entry in entries:
        latest[entry["factor_name"]] = entry
    return latest


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _factor_row(entry: dict[str, str]) -> dict[str, Any]:
    run_dir = Path(entry["run_dir"])
    data_summary = _load_json(run_dir / "data_run_summary.json")
    diagnostics = _load_json(run_dir / "diagnostics_summary.json")
    return {
        "factor_name": entry["factor_name"],
        "experiment_id": entry["experiment_id"],
        "table_name": data_summary["table_name"],
        "score_column": data_summary["score_column"],
        "dates": data_summary["dates"],
        "output_rows": data_summary["output_rows"],
        "distinct_instruments": diagnostics["distinct_instruments"],
        "overall_score_mean": diagnostics["overall_score_summary"]["mean"],
        "overall_score_min": diagnostics["overall_score_summary"]["min"],
        "overall_score_max": diagnostics["overall_score_summary"]["max"],
        "run_dir": entry["run_dir"],
        "notes": entry["notes"],
    }


def _latest_pre_eval_by_experiment(entries: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for entry in entries:
        latest[entry["experiment_id"]] = entry
    return latest


def _pre_eval_row(entry: dict[str, str] | None) -> dict[str, Any] | None:
    if not entry:
        return None
    summary = _load_json(Path(entry["summary_path"]))
    return {
        "pre_eval_id": entry["pre_eval_id"],
        "experiment_id": entry["experiment_id"],
        "factor_name": entry["factor_name"],
        "label_name": summary["label_name"],
        "labeled_dates": summary["labeled_dates"],
        "skipped_dates": summary["skipped_dates"],
        "joined_rows": summary["joined_rows"],
        "mean_rank_ic": summary["mean_rank_ic"],
        "mean_abs_rank_ic": summary["mean_abs_rank_ic"],
        "mean_top_bottom_spread": summary["mean_top_bottom_spread"],
        "mean_coverage_ratio": summary["mean_coverage_ratio"],
    }


def _comparison_index(entries: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    index: dict[tuple[str, str], dict[str, str]] = {}
    for entry in entries:
        key = tuple(sorted((entry["left_factor"], entry["right_factor"])))
        index[key] = entry
    return index


def _comparison_row(entry: dict[str, str]) -> dict[str, Any]:
    summary = _load_json(Path(entry["summary_path"]))
    return {
        "comparison_id": entry["comparison_id"],
        "left_factor": entry["left_factor"],
        "right_factor": entry["right_factor"],
        "common_dates": summary["common_dates"],
        "common_rows": summary["common_rows"],
        "per_date_corr": summary["per_date"],
        "top_overlap": summary["top_overlap"],
    }


def _score_sort_key(row: dict[str, Any]) -> tuple[bool, float, float, float]:
    abs_ic = row["mean_abs_rank_ic"]
    corr = row["mean_abs_peer_corr"]
    distinct = float(row["distinct_instruments"])
    return (
        abs_ic is None,
        0.0 if abs_ic is None else -float(abs_ic),
        float(corr),
        -distinct,
    )


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return fsum(values) / len(values)


def _derive_factor_board(
    factor_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    factor_names = [row["factor_name"] for row in factor_rows]
    comparison_index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in comparison_rows:
        key = tuple(sorted((row["left_factor"], row["right_factor"])))
        comparison_index[key] = row

    board: list[dict[str, Any]] = []
    for factor in factor_rows:
        peer_corrs: list[float] = []
        peer_overlaps: list[float] = []
        for peer in factor_names:
            if peer == factor["factor_name"]:
                continue
            key = tuple(sorted((factor["factor_name"], peer)))
            comparison = comparison_index.get(key)
            if comparison:
                corr_values = [
                    abs(item["pearson_corr"])
                    for item in comparison["per_date_corr"]
                    if item["pearson_corr"] is not None
                ]
                overlap_values = [float(item["top_overlap_count"]) for item in comparison["top_overlap"]]
                if corr_values:
                    peer_corrs.append(_average(corr_values))
                if overlap_values:
                    peer_overlaps.append(_average(overlap_values))
        pre_eval = factor.get("pre_eval") or {}
        board.append(
            {
                "factor_name": factor["factor_name"],
                "table_name": factor["table_name"],
                "output_rows": factor["output_rows"],
                "distinct_instruments": factor["distinct_instruments"],
                "overall_score_mean": factor["overall_score_mean"],
                "mean_abs_peer_corr": _average(peer_corrs),
                "mean_top_overlap_count": _average(peer_overlaps),
                "pre_eval_id": pre_eval.get("pre_eval_id"),
                "label_name": pre_eval.get("label_name"),
                "evaluated_dates": pre_eval.get("labeled_dates", []),
                "skipped_dates": pre_eval.get("skipped_dates", []),
                "joined_rows": pre_eval.get("joined_rows"),
                "mean_rank_ic": pre_eval.get("mean_rank_ic"),
                "mean_abs_rank_ic": pre_eval.get("mean_abs_rank_ic"),
                "mean_top_bottom_spread": pre_eval.get("mean_top_bottom_spread"),
                "mean_coverage_ratio": pre_eval.get("mean_coverage_ratio"),
                "dates": factor["dates"],
                "notes": factor["notes"],
            }
        )
    return sorted(board, key=_score_sort_key)


def _render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Candidate Scoreboard")
    lines.append("")
    lines.append(f"- scoreboard_id: `{payload['scoreboard_id']}`")
    lines.append(f"- created_at: `{payload['created_at']}`")
    lines.append(f"- factor_count: `{payload['factor_count']}`")
    lines.append(f"- comparison_count: `{payload['comparison_count']}`")
    lines.append(f"- pre_eval_count: `{payload['pre_eval_count']}`")
    lines.append("")
    lines.append("## Factor Board")
    lines.append("")
    for row in payload["factor_board"]:
        pre_eval_text = (
            f"mean_abs_rank_ic=`{row['mean_abs_rank_ic']:.4f}` "
            f"mean_spread=`{row['mean_top_bottom_spread']:.4f}` "
            f"coverage=`{row['mean_coverage_ratio']:.3f}`"
            if row["mean_abs_rank_ic"] is not None and row["mean_top_bottom_spread"] is not None
            else "pre_eval=`missing`"
        )
        lines.append(
            "- "
            f"`{row['factor_name']}` "
            f"table=`{row['table_name']}` "
            f"rows=`{row['output_rows']}` "
            f"distinct_instruments=`{row['distinct_instruments']}` "
            f"mean_abs_peer_corr=`{row['mean_abs_peer_corr']:.3f}` "
            f"mean_top_overlap=`{row['mean_top_overlap_count']:.2f}` "
            f"{pre_eval_text}"
        )
    lines.append("")
    lines.append("## Pre-Eval Notes")
    lines.append("")
    for row in payload["factor_board"]:
        if row["mean_abs_rank_ic"] is None:
            lines.append(f"- `{row['factor_name']}` pre_eval missing")
            continue
        lines.append(
            "- "
            f"`{row['factor_name']}` "
            f"dates=`{','.join(row['evaluated_dates'])}` "
            f"joined_rows=`{row['joined_rows']}` "
            f"mean_rank_ic=`{row['mean_rank_ic']:.4f}` "
            f"mean_abs_rank_ic=`{row['mean_abs_rank_ic']:.4f}` "
            f"mean_top_bottom_spread=`{row['mean_top_bottom_spread']:.4f}`"
        )
    lines.append("")
    lines.append("## Comparison Notes")
    lines.append("")
    for row in payload["comparisons"]:
        corr_values = [
            item["pearson_corr"]
            for item in row["per_date_corr"]
            if item["pearson_corr"] is not None
        ]
        mean_corr = _average([abs(value) for value in corr_values]) if corr_values else 0.0
        mean_overlap = _average([float(item["top_overlap_count"]) for item in row["top_overlap"]])
        lines.append(
            "- "
            f"`{row['left_factor']}` vs `{row['right_factor']}` "
            f"mean_abs_corr=`{mean_corr:.3f}` "
            f"mean_top_overlap=`{mean_overlap:.2f}` "
            f"common_rows=`{row['common_rows']}`"
        )
    if payload["missing_comparisons"]:
        lines.append("")
        lines.append("## Missing Comparisons")
        lines.append("")
        for item in payload["missing_comparisons"]:
            lines.append(f"- `{item}`")
    return "\n".join(lines) + "\n"


def ensure_scoreboard_log(path: Path = SCOREBOARD_LOG) -> None:
    if path.exists():
        return
    path.write_text(
        "scoreboard_id\tcreated_at\tfactor_count\tcomparison_count\tsummary_path\tnotes\n",
        encoding="utf-8",
    )


def build_scoreboard(factor_names: list[str], *, notes: str) -> tuple[str, dict[str, Any], Path]:
    experiment_entries = _read_tsv(EXPERIMENT_LOG)
    latest_runs = _latest_runs(experiment_entries)
    missing = [factor for factor in factor_names if factor not in latest_runs]
    if missing:
        raise ValueError(f"Missing latest runs for: {', '.join(missing)}")

    pre_eval_entries = _read_tsv(PRE_EVAL_LOG)
    latest_pre_eval = _latest_pre_eval_by_experiment(pre_eval_entries)
    factor_rows = []
    for factor in factor_names:
        row = _factor_row(latest_runs[factor])
        row["pre_eval"] = _pre_eval_row(latest_pre_eval.get(row["experiment_id"]))
        factor_rows.append(row)

    comparison_entries = _read_tsv(COMPARISON_LOG)
    comparison_index = _comparison_index(comparison_entries)
    comparison_rows: list[dict[str, Any]] = []
    missing_comparisons: list[str] = []
    for left, right in itertools.combinations(sorted(factor_names), 2):
        key = (left, right)
        if key in comparison_index:
            comparison_rows.append(_comparison_row(comparison_index[key]))
        else:
            missing_comparisons.append(f"{left}__{right}")

    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    scoreboard_id = f"score_{stamp}"
    run_dir = RUN_ROOT / scoreboard_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "scoreboard_summary.json"
    report_path = run_dir / "scoreboard_report.md"
    factor_board = _derive_factor_board(factor_rows, comparison_rows)

    payload = {
        "scoreboard_id": scoreboard_id,
        "created_at": created_at,
        "notes": notes,
        "factor_count": len(factor_rows),
        "comparison_count": len(comparison_rows),
        "pre_eval_count": sum(1 for row in factor_rows if row["pre_eval"] is not None),
        "factors": factor_rows,
        "factor_board": factor_board,
        "comparisons": comparison_rows,
        "missing_comparisons": missing_comparisons,
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report_path.write_text(_render_markdown(payload), encoding="utf-8")

    ensure_scoreboard_log()
    with SCOREBOARD_LOG.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                scoreboard_id,
                created_at,
                len(factor_rows),
                len(comparison_rows),
                str(summary_path),
                notes,
            ]
        )
    return scoreboard_id, payload, summary_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fixed scoreboard from latest factor runs.")
    parser.add_argument("--factors", nargs="+", required=True, help="Factor names to include.")
    parser.add_argument("--notes", default="", help="Short scoreboard note.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scoreboard_id, payload, _ = build_scoreboard(args.factors, notes=args.notes)
    print(
        f"{scoreboard_id} factors={payload['factor_count']} "
        f"comparisons={payload['comparison_count']} "
        f"missing={len(payload['missing_comparisons'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
