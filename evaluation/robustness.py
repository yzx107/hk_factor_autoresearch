"""Lightweight robustness helpers shared by Gate B and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum


@dataclass(frozen=True)
class SignSummary:
    evaluated_count: int
    signed_count: int
    positive_count: int
    negative_count: int
    zero_count: int
    dominant_sign: str
    sign_consistency: float | None
    sign_switch_count: int


def summarize_signs(values: list[float | None]) -> SignSummary:
    valid_values = [float(value) for value in values if value is not None]
    signed_values = [value for value in valid_values if value != 0.0]
    positive_count = sum(1 for value in signed_values if value > 0.0)
    negative_count = sum(1 for value in signed_values if value < 0.0)
    zero_count = len(valid_values) - len(signed_values)

    if positive_count == 0 and negative_count == 0:
        dominant_sign = "none"
        consistency = None
    elif positive_count >= negative_count:
        dominant_sign = "positive"
        consistency = positive_count / len(signed_values)
    else:
        dominant_sign = "negative"
        consistency = negative_count / len(signed_values)

    sign_switch_count = 0
    previous_sign = 0
    for value in valid_values:
        current_sign = 1 if value > 0.0 else -1 if value < 0.0 else 0
        if current_sign == 0:
            continue
        if previous_sign != 0 and current_sign != previous_sign:
            sign_switch_count += 1
        previous_sign = current_sign

    return SignSummary(
        evaluated_count=len(valid_values),
        signed_count=len(signed_values),
        positive_count=positive_count,
        negative_count=negative_count,
        zero_count=zero_count,
        dominant_sign=dominant_sign,
        sign_consistency=consistency,
        sign_switch_count=sign_switch_count,
    )


def sign_consistency(values: list[float]) -> float:
    summary = summarize_signs(values)
    return 0.0 if summary.sign_consistency is None else summary.sign_consistency


def bucket_means(observations: dict[str, list[float | None]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, values in observations.items():
        valid_values = [float(value) for value in values if value is not None]
        if not valid_values:
            result[key] = 0.0
        else:
            result[key] = fsum(valid_values) / len(valid_values)
    return result


def bucket_spread(observations: dict[str, list[float | None]]) -> float | None:
    means = list(bucket_means(observations).values())
    if not means:
        return None
    return max(means) - min(means)
