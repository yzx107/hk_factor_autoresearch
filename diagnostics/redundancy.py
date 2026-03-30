"""Baseline redundancy helpers for fixed factor scoreboards."""

from __future__ import annotations

from math import fsum
from pathlib import Path
import tomllib
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASELINE_REGISTRY = ROOT / "baselines" / "baseline_registry.toml"


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return fsum(values) / len(values)


def load_baseline_registry(path: Path = BASELINE_REGISTRY) -> dict[str, Any]:
    if not path.exists():
        return {
            "version": "missing",
            "name": "missing",
            "owner": "",
            "status": "missing",
            "default_baselines": [],
            "groups": {},
            "path": str(path),
        }

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    data["default_baselines"] = list(data.get("default_baselines", []))
    data["groups"] = dict(data.get("groups", {}))
    data["path"] = str(path)
    return data


def baseline_group_for_factor(factor_name: str, registry: dict[str, Any]) -> str:
    for group_name, payload in registry.get("groups", {}).items():
        factors = payload.get("factors", [])
        if factor_name in factors:
            return group_name
    return ""


def derive_baseline_metrics(
    *,
    factor_name: str,
    comparison_rows: list[dict[str, Any]],
    baseline_factors: list[str],
) -> dict[str, Any]:
    if factor_name in baseline_factors:
        return {
            "baseline_role": "baseline_anchor",
            "baseline_peer_count": max(0, len(baseline_factors) - 1),
            "mean_abs_baseline_corr": None,
            "mean_baseline_top_overlap": None,
        }

    corr_values: list[float] = []
    overlap_values: list[float] = []
    compared = 0
    baseline_set = set(baseline_factors)

    for row in comparison_rows:
        left = row["left_factor"]
        right = row["right_factor"]
        pair = {left, right}
        if factor_name not in pair:
            continue
        peer = right if left == factor_name else left
        if peer not in baseline_set:
            continue
        compared += 1
        corr_values.extend(
            abs(item["pearson_corr"])
            for item in row["per_date_corr"]
            if item["pearson_corr"] is not None
        )
        overlap_values.extend(float(item["top_overlap_count"]) for item in row["top_overlap"])

    return {
        "baseline_role": "challenger",
        "baseline_peer_count": compared,
        "mean_abs_baseline_corr": _average(corr_values),
        "mean_baseline_top_overlap": _average(overlap_values),
    }


def classify_incremental_hint(
    *,
    baseline_role: str,
    mean_abs_rank_ic: float | None,
    mean_abs_baseline_corr: float | None,
) -> str:
    if baseline_role == "baseline_anchor":
        return "baseline_anchor"
    if mean_abs_rank_ic is None:
        return "missing_pre_eval"
    if mean_abs_baseline_corr is None:
        return "missing_baseline_compare"
    if mean_abs_rank_ic >= 0.05 and mean_abs_baseline_corr <= 0.35:
        return "potential_incremental"
    if mean_abs_baseline_corr >= 0.85:
        return "likely_redundant"
    if mean_abs_baseline_corr >= 0.60:
        return "review_overlap"
    return "mixed"
