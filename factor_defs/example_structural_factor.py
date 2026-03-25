"""Minimal example factor definition using structural fields only."""

from __future__ import annotations

from typing import Iterable, Mapping


def price_times_volume(rows: Iterable[Mapping[str, float]]) -> list[float]:
    scores: list[float] = []
    for row in rows:
        price = float(row["Price"])
        volume = float(row["Volume"])
        scores.append(price * volume)
    return scores
