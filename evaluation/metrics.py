"""Minimal evaluation metric helpers."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev


@dataclass(frozen=True)
class MetricSummary:
    count: int
    mean: float
    std: float


def summarize_series(values: list[float]) -> MetricSummary:
    if not values:
        return MetricSummary(count=0, mean=0.0, std=0.0)
    std = pstdev(values) if len(values) > 1 else 0.0
    return MetricSummary(count=len(values), mean=mean(values), std=std)
