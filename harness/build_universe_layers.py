"""Build Phase A universe layer maps from safe local sources."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
import tomllib
from typing import Any

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.daily_agg import available_daily_agg_dates, load_daily_agg_lazy
from harness.instrument_universe import DEFAULT_TARGET_INSTRUMENT_UNIVERSE

DEFAULT_CONFIG_PATH = ROOT / "configs" / "universe_layers_phase_a.toml"
DEFAULT_LAYER_ROOT = ROOT / "cache" / "universe_layers"
LAYER_VERSION = "universe_layers_phase_a_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase A universe layer map.")
    parser.add_argument("--year", required=True, help="Layer year, for example 2026.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Layer config TOML path.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing layer output.")
    parser.add_argument("--notes", default="", help="Short build note.")
    return parser.parse_args()


def load_layer_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    if payload.get("target_instrument_universe") != DEFAULT_TARGET_INSTRUMENT_UNIVERSE:
        raise ValueError("Universe layers currently support only stock_research_candidate targets.")
    return payload


def _resolve_path(value: str, *, year: str) -> Path:
    path = Path(value.format(year=year))
    return path if path.is_absolute() else ROOT / path


def _ensure_column(frame: pl.DataFrame, name: str, dtype: pl.DataType, default: Any = None) -> pl.DataFrame:
    if name in frame.columns:
        return frame
    return frame.with_columns(pl.lit(default, dtype=dtype).alias(name))


def _ensure_date(frame: pl.DataFrame, name: str) -> pl.DataFrame:
    frame = _ensure_column(frame, name, pl.Date)
    dtype = frame.schema[name]
    if dtype == pl.Date:
        return frame
    if dtype == pl.Datetime:
        return frame.with_columns(pl.col(name).dt.date().alias(name))
    return frame.with_columns(pl.col(name).cast(pl.Utf8).str.to_date(strict=False).alias(name))


def _max_date_or_default(frame: pl.DataFrame, column: str, fallback: date) -> date:
    if column not in frame.columns or frame.height == 0:
        return fallback
    value = frame.select(pl.col(column).max()).item()
    return value or fallback


def _empty_liquidity_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "instrument_key": pl.Utf8,
            "active_liquidity_days": pl.UInt32,
            "avg_daily_turnover_hkd": pl.Float64,
            "avg_daily_share_volume": pl.Float64,
            "avg_daily_trade_count": pl.Float64,
        }
    )


def build_liquidity_proxy_frame(frame: pl.DataFrame | None) -> pl.DataFrame:
    if frame is None or frame.height == 0:
        return _empty_liquidity_frame()
    frame = _ensure_date(frame, "date")
    for name in ("turnover", "share_volume", "trade_count"):
        frame = _ensure_column(frame, name, pl.Float64)
    return (
        frame.group_by("instrument_key")
        .agg(
            [
                pl.col("date").n_unique().alias("active_liquidity_days"),
                pl.col("turnover").mean().alias("avg_daily_turnover_hkd"),
                pl.col("share_volume").mean().alias("avg_daily_share_volume"),
                pl.col("trade_count").mean().alias("avg_daily_trade_count"),
            ]
        )
        .sort("instrument_key")
    )


def _load_liquidity_source(year: str, config: dict[str, Any]) -> tuple[pl.DataFrame | None, dict[str, Any]]:
    liquidity_config = config.get("liquidity", {})
    if liquidity_config.get("mode") != "daily_agg_if_available":
        return None, {"status": "disabled"}
    table = str(liquidity_config.get("table", "verified_trades_daily"))
    dates = available_daily_agg_dates(table, year)
    lookback = int(liquidity_config.get("lookback_trading_days", 60))
    selected_dates = dates[-lookback:] if lookback > 0 else dates
    if not selected_dates:
        return None, {"status": "missing", "table": table, "date_count": 0}
    frame = (
        load_daily_agg_lazy(
            table,
            selected_dates,
            ["date", "instrument_key", "turnover", "share_volume", "trade_count"],
        )
        .collect()
        .sort(["date", "instrument_key"])
    )
    return frame, {
        "status": "loaded",
        "table": table,
        "date_count": len(selected_dates),
        "date_min": selected_dates[0],
        "date_max": selected_dates[-1],
    }


def _quantile_or_none(series: pl.Series, quantile: float) -> float | None:
    clean = series.drop_nulls()
    if clean.len() == 0:
        return None
    value = clean.quantile(quantile, interpolation="linear")
    return None if value is None else float(value)


def _base_profile_frame(profile: pl.DataFrame, year: str) -> pl.DataFrame:
    fallback_asof = date(int(year), 12, 31)
    profile = _ensure_date(profile, "listing_date")
    profile = _ensure_date(profile, "as_of_date")
    profile = _ensure_date(profile, "market_cap_as_of_date")
    profile = _ensure_date(profile, "liquidity_as_of_date")
    profile = _ensure_date(profile, "southbound_as_of_date")
    for name, dtype, default in [
        ("instrument_key", pl.Utf8, ""),
        ("float_mktcap_hkd", pl.Float64, None),
        ("total_mktcap_hkd", pl.Float64, None),
        ("circulating_mktcap_hkd", pl.Float64, None),
        ("market_cap_source_label", pl.Utf8, ""),
        ("latest_turnover_hkd", pl.Float64, None),
        ("latest_volume_shares", pl.Float64, None),
        ("liquidity_source_label", pl.Utf8, ""),
        ("southbound_eligible", pl.Boolean, None),
        ("southbound_source_label", pl.Utf8, ""),
        ("observed_trades_days", pl.UInt32, 0),
        ("observed_orders_days", pl.UInt32, 0),
        ("instrument_family", pl.Utf8, "unknown"),
        ("stock_research_candidate", pl.Boolean, False),
    ]:
        profile = _ensure_column(profile, name, dtype, default)
    max_asof = _max_date_or_default(profile, "as_of_date", fallback_asof)
    return (
        profile.filter(pl.col("stock_research_candidate"))
        .with_columns(pl.col("as_of_date").fill_null(pl.lit(max_asof)).alias("layer_date"))
        .select(
            [
                "instrument_key",
                "layer_date",
                "listing_date",
                "float_mktcap_hkd",
                "total_mktcap_hkd",
                "circulating_mktcap_hkd",
                "market_cap_as_of_date",
                "market_cap_source_label",
                "latest_turnover_hkd",
                "latest_volume_shares",
                "liquidity_as_of_date",
                "liquidity_source_label",
                "southbound_eligible",
                "southbound_as_of_date",
                "southbound_source_label",
                "observed_trades_days",
                "observed_orders_days",
                "instrument_family",
                "stock_research_candidate",
            ]
        )
    )


def _newly_listed_frame(newly_listed: pl.DataFrame | None) -> pl.DataFrame:
    if newly_listed is None or newly_listed.height == 0:
        return pl.DataFrame(
            schema={
                "instrument_key": pl.Utf8,
                "newly_listing_date": pl.Date,
                "newly_listed_reference_included": pl.Boolean,
            }
        )
    frame = _ensure_date(newly_listed, "listing_date")
    frame = _ensure_column(frame, "universe_status", pl.Utf8, "included")
    return (
        frame.filter(pl.col("universe_status") == "included")
        .select(
            [
                "instrument_key",
                pl.col("listing_date").alias("newly_listing_date"),
                pl.lit(True).alias("newly_listed_reference_included"),
            ]
        )
        .unique("instrument_key")
    )


def build_universe_layer_frame(
    profile: pl.DataFrame,
    *,
    year: str,
    config: dict[str, Any],
    newly_listed: pl.DataFrame | None = None,
    liquidity: pl.DataFrame | None = None,
    source_trace: dict[str, Any] | None = None,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    thresholds = config.get("thresholds", {})
    liquidity_config = config.get("liquidity", {})
    early_days = int(thresholds.get("early_listing_days", 90))
    recent_days = int(thresholds.get("recent_listing_days", 365))
    min_observed_trades = int(thresholds.get("min_observed_trades_days", 20))
    min_observed_orders = int(thresholds.get("min_observed_orders_days", 20))
    min_liquidity_days = int(liquidity_config.get("min_liquidity_days", 20))

    base = _base_profile_frame(profile, year)
    newly = _newly_listed_frame(newly_listed)
    liquidity_proxy = build_liquidity_proxy_frame(liquidity)
    liquidity_loaded = liquidity is not None and liquidity.height > 0
    trace_json = json.dumps(source_trace or {}, ensure_ascii=False, sort_keys=True)

    frame = (
        base.join(newly, on="instrument_key", how="left")
        .join(liquidity_proxy, on="instrument_key", how="left")
        .with_columns(
            [
                pl.col("newly_listed_reference_included").fill_null(False),
                pl.col("active_liquidity_days").fill_null(0),
                pl.coalesce(["newly_listing_date", "listing_date"]).alias("effective_listing_date"),
                pl.coalesce(["circulating_mktcap_hkd", "total_mktcap_hkd", "float_mktcap_hkd"]).alias(
                    "size_proxy_hkd"
                ),
                pl.coalesce(["avg_daily_turnover_hkd", "latest_turnover_hkd"]).alias("liquidity_proxy_hkd"),
            ]
        )
        .with_columns(
            [
                (pl.col("layer_date") - pl.col("effective_listing_date")).dt.total_days().alias("listing_age_days"),
                pl.when(pl.col("avg_daily_turnover_hkd").is_not_null())
                .then(pl.lit("avg_daily_turnover_hkd"))
                .when(pl.col("latest_turnover_hkd").is_not_null())
                .then(pl.lit("latest_turnover_hkd"))
                .otherwise(pl.lit("missing"))
                .alias("liquidity_proxy_source"),
                pl.when(pl.col("circulating_mktcap_hkd").is_not_null())
                .then(pl.lit("circulating_mktcap_hkd"))
                .when(pl.col("total_mktcap_hkd").is_not_null())
                .then(pl.lit("total_mktcap_hkd"))
                .when(pl.col("float_mktcap_hkd").is_not_null())
                .then(pl.lit("float_mktcap_hkd"))
                .otherwise(pl.lit("missing"))
                .alias("size_proxy_source"),
            ]
        )
    )

    tradability_proxy = pl.coalesce(["liquidity_proxy_hkd", "size_proxy_hkd"])
    frame = frame.with_columns(tradability_proxy.alias("tradability_proxy_hkd"))
    large_cutoff = _quantile_or_none(
        frame.get_column("tradability_proxy_hkd"),
        float(thresholds.get("large_liquidity_quantile", 0.80)),
    )
    small_cutoff = _quantile_or_none(
        frame.get_column("tradability_proxy_hkd"),
        float(thresholds.get("small_liquidity_quantile", 0.30)),
    )

    sparse_expr = (
        (pl.lit(liquidity_loaded) & (pl.col("active_liquidity_days") < min_liquidity_days))
        | (pl.col("observed_trades_days") < min_observed_trades)
        | (pl.col("observed_orders_days") < min_observed_orders)
    )
    primary_expr = (
        pl.when(pl.col("listing_age_days").is_not_null() & (pl.col("listing_age_days") <= recent_days))
        .then(pl.lit("new_or_recent_listing"))
        .when(sparse_expr)
        .then(pl.lit("small_illiquid_special"))
        .when(pl.col("tradability_proxy_hkd").is_null())
        .then(pl.lit("unknown"))
    )
    if large_cutoff is not None:
        primary_expr = primary_expr.when(pl.col("tradability_proxy_hkd") >= large_cutoff).then(
            pl.lit("large_liquid_core")
        )
    if small_cutoff is not None:
        primary_expr = primary_expr.when(pl.col("tradability_proxy_hkd") <= small_cutoff).then(
            pl.lit("small_illiquid_special")
        )
    primary_expr = primary_expr.otherwise(pl.lit("mid_liquid_tradable")).alias("primary_tradability_layer")

    frame = (
        frame.with_columns(
            [
                primary_expr,
                pl.when(pl.col("listing_age_days").is_null())
                .then(pl.lit("unknown"))
                .when(pl.col("listing_age_days") <= early_days)
                .then(pl.lit("new_0_90d"))
                .when(pl.col("listing_age_days") <= recent_days)
                .then(pl.lit("recent_91_365d"))
                .otherwise(pl.lit("mature_365d_plus"))
                .alias("listing_age_bucket"),
                pl.col("southbound_eligible").is_not_null().alias("southbound_eligible_known"),
                pl.col("southbound_eligible").fill_null(False),
                pl.lit("source_missing").alias("southbound_active_proxy"),
                pl.lit(False).alias("chapter_18a_biotech"),
                pl.lit(False).alias("chapter_18c_specialist_tech"),
                pl.lit("source_missing").alias("index_flow_bucket"),
                pl.lit(False).alias("cas_eligible"),
                pl.lit(False).alias("shortsell_or_options_eligible"),
                pl.lit(False).alias("top_of_book_bounded_ready"),
                pl.col("layer_date").alias("source_asof_date"),
                pl.lit(str(config.get("version", LAYER_VERSION))).alias("layer_version"),
                pl.lit(trace_json).alias("source_trace_json"),
            ]
        )
        .with_columns(
            (
                (pl.col("primary_tradability_layer") == "small_illiquid_special")
                & (~pl.col("southbound_eligible"))
            ).alias("legacy_illiquid_risk_proxy")
        )
        .select(
            [
                "instrument_key",
                "layer_date",
                "primary_tradability_layer",
                "listing_age_bucket",
                "southbound_eligible",
                "southbound_eligible_known",
                "southbound_active_proxy",
                "chapter_18a_biotech",
                "chapter_18c_specialist_tech",
                "index_flow_bucket",
                "cas_eligible",
                "shortsell_or_options_eligible",
                "legacy_illiquid_risk_proxy",
                "top_of_book_bounded_ready",
                "source_asof_date",
                "layer_version",
                "source_trace_json",
                "listing_age_days",
                "effective_listing_date",
                "tradability_proxy_hkd",
                "liquidity_proxy_hkd",
                "liquidity_proxy_source",
                "size_proxy_hkd",
                "size_proxy_source",
                "market_cap_as_of_date",
                "market_cap_source_label",
                "latest_turnover_hkd",
                "latest_volume_shares",
                "liquidity_as_of_date",
                "liquidity_source_label",
                "southbound_as_of_date",
                "southbound_source_label",
                "active_liquidity_days",
                "avg_daily_turnover_hkd",
                "avg_daily_share_volume",
                "avg_daily_trade_count",
            ]
        )
        .sort("instrument_key")
    )

    diagnostics = {
        "large_liquidity_cutoff": large_cutoff,
        "small_liquidity_cutoff": small_cutoff,
        "liquidity_source_loaded": liquidity_loaded,
        "liquidity_input_rows": 0 if liquidity is None else liquidity.height,
    }
    return frame, diagnostics


def summarize_universe_layers(
    frame: pl.DataFrame,
    *,
    year: str,
    config: dict[str, Any],
    source_paths: dict[str, str],
    diagnostics: dict[str, Any],
    notes: str = "",
) -> dict[str, Any]:
    coverage_by_layer = {
        row["primary_tradability_layer"]: row["len"]
        for row in frame.group_by("primary_tradability_layer").len().sort("primary_tradability_layer").to_dicts()
    }
    overlay_booleans = [
        "southbound_eligible",
        "chapter_18a_biotech",
        "chapter_18c_specialist_tech",
        "cas_eligible",
        "shortsell_or_options_eligible",
        "legacy_illiquid_risk_proxy",
        "top_of_book_bounded_ready",
    ]
    coverage_by_overlay = {name: int(frame.select(pl.col(name).sum()).item()) for name in overlay_booleans}
    unknown_counts = {
        "primary_tradability_layer_unknown": int(
            frame.filter(pl.col("primary_tradability_layer") == "unknown").height
        ),
        "listing_age_bucket_unknown": int(frame.filter(pl.col("listing_age_bucket") == "unknown").height),
        "liquidity_proxy_missing": int(frame.filter(pl.col("liquidity_proxy_source") == "missing").height),
        "size_proxy_missing": int(frame.filter(pl.col("size_proxy_source") == "missing").height),
        "tradability_proxy_missing": int(frame.filter(pl.col("tradability_proxy_hkd").is_null()).height),
        "southbound_eligible_unknown": int(frame.filter(~pl.col("southbound_eligible_known")).height),
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "year": year,
        "layer_version": str(config.get("version", LAYER_VERSION)),
        "source_paths": source_paths,
        "threshold_config": config.get("thresholds", {}),
        "liquidity_config": config.get("liquidity", {}),
        "row_count": frame.height,
        "coverage_by_layer": coverage_by_layer,
        "coverage_by_overlay": coverage_by_overlay,
        "unknown_counts": unknown_counts,
        "diagnostics": diagnostics,
        "notes": notes,
    }


def build_universe_layers_for_year(
    *,
    year: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
    force: bool = False,
    notes: str = "",
) -> tuple[str, dict[str, Any], Path]:
    config = load_layer_config(config_path)
    paths = config.get("paths", {})
    profile_path = _resolve_path(str(paths["instrument_profile"]), year=year)
    newly_path = _resolve_path(str(paths["newly_listed_hk_template"]), year=year)
    output_root = _resolve_path(str(paths.get("output_root", DEFAULT_LAYER_ROOT)), year=year)
    output_dir = output_root / f"year={year}"
    output_path = output_dir / f"universe_layers_{year}.parquet"
    manifest_path = output_dir / f"universe_layers_{year}_manifest.json"
    if output_path.exists() and not force:
        raise FileExistsError(f"Universe layer output already exists: {output_path}")

    profile = pl.read_parquet(profile_path)
    newly = pl.read_parquet(newly_path) if newly_path.exists() else None
    liquidity, liquidity_trace = _load_liquidity_source(year, config)
    source_paths = {
        "instrument_profile": str(profile_path),
        "newly_listed_hk": str(newly_path) if newly_path.exists() else "",
        "liquidity_source": json.dumps(liquidity_trace, ensure_ascii=False, sort_keys=True),
    }
    frame, diagnostics = build_universe_layer_frame(
        profile,
        year=year,
        config=config,
        newly_listed=newly,
        liquidity=liquidity,
        source_trace=source_paths,
    )
    manifest = summarize_universe_layers(
        frame,
        year=year,
        config=config,
        source_paths=source_paths,
        diagnostics=diagnostics | {"liquidity_trace": liquidity_trace},
        notes=notes,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(output_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    build_id = f"universe_layers_{year}_{config.get('version', LAYER_VERSION)}"
    return build_id, manifest, output_path


def main() -> int:
    args = parse_args()
    build_id, manifest, output_path = build_universe_layers_for_year(
        year=args.year,
        config_path=Path(args.config),
        force=args.force,
        notes=args.notes,
    )
    print(
        f"{build_id} rows={manifest['row_count']} "
        f"layers={json.dumps(manifest['coverage_by_layer'], ensure_ascii=False, sort_keys=True)} "
        f"output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
