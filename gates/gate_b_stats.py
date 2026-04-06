"""Fixed Gate B statistical validity rules for Phase A factors."""

from __future__ import annotations

from math import fsum
from typing import Any

from evaluation.robustness import summarize_signs

POLICY_VERSION = "gate_b_stats_v2"

PASS_THRESHOLDS = {
    "min_evaluated_dates": 3,
    "min_mean_abs_rank_ic": 0.08,
    "min_mean_normalized_mutual_info": 0.015,
    "min_mean_coverage_ratio": 0.85,
    "min_sign_consistency": 2.0 / 3.0,
    "min_mi_significant_date_ratio": 0.50,
}

MONITOR_THRESHOLDS = {
    "min_evaluated_dates": 3,
    "min_mean_abs_rank_ic": 0.04,
    "min_mean_normalized_mutual_info": 0.005,
    "min_mean_coverage_ratio": 0.75,
    "min_sign_consistency": 0.50,
    "min_mi_significant_date_ratio": 1.0 / 3.0,
}


def _as_float(value: object) -> float | None:
    if value in ("", None):
        return None
    return float(value)


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return fsum(values) / len(values)


def _summary_metric(pre_eval_summary: dict[str, Any], *, official_name: str, legacy_name: str) -> float | None:
    aggregate_metrics = pre_eval_summary.get("aggregate_metrics", {})
    if isinstance(aggregate_metrics, dict):
        value = aggregate_metrics.get(official_name)
        if value is not None:
            return float(value)
    legacy_value = pre_eval_summary.get(legacy_name)
    if legacy_value is None:
        return None
    return float(legacy_value)


def summarize_rank_ic_signs(per_date_rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = summarize_signs([_as_float(row.get("rank_ic")) for row in per_date_rows])
    return {
        "evaluated_date_count": summary.evaluated_count,
        "signed_date_count": summary.signed_count,
        "positive_count": summary.positive_count,
        "negative_count": summary.negative_count,
        "zero_count": summary.zero_count,
        "dominant_sign": summary.dominant_sign,
        "sign_consistency": summary.sign_consistency,
        "sign_switch_count": summary.sign_switch_count,
    }


def _metric_check(
    *,
    metric_name: str,
    metric_value: float | None,
    threshold_value: float,
    comparator: str = ">=",
    optional: bool = False,
) -> dict[str, Any]:
    applicable = metric_value is not None or not optional
    if not applicable:
        passed = True
    elif metric_value is None:
        passed = False
    elif comparator == ">=":
        passed = metric_value >= threshold_value
    else:
        raise ValueError(f"Unsupported comparator `{comparator}`.")
    return {
        "metric": metric_name,
        "value": metric_value,
        "threshold": threshold_value,
        "comparator": comparator,
        "passed": passed,
        "applicable": applicable,
    }


def evaluate_gate_b(pre_eval_summary: dict[str, Any]) -> dict[str, Any]:
    sign_summary = summarize_rank_ic_signs(list(pre_eval_summary.get("per_date", [])))
    mean_rank_ic = _summary_metric(pre_eval_summary, official_name="rank_ic", legacy_name="mean_rank_ic")
    mean_abs_rank_ic = _summary_metric(pre_eval_summary, official_name="abs_rank_ic", legacy_name="mean_abs_rank_ic")
    mean_normalized_mutual_info = _summary_metric(
        pre_eval_summary,
        official_name="nmi",
        legacy_name="mean_normalized_mutual_info",
    )
    mean_coverage_ratio = _summary_metric(
        pre_eval_summary,
        official_name="coverage_ratio",
        legacy_name="mean_coverage_ratio",
    )
    mean_top_bottom_spread = _summary_metric(
        pre_eval_summary,
        official_name="top_bottom_spread",
        legacy_name="mean_top_bottom_spread",
    )
    mean_nmi_ic_gap = _summary_metric(pre_eval_summary, official_name="nmi_ic_gap", legacy_name="mean_nmi_ic_gap")
    mean_mi_p_value = _summary_metric(pre_eval_summary, official_name="mi_p_value", legacy_name="mean_mi_p_value")
    mean_mi_excess_over_null = _summary_metric(
        pre_eval_summary,
        official_name="mi_excess_over_null",
        legacy_name="mean_mi_excess_over_null",
    )
    mi_significant_date_ratio = _summary_metric(
        pre_eval_summary,
        official_name="mi_significant_date_ratio",
        legacy_name="mi_significant_date_ratio",
    )
    evaluated_date_count = int(sign_summary["evaluated_date_count"])
    sign_consistency = _as_float(sign_summary.get("sign_consistency"))
    if mean_nmi_ic_gap is None:
        signal_shape_hint = "undetermined"
    elif mean_nmi_ic_gap > 0.02:
        signal_shape_hint = "nonlinear_candidate"
    elif mean_nmi_ic_gap < -0.02:
        signal_shape_hint = "mostly_monotonic"
    else:
        signal_shape_hint = "mixed_or_linear"

    metrics = {
        "mean_rank_ic": mean_rank_ic,
        "mean_abs_rank_ic": mean_abs_rank_ic,
        "mean_normalized_mutual_info": mean_normalized_mutual_info,
        "mean_coverage_ratio": mean_coverage_ratio,
        "mean_top_bottom_spread": mean_top_bottom_spread,
        "mean_nmi_ic_gap": mean_nmi_ic_gap,
        "mean_mi_p_value": mean_mi_p_value,
        "mean_mi_excess_over_null": mean_mi_excess_over_null,
        "mi_significant_date_ratio": mi_significant_date_ratio,
        "signal_shape_hint": signal_shape_hint,
        "evaluated_date_count": evaluated_date_count,
        "sign_consistency": sign_consistency,
        **sign_summary,
    }

    pass_checks = [
        _metric_check(
            metric_name="evaluated_date_count",
            metric_value=float(evaluated_date_count),
            threshold_value=float(PASS_THRESHOLDS["min_evaluated_dates"]),
        ),
        _metric_check(
            metric_name="mean_abs_rank_ic",
            metric_value=mean_abs_rank_ic,
            threshold_value=float(PASS_THRESHOLDS["min_mean_abs_rank_ic"]),
        ),
        _metric_check(
            metric_name="mean_normalized_mutual_info",
            metric_value=mean_normalized_mutual_info,
            threshold_value=float(PASS_THRESHOLDS["min_mean_normalized_mutual_info"]),
        ),
        _metric_check(
            metric_name="mean_coverage_ratio",
            metric_value=mean_coverage_ratio,
            threshold_value=float(PASS_THRESHOLDS["min_mean_coverage_ratio"]),
        ),
        _metric_check(
            metric_name="sign_consistency",
            metric_value=sign_consistency,
            threshold_value=float(PASS_THRESHOLDS["min_sign_consistency"]),
        ),
        _metric_check(
            metric_name="mi_significant_date_ratio",
            metric_value=mi_significant_date_ratio,
            threshold_value=float(PASS_THRESHOLDS["min_mi_significant_date_ratio"]),
            optional=True,
        ),
    ]

    monitor_checks = [
        _metric_check(
            metric_name="evaluated_date_count",
            metric_value=float(evaluated_date_count),
            threshold_value=float(MONITOR_THRESHOLDS["min_evaluated_dates"]),
        ),
        _metric_check(
            metric_name="mean_abs_rank_ic",
            metric_value=mean_abs_rank_ic,
            threshold_value=float(MONITOR_THRESHOLDS["min_mean_abs_rank_ic"]),
        ),
        _metric_check(
            metric_name="mean_normalized_mutual_info",
            metric_value=mean_normalized_mutual_info,
            threshold_value=float(MONITOR_THRESHOLDS["min_mean_normalized_mutual_info"]),
        ),
        _metric_check(
            metric_name="mean_coverage_ratio",
            metric_value=mean_coverage_ratio,
            threshold_value=float(MONITOR_THRESHOLDS["min_mean_coverage_ratio"]),
        ),
        _metric_check(
            metric_name="sign_consistency",
            metric_value=sign_consistency,
            threshold_value=float(MONITOR_THRESHOLDS["min_sign_consistency"]),
        ),
        _metric_check(
            metric_name="mi_significant_date_ratio",
            metric_value=mi_significant_date_ratio,
            threshold_value=float(MONITOR_THRESHOLDS["min_mi_significant_date_ratio"]),
            optional=True,
        ),
    ]

    if all(check["passed"] for check in pass_checks):
        decision = "pass"
    elif all(check["passed"] for check in monitor_checks):
        decision = "monitor"
    else:
        decision = "fail"

    failed_pass_metrics = [
        check["metric"] for check in pass_checks if check.get("applicable", True) and not check["passed"]
    ]
    failed_monitor_metrics = [
        check["metric"] for check in monitor_checks if check.get("applicable", True) and not check["passed"]
    ]

    if decision == "pass":
        reasons = ["stable_statistical_relationship"]
    elif decision == "monitor":
        reasons = [f"below_pass:{metric}" for metric in failed_pass_metrics] or ["borderline_signal"]
    else:
        reasons = [f"below_monitor:{metric}" for metric in failed_monitor_metrics] or ["insufficient_signal"]

    if mean_rank_ic is None or mean_rank_ic == 0.0:
        direction_hint = "undetermined"
    elif mean_rank_ic > 0.0:
        direction_hint = "as_is_candidate"
    else:
        direction_hint = "inverse_candidate"

    return {
        "policy_version": POLICY_VERSION,
        "decision": decision,
        "reasons": reasons,
        "thresholds": {
            "pass": PASS_THRESHOLDS,
            "monitor": MONITOR_THRESHOLDS,
        },
        "metrics": metrics,
        "direction_hint": direction_hint,
        "pass_checks": pass_checks,
        "monitor_checks": monitor_checks,
    }
