"""Minimal robustness interface."""

from __future__ import annotations


def sign_consistency(values: list[float]) -> float:
    if not values:
        return 0.0
    positives = sum(1 for value in values if value > 0)
    negatives = sum(1 for value in values if value < 0)
    return max(positives, negatives) / len(values)


def bucket_means(observations: dict[str, list[float]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, values in observations.items():
        if not values:
            result[key] = 0.0
        else:
            result[key] = sum(values) / len(values)
    return result
