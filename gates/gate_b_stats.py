"""Fixed Gate B statistical validity rules for Phase A factors."""

from __future__ import annotations

from math import fsum
from typing import Any

POLICY_VERSION = "gate_b_stats_v1"

PASS_THRESHOLDS = {
    "min_evaluated_dates": 3,
    "min_mean_abs_rank_ic": 0.08,
    "min_mean_normalized_mutual_info": 0.015,
    "min_mean_coverage_ratio": 0.85,
    "min_sign_consistency": 2.0 / 3.0,
}

MONITOR_THRESHOLDS = {
    "min_evaluated_dates": 3,
    "min_mean_abs_rank_ic": 0.04,
    "min_mean_normalized_mutual_info": 0.005,
    "min_mean_coverage_ratio": 0.75,
    "min_sign_consistency": 0.50,
}


def _as_float(value: object) -> float | None:
    if value in ("", None):
        return None
    return float(value)


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return fsum(values) / len(values)


def summarize_rank_ic_signs(per_date_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rank_ic_values = [_as_float(row.get("rank_ic")) for row in per_date_rows]
    valid_values = [value for value in rank_ic_values if value is not None]
    signed_values = [value for value in valid_values if value != 0.0]
    positive_count = sum(1 for value in signed_values if value > 0.0)
    negative_count = sum(1 for value in signed_values if value < 0.0)
    zero_count = len(valid_values) - len(signed_values)
    if positive_count == 0 and negative_count == 0:
        dominant_sign = "none"
        sign_consistency = None
    elif positive_count >= negative_count:
        dominant_sign = "positive"
        sign_consistency = positive_count / len(signed_values)
    else:
        dominant_sign = "negative"
        sign_consistency = negative_count / len(signed_values)
    sign_switch_count = 0
    previous_sign = 0
    for value in valid_values:
        current_sign = 1 if value > 0.0 else -1 if value < 0.0 else 0
        if current_sign == 0:
            continue
        if previous_sign != 0 and current_sign != previous_sign:
            sign_switch_count += 1
        previous_sign = current_sign
    return {
        "evaluated_date_count": len(valid_values),
        "signed_date_count": len(signed_values),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "zero_count": zero_count,
        "dominant_sign": dominant_sign,
        "sign_consistency": sign_consistency,
        "sign_switch_count": sign_switch_count,
    }


def _metric_check(
    *,
    metric_name: str,
    metric_value: float | None,
    threshold_value: float,
    comparator: str = ">=",
) -> dict[str, Any]:
    if metric_value is None:
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
    }


def evaluate_gate_b(pre_eval_summary: dict[str, Any]) -> dict[str, Any]:
    sign_summary = summarize_rank_ic_signs(list(pre_eval_summary.get("per_date", [])))
    mean_rank_ic = _as_float(pre_eval_summary.get("mean_rank_ic"))
    mean_abs_rank_ic = _as_float(pre_eval_summary.get("mean_abs_rank_ic"))
    mean_normalized_mutual_info = _as_float(pre_eval_summary.get("mean_normalized_mutual_info"))
    mean_coverage_ratio = _as_float(pre_eval_summary.get("mean_coverage_ratio"))
    mean_top_bottom_spread = _as_float(pre_eval_summary.get("mean_top_bottom_spread"))
    evaluated_date_count = int(sign_summary["evaluated_date_count"])
    sign_consistency = _as_float(sign_summary.get("sign_consistency"))

    metrics = {
        "mean_rank_ic": mean_rank_ic,
        "mean_abs_rank_ic": mean_abs_rank_ic,
        "mean_normalized_mutual_info": mean_normalized_mutual_info,
        "mean_coverage_ratio": mean_coverage_ratio,
        "mean_top_bottom_spread": mean_top_bottom_spread,
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
    ]

    if all(check["passed"] for check in pass_checks):
        decision = "pass"
    elif all(check["passed"] for check in monitor_checks):
        decision = "monitor"
    else:
        decision = "fail"

    failed_pass_metrics = [check["metric"] for check in pass_checks if not check["passed"]]
    failed_monitor_metrics = [check["metric"] for check in monitor_checks if not check["passed"]]

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
