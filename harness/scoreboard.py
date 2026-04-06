"""Build a fixed candidate scoreboard from latest factor runs and comparisons."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import importlib
import itertools
import json
from math import fsum
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from diagnostics.redundancy import (
    baseline_group_for_factor,
    classify_incremental_hint,
    derive_baseline_metrics,
    load_baseline_registry,
)

EXPERIMENT_LOG = ROOT / "registry" / "experiment_log.tsv"
COMPARISON_LOG = ROOT / "registry" / "comparison_log.tsv"
PRE_EVAL_LOG = ROOT / "registry" / "pre_eval_log.tsv"
SCOREBOARD_LOG = ROOT / "registry" / "scoreboard_log.tsv"
RUN_ROOT = ROOT / "runs"
ENTROPY_SLICE_NAME = "entropy_quantile"


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _has_materialized_output(entry: dict[str, str]) -> bool:
    return (Path(entry["run_dir"]) / "data_run_summary.json").exists()


def _latest_runs(entries: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for entry in entries:
        if _has_materialized_output(entry):
            latest[entry["factor_name"]] = entry
    return latest


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pre_eval_metric(summary: dict[str, Any], *, official_name: str, legacy_name: str) -> float | None:
    aggregate_metrics = summary.get("aggregate_metrics", {})
    if isinstance(aggregate_metrics, dict):
        value = aggregate_metrics.get(official_name)
        if value is not None:
            return float(value)
    legacy_value = summary.get(legacy_name)
    if legacy_value is None:
        return None
    return float(legacy_value)


def _entropy_regime_summary(regime_slices: dict[str, Any]) -> dict[str, Any]:
    entries = list(regime_slices.get(ENTROPY_SLICE_NAME, []))
    digest = [
        {
            "slice_value": item["slice_value"],
            "mean_abs_rank_ic": item.get("mean_abs_rank_ic"),
            "mean_nmi": item.get("mean_nmi", item.get("mean_normalized_mutual_info")),
        }
        for item in entries
    ]
    scored_entries = [item for item in digest if item["mean_abs_rank_ic"] is not None]
    if len(scored_entries) >= 2:
        values = [float(item["mean_abs_rank_ic"]) for item in scored_entries]
        dispersion = max(values) - min(values)
        strongest = max(scored_entries, key=lambda item: float(item["mean_abs_rank_ic"]))
        weakest = min(scored_entries, key=lambda item: float(item["mean_abs_rank_ic"]))
    elif len(scored_entries) == 1:
        dispersion = 0.0
        strongest = scored_entries[0]
        weakest = scored_entries[0]
    else:
        dispersion = None
        strongest = None
        weakest = None
    return {
        "entries": digest,
        "dispersion": dispersion,
        "strongest_slice": None if strongest is None else strongest["slice_value"],
        "weakest_slice": None if weakest is None else weakest["slice_value"],
    }


def _regime_digest(entries: list[dict[str, Any]], *, include_nmi: bool) -> str:
    parts: list[str] = []
    for item in entries:
        mean_abs_rank_ic = item.get("mean_abs_rank_ic")
        if mean_abs_rank_ic is None:
            continue
        if include_nmi:
            mean_nmi = item.get("mean_nmi", item.get("mean_normalized_mutual_info"))
            if mean_nmi is None:
                parts.append(f"{item['slice_value']}:ic={float(mean_abs_rank_ic):.4f}")
            else:
                parts.append(
                    f"{item['slice_value']}:ic={float(mean_abs_rank_ic):.4f}|nmi={float(mean_nmi):.4f}"
                )
        else:
            parts.append(f"{item['slice_value']}:{float(mean_abs_rank_ic):.4f}")
    return ",".join(parts)


def _resolve_factor_module_name(entry: dict[str, str], data_summary: dict[str, Any]) -> str:
    candidates = [str(data_summary.get("module_name", "")), entry["factor_name"]]
    if entry["factor_name"].endswith("_change"):
        candidates.append(entry["factor_name"][: -len("_change")])
    for module_name in candidates:
        if not module_name:
            continue
        try:
            importlib.import_module(f"factor_defs.{module_name}")
            return module_name
        except ModuleNotFoundError:
            continue
    raise ModuleNotFoundError(f"Unable to resolve factor module for `{entry['factor_name']}`.")


def _factor_row(entry: dict[str, str]) -> dict[str, Any]:
    run_dir = Path(entry["run_dir"])
    data_summary = _load_json(run_dir / "data_run_summary.json")
    diagnostics = _load_json(run_dir / "diagnostics_summary.json")
    module_name = _resolve_factor_module_name(entry, data_summary)
    module = importlib.import_module(f"factor_defs.{module_name}")
    return {
        "factor_name": entry["factor_name"],
        "module_name": module_name,
        "transform_name": data_summary.get("transform_name", "level"),
        "factor_id": getattr(module, "FACTOR_ID", entry["factor_name"]),
        "factor_family": getattr(module, "FACTOR_FAMILY", ""),
        "mechanism": getattr(module, "MECHANISM", ""),
        "transform_chain": list(getattr(module, "TRANSFORM_CHAIN", [])),
        "forbidden_semantic_assumptions": list(
            getattr(module, "FORBIDDEN_SEMANTIC_ASSUMPTIONS", [])
        ),
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
    regime_slices = summary.get("regime_slices", {})
    entropy_summary = _entropy_regime_summary(regime_slices)
    mean_rank_ic = _pre_eval_metric(summary, official_name="rank_ic", legacy_name="mean_rank_ic")
    mean_abs_rank_ic = _pre_eval_metric(summary, official_name="abs_rank_ic", legacy_name="mean_abs_rank_ic")
    mean_mutual_info = _pre_eval_metric(summary, official_name="mi", legacy_name="mean_mutual_info")
    mean_nmi = _pre_eval_metric(summary, official_name="nmi", legacy_name="mean_normalized_mutual_info")
    mean_top_bottom_spread = _pre_eval_metric(
        summary,
        official_name="top_bottom_spread",
        legacy_name="mean_top_bottom_spread",
    )
    mean_coverage_ratio = _pre_eval_metric(summary, official_name="coverage_ratio", legacy_name="mean_coverage_ratio")
    return {
        "pre_eval_id": entry["pre_eval_id"],
        "experiment_id": entry["experiment_id"],
        "factor_name": entry["factor_name"],
        "label_name": summary["label_name"],
        "labeled_dates": summary["labeled_dates"],
        "skipped_dates": summary["skipped_dates"],
        "joined_rows": summary["joined_rows"],
        "aggregate_metrics": summary.get("aggregate_metrics", {}),
        "mean_rank_ic": mean_rank_ic,
        "mean_abs_rank_ic": mean_abs_rank_ic,
        "mean_mutual_info": mean_mutual_info,
        "mean_normalized_mutual_info": mean_nmi,
        "mean_nmi": mean_nmi,
        "mean_top_bottom_spread": mean_top_bottom_spread,
        "mean_coverage_ratio": mean_coverage_ratio,
        "regime_slices": regime_slices,
        "entropy_regime_summary": entropy_summary["entries"],
        "entropy_regime_dispersion": entropy_summary["dispersion"],
        "entropy_regime_strongest_slice": entropy_summary["strongest_slice"],
        "entropy_regime_weakest_slice": entropy_summary["weakest_slice"],
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


def _score_sort_key(row: dict[str, Any]) -> tuple[bool, float, float, float, float, float]:
    abs_ic = row["mean_abs_rank_ic"]
    normalized_mi = row.get("mean_nmi", row.get("mean_normalized_mutual_info"))
    corr = row["mean_abs_baseline_corr"]
    distinct = float(row["distinct_instruments"])
    return (
        abs_ic is None and normalized_mi is None,
        0.0 if abs_ic is None else -float(abs_ic),
        0.0 if normalized_mi is None else -float(normalized_mi),
        0.0 if corr is None else float(corr),
        float(row["mean_abs_peer_corr"]),
        -distinct,
    )


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return fsum(values) / len(values)


def _derive_factor_board(
    factor_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    baseline_registry: dict[str, Any],
) -> list[dict[str, Any]]:
    factor_names = [row["factor_name"] for row in factor_rows]
    baseline_factors = list(baseline_registry.get("default_baselines", []))
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
        baseline_metrics = derive_baseline_metrics(
            factor_name=factor["factor_name"],
            comparison_rows=comparison_rows,
            baseline_factors=baseline_factors,
        )
        board.append(
            {
                "factor_name": factor["factor_name"],
                "module_name": factor["module_name"],
                "transform_name": factor["transform_name"],
                "factor_id": factor["factor_id"],
                "factor_family": factor["factor_family"],
                "baseline_group": baseline_group_for_factor(factor["factor_name"], baseline_registry),
                "baseline_role": baseline_metrics["baseline_role"],
                "baseline_peer_count": baseline_metrics["baseline_peer_count"],
                "table_name": factor["table_name"],
                "output_rows": factor["output_rows"],
                "distinct_instruments": factor["distinct_instruments"],
                "overall_score_mean": factor["overall_score_mean"],
                "mean_abs_peer_corr": _average(peer_corrs),
                "mean_top_overlap_count": _average(peer_overlaps),
                "mean_abs_baseline_corr": baseline_metrics["mean_abs_baseline_corr"],
                "mean_baseline_top_overlap": baseline_metrics["mean_baseline_top_overlap"],
                "pre_eval_id": pre_eval.get("pre_eval_id"),
                "label_name": pre_eval.get("label_name"),
                "evaluated_dates": pre_eval.get("labeled_dates", []),
                "skipped_dates": pre_eval.get("skipped_dates", []),
                "joined_rows": pre_eval.get("joined_rows"),
                "mean_rank_ic": pre_eval.get("mean_rank_ic"),
                "mean_abs_rank_ic": pre_eval.get("mean_abs_rank_ic"),
                "mean_mutual_info": pre_eval.get("mean_mutual_info"),
                "mean_normalized_mutual_info": pre_eval.get("mean_normalized_mutual_info"),
                "mean_nmi": pre_eval.get("mean_nmi"),
                "mean_top_bottom_spread": pre_eval.get("mean_top_bottom_spread"),
                "mean_coverage_ratio": pre_eval.get("mean_coverage_ratio"),
                "incremental_hint": classify_incremental_hint(
                    baseline_role=baseline_metrics["baseline_role"],
                    mean_abs_rank_ic=pre_eval.get("mean_abs_rank_ic"),
                    mean_abs_baseline_corr=baseline_metrics["mean_abs_baseline_corr"],
                ),
                "regime_slices": pre_eval.get("regime_slices", {}),
                "entropy_regime_summary": pre_eval.get("entropy_regime_summary", []),
                "entropy_regime_dispersion": pre_eval.get("entropy_regime_dispersion"),
                "entropy_regime_strongest_slice": pre_eval.get("entropy_regime_strongest_slice"),
                "entropy_regime_weakest_slice": pre_eval.get("entropy_regime_weakest_slice"),
                "mechanism": factor["mechanism"],
                "transform_chain": factor["transform_chain"],
                "forbidden_semantic_assumptions": factor["forbidden_semantic_assumptions"],
                "dates": factor["dates"],
                "notes": factor["notes"],
            }
        )
    return sorted(board, key=_score_sort_key)


def _render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    baseline_factors = list(payload.get("baseline_factors", []))
    lines.append("# Candidate Scoreboard")
    lines.append("")
    lines.append(f"- scoreboard_id: `{payload['scoreboard_id']}`")
    lines.append(f"- created_at: `{payload['created_at']}`")
    lines.append(f"- factor_count: `{payload['factor_count']}`")
    lines.append(f"- comparison_count: `{payload['comparison_count']}`")
    lines.append(f"- pre_eval_count: `{payload['pre_eval_count']}`")
    lines.append(f"- baseline_count: `{len(baseline_factors)}`")
    if baseline_factors:
        lines.append("")
        lines.append("## Baseline Set")
        lines.append("")
        for factor_name in baseline_factors:
            lines.append(f"- `{factor_name}`")
    lines.append("")
    lines.append("## Factor Board")
    lines.append("")
    for row in payload["factor_board"]:
        baseline_corr = row.get("mean_abs_baseline_corr")
        baseline_corr_text = (
            "na" if baseline_corr is None else f"{baseline_corr:.3f}"
        )
        factor_family = row.get("factor_family", "")
        baseline_role = row.get("baseline_role", "unknown")
        incremental_hint = row.get("incremental_hint", "unknown")
        mean_nmi = row.get("mean_nmi", row.get("mean_normalized_mutual_info"))
        entropy_dispersion = row.get("entropy_regime_dispersion")
        entropy_text = "" if entropy_dispersion is None else f" entropy_dispersion=`{entropy_dispersion:.4f}`"
        pre_eval_text = (
            f"mean_abs_rank_ic=`{row['mean_abs_rank_ic']:.4f}` "
            f"mean_nmi=`{mean_nmi:.4f}` "
            f"mean_spread=`{row['mean_top_bottom_spread']:.4f}` "
            f"coverage=`{row['mean_coverage_ratio']:.3f}` "
            f"incremental_hint=`{incremental_hint}`"
            f"{entropy_text}"
            if row["mean_abs_rank_ic"] is not None
            and mean_nmi is not None
            and row["mean_top_bottom_spread"] is not None
            else "pre_eval=`missing`"
        )
        lines.append(
            "- "
            f"`{row['factor_name']}` "
            f"family=`{factor_family}` "
            f"baseline_role=`{baseline_role}` "
            f"table=`{row['table_name']}` "
            f"rows=`{row['output_rows']}` "
            f"distinct_instruments=`{row['distinct_instruments']}` "
            f"mean_abs_peer_corr=`{row['mean_abs_peer_corr']:.3f}` "
            f"mean_top_overlap=`{row['mean_top_overlap_count']:.2f}` "
            f"mean_abs_baseline_corr=`{baseline_corr_text}` "
            f"{pre_eval_text}"
        )
    lines.append("")
    lines.append("## Pre-Eval Notes")
    lines.append("")
    for row in payload["factor_board"]:
        if row["mean_abs_rank_ic"] is None:
            lines.append(f"- `{row['factor_name']}` pre_eval missing")
            continue
        incremental_hint = row.get("incremental_hint", "unknown")
        mean_nmi = row.get("mean_nmi", row.get("mean_normalized_mutual_info"))
        mean_nmi_text = "na" if mean_nmi is None else f"{mean_nmi:.4f}"
        note = (
            "- "
            f"`{row['factor_name']}` "
            f"dates=`{','.join(row['evaluated_dates'])}` "
            f"joined_rows=`{row['joined_rows']}` "
            f"mean_rank_ic=`{row['mean_rank_ic']:.4f}` "
            f"mean_abs_rank_ic=`{row['mean_abs_rank_ic']:.4f}` "
            f"mean_nmi=`{mean_nmi_text}` "
            f"mean_top_bottom_spread=`{row['mean_top_bottom_spread']:.4f}` "
            f"incremental_hint=`{incremental_hint}`"
        )
        if row.get("entropy_regime_dispersion") is not None:
            note += f" entropy_dispersion=`{row['entropy_regime_dispersion']:.4f}`"
        lines.append(note)
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
    lines.append("")
    lines.append("## Regime Notes")
    lines.append("")
    for row in payload["factor_board"]:
        regime_slices = row.get("regime_slices", {})
        if not regime_slices:
            lines.append(f"- `{row['factor_name']}` regime_slices=`missing`")
            continue
        parts: list[str] = []
        entropy_entries = regime_slices.get(ENTROPY_SLICE_NAME, [])
        entropy_digest = _regime_digest(entropy_entries, include_nmi=True)
        if entropy_digest:
            parts.append(f"{ENTROPY_SLICE_NAME}=`{entropy_digest}`")
        if row.get("entropy_regime_dispersion") is not None:
            parts.append(f"entropy_dispersion=`{row['entropy_regime_dispersion']:.4f}`")
        for slice_name in ["year_grade", "market_turnover_regime", "market_volatility_regime"]:
            entries = regime_slices.get(slice_name, [])
            if not entries:
                continue
            digest = _regime_digest(entries, include_nmi=False)
            if digest:
                parts.append(f"{slice_name}=`{digest}`")
        if not parts:
            parts.append("regime_slices=`present_but_empty`")
        lines.append(f"- `{row['factor_name']}` " + " ".join(parts))
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
    baseline_registry = load_baseline_registry()
    factor_board = _derive_factor_board(factor_rows, comparison_rows, baseline_registry)

    payload = {
        "scoreboard_id": scoreboard_id,
        "created_at": created_at,
        "notes": notes,
        "factor_count": len(factor_rows),
        "comparison_count": len(comparison_rows),
        "pre_eval_count": sum(1 for row in factor_rows if row["pre_eval"] is not None),
        "baseline_registry": baseline_registry,
        "baseline_factors": list(baseline_registry.get("default_baselines", [])),
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
    parser.add_argument("--factors", nargs="+", help="Factor names to include.")
    parser.add_argument("--notes", default="", help="Short scoreboard note.")
    args = parser.parse_args()

    if not args.factors:
        # Fallback: get some recent successful factors if none specified
        try:
            experiment_entries = _read_tsv(EXPERIMENT_LOG)
            # Find distinct names for factors with successful materialize outputs or diagnostics
            # We filter for those that have at least one materialized output available
            found = []
            seen = set()
            for entry in reversed(experiment_entries):
                name = entry.get("factor_name")
                if name and name not in seen:
                    if _has_materialized_output(entry):
                        found.append(name)
                        seen.add(name)
                if len(found) >= 12:
                    break
            if found:
                args.factors = found
                if not args.notes:
                    args.notes = f"Auto-detected {len(found)} recent factors"
            else:
                parser.error("No factors provided and no recent successful runs found in experiment_log.tsv.")
        except Exception as e:
            parser.error(f"the following arguments are required: --factors (Automatic fallback failed: {e})")

    return args


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
