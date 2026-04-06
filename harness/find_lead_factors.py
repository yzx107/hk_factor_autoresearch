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

from evaluation.transfer_entropy import transfer_entropy_summary

PRE_EVAL_LOG = ROOT / "registry" / "pre_eval_log.tsv"
RUN_ROOT = ROOT / "runs"

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


def build_lead_factor_summary(
    series_by_factor: dict[str, dict[str, float]],
    *,
    metric: str,
    lag: int,
    bins: int | None,
    min_overlap: int,
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
                    "transfer_entropy": forward.transfer_entropy,
                    "reverse_transfer_entropy": reverse.transfer_entropy,
                    "lead_gap": lead_gap,
                    "common_dates": common_dates,
                }
            )

    ranked_edges = sorted(edges, key=lambda item: item["lead_gap"], reverse=True)
    return {
        "metric": metric,
        "lag": lag,
        "bins": bins,
        "min_overlap": required_overlap,
        "factors": factors,
        "matrix": matrix,
        "ranked_edges": ranked_edges,
        "note": "Exploratory transfer-entropy scan only; not part of fixed pre-eval or promotion gates.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan latest pre-eval factor series with transfer entropy.")
    parser.add_argument("--factor", nargs="*", default=[], help="Optional factor subset. Defaults to all latest pre-evals.")
    parser.add_argument("--metric", default="rank_ic", help="Per-date metric to scan, for example rank_ic or nmi.")
    parser.add_argument("--lag", type=int, default=1, help="Lag used in transfer entropy.")
    parser.add_argument("--bins", type=int, default=0, help="Optional fixed bin count. Use 0 for adaptive bins.")
    parser.add_argument("--min-overlap", type=int, default=3, help="Minimum shared dates required per factor pair.")
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
    )
    payload = {
        "lead_factor_id": run_id,
        "created_at": created_at,
        "notes": args.notes,
        **summary,
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for edge in payload["ranked_edges"][: args.top_k]:
        print(
            f"{edge['source_factor']}->{edge['target_factor']} "
            f"te={edge['transfer_entropy']:.6f} "
            f"reverse={edge['reverse_transfer_entropy']:.6f} "
            f"gap={edge['lead_gap']:.6f} "
            f"obs={edge['observation_count']}"
        )
    print(f"summary_path={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
