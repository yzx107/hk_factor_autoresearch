"""Read-only helpers for target-instrument universe filtering.

The default harness only supports stock targets. Future cross-security
source lanes should be wired explicitly above this layer instead of
reusing the target-universe filter as an implicit mixed-security join.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl


UPSTREAM_LAB_ROOT = Path("/Users/yxin/AI_Workstation/Hshare_Lab_v2")
INSTRUMENT_PROFILE_PATH = Path("/Volumes/Data/港股Tick数据/reference/instrument_profile/latest/instrument_profile.parquet")
DEFAULT_TARGET_INSTRUMENT_UNIVERSE = "stock_research_candidate"
DEFAULT_SOURCE_INSTRUMENT_UNIVERSE = "target_only"
UNIVERSE_FILTER_VERSION = "stock_research_candidate_filter_v1"
SUPPORTED_TARGET_INSTRUMENT_UNIVERSES = {
    DEFAULT_TARGET_INSTRUMENT_UNIVERSE,
}


def require_target_instrument_universe(target_instrument_universe: str) -> str:
    value = str(target_instrument_universe or "").strip()
    if not value:
        raise ValueError(
            "target_instrument_universe is required. "
            f"Set it explicitly or use `{DEFAULT_TARGET_INSTRUMENT_UNIVERSE}`."
        )
    return value


def instrument_profile_summary_path(path: Path = INSTRUMENT_PROFILE_PATH) -> Path:
    return path.with_name("summary.json")


def instrument_profile_bootstrap_message(path: Path = INSTRUMENT_PROFILE_PATH) -> str:
    return (
        f"Instrument profile sidecar not found: {path}\n"
        "Bootstrap it from the upstream lab repo, for example:\n"
        f"  cd {UPSTREAM_LAB_ROOT}\n"
        "  python -m Scripts.build_instrument_profile --years 2025,2026\n"
        "If you want to sanity-check the builder first, run:\n"
        f"  cd {UPSTREAM_LAB_ROOT}\n"
        "  python -m Scripts.build_instrument_profile --print-plan"
    )


def ensure_instrument_profile_sidecar(path: Path = INSTRUMENT_PROFILE_PATH) -> Path:
    if not path.exists():
        raise FileNotFoundError(instrument_profile_bootstrap_message(path))
    return path


def bootstrap_instrument_universe_status(path: Path = INSTRUMENT_PROFILE_PATH) -> dict[str, object]:
    summary_path = instrument_profile_summary_path(path)
    return {
        "exists": path.exists(),
        "instrument_profile_path": str(path),
        "summary_path": str(summary_path),
        "target_instrument_universe": DEFAULT_TARGET_INSTRUMENT_UNIVERSE,
        "source_instrument_universe": DEFAULT_SOURCE_INSTRUMENT_UNIVERSE,
        "contains_cross_security_source": False,
        "universe_filter_version": UNIVERSE_FILTER_VERSION,
        "build_command": f"cd {UPSTREAM_LAB_ROOT} && python -m Scripts.build_instrument_profile --years 2025,2026",
        "plan_command": f"cd {UPSTREAM_LAB_ROOT} && python -m Scripts.build_instrument_profile --print-plan",
    }


def load_target_instrument_universe_lazy(target_instrument_universe: str) -> pl.LazyFrame:
    target_instrument_universe = require_target_instrument_universe(target_instrument_universe)
    if target_instrument_universe not in SUPPORTED_TARGET_INSTRUMENT_UNIVERSES:
        allowed = ", ".join(sorted(SUPPORTED_TARGET_INSTRUMENT_UNIVERSES))
        raise ValueError(f"Unsupported target instrument universe `{target_instrument_universe}`. Allowed: {allowed}.")
    scan = pl.scan_parquet(str(ensure_instrument_profile_sidecar(INSTRUMENT_PROFILE_PATH)))
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
    target_instrument_universe = require_target_instrument_universe(target_instrument_universe)
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
