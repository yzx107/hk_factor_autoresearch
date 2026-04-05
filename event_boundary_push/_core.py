"""Core helpers for the event-driven boundary push module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
import json
from pathlib import Path
import sys
import tomllib
from typing import Any

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VALID_DAILY_TABLES = {"verified_trades_daily", "verified_orders_daily"}


def _preview_rows(frame: pl.DataFrame, limit: int = 5) -> list[dict[str, Any]]:
    rows = frame.head(limit).to_dicts()
    for row in rows:
        for key, value in list(row.items()):
            if isinstance(value, date_type):
                row[key] = value.isoformat()
    return rows


def _numeric_summary(frame: pl.DataFrame, columns: list[str]) -> dict[str, dict[str, float]]:
    payload: dict[str, dict[str, float]] = {}
    for column in columns:
        if column not in frame.columns:
            continue
        values = [float(value) for value in frame[column].to_list() if value is not None]
        if not values:
            continue
        payload[column] = {
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
        }
    return payload


def write_dataframe_with_summary(
    frame: pl.DataFrame,
    *,
    data_path: Path,
    summary_path: Path,
    extra_summary: dict[str, Any] | None = None,
    numeric_columns: list[str] | None = None,
) -> dict[str, Any]:
    data_path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(data_path)
    payload: dict[str, Any] = {
        "path": str(data_path),
        "row_count": frame.height,
        "column_count": frame.width,
        "columns": frame.columns,
        "preview": _preview_rows(frame),
    }
    if numeric_columns:
        payload["numeric_summary"] = _numeric_summary(frame, numeric_columns)
    if extra_summary:
        payload.update(extra_summary)
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return payload


@dataclass(frozen=True)
class EventModuleConfig:
    config_path: Path
    year: str
    cache_root: Path
    outputs_root: Path
    trade_table: str
    order_table: str
    instrument_profile_csv: Path | None
    control_feature_csv: Path | None
    start_date: str | None
    end_date: str | None
    max_listing_age_days: int
    min_observed_days: int
    size_percentile_min: float
    size_percentile_max: float
    require_non_southbound_proxy: bool
    boundary_lookback_days: int
    control_lookback_days: int
    push_lookback_days: int
    control_build_threshold: float
    control_build_sustain_threshold: float
    boundary_target_percentile: float
    boundary_band_width: float
    push_positive_share_min: float
    push_return_min: float
    push_drawdown_floor: float
    control_event_ratio_weight: float
    control_notional_ratio_weight: float
    control_churn_weight: float
    control_broker_blend_weight: float
    max_gap_sessions: int
    review_top_n: int
    event_universe_filename: str
    event_state_filename: str
    event_case_filename: str
    event_review_filename: str

    @property
    def event_universe_path(self) -> Path:
        return self.outputs_root / self.event_universe_filename

    @property
    def event_universe_summary_path(self) -> Path:
        return self.outputs_root / "event_universe_summary.json"

    @property
    def event_state_path(self) -> Path:
        return self.outputs_root / self.event_state_filename

    @property
    def event_state_summary_path(self) -> Path:
        return self.outputs_root / "event_state_daily_summary.json"

    @property
    def event_case_path(self) -> Path:
        return self.outputs_root / self.event_case_filename

    @property
    def event_case_summary_path(self) -> Path:
        return self.outputs_root / "event_cases_summary.json"

    @property
    def event_review_path(self) -> Path:
        return self.outputs_root / self.event_review_filename

    @property
    def event_review_summary_path(self) -> Path:
        return self.outputs_root / "event_review_pack_summary.json"


def _resolve_optional_path(base: Path, raw_value: str) -> Path | None:
    if not raw_value:
        return None
    path = Path(raw_value)
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def load_config(config_path: Path) -> EventModuleConfig:
    raw_path = config_path if config_path.is_absolute() else (ROOT / config_path).resolve()
    payload = tomllib.loads(raw_path.read_text(encoding="utf-8"))

    inputs = payload["inputs"]
    universe = payload["universe"]
    state_rules = payload["states"]
    outputs = payload["outputs"]

    cache_root = Path(inputs.get("cache_root", "cache/daily_agg"))
    if not cache_root.is_absolute():
        cache_root = (ROOT / cache_root).resolve()
    outputs_root = Path(outputs.get("root", "event_boundary_push/outputs"))
    if not outputs_root.is_absolute():
        outputs_root = (ROOT / outputs_root).resolve()

    return EventModuleConfig(
        config_path=raw_path,
        year=str(inputs["year"]),
        cache_root=cache_root,
        outputs_root=outputs_root,
        trade_table=str(inputs.get("trade_table", "verified_trades_daily")),
        order_table=str(inputs.get("order_table", "verified_orders_daily")),
        instrument_profile_csv=_resolve_optional_path(ROOT, str(inputs.get("instrument_profile_csv", ""))),
        control_feature_csv=_resolve_optional_path(ROOT, str(inputs.get("control_feature_csv", ""))),
        start_date=str(inputs.get("start_date", "")) or None,
        end_date=str(inputs.get("end_date", "")) or None,
        max_listing_age_days=int(universe.get("max_listing_age_days", 730)),
        min_observed_days=int(universe.get("min_observed_days", 20)),
        size_percentile_min=float(universe.get("size_percentile_min", 0.10)),
        size_percentile_max=float(universe.get("size_percentile_max", 0.80)),
        require_non_southbound_proxy=bool(universe.get("require_non_southbound_proxy", True)),
        boundary_lookback_days=int(state_rules.get("boundary_lookback_days", 10)),
        control_lookback_days=int(state_rules.get("control_lookback_days", 10)),
        push_lookback_days=int(state_rules.get("push_lookback_days", 10)),
        control_build_threshold=float(state_rules.get("control_build_threshold", 0.80)),
        control_build_sustain_threshold=float(state_rules.get("control_build_sustain_threshold", 0.72)),
        boundary_target_percentile=float(state_rules.get("boundary_target_percentile", 0.80)),
        boundary_band_width=float(state_rules.get("boundary_band_width", 0.08)),
        push_positive_share_min=float(state_rules.get("push_positive_share_min", 0.60)),
        push_return_min=float(state_rules.get("push_return_min", 0.05)),
        push_drawdown_floor=float(state_rules.get("push_drawdown_floor", -0.08)),
        control_event_ratio_weight=float(state_rules.get("control_event_ratio_weight", 0.30)),
        control_notional_ratio_weight=float(state_rules.get("control_notional_ratio_weight", 0.50)),
        control_churn_weight=float(state_rules.get("control_churn_weight", 0.20)),
        control_broker_blend_weight=float(state_rules.get("control_broker_blend_weight", 0.25)),
        max_gap_sessions=int(state_rules.get("max_gap_sessions", 2)),
        review_top_n=int(outputs.get("review_top_n", 100)),
        event_universe_filename=str(outputs.get("event_universe", "event_universe.parquet")),
        event_state_filename=str(outputs.get("event_state_daily", "event_state_daily.parquet")),
        event_case_filename=str(outputs.get("event_cases", "event_cases.parquet")),
        event_review_filename=str(outputs.get("event_review_pack", "event_review_pack.csv")),
    )


def _table_partition_path(config: EventModuleConfig, table_name: str, date: str) -> Path:
    if table_name not in VALID_DAILY_TABLES:
        raise ValueError(f"Unsupported daily table `{table_name}`.")
    return config.cache_root / table_name / f"year={date.split('-', 1)[0]}" / f"date={date}" / "part-00000.parquet"


def _available_daily_dates(config: EventModuleConfig, table_name: str) -> list[str]:
    if table_name not in VALID_DAILY_TABLES:
        raise ValueError(f"Unsupported daily table `{table_name}`.")
    year_root = config.cache_root / table_name / f"year={config.year}"
    if not year_root.exists():
        return []
    return sorted(
        path.name.split("=", 1)[1]
        for path in year_root.iterdir()
        if path.is_dir() and path.name.startswith("date=")
    )


def _date_filter(dates: list[str], *, start_date: str | None, end_date: str | None) -> list[str]:
    filtered = dates
    if start_date:
        filtered = [value for value in filtered if value >= start_date]
    if end_date:
        filtered = [value for value in filtered if value <= end_date]
    return filtered


def available_event_dates(config: EventModuleConfig) -> list[str]:
    trade_dates = set(_available_daily_dates(config, config.trade_table))
    order_dates = set(_available_daily_dates(config, config.order_table))
    return _date_filter(sorted(trade_dates & order_dates), start_date=config.start_date, end_date=config.end_date)


def _load_daily_table(
    *,
    config: EventModuleConfig,
    table_name: str,
    dates: list[str],
    columns: list[str],
) -> pl.DataFrame:
    paths = []
    for value in dates:
        path = _table_partition_path(config, table_name, value)
        if not path.exists():
            raise FileNotFoundError(f"Missing daily agg partition: {path}")
        paths.append(str(path))
    return pl.scan_parquet(paths).select(list(dict.fromkeys(columns))).collect()


def _load_optional_profile(config: EventModuleConfig) -> pl.DataFrame | None:
    path = config.instrument_profile_csv
    if path is None or not path.exists():
        return None
    frame = pl.read_csv(path, try_parse_dates=True)
    if "instrument_key" not in frame.columns:
        raise ValueError("instrument_profile_csv must include instrument_key.")
    rename_map: dict[str, str] = {}
    if "ticker" in frame.columns:
        rename_map["ticker"] = "ticker_profile"
    if "listing_date" in frame.columns:
        rename_map["listing_date"] = "listing_date_profile"
    if "float_mktcap" in frame.columns:
        rename_map["float_mktcap"] = "float_mktcap_profile"
    if "southbound_eligible" in frame.columns:
        rename_map["southbound_eligible"] = "southbound_eligible_profile"
    frame = frame.rename(rename_map)
    casts: list[pl.Expr] = [pl.col("instrument_key").cast(pl.String, strict=False).str.zfill(5)]
    if "ticker_profile" in frame.columns:
        casts.append(pl.col("ticker_profile").cast(pl.String, strict=False).str.zfill(5))
    if "listing_date_profile" in frame.columns:
        casts.append(pl.col("listing_date_profile").cast(pl.Date, strict=False))
    if "float_mktcap_profile" in frame.columns:
        casts.append(pl.col("float_mktcap_profile").cast(pl.Float64, strict=False))
    if "southbound_eligible_profile" in frame.columns:
        casts.append(pl.col("southbound_eligible_profile").cast(pl.Boolean, strict=False))
    return frame.with_columns(casts)


def _load_optional_control_features(config: EventModuleConfig) -> pl.DataFrame | None:
    path = config.control_feature_csv
    if path is None or not path.exists():
        return None
    frame = pl.read_csv(path, try_parse_dates=True)
    if not {"date", "instrument_key"}.issubset(frame.columns):
        raise ValueError("control_feature_csv must include date and instrument_key.")
    casts: list[pl.Expr] = [pl.col("date").cast(pl.Date, strict=False)]
    for column in frame.columns:
        if column in {"date", "instrument_key"}:
            continue
        casts.append(pl.col(column).cast(pl.Float64, strict=False))
    return frame.with_columns(casts)


def build_trade_order_panel(config: EventModuleConfig) -> pl.DataFrame:
    dates = available_event_dates(config)
    if not dates:
        raise FileNotFoundError(f"No overlapping daily agg dates found for year {config.year}.")

    trades = _load_daily_table(
        config=config,
        table_name=config.trade_table,
        dates=dates,
        columns=[
            "date",
            "instrument_key",
            "trade_count",
            "turnover",
            "share_volume",
            "avg_trade_size",
            "close_like_price",
            "vwap",
            "instrument_key_source",
        ],
    )
    orders = _load_daily_table(
        config=config,
        table_name=config.order_table,
        dates=dates,
        columns=[
            "date",
            "instrument_key",
            "order_event_count",
            "unique_order_ids",
            "total_order_notional",
            "churn_ratio",
        ],
    )

    panel = (
        trades.join(orders, on=["date", "instrument_key"], how="left")
        .with_columns(
            [
                pl.col("order_event_count").fill_null(0.0),
                pl.col("unique_order_ids").fill_null(0.0),
                pl.col("total_order_notional").fill_null(0.0),
                pl.col("churn_ratio").fill_null(0.0),
            ]
        )
        .sort(["instrument_key", "date"])
    )

    instrument_meta = (
        panel.group_by("instrument_key")
        .agg(
            [
                pl.col("date").min().alias("first_seen_date"),
                pl.col("date").max().alias("last_seen_date"),
                pl.len().alias("observed_days"),
                pl.col("instrument_key_source").drop_nulls().first().alias("instrument_key_source"),
            ]
        )
        .sort("instrument_key")
    )

    profile = _load_optional_profile(config)
    if profile is not None:
        instrument_meta = instrument_meta.join(profile, on="instrument_key", how="left")

    for column_name, dtype in [("ticker_profile", pl.String), ("listing_date_profile", pl.Date), ("float_mktcap_profile", pl.Float64), ("southbound_eligible_profile", pl.Boolean)]:
        if column_name not in instrument_meta.columns:
            instrument_meta = instrument_meta.with_columns(pl.lit(None, dtype=dtype).alias(column_name))

    instrument_meta = instrument_meta.with_columns(
        [
            pl.coalesce(["ticker_profile", "instrument_key"]).alias("ticker"),
            pl.coalesce(["listing_date_profile", "first_seen_date"]).alias("listing_date_effective"),
            pl.when(pl.col("listing_date_profile").is_not_null())
            .then(pl.lit("instrument_profile"))
            .otherwise(pl.lit("first_seen_in_cache_proxy"))
            .alias("listing_date_source"),
            pl.col("float_mktcap_profile").alias("float_mktcap_effective"),
            pl.coalesce(["southbound_eligible_profile", pl.lit(False)]).alias("southbound_eligible_effective"),
            pl.when(pl.col("southbound_eligible_profile").is_not_null())
            .then(pl.lit("instrument_profile"))
            .otherwise(pl.lit("assumed_false_proxy"))
            .alias("southbound_source"),
        ]
    ).drop(
        [
            column
            for column in [
                "ticker_profile",
                "listing_date_profile",
                "float_mktcap_profile",
                "southbound_eligible_profile",
            ]
            if column in instrument_meta.columns
        ]
    )

    panel = panel.join(instrument_meta, on="instrument_key", how="left")
    if "instrument_key_source_right" in panel.columns:
        panel = panel.drop("instrument_key_source_right")
    control_features = _load_optional_control_features(config)
    if control_features is not None:
        panel = panel.join(control_features, on=["date", "instrument_key"], how="left")

    return panel.sort(["instrument_key", "date"]).with_columns(
        [
            (pl.col("date") - pl.col("listing_date_effective")).dt.total_days().cast(pl.Int64).alias(
                "listing_age_days"
            ),
            (pl.col("order_event_count") / pl.max_horizontal(pl.col("trade_count"), pl.lit(1.0))).alias(
                "order_trade_event_ratio"
            ),
            (pl.col("total_order_notional") / pl.max_horizontal(pl.col("turnover"), pl.lit(1.0))).alias(
                "order_trade_notional_ratio"
            ),
            pl.when(pl.col("vwap") > 0)
            .then((pl.col("close_like_price") / pl.col("vwap")) - 1.0)
            .otherwise(None)
            .alias("close_vwap_gap"),
        ]
    )


def build_event_universe_frame(config: EventModuleConfig) -> pl.DataFrame:
    panel = build_trade_order_panel(config)
    analysis_end_date = panel["date"].max()

    universe = (
        panel.group_by(["instrument_key", "ticker"])
        .agg(
            [
                pl.col("first_seen_date").first(),
                pl.col("last_seen_date").first(),
                pl.col("observed_days").first(),
                pl.col("listing_date_effective").first(),
                pl.col("listing_date_source").first(),
                pl.col("southbound_eligible_effective").first(),
                pl.col("southbound_source").first(),
                pl.col("float_mktcap_effective").first(),
                pl.when(pl.col("float_mktcap_effective").is_not_null())
                .then(pl.col("float_mktcap_effective"))
                .otherwise(pl.col("turnover"))
                .median()
                .alias("boundary_proxy_reference_value"),
                pl.col("turnover").median().alias("median_turnover"),
                pl.col("trade_count").median().alias("median_trade_count"),
                pl.col("order_event_count").median().alias("median_order_event_count"),
            ]
        )
        .sort("instrument_key")
        .with_columns(
            [
                pl.lit(analysis_end_date).alias("analysis_end_date"),
                (pl.lit(analysis_end_date) - pl.col("listing_date_effective"))
                .dt.total_days()
                .cast(pl.Int64)
                .alias("listing_age_days_at_end"),
            ]
        )
    )

    boundary_rank = (
        (pl.col("boundary_proxy_reference_value").rank("average") - 1.0)
        / pl.max_horizontal(pl.len().cast(pl.Float64) - 1.0, pl.lit(1.0))
    )
    universe = universe.with_columns(boundary_rank.alias("boundary_proxy_reference_percentile"))
    universe = universe.with_columns(
        [
            (pl.col("listing_age_days_at_end") <= config.max_listing_age_days).alias("is_recent_listing_proxy"),
            (pl.col("observed_days") >= config.min_observed_days).alias("has_min_observed_days"),
            pl.col("boundary_proxy_reference_percentile")
            .is_between(config.size_percentile_min, config.size_percentile_max, closed="both")
            .alias("is_small_mid_boundary_proxy"),
            (~pl.col("southbound_eligible_effective")).alias("is_non_southbound_proxy"),
            pl.when(pl.col("float_mktcap_effective").is_not_null())
            .then(pl.lit("float_mktcap_effective"))
            .otherwise(pl.lit("turnover_median_proxy"))
            .alias("boundary_proxy_source"),
        ]
    )
    include_expr = (
        pl.col("is_recent_listing_proxy")
        & pl.col("has_min_observed_days")
        & pl.col("is_small_mid_boundary_proxy")
    )
    if config.require_non_southbound_proxy:
        include_expr = include_expr & pl.col("is_non_southbound_proxy")
    return universe.with_columns(include_expr.alias("event_universe_included")).sort(
        ["event_universe_included", "boundary_proxy_reference_percentile"],
        descending=[True, True],
    )


def write_event_universe(config: EventModuleConfig) -> tuple[pl.DataFrame, dict[str, Any]]:
    universe = build_event_universe_frame(config)
    profile_coverage = {
        "listing_date_instrument_profile_count": universe.filter(pl.col("listing_date_source") == "instrument_profile").height,
        "float_mktcap_non_null_count": universe.filter(pl.col("float_mktcap_effective").is_not_null()).height,
        "southbound_instrument_profile_count": universe.filter(pl.col("southbound_source") == "instrument_profile").height,
        "boundary_true_mktcap_count": universe.filter(pl.col("boundary_proxy_source") == "float_mktcap_effective").height,
    }
    summary = write_dataframe_with_summary(
        universe,
        data_path=config.event_universe_path,
        summary_path=config.event_universe_summary_path,
        numeric_columns=[
            "boundary_proxy_reference_value",
            "boundary_proxy_reference_percentile",
            "listing_age_days_at_end",
        ],
        extra_summary={
            "config_path": str(config.config_path),
            "year": config.year,
            "included_count": universe.filter(pl.col("event_universe_included")).height,
            "profile_coverage": profile_coverage,
        },
    )
    return universe, summary


def _percentile_rank_expr(column: str) -> pl.Expr:
    count_expr = pl.len().over("date")
    rank_expr = pl.col(column).rank("average").over("date")
    return (
        pl.when(pl.col(column).is_null())
        .then(None)
        .when(count_expr <= 1)
        .then(0.5)
        .otherwise((rank_expr - 1.0) / (count_expr - 1.0))
        .alias(f"{column}_pct")
    )


def _clip01(expr: pl.Expr) -> pl.Expr:
    return expr.clip(lower_bound=0.0, upper_bound=1.0)



def _weighted_mean_expr(column_weights: list[tuple[str, float]]) -> pl.Expr:
    active = [(column, weight) for column, weight in column_weights if weight > 0]
    if not active:
        return pl.lit(None, dtype=pl.Float64)
    total_weight = sum(weight for _, weight in active)
    expr = pl.lit(0.0)
    for column, weight in active:
        expr = expr + (pl.col(column) * (weight / total_weight))
    return expr

def _empty_event_state_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "date": pl.Date,
            "instrument_key": pl.String,
            "ticker": pl.String,
            "event_type": pl.String,
            "control_build": pl.Boolean,
            "boundary_approach": pl.Boolean,
            "push_regime": pl.Boolean,
            "control_proxy": pl.Float64,
            "control_proxy_sustain": pl.Float64,
            "boundary_proxy_value": pl.Float64,
            "boundary_proxy_percentile": pl.Float64,
            "boundary_distance_abs": pl.Float64,
            "rolling_return_lookback": pl.Float64,
            "drawdown_from_high_lookback": pl.Float64,
            "push_strength": pl.Float64,
            "event_strength": pl.Float64,
            "control_proxy_source": pl.String,
            "boundary_proxy_source": pl.String,
        }
    )


def _empty_event_case_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "event_id": pl.String,
            "instrument_key": pl.String,
            "ticker": pl.String,
            "event_type": pl.String,
            "start_date": pl.String,
            "end_date": pl.String,
            "status": pl.String,
            "event_day_count": pl.Int64,
            "control_build_days": pl.Int64,
            "boundary_approach_days": pl.Int64,
            "push_regime_days": pl.Int64,
            "peak_event_strength": pl.Float64,
            "peak_control_proxy": pl.Float64,
            "peak_push_strength": pl.Float64,
            "min_boundary_distance_abs": pl.Float64,
            "boundary_proxy_start": pl.Float64,
            "boundary_proxy_end": pl.Float64,
            "boundary_percentile_start": pl.Float64,
            "boundary_percentile_end": pl.Float64,
            "price_return_during_event": pl.Float64,
            "max_drawdown_during_event": pl.Float64,
            "control_proxy_source": pl.String,
            "boundary_proxy_source": pl.String,
        }
    )


def _empty_event_review_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "event_id": pl.String,
            "ticker": pl.String,
            "event_type": pl.String,
            "start_date": pl.String,
            "end_date": pl.String,
            "status": pl.String,
            "annotator": pl.String,
            "expert_suspect_flag": pl.String,
            "perceived_path_type": pl.String,
            "confidence": pl.String,
            "reason_code_1": pl.String,
            "reason_code_2": pl.String,
            "reason_code_3": pl.String,
            "operator_fingerprint_guess": pl.String,
            "comment": pl.String,
        }
    )

def build_event_state_frame(config: EventModuleConfig, *, universe: pl.DataFrame | None = None) -> pl.DataFrame:
    universe_frame = universe if universe is not None else build_event_universe_frame(config)
    included = universe_frame.filter(pl.col("event_universe_included")).select(["instrument_key"])
    if included.is_empty():
        return _empty_event_state_frame()

    panel = (
        build_trade_order_panel(config)
        .join(included, on="instrument_key", how="inner")
        .sort(["instrument_key", "date"])
    )

    control_window = config.control_lookback_days
    boundary_window = config.boundary_lookback_days
    push_window = config.push_lookback_days

    panel = panel.with_columns(
        [
            pl.col("turnover")
            .rolling_median(window_size=boundary_window, min_samples=boundary_window)
            .over("instrument_key")
            .alias("turnover_median_lookback"),
            pl.col("order_trade_event_ratio")
            .rolling_mean(window_size=control_window, min_samples=control_window)
            .over("instrument_key")
            .alias("order_trade_event_ratio_lookback"),
            pl.col("order_trade_notional_ratio")
            .rolling_mean(window_size=control_window, min_samples=control_window)
            .over("instrument_key")
            .alias("order_trade_notional_ratio_lookback"),
            pl.col("churn_ratio")
            .rolling_mean(window_size=control_window, min_samples=control_window)
            .over("instrument_key")
            .alias("churn_ratio_lookback"),
            (pl.col("close_like_price") / pl.col("close_like_price").shift(1).over("instrument_key") - 1.0).alias(
                "daily_return_1d"
            ),
        ]
    ).with_columns(
        [
            (pl.col("daily_return_1d") > 0).cast(pl.Float64).alias("positive_day_flag"),
            pl.when(pl.col("float_mktcap_effective").is_not_null())
            .then(pl.col("float_mktcap_effective"))
            .otherwise(pl.col("turnover_median_lookback"))
            .alias("boundary_proxy_value"),
            (
                pl.col("close_like_price")
                / pl.col("close_like_price").shift(push_window - 1).over("instrument_key")
                - 1.0
            ).alias("rolling_return_lookback"),
            (
                pl.col("close_like_price")
                / pl.col("close_like_price")
                .rolling_max(window_size=push_window, min_samples=push_window)
                .over("instrument_key")
                - 1.0
            ).alias("drawdown_from_high_lookback"),
        ]
    ).with_columns(
        [
            pl.col("positive_day_flag")
            .rolling_mean(window_size=push_window, min_samples=push_window)
            .over("instrument_key")
            .alias("positive_return_share_lookback"),
        ]
    )

    control_component_columns = [
        "order_trade_event_ratio_lookback",
        "order_trade_notional_ratio_lookback",
        "churn_ratio_lookback",
    ]
    for column in ["broker_hhi", "broker_netflow_persistence"]:
        if column in panel.columns:
            control_component_columns.append(column)

    rank_columns = control_component_columns + ["boundary_proxy_value"]
    panel = panel.with_columns([_percentile_rank_expr(column) for column in rank_columns])

    base_control_weights = [
        ("order_trade_event_ratio_lookback_pct", config.control_event_ratio_weight),
        ("order_trade_notional_ratio_lookback_pct", config.control_notional_ratio_weight),
        ("churn_ratio_lookback_pct", config.control_churn_weight),
    ]
    broker_control_weights: list[tuple[str, float]] = []
    if "broker_hhi_pct" in panel.columns:
        broker_control_weights.append(("broker_hhi_pct", 1.0))
    if "broker_netflow_persistence_pct" in panel.columns:
        broker_control_weights.append(("broker_netflow_persistence_pct", 1.0))

    panel = panel.with_columns(
        [
            _weighted_mean_expr(base_control_weights).alias("control_proxy_base"),
            _weighted_mean_expr(broker_control_weights).alias("control_proxy_broker"),
            pl.col("boundary_proxy_value_pct").alias("boundary_proxy_percentile"),
            (pl.col("boundary_proxy_value_pct") - config.boundary_target_percentile).abs().alias(
                "boundary_distance_abs"
            ),
        ]
    ).with_columns(
        [
            pl.when(pl.col("control_proxy_broker").is_not_null())
            .then(
                (1.0 - config.control_broker_blend_weight) * pl.col("control_proxy_base")
                + config.control_broker_blend_weight * pl.col("control_proxy_broker")
            )
            .otherwise(pl.col("control_proxy_base"))
            .alias("control_proxy")
        ]
    ).with_columns(
        [
            pl.col("control_proxy")
            .rolling_mean(window_size=control_window, min_samples=control_window)
            .over("instrument_key")
            .alias("control_proxy_sustain"),
        ]
    )

    control_source = "weighted_order_trade_pressure_proxy"
    if {"broker_hhi", "broker_netflow_persistence"}.issubset(panel.columns):
        control_source = "weighted_broker_plus_order_pressure_proxy"

    push_return_scale = max(config.push_return_min, 0.01) * 2.0
    drawdown_denominator = abs(config.push_drawdown_floor) if config.push_drawdown_floor < 0 else 0.05
    panel = panel.with_columns(
        [
            _clip01((pl.col("control_proxy") - config.control_build_threshold) / (1.0 - config.control_build_threshold)).alias(
                "control_strength"
            ),
            _clip01(1.0 - (pl.col("boundary_distance_abs") / config.boundary_band_width)).alias(
                "boundary_closeness"
            ),
            pl.mean_horizontal(
                [
                    _clip01(
                        (pl.col("positive_return_share_lookback") - config.push_positive_share_min)
                        / (1.0 - config.push_positive_share_min)
                    ),
                    _clip01(pl.col("rolling_return_lookback") / push_return_scale),
                    _clip01(
                        (pl.col("drawdown_from_high_lookback") - config.push_drawdown_floor) / drawdown_denominator
                    ),
                ]
            ).alias("push_strength"),
            pl.lit(control_source).alias("control_proxy_source"),
            pl.when(pl.col("float_mktcap_effective").is_not_null())
            .then(pl.lit("float_mktcap_effective"))
            .otherwise(pl.lit("turnover_median_lookback_proxy"))
            .alias("boundary_proxy_source"),
        ]
    ).with_columns(
        [
            (
                (pl.col("control_proxy") >= config.control_build_threshold)
                & (pl.col("control_proxy_sustain") >= config.control_build_sustain_threshold)
            ).alias("control_build"),
            pl.col("boundary_proxy_percentile")
            .is_between(
                config.boundary_target_percentile - config.boundary_band_width,
                config.boundary_target_percentile + config.boundary_band_width,
                closed="both",
            )
            .alias("boundary_approach"),
            (
                (pl.col("positive_return_share_lookback") >= config.push_positive_share_min)
                & (pl.col("rolling_return_lookback") >= config.push_return_min)
                & (pl.col("drawdown_from_high_lookback") >= config.push_drawdown_floor)
            ).alias("push_regime"),
        ]
    ).with_columns(
        [
            (pl.col("control_build") & pl.col("boundary_approach") & pl.col("push_regime")).alias(
                "full_path_signal"
            ),
            (pl.col("control_build") & pl.col("boundary_approach") & ~pl.col("push_regime")).alias(
                "trigger_boundary_control_setup"
            ),
            (pl.col("control_build") & pl.col("push_regime") & ~pl.col("boundary_approach")).alias(
                "trigger_control_push"
            ),
            (pl.col("boundary_approach") & pl.col("push_regime") & ~pl.col("control_build")).alias(
                "trigger_boundary_push"
            ),
        ]
    ).with_columns(
        [
            pl.when(pl.col("full_path_signal"))
            .then(pl.lit("full_path_signal"))
            .when(pl.col("trigger_boundary_control_setup"))
            .then(pl.lit("boundary_control_setup"))
            .when(pl.col("trigger_control_push"))
            .then(pl.lit("control_push"))
            .when(pl.col("trigger_boundary_push"))
            .then(pl.lit("boundary_push"))
            .otherwise(None)
            .alias("event_type"),
            pl.mean_horizontal([pl.col("control_strength"), pl.col("boundary_closeness"), pl.col("push_strength")]).alias(
                "event_strength"
            ),
        ]
    )
    return panel.sort(["date", "event_strength"], descending=[False, True])


def write_event_state_daily(config: EventModuleConfig) -> tuple[pl.DataFrame, dict[str, Any]]:
    universe = build_event_universe_frame(config)
    panel = build_event_state_frame(config, universe=universe)
    profile_coverage = {
        "listing_date_instrument_profile_rows": panel.filter(pl.col("listing_date_source") == "instrument_profile").height if not panel.is_empty() else 0,
        "boundary_true_mktcap_rows": panel.filter(pl.col("boundary_proxy_source") == "float_mktcap_effective").height if not panel.is_empty() else 0,
        "southbound_instrument_profile_rows": panel.filter(pl.col("southbound_source") == "instrument_profile").height if not panel.is_empty() else 0,
    }
    summary = write_dataframe_with_summary(
        panel,
        data_path=config.event_state_path,
        summary_path=config.event_state_summary_path,
        numeric_columns=["control_proxy", "boundary_proxy_percentile", "rolling_return_lookback", "event_strength"],
        extra_summary={
            "config_path": str(config.config_path),
            "year": config.year,
            "event_universe_count": universe.filter(pl.col("event_universe_included")).height,
            "active_event_rows": panel.filter(pl.col("event_type").is_not_null()).height if not panel.is_empty() else 0,
            "event_type_counts": (
                panel.filter(pl.col("event_type").is_not_null())
                .group_by("event_type")
                .agg(pl.len().alias("count"))
                .sort("count", descending=True)
                .to_dicts()
                if not panel.is_empty()
                else []
            ),
            "profile_coverage": profile_coverage,
        },
    )
    return panel, summary


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _safe_date(value: Any) -> str:
    if isinstance(value, date_type):
        return value.isoformat()
    return str(value)


def build_event_cases_frame(config: EventModuleConfig, *, state_panel: pl.DataFrame | None = None) -> pl.DataFrame:
    panel = state_panel if state_panel is not None else build_event_state_frame(config)
    active = panel.filter(pl.col("event_type").is_not_null()).sort(["instrument_key", "date"])
    if active.is_empty():
        return _empty_event_case_frame()

    trading_dates = sorted({_safe_date(value) for value in panel["date"].to_list()})
    date_index = {value: idx for idx, value in enumerate(trading_dates)}
    last_date = trading_dates[-1]

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in active.to_dicts():
        key = (str(row["instrument_key"]), str(row["event_type"]))
        grouped.setdefault(key, []).append(row)

    cases: list[dict[str, Any]] = []
    allowed_gap = config.max_gap_sessions + 1

    def _finalize(event_rows: list[dict[str, Any]], *, event_type: str, instrument_key: str) -> None:
        if not event_rows:
            return
        start_date = _safe_date(event_rows[0]["date"])
        end_date = _safe_date(event_rows[-1]["date"])
        start_close = _safe_float(event_rows[0].get("close_like_price"))
        end_close = _safe_float(event_rows[-1].get("close_like_price"))
        price_return = None
        if start_close not in (None, 0.0) and end_close is not None:
            price_return = (end_close / start_close) - 1.0
        cases.append(
            {
                "event_id": f"{instrument_key}__{event_type}__{start_date}__{end_date}",
                "instrument_key": instrument_key,
                "ticker": event_rows[0]["ticker"],
                "event_type": event_type,
                "start_date": start_date,
                "end_date": end_date,
                "status": "open" if end_date == last_date else "closed",
                "event_day_count": len(event_rows),
                "control_build_days": sum(1 for row in event_rows if row.get("control_build")),
                "boundary_approach_days": sum(1 for row in event_rows if row.get("boundary_approach")),
                "push_regime_days": sum(1 for row in event_rows if row.get("push_regime")),
                "peak_event_strength": max(_safe_float(row.get("event_strength")) or 0.0 for row in event_rows),
                "peak_control_proxy": max(_safe_float(row.get("control_proxy")) or 0.0 for row in event_rows),
                "peak_push_strength": max(_safe_float(row.get("push_strength")) or 0.0 for row in event_rows),
                "min_boundary_distance_abs": min(
                    _safe_float(row.get("boundary_distance_abs")) or 999.0 for row in event_rows
                ),
                "boundary_proxy_start": _safe_float(event_rows[0].get("boundary_proxy_value")),
                "boundary_proxy_end": _safe_float(event_rows[-1].get("boundary_proxy_value")),
                "boundary_percentile_start": _safe_float(event_rows[0].get("boundary_proxy_percentile")),
                "boundary_percentile_end": _safe_float(event_rows[-1].get("boundary_proxy_percentile")),
                "price_return_during_event": price_return,
                "max_drawdown_during_event": min(
                    _safe_float(row.get("drawdown_from_high_lookback")) or 0.0 for row in event_rows
                ),
                "control_proxy_source": event_rows[0].get("control_proxy_source"),
                "boundary_proxy_source": event_rows[0].get("boundary_proxy_source"),
            }
        )

    for (instrument_key, event_type), rows in grouped.items():
        current: list[dict[str, Any]] = []
        previous_index: int | None = None
        for row in rows:
            current_index = date_index[_safe_date(row["date"])]
            if previous_index is None or current_index - previous_index <= allowed_gap:
                current.append(row)
            else:
                _finalize(current, event_type=event_type, instrument_key=instrument_key)
                current = [row]
            previous_index = current_index
        _finalize(current, event_type=event_type, instrument_key=instrument_key)

    return pl.from_dicts(cases).sort(["start_date", "peak_event_strength"], descending=[False, True])


def write_event_cases(config: EventModuleConfig) -> tuple[pl.DataFrame, dict[str, Any]]:
    panel = build_event_state_frame(config)
    cases = build_event_cases_frame(config, state_panel=panel)
    summary = write_dataframe_with_summary(
        cases,
        data_path=config.event_case_path,
        summary_path=config.event_case_summary_path,
        numeric_columns=["peak_event_strength", "peak_control_proxy", "peak_push_strength", "price_return_during_event"],
        extra_summary={
            "config_path": str(config.config_path),
            "case_count": cases.height,
            "event_type_counts": (
                cases.group_by("event_type")
                .agg(pl.len().alias("count"))
                .sort("count", descending=True)
                .to_dicts()
                if not cases.is_empty()
                else []
            ),
        },
    )
    return cases, summary


def build_event_review_pack_frame(config: EventModuleConfig, *, cases: pl.DataFrame | None = None) -> pl.DataFrame:
    case_frame = cases if cases is not None else build_event_cases_frame(config)
    if case_frame.is_empty():
        return _empty_event_review_frame()
    review = (
        case_frame.sort(["peak_event_strength", "end_date"], descending=[True, True])
        .head(config.review_top_n)
        .with_columns(
            [
                pl.lit("").alias("annotator"),
                pl.lit("").alias("expert_suspect_flag"),
                pl.lit("").alias("perceived_path_type"),
                pl.lit("").alias("confidence"),
                pl.lit("").alias("reason_code_1"),
                pl.lit("").alias("reason_code_2"),
                pl.lit("").alias("reason_code_3"),
                pl.lit("").alias("operator_fingerprint_guess"),
                pl.lit("").alias("comment"),
            ]
        )
    )
    ordered_columns = [
        "event_id",
        "ticker",
        "event_type",
        "start_date",
        "end_date",
        "status",
        "event_day_count",
        "control_build_days",
        "boundary_approach_days",
        "push_regime_days",
        "peak_event_strength",
        "peak_control_proxy",
        "peak_push_strength",
        "min_boundary_distance_abs",
        "boundary_proxy_start",
        "boundary_proxy_end",
        "boundary_percentile_start",
        "boundary_percentile_end",
        "price_return_during_event",
        "max_drawdown_during_event",
        "control_proxy_source",
        "boundary_proxy_source",
        "annotator",
        "expert_suspect_flag",
        "perceived_path_type",
        "confidence",
        "reason_code_1",
        "reason_code_2",
        "reason_code_3",
        "operator_fingerprint_guess",
        "comment",
    ]
    return review.select([column for column in ordered_columns if column in review.columns])


def write_event_review_pack(config: EventModuleConfig) -> tuple[pl.DataFrame, dict[str, Any]]:
    review = build_event_review_pack_frame(config)
    config.outputs_root.mkdir(parents=True, exist_ok=True)
    review.write_csv(config.event_review_path)
    payload = {
        "path": str(config.event_review_path),
        "row_count": review.height,
        "column_count": review.width,
        "columns": review.columns,
        "preview": _preview_rows(review),
        "config_path": str(config.config_path),
    }
    config.event_review_summary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return review, payload
