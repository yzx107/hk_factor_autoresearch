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
from evaluation.robustness import summarize_signs
from harness.compare_factors import run_factor_comparison
from harness.triage import derive_reject_reasons

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


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
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
    factor_profile = _load_optional_json(run_dir / "factor_profile.json") or dict(data_summary.get("factor_profile", {}))
    family_profile = _load_optional_json(run_dir / "family_profile.json") or dict(data_summary.get("family_profile", {}))
    module_name = _resolve_factor_module_name(entry, data_summary)
    module = importlib.import_module(f"factor_defs.{module_name}")
    family_id = str(
        factor_profile.get("family_id")
        or getattr(module, "FACTOR_FAMILY", "")
    )
    family_name = str(
        factor_profile.get("family_name")
        or family_profile.get("family_name")
        or family_id
    )
    return {
        "factor_name": entry["factor_name"],
        "module_name": module_name,
        "transform_name": data_summary.get("transform_name", "level"),
        "factor_id": factor_profile.get("factor_id", getattr(module, "FACTOR_ID", entry["factor_name"])),
        "factor_family": family_id,
        "family_name": family_name,
        "mechanism": factor_profile.get("mechanism_hypothesis", getattr(module, "MECHANISM", "")),
        "transform_chain": list(
            factor_profile.get("transform_chain", list(getattr(module, "TRANSFORM_CHAIN", [])))
        ),
        "forbidden_semantic_assumptions": list(
            factor_profile.get(
                "forbidden_semantic_assumptions",
                list(getattr(module, "FORBIDDEN_SEMANTIC_ASSUMPTIONS", [])),
            )
        ),
        "target_instrument_universe": data_summary.get("target_instrument_universe", ""),
        "source_instrument_universe": data_summary.get("source_instrument_universe", ""),
        "contains_cross_security_source": bool(data_summary.get("contains_cross_security_source", False)),
        "universe_filter_version": data_summary.get("universe_filter_version", ""),
        "contains_caveat_fields": bool(factor_profile.get("contains_caveat_fields", False)),
        "supports_default_lane": bool(factor_profile.get("supports_default_lane", True)),
        "supports_extension_lane": bool(factor_profile.get("supports_extension_lane", False)),
        "required_data_lane": factor_profile.get("required_data_lane", data_summary.get("data_source_mode", "")),
        "required_year_grade": list(factor_profile.get("required_year_grade", [])),
        "time_grade_requirement": factor_profile.get("time_grade_requirement", ""),
        "baseline_comparators": list(factor_profile.get("baseline_comparators", [])),
        "known_failure_modes": list(factor_profile.get("known_failure_modes", [])),
        "requires_cross_security_mapping": bool(factor_profile.get("requires_cross_security_mapping", False)),
        "factor_profile": factor_profile,
        "family_profile": family_profile,
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
    mean_nmi_ic_gap = _pre_eval_metric(summary, official_name="nmi_ic_gap", legacy_name="mean_nmi_ic_gap")
    mean_mi_p_value = _pre_eval_metric(summary, official_name="mi_p_value", legacy_name="mean_mi_p_value")
    mean_mi_excess_over_null = _pre_eval_metric(
        summary,
        official_name="mi_excess_over_null",
        legacy_name="mean_mi_excess_over_null",
    )
    mi_significant_date_ratio = _pre_eval_metric(
        summary,
        official_name="mi_significant_date_ratio",
        legacy_name="mi_significant_date_ratio",
    )
    mean_top_bottom_spread = _pre_eval_metric(
        summary,
        official_name="top_bottom_spread",
        legacy_name="mean_top_bottom_spread",
    )
    mean_coverage_ratio = _pre_eval_metric(summary, official_name="coverage_ratio", legacy_name="mean_coverage_ratio")
    sign_summary = summarize_signs(
        [
            float(row["rank_ic"])
            for row in summary.get("per_date", [])
            if row.get("rank_ic") is not None
        ]
    )
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
        "mean_nmi_ic_gap": mean_nmi_ic_gap,
        "mean_mi_p_value": mean_mi_p_value,
        "mean_mi_excess_over_null": mean_mi_excess_over_null,
        "mi_significant_date_ratio": mi_significant_date_ratio,
        "mean_top_bottom_spread": mean_top_bottom_spread,
        "mean_coverage_ratio": mean_coverage_ratio,
        "sign_consistency": sign_summary.sign_consistency,
        "sign_switch_count": sign_summary.sign_switch_count,
        "regime_metadata": summary.get("regime_metadata", {}),
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


def _comparison_payload_row(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "comparison_id": payload["comparison_id"],
        "left_factor": payload["left"]["factor_name"],
        "right_factor": payload["right"]["factor_name"],
        "common_dates": payload["common_dates"],
        "common_rows": payload["common_rows"],
        "per_date_corr": payload["per_date"],
        "top_overlap": payload["top_overlap"],
    }


def _comparison_matches_experiments(
    entry: dict[str, str],
    *,
    left_experiment_id: str,
    right_experiment_id: str,
) -> bool:
    return {
        str(entry.get("left_experiment_id", "")),
        str(entry.get("right_experiment_id", "")),
    } == {left_experiment_id, right_experiment_id}


def _load_or_materialize_comparison_row(
    *,
    left_entry: dict[str, str],
    right_entry: dict[str, str],
    comparison_index: dict[tuple[str, str], dict[str, str]],
    notes: str,
) -> dict[str, Any]:
    key = tuple(sorted((left_entry["factor_name"], right_entry["factor_name"])))
    existing = comparison_index.get(key)
    if existing and _comparison_matches_experiments(
        existing,
        left_experiment_id=left_entry["experiment_id"],
        right_experiment_id=right_entry["experiment_id"],
    ):
        return _comparison_row(existing)

    comparison_id, payload, summary_path = run_factor_comparison(
        left_factor=left_entry["factor_name"],
        right_factor=right_entry["factor_name"],
        left_experiment=left_entry["experiment_id"],
        right_experiment=right_entry["experiment_id"],
        notes=notes,
    )
    comparison_index[key] = {
        "comparison_id": comparison_id,
        "left_experiment_id": left_entry["experiment_id"],
        "right_experiment_id": right_entry["experiment_id"],
        "left_factor": payload["left"]["factor_name"],
        "right_factor": payload["right"]["factor_name"],
        "summary_path": str(summary_path),
    }
    return _comparison_payload_row(payload)


def _collect_baseline_comparison_rows(
    *,
    factor_rows: list[dict[str, Any]],
    latest_runs: dict[str, dict[str, str]],
    comparison_index: dict[tuple[str, str], dict[str, str]],
    baseline_registry: dict[str, Any],
    notes: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    baseline_factors = [str(name) for name in baseline_registry.get("default_baselines", [])]
    requested_factor_names = {str(row["factor_name"]) for row in factor_rows}
    seen_pairs: set[tuple[str, str]] = set()
    comparison_rows: list[dict[str, Any]] = []
    missing_comparisons: list[str] = []

    for factor in factor_rows:
        factor_name = str(factor["factor_name"])
        factor_entry = latest_runs[factor_name]
        for baseline_name in baseline_factors:
            if baseline_name == factor_name or baseline_name in requested_factor_names:
                continue
            baseline_entry = latest_runs.get(baseline_name)
            key = tuple(sorted((factor_name, baseline_name)))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            if baseline_entry is None:
                missing_comparisons.append(f"{factor_name}__{baseline_name}")
                continue
            comparison_rows.append(
                _load_or_materialize_comparison_row(
                    left_entry=factor_entry,
                    right_entry=baseline_entry,
                    comparison_index=comparison_index,
                    notes=notes,
                )
            )
    return comparison_rows, missing_comparisons


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
        board_row = {
            "factor_name": factor["factor_name"],
            "module_name": factor["module_name"],
            "transform_name": factor["transform_name"],
            "factor_id": factor["factor_id"],
            "factor_family": factor["factor_family"],
            "family_name": factor["family_name"],
            "factor_profile": factor["factor_profile"],
            "family_profile": factor["family_profile"],
            "baseline_group": baseline_group_for_factor(factor["factor_name"], baseline_registry),
            "baseline_role": baseline_metrics["baseline_role"],
            "baseline_peer_count": baseline_metrics["baseline_peer_count"],
            "table_name": factor["table_name"],
            "score_column": factor["score_column"],
            "output_rows": factor["output_rows"],
            "distinct_instruments": factor["distinct_instruments"],
            "overall_score_mean": factor["overall_score_mean"],
            "mean_abs_peer_corr": _average(peer_corrs),
            "mean_top_overlap_count": _average(peer_overlaps),
            "mean_abs_baseline_corr": baseline_metrics["mean_abs_baseline_corr"],
            "baseline_redundancy_score": baseline_metrics["mean_abs_baseline_corr"],
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
            "mean_nmi_ic_gap": pre_eval.get("mean_nmi_ic_gap"),
            "mean_mi_p_value": pre_eval.get("mean_mi_p_value"),
            "mean_mi_excess_over_null": pre_eval.get("mean_mi_excess_over_null"),
            "mi_significant_date_ratio": pre_eval.get("mi_significant_date_ratio"),
            "significance_proxy": pre_eval.get("mi_significant_date_ratio"),
            "mean_top_bottom_spread": pre_eval.get("mean_top_bottom_spread"),
            "mean_coverage_ratio": pre_eval.get("mean_coverage_ratio"),
            "sign_consistency": pre_eval.get("sign_consistency"),
            "sign_switch_count": pre_eval.get("sign_switch_count"),
            "incremental_hint": classify_incremental_hint(
                baseline_role=baseline_metrics["baseline_role"],
                mean_abs_rank_ic=pre_eval.get("mean_abs_rank_ic"),
                mean_abs_baseline_corr=baseline_metrics["mean_abs_baseline_corr"],
            ),
            "regime_slices": pre_eval.get("regime_slices", {}),
            "regime_metadata": pre_eval.get("regime_metadata", {}),
            "entropy_regime_summary": pre_eval.get("entropy_regime_summary", []),
            "entropy_regime_dispersion": pre_eval.get("entropy_regime_dispersion"),
            "entropy_regime_strongest_slice": pre_eval.get("entropy_regime_strongest_slice"),
            "entropy_regime_weakest_slice": pre_eval.get("entropy_regime_weakest_slice"),
            "mechanism": factor["mechanism"],
            "transform_chain": factor["transform_chain"],
            "forbidden_semantic_assumptions": factor["forbidden_semantic_assumptions"],
            "dates": factor["dates"],
            "notes": factor["notes"],
            "target_instrument_universe": factor["target_instrument_universe"],
            "source_instrument_universe": factor["source_instrument_universe"],
            "contains_cross_security_source": factor["contains_cross_security_source"],
            "universe_filter_version": factor["universe_filter_version"],
            "contains_caveat_fields": factor["contains_caveat_fields"],
            "supports_default_lane": factor["supports_default_lane"],
            "supports_extension_lane": factor["supports_extension_lane"],
            "required_data_lane": factor["required_data_lane"],
            "required_year_grade": factor["required_year_grade"],
            "time_grade_requirement": factor["time_grade_requirement"],
            "baseline_comparators": factor["baseline_comparators"],
            "known_failure_modes": factor["known_failure_modes"],
            "requires_cross_security_mapping": factor["requires_cross_security_mapping"],
            "family_allowed_input_lane": factor["family_profile"].get("allowed_input_lane", ""),
            "family_current_best_variants": factor["family_profile"].get("current_best_variants", []),
            "family_redundancy_pattern": factor["family_profile"].get("redundancy_pattern", ""),
            "family_regime_sensitivity": factor["family_profile"].get("regime_sensitivity", []),
            "family_expand_direction": factor["family_profile"].get("whether_to_expand_further", ""),
            "universe_scope": (
                f"target={factor['target_instrument_universe']}|source={factor['source_instrument_universe']}"
            ),
            "run_dir": factor["run_dir"],
        }
        primary, secondary, readiness, _ = derive_reject_reasons(
            board_row,
            factor_profile=factor["factor_profile"],
            family_profile=factor["family_profile"],
        )
        board_row["promotion_readiness"] = readiness
        board_row["primary_reject_reason"] = primary
        board_row["secondary_reject_reasons"] = secondary
        board.append(board_row)
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
    if "peer_comparison_count" in payload:
        lines.append(f"- peer_comparison_count: `{payload['peer_comparison_count']}`")
    if "baseline_comparison_count" in payload:
        lines.append(f"- baseline_comparison_count: `{payload['baseline_comparison_count']}`")
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
        readiness = row.get("promotion_readiness", "unknown")
        reject_reason = row.get("primary_reject_reason", "none")
        universe_scope = row.get("universe_scope", "unknown")
        caveat_text = "true" if row.get("contains_caveat_fields") else "false"
        mean_nmi = row.get("mean_nmi", row.get("mean_normalized_mutual_info"))
        mean_nmi_ic_gap = row.get("mean_nmi_ic_gap")
        mi_sig_ratio = row.get("mi_significant_date_ratio")
        entropy_dispersion = row.get("entropy_regime_dispersion")
        entropy_text = "" if entropy_dispersion is None else f" entropy_dispersion=`{entropy_dispersion:.4f}`"
        nonlinear_text = "" if mean_nmi_ic_gap is None else f" nmi_ic_gap=`{mean_nmi_ic_gap:.4f}`"
        mi_sig_text = "" if mi_sig_ratio is None else f" mi_sig_ratio=`{mi_sig_ratio:.3f}`"
        pre_eval_text = (
            f"mean_abs_rank_ic=`{row['mean_abs_rank_ic']:.4f}` "
            f"mean_nmi=`{mean_nmi:.4f}` "
            f"mean_spread=`{row['mean_top_bottom_spread']:.4f}` "
            f"coverage=`{row['mean_coverage_ratio']:.3f}` "
            f"incremental_hint=`{incremental_hint}`"
            f"{entropy_text}{nonlinear_text}{mi_sig_text}"
            if row["mean_abs_rank_ic"] is not None
            and mean_nmi is not None
            and row["mean_top_bottom_spread"] is not None
            else "pre_eval=`missing`"
        )
        lines.append(
            "- "
            f"`{row['factor_name']}` "
            f"family=`{factor_family}` "
            f"readiness=`{readiness}` "
            f"reason=`{reject_reason}` "
            f"universe=`{universe_scope}` "
            f"contains_caveat_fields=`{caveat_text}` "
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
        mean_nmi_ic_gap = row.get("mean_nmi_ic_gap")
        mi_sig_ratio = row.get("mi_significant_date_ratio")
        note = (
            "- "
            f"`{row['factor_name']}` "
            f"dates=`{','.join(row['evaluated_dates'])}` "
            f"joined_rows=`{row['joined_rows']}` "
            f"mean_rank_ic=`{row['mean_rank_ic']:.4f}` "
            f"mean_abs_rank_ic=`{row['mean_abs_rank_ic']:.4f}` "
            f"mean_nmi=`{mean_nmi_text}` "
            f"mean_top_bottom_spread=`{row['mean_top_bottom_spread']:.4f}` "
            f"incremental_hint=`{incremental_hint}` "
            f"promotion_readiness=`{row.get('promotion_readiness', 'unknown')}` "
            f"primary_reject_reason=`{row.get('primary_reject_reason', 'none')}` "
            f"baseline_redundancy_score=`{row.get('baseline_redundancy_score')}`"
        )
        if row.get("entropy_regime_dispersion") is not None:
            note += f" entropy_dispersion=`{row['entropy_regime_dispersion']:.4f}`"
        if mean_nmi_ic_gap is not None:
            note += f" nmi_ic_gap=`{mean_nmi_ic_gap:.4f}`"
        if mi_sig_ratio is not None:
            note += f" mi_sig_ratio=`{mi_sig_ratio:.3f}`"
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
    missing_baseline_comparisons = list(payload.get("missing_baseline_comparisons", []))
    if missing_baseline_comparisons:
        lines.append("")
        lines.append("## Missing Baseline Comparisons")
        lines.append("")
        for item in missing_baseline_comparisons:
            lines.append(f"- `{item}`")
    lines.append("")
    lines.append("## Triage")
    lines.append("")
    for row in payload["factor_board"]:
        lines.append(
            "- "
            f"`{row['factor_name']}` "
            f"family=`{row.get('family_name', row.get('factor_family', ''))}` "
            f"promotion_readiness=`{row.get('promotion_readiness', 'unknown')}` "
            f"primary_reject_reason=`{row.get('primary_reject_reason', 'none')}` "
            f"baseline_redundancy_score=`{row.get('baseline_redundancy_score')}` "
            f"universe=`{row.get('universe_scope', 'unknown')}` "
            f"contains_caveat_fields=`{row.get('contains_caveat_fields', False)}`"
        )
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
        regime_metadata = row.get("regime_metadata", {})
        label_mode = regime_metadata.get("label_mode")
        if label_mode:
            parts.append(f"label_mode=`{label_mode}`")
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

    baseline_registry = load_baseline_registry()
    comparison_entries = _read_tsv(COMPARISON_LOG)
    comparison_index = _comparison_index(comparison_entries)
    peer_comparison_rows: list[dict[str, Any]] = []
    missing_comparisons: list[str] = []
    for left, right in itertools.combinations(sorted(factor_names), 2):
        key = (left, right)
        if key in comparison_index:
            peer_comparison_rows.append(_comparison_row(comparison_index[key]))
        else:
            missing_comparisons.append(f"{left}__{right}")

    baseline_comparison_rows, missing_baseline_comparisons = _collect_baseline_comparison_rows(
        factor_rows=factor_rows,
        latest_runs=latest_runs,
        comparison_index=comparison_index,
        baseline_registry=baseline_registry,
        notes=notes,
    )
    comparison_rows = peer_comparison_rows + baseline_comparison_rows

    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    scoreboard_id = f"score_{stamp}"
    run_dir = RUN_ROOT / scoreboard_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "scoreboard_summary.json"
    report_path = run_dir / "scoreboard_report.md"
    factor_board = _derive_factor_board(factor_rows, comparison_rows, baseline_registry)

    payload = {
        "scoreboard_id": scoreboard_id,
        "created_at": created_at,
        "notes": notes,
        "factor_count": len(factor_rows),
        "comparison_count": len(comparison_rows),
        "peer_comparison_count": len(peer_comparison_rows),
        "baseline_comparison_count": len(baseline_comparison_rows),
        "pre_eval_count": sum(1 for row in factor_rows if row["pre_eval"] is not None),
        "baseline_registry": baseline_registry,
        "baseline_factors": list(baseline_registry.get("default_baselines", [])),
        "factors": factor_rows,
        "factor_board": factor_board,
        "comparisons": comparison_rows,
        "missing_comparisons": missing_comparisons,
        "missing_baseline_comparisons": missing_baseline_comparisons,
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
