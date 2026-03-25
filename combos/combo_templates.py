"""Minimal combination helpers."""

from __future__ import annotations


def equal_weight_average(signal_matrix: list[list[float]]) -> list[float]:
    if not signal_matrix:
        return []

    width = len(signal_matrix[0])
    if any(len(row) != width for row in signal_matrix):
        raise ValueError("All signals must have the same length.")

    combined: list[float] = []
    for index in range(width):
        column_total = 0.0
        for signal in signal_matrix:
            column_total += signal[index]
        combined.append(column_total / len(signal_matrix))
    return combined
