"""Run rule-based auto-triage over a scoreboard summary."""

from __future__ import annotations

import argparse
import importlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from math import fsum
from pathlib import Path
import sys
from typing import Any

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest_engine.minimal_lane import run_minimal_backtest
from factor_families.profile import build_family_profile
from harness.instrument_universe import UNIVERSE_FILTER_VERSION
from harness.triage import (
    append_family_performance_summary,
    append_reject_reason_log,
    derive_reject_reasons,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run auto-triage for a scoreboard summary.")
    parser.add_argument("--scoreboard-summary", required=True, help="Path to scoreboard_summary.json.")
    parser.add_argument("--labels-path", default="", help="Optional labels parquet for minimal backtests.")
    parser.add_argument("--notes", default="", help="Short triage note.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSON artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _scoreboard_factor_rows(scoreboard_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return list(scoreboard_payload.get("factor_board") or scoreboard_payload.get("factors") or [])


def _year_grade_from_dates(dates: list[str]) -> list[str]:
    years = []
    for date in dates:
        text = str(date)
        if len(text) >= 4:
            years.append(text[:4])
    return list(dict.fromkeys(years))


def _fallback_factor_profile(row: dict[str, Any], data_summary: dict[str, Any], family_profile: dict[str, Any]) -> dict[str, Any]:
    target_scope = str(data_summary.get("target_instrument_universe", "stock_research_candidate"))
    source_scope = str(data_summary.get("source_instrument_universe", "target_only"))
    contains_cross_security = bool(data_summary.get("contains_cross_security_source", False))
    universe_filter_version = str(data_summary.get("universe_filter_version", UNIVERSE_FILTER_VERSION))
    factor_family = str(family_profile.get("family_name") or row.get("factor_family", ""))
    mechanism = str(data_summary.get("mechanism", row.get("mechanism", "")))
    dates = list(data_summary.get("dates", []))
    transform_name = str(data_summary.get("transform_name", "level"))
    baseline_refs = list(data_summary.get("baseline_refs", []))
    failure_modes = list(data_summary.get("failure_modes", []))
    return {
        "factor_name": str(row["factor_name"]),
        "factor_id": str(data_summary.get("factor_id", row.get("factor_name", ""))),
        "family_name": factor_family,
        "mechanism_hypothesis": mechanism,
        "target_universe_scope": target_scope,
        "source_universe_scope": source_scope,
        "required_data_lane": str(data_summary.get("data_source_mode", "verified_raw")),
        "required_year_grade": _year_grade_from_dates(dates),
        "time_grade_requirement": transform_name,
        "contains_caveat_fields": bool(data_summary.get("contains_caveat_fields", False)),
        "supports_default_lane": target_scope == "stock_research_candidate" and source_scope == "target_only" and not contains_cross_security,
        "supports_extension_lane": contains_cross_security or source_scope != "target_only",
        "label_definition": str(data_summary.get("label_name", "forward_return_1d_close_like")),
        "evaluation_horizons": [transform_name],
        "known_failure_modes": failure_modes,
        "baseline_comparators": baseline_refs,
        "requires_cross_security_mapping": contains_cross_security,
        "contains_cross_security_source": contains_cross_security,
        "universe_filter_version": universe_filter_version,
        "research_card_path": str(data_summary.get("card_path", "")),
        "module_name": str(data_summary.get("module_name", row.get("factor_name", ""))),
        "family_registry_path": str(ROOT / "registry" / "factor_families.tsv"),
    }


def _family_summary_candidates(records: list[dict[str, Any]], family_name: str) -> list[dict[str, Any]]:
    return [row for row in records if str(row.get("family_name", "")) == family_name]


def _recommendations(histogram: Counter[str], total: int) -> list[str]:
    if total == 0:
        return ["No candidates were available for triage."]
    recommendations: list[str] = []
    if histogram["low_coverage"] >= max(2, total // 3):
        recommendations.append("Tighten the lane or label coverage before adding new candidates.")
    if histogram["high_redundancy_to_baseline"] >= max(2, total // 3):
        recommendations.append("Shift search toward a different family or a less redundant transform chain.")
    if histogram["weak_ic"] >= max(2, total // 3):
        recommendations.append("Retire weak variants and reframe the family mechanism hypothesis.")
    if histogram["narrow_entropy_regime_only"] >= max(2, total // 4):
        recommendations.append("Add regime-explicit variants or broaden entropy slice coverage.")
    if histogram["caveat_dependence_too_high"] > 0:
        recommendations.append("Keep caveat-heavy ideas in the explicit extension lane only.")
    if histogram["insufficient_significance"] > 0:
        recommendations.append("Require stronger permutation evidence or a larger evaluation window.")
    if not recommendations:
        recommendations.append("The current batch is reasonably balanced; prioritize ready candidates and trim redundant follow-ups.")
    return recommendations


def run_auto_triage(
    *,
    scoreboard_summary_path: Path,
    labels_path: Path | None = None,
    notes: str = "",
) -> tuple[str, dict[str, Any], Path]:
    scoreboard_payload = _load_json(scoreboard_summary_path)
    factor_rows = _scoreboard_factor_rows(scoreboard_payload)
    if not factor_rows:
        raise ValueError("No factor rows found in scoreboard summary.")

    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    triage_id = f"triage_{stamp}_{scoreboard_payload['scoreboard_id']}"
    run_dir = ROOT / "runs" / triage_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "triage_summary.json"
    report_path = run_dir / "triage_report.md"

    triaged_rows: list[dict[str, Any]] = []
    backtest_payloads: dict[str, dict[str, Any]] = {}
    reason_histogram: Counter[str] = Counter()

    labels_df = pl.read_parquet(labels_path) if labels_path else None

    for row in factor_rows:
        run_dir_path = Path(row["run_dir"])
        data_summary = _load_json(run_dir_path / "data_run_summary.json")
        factor_profile = _load_optional_json(run_dir_path / "factor_profile.json")
        family_profile = _load_optional_json(run_dir_path / "family_profile.json")
        if not factor_profile:
            module_name = str(data_summary.get("module_name", row.get("module_name", row["factor_name"])))
            try:
                importlib.import_module(f"factor_defs.{module_name}")
            except ModuleNotFoundError:
                pass
            factor_profile = _fallback_factor_profile(row, data_summary, family_profile)
        if not family_profile:
            family_id = str(row.get("factor_family", ""))
            family_profile = build_family_profile(family_id).as_dict() if family_id else {}

        backtest_summary: dict[str, Any] | None = None
        if labels_df is not None:
            factor_output = pl.read_parquet(run_dir_path / "factor_output.parquet")
            backtest_result = run_minimal_backtest(
                factor_output,
                labels_df,
                factor_name=str(row["factor_name"]),
                score_column=str(row["score_column"]),
                label_column=str(labels_path and "forward_return_1d_close_like" or "forward_return_1d_close_like"),
                target_instrument_universe=str(data_summary.get("target_instrument_universe", "")),
                source_instrument_universe=str(data_summary.get("source_instrument_universe", "")),
                contains_cross_security_source=bool(data_summary.get("contains_cross_security_source", False)),
                universe_filter_version=str(data_summary.get("universe_filter_version", "")),
                horizon=str(data_summary.get("transform_name", "1d")),
            )
            backtest_summary = backtest_result.as_dict()
            backtest_payloads[str(row["factor_name"])] = backtest_summary

        primary, secondary, readiness, snapshot = derive_reject_reasons(
            row,
            factor_profile=factor_profile,
            family_profile=family_profile,
            backtest_summary=backtest_summary,
        )
        family_name = str(factor_profile.get("family_name") or row.get("factor_family", ""))
        reason_histogram[primary] += 1 if primary != "none" else 0
        for reason in secondary:
            reason_histogram[reason] += 1

        triaged_rows.append(
            {
                "factor_name": row["factor_name"],
                "family_name": family_name,
                "promotion_readiness": readiness,
                "primary_reject_reason": primary,
                "secondary_reject_reasons": secondary,
                "scoreboard_row": row,
                "factor_profile": factor_profile,
                "family_profile": family_profile,
                "backtest": backtest_summary or {},
                "reason_snapshot": snapshot,
                "run_dir": str(run_dir_path),
                "pre_eval_id": str(row.get("pre_eval_id", "")),
                "score_column": str(row.get("score_column", "")),
            }
        )

    shortlisted_candidates = [row for row in triaged_rows if row["promotion_readiness"] == "ready"]
    rejected_candidates = [row for row in triaged_rows if row["promotion_readiness"] == "reject"]
    watch_candidates = [row for row in triaged_rows if row["promotion_readiness"] == "watch"]

    family_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in triaged_rows:
        family_groups[row["family_name"]].append(row)
        append_reject_reason_log(
            triage_id=triage_id,
            factor_name=row["factor_name"],
            family_name=row["family_name"],
            reason_snapshot=row["reason_snapshot"],
            primary_reject_reason=row["primary_reject_reason"],
            secondary_reject_reasons=list(row["secondary_reject_reasons"]),
            run_dir=row["run_dir"],
            pre_eval_id=row["pre_eval_id"],
            scoreboard_id=str(scoreboard_payload["scoreboard_id"]),
            backtest_id=str(row["backtest"].get("backtest_id", "")),
            notes=notes,
        )

    for family_name, rows in family_groups.items():
        append_family_performance_summary(
            triage_id=triage_id,
            family_name=family_name,
            candidate_rows=[row["reason_snapshot"] | {"promotion_readiness": row["promotion_readiness"], "primary_reject_reason": row["primary_reject_reason"]} for row in rows],
            notes=notes,
        )

    family_summaries = []
    for family_name, rows in sorted(family_groups.items()):
        snapshot_rows = [row["reason_snapshot"] for row in rows]
        readiness_counts = Counter(row["promotion_readiness"] for row in rows)
        family_summaries.append(
            {
                "family_name": family_name,
                "candidate_count": len(rows),
                "shortlisted_count": readiness_counts["ready"],
                "watch_count": readiness_counts["watch"],
                "rejected_count": readiness_counts["reject"],
                "shortlist_rate": 0.0 if not rows else readiness_counts["ready"] / len(rows),
                "average_redundancy_profile": _mean(
                    [value for value in (row.get("mean_abs_baseline_corr") for row in snapshot_rows) if value is not None]
                ),
                "entropy_regime_sensitivity": _mean(
                    [value for value in (row.get("entropy_regime_dispersion") for row in snapshot_rows) if value is not None]
                ),
                "significance_quality": _mean(
                    [value for value in (row.get("mi_significant_date_ratio") for row in snapshot_rows) if value is not None]
                ),
                "common_failure_modes": dict(
                    Counter(
                        row["primary_reject_reason"]
                        for row in rows
                        if row["primary_reject_reason"] != "none"
                    )
                ),
            }
        )

    payload = {
        "triage_id": triage_id,
        "created_at": created_at,
        "notes": notes,
        "scoreboard_id": scoreboard_payload["scoreboard_id"],
        "scoreboard_summary_path": str(scoreboard_summary_path),
        "candidate_count": len(triaged_rows),
        "shortlisted_candidates": shortlisted_candidates,
        "watch_candidates": watch_candidates,
        "rejected_candidates": rejected_candidates,
        "reject_reason_histogram": dict(reason_histogram),
        "family_summaries": family_summaries,
        "family_level_summary": family_summaries,
        "backtests": backtest_payloads,
        "recommended_next_batch_directions": _recommendations(reason_histogram, len(triaged_rows)),
    }
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    report_path.write_text(_render_report(payload), encoding="utf-8")
    return triage_id, payload, summary_path


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return fsum(values) / len(values)


def _render_report(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Auto Triage")
    lines.append("")
    lines.append(f"- triage_id: `{payload['triage_id']}`")
    lines.append(f"- scoreboard_id: `{payload['scoreboard_id']}`")
    lines.append(f"- candidate_count: `{payload['candidate_count']}`")
    lines.append("")
    lines.append("## Shortlisted")
    lines.append("")
    for row in payload["shortlisted_candidates"]:
        lines.append(
            "- "
            f"`{row['factor_name']}` "
            f"family=`{row['family_name']}` "
            f"reason=`{row['primary_reject_reason']}` "
            f"readiness=`{row['promotion_readiness']}`"
        )
    lines.append("")
    lines.append("## Rejected")
    lines.append("")
    for row in payload["rejected_candidates"]:
        lines.append(
            "- "
            f"`{row['factor_name']}` "
            f"family=`{row['family_name']}` "
            f"reason=`{row['primary_reject_reason']}` "
            f"secondary=`{','.join(row['secondary_reject_reasons'])}`"
        )
    if payload["watch_candidates"]:
        lines.append("")
        lines.append("## Watch")
        lines.append("")
        for row in payload["watch_candidates"]:
            lines.append(
                "- "
                f"`{row['factor_name']}` "
                f"family=`{row['family_name']}` "
                f"reason=`{row['primary_reject_reason']}`"
            )
    lines.append("")
    lines.append("## Reason Histogram")
    lines.append("")
    for reason, count in sorted(payload["reject_reason_histogram"].items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- `{reason}`: `{count}`")
    lines.append("")
    lines.append("## Family Summary")
    lines.append("")
    for row in payload["family_summaries"]:
        lines.append(
            "- "
            f"`{row['family_name']}` "
            f"candidate_count=`{row['candidate_count']}` "
            f"shortlist_rate=`{row['shortlist_rate']}` "
            f"avg_redundancy=`{row['average_redundancy_profile']}` "
            f"entropy_sensitivity=`{row['entropy_regime_sensitivity']}`"
        )
    lines.append("")
    lines.append("## Next Batch")
    lines.append("")
    for item in payload["recommended_next_batch_directions"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    triage_id, payload, _ = run_auto_triage(
        scoreboard_summary_path=Path(args.scoreboard_summary),
        labels_path=Path(args.labels_path) if args.labels_path else None,
        notes=args.notes,
    )
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(
            f"{triage_id} shortlisted={len(payload['shortlisted_candidates'])} "
            f"rejected={len(payload['rejected_candidates'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
