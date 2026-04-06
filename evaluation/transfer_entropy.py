"""Transfer-entropy helpers for exploratory lead-lag analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import fsum, log

from evaluation.metrics import adaptive_bin_count, equal_frequency_bins


@dataclass(frozen=True)
class TransferEntropySummary:
    transfer_entropy: float
    effective_bin_count: int
    lag: int
    observation_count: int


def _prepare_triplets(
    source: list[float],
    target: list[float],
    *,
    lag: int,
) -> tuple[list[float], list[float], list[float]]:
    if len(source) != len(target):
        raise ValueError("source and target must have the same length.")
    if lag < 1:
        raise ValueError("lag must be >= 1.")
    if len(source) <= lag:
        return [], [], []
    return (
        [float(value) for value in source[:-lag]],
        [float(value) for value in target[lag - 1 : -1]],
        [float(value) for value in target[lag:]],
    )


def transfer_entropy_summary(
    source: list[float],
    target: list[float],
    *,
    lag: int = 1,
    bins: int | None = None,
    min_bins: int = 2,
    max_bins: int = 8,
) -> TransferEntropySummary:
    source_lagged, target_past, target_present = _prepare_triplets(source, target, lag=lag)
    observation_count = len(target_present)
    if observation_count <= 1:
        return TransferEntropySummary(
            transfer_entropy=0.0,
            effective_bin_count=1,
            lag=lag,
            observation_count=observation_count,
        )

    requested_bins = (
        adaptive_bin_count(observation_count, minimum=min_bins, maximum=max_bins)
        if bins is None
        else max(2, bins)
    )
    source_bins, source_effective = equal_frequency_bins(source_lagged, requested_bins)
    target_past_bins, target_past_effective = equal_frequency_bins(target_past, requested_bins)
    target_present_bins, target_present_effective = equal_frequency_bins(target_present, requested_bins)
    effective_bins = min(source_effective, target_past_effective, target_present_effective)

    xyz_counts = Counter(zip(target_present_bins, target_past_bins, source_bins))
    yx_counts = Counter(zip(target_past_bins, source_bins))
    yy_counts = Counter(zip(target_present_bins, target_past_bins))
    y_counts = Counter(target_past_bins)

    transfer_entropy_value = fsum(
        (xyz_count / observation_count)
        * log(
            (xyz_count * y_counts[target_past_bin])
            / (yx_counts[(target_past_bin, source_bin)] * yy_counts[(target_present_bin, target_past_bin)])
        )
        for (target_present_bin, target_past_bin, source_bin), xyz_count in xyz_counts.items()
        if xyz_count > 0
        and yx_counts[(target_past_bin, source_bin)] > 0
        and yy_counts[(target_present_bin, target_past_bin)] > 0
        and y_counts[target_past_bin] > 0
    )

    return TransferEntropySummary(
        transfer_entropy=transfer_entropy_value,
        effective_bin_count=effective_bins,
        lag=lag,
        observation_count=observation_count,
    )


def transfer_entropy(
    source: list[float],
    target: list[float],
    *,
    lag: int = 1,
    bins: int | None = None,
    min_bins: int = 2,
    max_bins: int = 8,
) -> float:
    return transfer_entropy_summary(
        source,
        target,
        lag=lag,
        bins=bins,
        min_bins=min_bins,
        max_bins=max_bins,
    ).transfer_entropy
