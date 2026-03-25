"""Minimal significance interface."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev


@dataclass(frozen=True)
class SignificanceResult:
    method: str
    statistic: float
    passed: bool
    note: str


def simple_t_stat(values: list[float], threshold: float = 2.0) -> SignificanceResult:
    if len(values) < 2:
        return SignificanceResult(
            method="simple_t_stat",
            statistic=0.0,
            passed=False,
            note="Need at least two observations.",
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
    )
