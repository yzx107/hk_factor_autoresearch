"""Minimal significance interface."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from random import Random
from statistics import mean, pstdev

from evaluation.metrics import mutual_information_metrics


@dataclass(frozen=True)
class SignificanceResult:
    method: str
    statistic: float
    passed: bool
    note: str
    p_value: float | None = None
    threshold: float | None = None
    null_mean: float | None = None
    null_std: float | None = None


def permutation_significance(
    observed_value: float,
    null_values: list[float],
    *,
    threshold: float = 0.05,
    method: str = "permutation_test",
    note: str = "Permutation baseline significance test.",
) -> SignificanceResult:
    if threshold <= 0.0 or threshold >= 1.0:
        raise ValueError("threshold must be in (0, 1).")
    if not null_values:
        return SignificanceResult(
            method=method,
            statistic=observed_value,
            passed=False,
            note="Need at least one null draw.",
            p_value=None,
            threshold=threshold,
            null_mean=None,
            null_std=None,
        )

    extreme_count = sum(1 for value in null_values if value >= observed_value)
    p_value = (extreme_count + 1.0) / (len(null_values) + 1.0)
    null_mean = mean(null_values)
    null_std = pstdev(null_values) if len(null_values) > 1 else 0.0
    return SignificanceResult(
        method=method,
        statistic=observed_value,
        passed=p_value <= threshold,
        note=note,
        p_value=p_value,
        threshold=threshold,
        null_mean=null_mean,
        null_std=null_std,
    )


def simple_t_stat(values: list[float], threshold: float = 2.0) -> SignificanceResult:
    if len(values) < 2:
        return SignificanceResult(
            method="simple_t_stat",
            statistic=0.0,
            passed=False,
            note="Need at least two observations.",
            threshold=threshold,
        )

    std = pstdev(values)
    if std == 0:
        statistic = 0.0
    else:
        statistic = mean(values) / (std / sqrt(len(values)))

    return SignificanceResult(
        method="simple_t_stat",
        statistic=statistic,
        passed=abs(statistic) >= threshold,
        note="Placeholder only. Phase A does not claim Newey-West support yet.",
        threshold=threshold,
    )


def mutual_information_permutation_test(
    score_values: list[float],
    label_values: list[float],
    *,
    requested_bins: int,
    permutations: int = 100,
    seed: int = 0,
    p_value_threshold: float = 0.05,
) -> SignificanceResult:
    if len(score_values) != len(label_values):
        raise ValueError("score_values and label_values must have the same length.")
    if permutations < 1:
        raise ValueError("permutations must be >= 1.")
    if len(score_values) <= 1:
        return SignificanceResult(
            method="mi_permutation_test_v1",
            statistic=0.0,
            passed=False,
            note="Need at least two observations.",
            p_value=None,
            threshold=p_value_threshold,
        )

    observed = mutual_information_metrics(
        score_values,
        label_values,
        requested_bins=requested_bins,
    ).mutual_information
    observed_value = 0.0 if observed is None else observed

    rng = Random(seed)
    null_values: list[float] = []
    for _ in range(permutations):
        shuffled = list(score_values)
        rng.shuffle(shuffled)
        null_summary = mutual_information_metrics(
            shuffled,
            label_values,
            requested_bins=requested_bins,
        )
        null_values.append(0.0 if null_summary.mutual_information is None else null_summary.mutual_information)

    return permutation_significance(
        observed_value,
        null_values,
        threshold=p_value_threshold,
        method="mi_permutation_test_v1",
        note="Permutation baseline for mutual-information bias control.",
    )
