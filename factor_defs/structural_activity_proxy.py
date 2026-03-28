"""Safe structural activity proxy example for Phase A."""

from __future__ import annotations

from typing import Iterable, Mapping


def structural_activity_proxy(rows: Iterable[Mapping[str, float]]) -> list[float]:
    """Use only structural fields admitted by the Phase A baseline."""
    scores: list[float] = []
    for row in rows:
        price = float(row["Price"])
        volume = float(row["Volume"])
        scores.append(price * volume)
    return scores
