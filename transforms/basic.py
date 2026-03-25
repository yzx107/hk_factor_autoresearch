"""Minimal transform helpers with no external dependencies."""

from __future__ import annotations

from statistics import mean, pstdev


def clip(values: list[float], lower: float, upper: float) -> list[float]:
    return [min(max(value, lower), upper) for value in values]


def zscore(values: list[float]) -> list[float]:
    if not values:
        return []
    sigma = pstdev(values)
    if sigma == 0:
        return [0.0 for _ in values]
    mu = mean(values)
    return [(value - mu) / sigma for value in values]
