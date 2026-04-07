"""Rule-based auto-triage helpers for shortlisted factors."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from math import fsum
from pathlib import Path
from typing import Any

from harness.instrument_universe import UNIVERSE_FILTER_VERSION

ROOT = Path(__file__).resolve().parents[1]
REJECT_REASON_LOG = ROOT / "registry" / "reject_reason_log.tsv"
FAMILY_PERFORMANCE_SUMMARY = ROOT / "registry" / "family_performance_summary.tsv"

HARD_REJECT_REASON_ORDER = [
    "universe_mismatch",
    "caveat_dependence_too_high",
    "low_coverage",
    "insufficient_significance",
    "weak_ic",
    "weak_nmi",
]

SOFT_REJECT_REASON_ORDER = [
    "inverse_candidate_only",
    "unstable_across_dates",
    "narrow_entropy_regime_only",
    "high_redundancy_to_baseline",
]

THRESHOLDS = {
    "min_coverage_ratio": 0.85,
    "min_mean_abs_rank_ic": 0.04,
    "min_mean_nmi": 0.005,
    "min_sign_consistency": 0.6,
    "min_mi_significant_date_ratio": 0.50,
    "max_baseline_redundancy": 0.60,
    "min_backtest_hit_rate": 0.55,
    "min_backtest_spread_return": 0.0,
    "max_backtest_turnover_proxy": 0.75,
    "min_backtest_stability_proxy": 0.6,
    "narrow_entropy_dispersion": 0.05,
}


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return fsum(values) / len(values)


def _as_float(value: object) -> float | None:
    if value in ("", None):
        return None
    return float(value)


def _metric(row: dict[str, Any], *names: str) -> float | None:
    for name in names:
        value = row.get(name)
        if value not in ("", None):
            return float(value)
    return None


def _entropy_narrow_only(regime_summary: list[dict[str, Any]] | None) -> bool:
    if not regime_summary:
        return False
    scored = [
        (str(item.get("slice_value", "")), _as_float(item.get("mean_abs_rank_ic")))
        for item in regime_summary
        if _as_float(item.get("mean_abs_rank_ic")) is not None
    ]
    if len(scored) < 2:
        return False
    scored.sort(key=lambda item: float(item[1] or 0.0), reverse=True)
    best = float(scored[0][1] or 0.0)
    runner_up = float(scored[1][1] or 0.0)
    if best < THRESHOLDS["min_mean_abs_rank_ic"]:
        return False
    if best - runner_up < THRESHOLDS["narrow_entropy_dispersion"]:
        return False
    tail_strong = sum(1 for _, value in scored[1:] if value is not None and float(value) >= best * 0.5)
    return tail_strong == 0


def _inverse_candidate_only(row: dict[str, Any]) -> bool:
    mean_abs_rank_ic = _metric(row, "mean_abs_rank_ic")
    mean_rank_ic = _metric(row, "mean_rank_ic")
    mean_top_bottom_spread = _metric(row, "mean_top_bottom_spread")
    if mean_abs_rank_ic is None or mean_rank_ic is None or mean_top_bottom_spread is None:
        return False
    if mean_abs_rank_ic < THRESHOLDS["min_mean_abs_rank_ic"]:
        return False
    return mean_rank_ic < 0.0 and mean_top_bottom_spread < 0.0


def _reason_snapshot(row: dict[str, Any], backtest_summary: dict[str, Any] | None) -> dict[str, Any]:
    snapshot = {
        "mean_rank_ic": _metric(row, "mean_rank_ic"),
        "mean_abs_rank_ic": _metric(row, "mean_abs_rank_ic"),
        "mean_nmi": _metric(row, "mean_nmi", "mean_normalized_mutual_info"),
        "mean_top_bottom_spread": _metric(row, "mean_top_bottom_spread"),
        "mean_coverage_ratio": _metric(row, "mean_coverage_ratio"),
        "mean_abs_baseline_corr": _metric(row, "mean_abs_baseline_corr"),
        "mi_significant_date_ratio": _metric(row, "mi_significant_date_ratio"),
        "mean_mi_p_value": _metric(row, "mean_mi_p_value"),
        "entropy_regime_dispersion": _metric(row, "entropy_regime_dispersion"),
        "sign_consistency": _metric(row, "sign_consistency"),
    }
    if backtest_summary:
        snapshot.update(
            {
                "backtest_spread_return": _metric(backtest_summary, "spread_return"),
                "backtest_cost_adjusted_spread_return": _metric(
                    backtest_summary,
                    "cost_adjusted_spread_return",
                ),
                "backtest_turnover_proxy": _metric(backtest_summary, "turnover_proxy"),
                "backtest_hit_rate": _metric(backtest_summary, "hit_rate"),
                "backtest_stability_proxy": _metric(backtest_summary, "stability_proxy"),
            }
        )
    return snapshot


def derive_reject_reasons(
    row: dict[str, Any],
    *,
    factor_profile: dict[str, Any] | None = None,
    family_profile: dict[str, Any] | None = None,
    backtest_summary: dict[str, Any] | None = None,
) -> tuple[str, list[str], str, dict[str, Any]]:
    factor_profile = factor_profile or {}
    family_profile = family_profile or {}

    reasons: list[str] = []
    target_scope = str(factor_profile.get("target_universe_scope", row.get("target_instrument_universe", "")))
    source_scope = str(factor_profile.get("source_universe_scope", row.get("source_instrument_universe", "")))
    contains_caveat = bool(factor_profile.get("contains_caveat_fields", row.get("contains_caveat_fields", False)))
    contains_cross_security = bool(
        factor_profile.get("contains_cross_security_source", row.get("contains_cross_security_source", False))
    )
    universe_filter_version = str(
        factor_profile.get("universe_filter_version", row.get("universe_filter_version", ""))
    )

    if target_scope != "stock_research_candidate" or source_scope != "target_only":
        reasons.append("universe_mismatch")
    if contains_caveat or contains_cross_security or source_scope != "target_only":
        reasons.append("caveat_dependence_too_high")
    if universe_filter_version and universe_filter_version != UNIVERSE_FILTER_VERSION:
        reasons.append("universe_mismatch")

    coverage = _metric(row, "mean_coverage_ratio")
    if coverage is not None and coverage < THRESHOLDS["min_coverage_ratio"]:
        reasons.append("low_coverage")

    mean_abs_rank_ic = _metric(row, "mean_abs_rank_ic")
    if mean_abs_rank_ic is not None and mean_abs_rank_ic < THRESHOLDS["min_mean_abs_rank_ic"]:
        reasons.append("weak_ic")
    elif _inverse_candidate_only(row):
        reasons.append("inverse_candidate_only")

    mean_nmi = _metric(row, "mean_nmi", "mean_normalized_mutual_info")
    if mean_nmi is not None and mean_nmi < THRESHOLDS["min_mean_nmi"]:
        reasons.append("weak_nmi")

    mi_significant = _metric(row, "mi_significant_date_ratio")
    mean_mi_p_value = _metric(row, "mean_mi_p_value")
    if (
        (mi_significant is not None and mi_significant < THRESHOLDS["min_mi_significant_date_ratio"])
        or (mean_mi_p_value is not None and mean_mi_p_value > 0.05)
    ):
        reasons.append("insufficient_significance")

    sign_consistency = _metric(row, "sign_consistency")
    if sign_consistency is not None and sign_consistency < THRESHOLDS["min_sign_consistency"]:
        reasons.append("unstable_across_dates")

    entropy_summary = list(row.get("entropy_regime_summary", []) or [])
    if _entropy_narrow_only(entropy_summary):
        reasons.append("narrow_entropy_regime_only")

    baseline_corr = _metric(row, "mean_abs_baseline_corr")
    if baseline_corr is not None and baseline_corr >= THRESHOLDS["max_baseline_redundancy"]:
        reasons.append("high_redundancy_to_baseline")

    if backtest_summary:
        hit_rate = _metric(backtest_summary, "hit_rate")
        stability_proxy = _metric(backtest_summary, "stability_proxy")
        spread_return = _metric(backtest_summary, "spread_return")
        turnover_proxy = _metric(backtest_summary, "turnover_proxy")
        if hit_rate is not None and hit_rate < THRESHOLDS["min_backtest_hit_rate"]:
            reasons.append("unstable_across_dates")
        if stability_proxy is not None and stability_proxy < THRESHOLDS["min_backtest_stability_proxy"]:
            reasons.append("unstable_across_dates")
        if spread_return is not None and spread_return <= THRESHOLDS["min_backtest_spread_return"]:
            reasons.append("weak_ic")
        if turnover_proxy is not None and turnover_proxy > THRESHOLDS["max_backtest_turnover_proxy"]:
            reasons.append("high_redundancy_to_baseline")

    ordered_reasons = []
    for reason in HARD_REJECT_REASON_ORDER + SOFT_REJECT_REASON_ORDER:
        if reason in reasons and reason not in ordered_reasons:
            ordered_reasons.append(reason)

    primary = ordered_reasons[0] if ordered_reasons else "none"
    secondary = ordered_reasons[1:]
    hard_hit = any(reason in HARD_REJECT_REASON_ORDER for reason in ordered_reasons)
    soft_hit = any(reason in SOFT_REJECT_REASON_ORDER for reason in ordered_reasons)

    if hard_hit:
        readiness = "reject"
    elif soft_hit:
        readiness = "watch"
    else:
        readiness = "ready"

    snapshot = _reason_snapshot(row, backtest_summary)
    snapshot["factor_family"] = factor_profile.get("family_name") or row.get("factor_family", "")
    snapshot["family_mechanism_hypothesis"] = family_profile.get("mechanism_hypothesis", "")
    snapshot["contains_caveat_fields"] = contains_caveat
    snapshot["contains_cross_security_source"] = contains_cross_security
    snapshot["target_instrument_universe"] = target_scope
    snapshot["source_instrument_universe"] = source_scope
    snapshot["universe_filter_version"] = universe_filter_version
    snapshot["baseline_redundancy_score"] = snapshot.get("mean_abs_baseline_corr")
    snapshot["significance_proxy"] = snapshot.get("mi_significant_date_ratio")
    snapshot["promotion_readiness"] = readiness
    snapshot["primary_reject_reason"] = primary
    snapshot["secondary_reject_reasons"] = secondary
    return primary, secondary, readiness, snapshot


def _ensure_tsv(path: Path, header: list[str]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\t".join(header) + "\n", encoding="utf-8")


def append_reject_reason_log(
    *,
    triage_id: str,
    factor_name: str,
    family_name: str,
    reason_snapshot: dict[str, Any],
    primary_reject_reason: str,
    secondary_reject_reasons: list[str],
    run_dir: str,
    pre_eval_id: str,
    scoreboard_id: str,
    backtest_id: str,
    notes: str,
    path: Path | None = None,
) -> None:
    path = path or REJECT_REASON_LOG
    header = [
        "triage_id",
        "created_at",
        "factor_name",
        "family_name",
        "primary_reject_reason",
        "secondary_reject_reasons_json",
        "promotion_readiness",
        "target_instrument_universe",
        "source_instrument_universe",
        "contains_cross_security_source",
        "universe_filter_version",
        "run_dir",
        "pre_eval_id",
        "scoreboard_id",
        "backtest_id",
        "metrics_snapshot_json",
        "notes",
    ]
    _ensure_tsv(path, header)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                triage_id,
                datetime.now(timezone.utc).isoformat(),
                factor_name,
                family_name,
                primary_reject_reason,
                json.dumps(secondary_reject_reasons, ensure_ascii=False),
                reason_snapshot.get("promotion_readiness", "unknown"),
                reason_snapshot.get("target_instrument_universe", ""),
                reason_snapshot.get("source_instrument_universe", ""),
                reason_snapshot.get("contains_cross_security_source", False),
                reason_snapshot.get("universe_filter_version", ""),
                run_dir,
                pre_eval_id,
                scoreboard_id,
                backtest_id,
                json.dumps(reason_snapshot, ensure_ascii=False, default=str),
                notes,
            ]
        )


def append_family_performance_summary(
    *,
    triage_id: str,
    family_name: str,
    candidate_rows: list[dict[str, Any]],
    notes: str,
    path: Path | None = None,
) -> None:
    path = path or FAMILY_PERFORMANCE_SUMMARY
    header = [
        "triage_id",
        "created_at",
        "family_name",
        "candidate_count",
        "shortlisted_count",
        "shortlist_rate",
        "common_failure_modes_json",
        "average_redundancy_profile",
        "entropy_regime_sensitivity",
        "significance_quality",
        "promotion_ready_count",
        "notes",
    ]
    _ensure_tsv(path, header)

    candidate_count = len(candidate_rows)
    shortlisted_count = sum(1 for row in candidate_rows if row.get("promotion_readiness") == "ready")
    ready_count = shortlisted_count
    reject_histogram: dict[str, int] = {}
    redundancy_values: list[float] = []
    entropy_values: list[float] = []
    significance_values: list[float] = []
    for row in candidate_rows:
        primary = str(row.get("primary_reject_reason", "none"))
        if primary != "none":
            reject_histogram[primary] = reject_histogram.get(primary, 0) + 1
        redundancy = _as_float(row.get("mean_abs_baseline_corr"))
        if redundancy is not None:
            redundancy_values.append(redundancy)
        entropy_dispersion = _as_float(row.get("entropy_regime_dispersion"))
        if entropy_dispersion is not None:
            entropy_values.append(entropy_dispersion)
        significance = _as_float(row.get("mi_significant_date_ratio"))
        if significance is not None:
            significance_values.append(significance)

    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                triage_id,
                datetime.now(timezone.utc).isoformat(),
                family_name,
                candidate_count,
                shortlisted_count,
                0.0 if candidate_count == 0 else shortlisted_count / candidate_count,
                json.dumps(reject_histogram, ensure_ascii=False),
                _mean(redundancy_values),
                _mean(entropy_values),
                _mean(significance_values),
                ready_count,
                notes,
            ]
        )
