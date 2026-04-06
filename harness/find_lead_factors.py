"""Exploratory transfer-entropy scan across latest pre-eval factor series."""

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

from evaluation.transfer_entropy import transfer_entropy_permutation_test, transfer_entropy_summary

PRE_EVAL_LOG = ROOT / "registry" / "pre_eval_log.tsv"
RUN_ROOT = ROOT / "runs"
UPSTREAM_INFORMATION_THEORY_POLICY = (
    "/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/information_theory_admissibility.md"
)

PER_DATE_METRIC_ALIASES = {
    "mi": ("mi", "mutual_info"),
    "nmi": ("nmi", "normalized_mutual_info"),
}


def _read_pre_eval_log(path: Path = PRE_EVAL_LOG) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _latest_pre_eval_by_factor(entries: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for entry in entries:
        latest[entry["factor_name"]] = entry
    return latest


def _load_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _metric_value(row: dict[str, Any], metric: str) -> float | None:
    candidates = PER_DATE_METRIC_ALIASES.get(metric, (metric,))
    for name in candidates:
        value = row.get(name)
        if value is not None:
            return float(value)
    return None


def build_metric_series(summary: dict[str, Any], *, metric: str) -> dict[str, float]:
    series: dict[str, float] = {}
    for row in summary.get("per_date", []):
        date_value = row.get("date")
        metric_value = _metric_value(row, metric)
        if date_value is None or metric_value is None:
            continue
        series[str(date_value)] = metric_value
    return series


def align_series(
    left: dict[str, float],
    right: dict[str, float],
) -> tuple[list[str], list[float], list[float]]:
    common_dates = sorted(set(left) & set(right))
    return (
        common_dates,
        [float(left[date]) for date in common_dates],
        [float(right[date]) for date in common_dates],
    )


def _policy_trace(
    *,
    series_by_factor: dict[str, dict[str, float]],
    metric: str,
    lag: int,
    bins: int | None,
    min_overlap: int,
    permutations: int,
    significance_threshold: float,
    generated_at: str,
) -> dict[str, Any]:
    all_dates = sorted({date for series in series_by_factor.values() for date in series})
    requested_bins = "adaptive_equal_frequency_bins(min=2,max=8)" if bins is None else f"fixed_equal_frequency_bins({bins})"
    return {
        "year": sorted({date.split("-", 1)[0] for date in all_dates}),
        "source_layer": "autoresearch_pre_eval_summary",
        "input_tables": ["pre_eval_summary.per_date"],
        "input_field_class": "derived_downstream_metric_proxy",
        "research_time_grade": "date_level_summary_only",
        "instrument_universe": "stock_research_candidate_target_only",
        "time_resolution": "1d factor-date summary series",
        "window_definition": (
            "latest per-factor pre_eval per-date metric series, pairwise aligned on common dates"
        ),
        "discretization_rule": requested_bins,
        "lag_grid": [lag],
        "null_drop_rule": (
            "inner join on common dates; require at least "
            f"{min_overlap} shared dates; permutation significance shuffles source series only"
        ),
        "special_bucket_handling": (
            "not_applicable_for_downstream_metric_series; no Dir/Type special bucket rewriting is performed here"
        ),
        "sample_days": len(all_dates),
        "sample_rows": sum(len(series) for series in series_by_factor.values()),
        "effective_observations": "edge_specific_in_ranked_edges",
        "generated_at": generated_at,
        "code_or_policy_version": {
            "tool": "find_lead_factors_v2",
            "upstream_policy": UPSTREAM_INFORMATION_THEORY_POLICY,
        },
        "formal_consumption_eligible": False,
        "formal_consumption_reason": (
            "This utility operates on downstream pre_eval metric series, not direct verified SendTime-aligned field inputs."
        ),
        "metric": metric,
        "permutations": permutations,
        "significance_threshold": significance_threshold,
    }


def build_lead_factor_summary(
    series_by_factor: dict[str, dict[str, float]],
    *,
    metric: str,
    lag: int,
    bins: int | None,
    min_overlap: int,
    permutations: int = 200,
    significance_threshold: float = 0.05,
    generated_at: str = "",
) -> dict[str, Any]:
    factors = sorted(series_by_factor)
    matrix: dict[str, dict[str, float | None]] = {factor: {} for factor in factors}
    edges: list[dict[str, Any]] = []
    required_overlap = max(min_overlap, lag + 2)

    for left_factor in factors:
        for right_factor in factors:
            if left_factor == right_factor:
                matrix[left_factor][right_factor] = None
                continue
            common_dates, left_values, right_values = align_series(
                series_by_factor[left_factor],
                series_by_factor[right_factor],
            )
            if len(common_dates) < required_overlap:
                matrix[left_factor][right_factor] = None
                continue
            forward = transfer_entropy_summary(left_values, right_values, lag=lag, bins=bins)
            reverse = transfer_entropy_summary(right_values, left_values, lag=lag, bins=bins)
            forward_sig = transfer_entropy_permutation_test(
                left_values,
                right_values,
                lag=lag,
                bins=bins,
                permutations=permutations,
                p_value_threshold=significance_threshold,
            )
            reverse_sig = transfer_entropy_permutation_test(
                right_values,
                left_values,
                lag=lag,
                bins=bins,
                permutations=permutations,
                p_value_threshold=significance_threshold,
            )
            lead_gap = forward.transfer_entropy - reverse.transfer_entropy
            matrix[left_factor][right_factor] = forward.transfer_entropy
            edges.append(
                {
                    "source_factor": left_factor,
                    "target_factor": right_factor,
                    "metric": metric,
                    "lag": lag,
                    "effective_bin_count": forward.effective_bin_count,
                    "observation_count": forward.observation_count,
                    "sample_days": len(common_dates),
                    "sample_rows": len(common_dates) * 2,
                    "effective_observations": forward.observation_count,
                    "transfer_entropy": forward.transfer_entropy,
                    "transfer_entropy_p_value": forward_sig.p_value,
                    "transfer_entropy_null_mean": forward_sig.null_mean,
                    "transfer_entropy_null_std": forward_sig.null_std,
                    "transfer_entropy_significant": forward_sig.passed,
                    "reverse_transfer_entropy": reverse.transfer_entropy,
                    "reverse_transfer_entropy_p_value": reverse_sig.p_value,
                    "reverse_transfer_entropy_significant": reverse_sig.passed,
                    "lead_gap": lead_gap,
                    "common_dates": common_dates,
                }
            )

    ranked_edges = sorted(
        edges,
        key=lambda item: (
            bool(item["transfer_entropy_significant"]),
            float(item["lead_gap"]),
        ),
        reverse=True,
    )
    significant_ranked_edges = [edge for edge in ranked_edges if edge["transfer_entropy_significant"]]
    return {
        "metric": metric,
        "lag": lag,
        "bins": bins,
        "permutations": permutations,
        "significance_threshold": significance_threshold,
        "min_overlap": required_overlap,
        "factors": factors,
        "matrix": matrix,
        "ranked_edges": ranked_edges,
        "significant_ranked_edges": significant_ranked_edges,
        "policy_trace": _policy_trace(
            series_by_factor=series_by_factor,
            metric=metric,
            lag=lag,
            bins=bins,
            min_overlap=required_overlap,
            permutations=permutations,
            significance_threshold=significance_threshold,
            generated_at=generated_at,
        ),
        "note": (
            "Exploratory transfer-entropy scan only; not part of fixed pre-eval or promotion gates. "
            "Formal-consumption eligibility is false unless a future direct verified-field TE lane is added."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan latest pre-eval factor series with transfer entropy.")
    parser.add_argument("--factor", nargs="*", default=[], help="Optional factor subset. Defaults to all latest pre-evals.")
    parser.add_argument("--metric", default="rank_ic", help="Per-date metric to scan, for example rank_ic or nmi.")
    parser.add_argument("--lag", type=int, default=1, help="Lag used in transfer entropy.")
    parser.add_argument("--bins", type=int, default=0, help="Optional fixed bin count. Use 0 for adaptive bins.")
    parser.add_argument("--min-overlap", type=int, default=3, help="Minimum shared dates required per factor pair.")
    parser.add_argument("--permutations", type=int, default=200, help="Permutation draws for TE significance.")
    parser.add_argument(
        "--significance-threshold",
        type=float,
        default=0.05,
        help="P-value cutoff used for exploratory TE significance.",
    )
    parser.add_argument("--top-k", type=int, default=10, help="How many strongest lead edges to print.")
    parser.add_argument("--notes", default="", help="Short note stored in the output artifact.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entries = _read_pre_eval_log()
    latest = _latest_pre_eval_by_factor(entries)
    requested_factors = sorted(set(args.factor)) if args.factor else sorted(latest)
    missing = [factor for factor in requested_factors if factor not in latest]
    if missing:
        raise SystemExit(f"Missing latest pre-eval entries for: {', '.join(missing)}")

    series_by_factor: dict[str, dict[str, float]] = {}
    for factor in requested_factors:
        summary = _load_summary(Path(latest[factor]["summary_path"]))
        metric_series = build_metric_series(summary, metric=args.metric)
        if metric_series:
            series_by_factor[factor] = metric_series

    if len(series_by_factor) < 2:
        raise SystemExit("Need at least two factors with non-empty per-date metric series.")

    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"lead_{stamp}"
    run_dir = RUN_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "lead_factor_summary.json"

    summary = build_lead_factor_summary(
        series_by_factor,
        metric=args.metric,
        lag=args.lag,
        bins=None if args.bins <= 0 else args.bins,
        min_overlap=args.min_overlap,
        permutations=args.permutations,
        significance_threshold=args.significance_threshold,
        generated_at=created_at,
    )
    payload = {
        "lead_factor_id": run_id,
        "created_at": created_at,
        "notes": args.notes,
        **summary,
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    display_edges = payload["significant_ranked_edges"] or payload["ranked_edges"]
    for edge in display_edges[: args.top_k]:
        print(
            f"{edge['source_factor']}->{edge['target_factor']} "
            f"te={edge['transfer_entropy']:.6f} "
            f"p={edge['transfer_entropy_p_value'] if edge['transfer_entropy_p_value'] is not None else 'na'} "
            f"reverse={edge['reverse_transfer_entropy']:.6f} "
            f"gap={edge['lead_gap']:.6f} "
            f"obs={edge['observation_count']}"
        )
    print(f"summary_path={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
