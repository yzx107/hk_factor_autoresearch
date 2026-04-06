"""Evaluation metric helpers shared by pre-eval and diagnostics."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import ceil, fsum, log, log2
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


@dataclass(frozen=True)
class MutualInformationSummary:
    mutual_information: float | None
    normalized_mutual_information: float | None
    effective_bin_count: int
    score_entropy: float
    label_entropy: float


def effective_bin_count(row_count: int, requested_bins: int) -> int:
    if requested_bins < 2:
        raise ValueError("requested_bins must be >= 2.")
    if row_count <= 1:
        return 1
    # Keep at least two observations per bin whenever possible; singleton bins
    # make small-sample MI artificially rigid and flatten permutation baselines.
    occupancy_cap = max(2, row_count // 2)
    return max(2, min(requested_bins, row_count, occupancy_cap))


def adaptive_bin_count(
    row_count: int,
    *,
    minimum: int = 4,
    maximum: int = 16,
) -> int:
    if minimum < 2:
        raise ValueError("minimum must be >= 2.")
    if maximum < minimum:
        raise ValueError("maximum must be >= minimum.")
    if row_count <= 1:
        return 1
    proposed = ceil(1.0 + log2(row_count))
    bounded = max(minimum, min(proposed, maximum))
    return effective_bin_count(row_count, bounded)


def equal_frequency_bins(values: list[float], requested_bins: int) -> tuple[list[int], int]:
    effective_bins = effective_bin_count(len(values), requested_bins)
    if effective_bins <= 1:
        return [0 for _ in values], effective_bins
    order = sorted(range(len(values)), key=lambda idx: (values[idx], idx))
    bins = [0 for _ in values]
    for rank, idx in enumerate(order):
        bins[idx] = min((rank * effective_bins) // len(values), effective_bins - 1)
    return bins, effective_bins


def entropy(counts: Counter[int], total: int) -> float:
    if total <= 0:
        return 0.0
    return -fsum((count / total) * log(count / total) for count in counts.values() if count > 0)


def mutual_information_metrics(
    score_values: list[float],
    label_values: list[float],
    *,
    requested_bins: int,
) -> MutualInformationSummary:
    if len(score_values) != len(label_values):
        raise ValueError("score_values and label_values must have the same length.")
    if len(score_values) <= 1:
        return MutualInformationSummary(
            mutual_information=None,
            normalized_mutual_information=None,
            effective_bin_count=1,
            score_entropy=0.0,
            label_entropy=0.0,
        )

    score_bins, score_effective = equal_frequency_bins(score_values, requested_bins)
    label_bins, label_effective = equal_frequency_bins(label_values, requested_bins)
    effective_bins = min(score_effective, label_effective)
    total = len(score_values)

    score_counts = Counter(score_bins)
    label_counts = Counter(label_bins)
    joint_counts = Counter(zip(score_bins, label_bins))

    score_entropy = entropy(score_counts, total)
    label_entropy = entropy(label_counts, total)
    if score_entropy <= 0.0 or label_entropy <= 0.0:
        return MutualInformationSummary(
            mutual_information=0.0,
            normalized_mutual_information=0.0,
            effective_bin_count=effective_bins,
            score_entropy=score_entropy,
            label_entropy=label_entropy,
        )

    mutual_info = fsum(
        (joint_count / total)
        * log((joint_count * total) / (score_counts[score_bin] * label_counts[label_bin]))
        for (score_bin, label_bin), joint_count in joint_counts.items()
        if joint_count > 0
    )
    normalized_mutual_info = mutual_info / max(score_entropy, label_entropy)
    return MutualInformationSummary(
        mutual_information=mutual_info,
        normalized_mutual_information=normalized_mutual_info,
        effective_bin_count=effective_bins,
        score_entropy=score_entropy,
        label_entropy=label_entropy,
    )
