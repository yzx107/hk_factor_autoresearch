"""Read-only helpers for target-instrument universe filtering.

The default harness only supports stock targets. Future cross-security
source lanes should be wired explicitly above this layer instead of
reusing the target-universe filter as an implicit mixed-security join.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl


INSTRUMENT_PROFILE_PATH = Path("/Volumes/Data/港股Tick数据/reference/instrument_profile/latest/instrument_profile.parquet")
DEFAULT_TARGET_INSTRUMENT_UNIVERSE = "stock_research_candidate"
DEFAULT_SOURCE_INSTRUMENT_UNIVERSE = "target_only"
SUPPORTED_TARGET_INSTRUMENT_UNIVERSES = {
    DEFAULT_TARGET_INSTRUMENT_UNIVERSE,
}


def load_target_instrument_universe_lazy(target_instrument_universe: str) -> pl.LazyFrame:
    if target_instrument_universe not in SUPPORTED_TARGET_INSTRUMENT_UNIVERSES:
        allowed = ", ".join(sorted(SUPPORTED_TARGET_INSTRUMENT_UNIVERSES))
        raise ValueError(f"Unsupported target instrument universe `{target_instrument_universe}`. Allowed: {allowed}.")
    if not INSTRUMENT_PROFILE_PATH.exists():
        raise FileNotFoundError(f"Instrument profile sidecar not found: {INSTRUMENT_PROFILE_PATH}")

    scan = pl.scan_parquet(str(INSTRUMENT_PROFILE_PATH))
    if target_instrument_universe == "stock_research_candidate":
        return (
            scan.select(["instrument_key", "stock_research_candidate"])
            .filter(pl.col("stock_research_candidate"))
            .select("instrument_key")
        )
    raise AssertionError(f"Unhandled target instrument universe `{target_instrument_universe}`.")


def apply_target_instrument_universe_filter(
    frame: pl.LazyFrame,
    *,
    target_instrument_universe: str,
    instrument_key_column: str = "instrument_key",
    allowed_instruments: pl.LazyFrame | None = None,
) -> pl.LazyFrame:
    if not target_instrument_universe:
        return frame
    allowed = (
        allowed_instruments
        if allowed_instruments is not None
        else load_target_instrument_universe_lazy(target_instrument_universe)
    )
    return frame.join(
        allowed.select(pl.col("instrument_key").alias(instrument_key_column)),
        on=instrument_key_column,
        how="semi",
    )
