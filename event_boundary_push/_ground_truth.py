"""Ground-truth validation helpers for event_boundary_push."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
import tomllib
from typing import Any

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from event_boundary_push._core import EventModuleConfig, _preview_rows, load_config, write_dataframe_with_summary


DEFAULT_EVENT_PRIORITY = {
    "full_path_signal": 4,
    "boundary_control_setup": 3,
    "control_push": 2,
    "boundary_push": 1,
}


@dataclass(frozen=True)
class GroundTruthValidationConfig:
    config_path: Path
    event_config: EventModuleConfig
    ground_truth_csv: Path
    outputs_root: Path
    lookback_days: int
    lag_tolerance_days: int
    include_event_types: tuple[str, ...]
    max_noise_cases: int
    matches_filename: str
    noise_cases_filename: str
    summary_filename: str

    @property
    def matches_path(self) -> Path:
        return self.outputs_root / self.matches_filename

    @property
    def noise_cases_path(self) -> Path:
        return self.outputs_root / self.noise_cases_filename

    @property
    def summary_path(self) -> Path:
        return self.outputs_root / self.summary_filename


def _resolve_optional_path(base: Path, raw_value: str) -> Path:
    path = Path(raw_value)
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def load_ground_truth_config(config_path: Path) -> GroundTruthValidationConfig:
    raw_path = config_path if config_path.is_absolute() else (ROOT / config_path).resolve()
    payload = tomllib.loads(raw_path.read_text(encoding="utf-8"))
    inputs = payload["inputs"]
    matching = payload["matching"]
    outputs = payload["outputs"]

    event_config_path = _resolve_optional_path(ROOT, str(inputs["event_config"]))
    event_config = load_config(event_config_path)

    outputs_root = Path(outputs.get("root", "event_boundary_push/outputs"))
    if not outputs_root.is_absolute():
        outputs_root = (ROOT / outputs_root).resolve()

    return GroundTruthValidationConfig(
        config_path=raw_path,
        event_config=event_config,
        ground_truth_csv=_resolve_optional_path(ROOT, str(inputs["ground_truth_csv"])),
        outputs_root=outputs_root,
        lookback_days=int(matching.get("lookback_days", 60)),
        lag_tolerance_days=int(matching.get("lag_tolerance_days", 0)),
        include_event_types=tuple(matching.get("include_event_types", list(DEFAULT_EVENT_PRIORITY.keys()))),
        max_noise_cases=int(outputs.get("max_noise_cases", 100)),
        matches_filename=str(outputs.get("matches", "ground_truth_matches.parquet")),
        noise_cases_filename=str(outputs.get("noise_cases", "ground_truth_noise_cases.parquet")),
        summary_filename=str(outputs.get("summary", "ground_truth_validation_summary.json")),
    )


def _load_ground_truth_frame(config: GroundTruthValidationConfig) -> pl.DataFrame:
    if not config.ground_truth_csv.exists():
        raise FileNotFoundError(f"Missing ground-truth CSV: {config.ground_truth_csv}")
    frame = pl.read_csv(config.ground_truth_csv, try_parse_dates=True)
    if not ({"ticker", "instrument_key"} & set(frame.columns)):
        raise ValueError("ground_truth_csv must include at least one of ticker or instrument_key.")
    if "inclusion_date" not in frame.columns:
        raise ValueError("ground_truth_csv must include inclusion_date.")

    if "truth_id" not in frame.columns:
        frame = frame.with_row_count("truth_row_number").with_columns(
            (pl.lit("truth_") + pl.col("truth_row_number").cast(pl.String)).alias("truth_id")
        ).drop("truth_row_number")

    for column in ["ticker", "instrument_key", "source", "notes", "event_label"]:
        if column not in frame.columns:
            frame = frame.with_columns(pl.lit(None, dtype=pl.String).alias(column))
    for column in ["window_start", "window_end"]:
        if column not in frame.columns:
            frame = frame.with_columns(pl.lit(None, dtype=pl.Date).alias(column))

    frame = frame.with_columns(
        [
            pl.col("truth_id").cast(pl.String, strict=False),
            pl.col("ticker").cast(pl.String, strict=False).str.zfill(5),
            pl.col("instrument_key").cast(pl.String, strict=False).str.zfill(5),
            pl.col("source").cast(pl.String, strict=False),
            pl.col("notes").cast(pl.String, strict=False),
            pl.col("event_label").cast(pl.String, strict=False),
            pl.col("inclusion_date").cast(pl.Date, strict=False),
            pl.col("window_start").cast(pl.Date, strict=False),
            pl.col("window_end").cast(pl.Date, strict=False),
        ]
    ).with_columns(
        [
            pl.coalesce(["instrument_key", "ticker"]).alias("match_key"),
            pl.coalesce(["ticker", "instrument_key"]).alias("ticker_effective"),
            pl.when(pl.col("window_start").is_not_null())
            .then(pl.col("window_start"))
            .otherwise(pl.col("inclusion_date") - pl.duration(days=config.lookback_days))
            .alias("window_start_effective"),
            pl.when(pl.col("window_end").is_not_null())
            .then(pl.col("window_end"))
            .otherwise(pl.col("inclusion_date") + pl.duration(days=config.lag_tolerance_days))
            .alias("window_end_effective"),
        ]
    )
    return frame.sort(["inclusion_date", "match_key"])


def _load_event_cases(config: GroundTruthValidationConfig) -> pl.DataFrame:
    path = config.event_config.event_case_path
    if not path.exists():
        raise FileNotFoundError(f"Missing event cases parquet: {path}")
    frame = pl.read_parquet(path)
    if frame.is_empty():
        return frame
    return frame.with_columns(
        [
            pl.col("instrument_key").cast(pl.String, strict=False).str.zfill(5),
            pl.col("ticker").cast(pl.String, strict=False).str.zfill(5),
            pl.col("start_date").cast(pl.Date, strict=False),
            pl.col("end_date").cast(pl.Date, strict=False),
        ]
    )


def _empty_match_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "truth_id": pl.String,
            "ticker": pl.String,
            "match_key": pl.String,
            "inclusion_date": pl.Date,
            "window_start": pl.Date,
            "window_end": pl.Date,
            "event_label": pl.String,
            "source": pl.String,
            "matched": pl.Boolean,
            "matched_case_count": pl.Int64,
            "best_event_id": pl.String,
            "best_event_type": pl.String,
            "best_event_start_date": pl.Date,
            "best_event_end_date": pl.Date,
            "best_event_strength": pl.Float64,
            "lead_days_from_start": pl.Int64,
            "lead_days_from_end": pl.Int64,
            "best_event_day_count": pl.Int64,
            "best_price_return_during_event": pl.Float64,
            "notes": pl.String,
        }
    )


def _priority(event_type: str | None) -> int:
    if event_type is None:
        return 0
    return DEFAULT_EVENT_PRIORITY.get(event_type, 0)


def build_ground_truth_matches_frame(
    config: GroundTruthValidationConfig,
    *,
    cases: pl.DataFrame | None = None,
    truth: pl.DataFrame | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    truth_frame = truth if truth is not None else _load_ground_truth_frame(config)
    case_frame = cases if cases is not None else _load_event_cases(config)

    if truth_frame.is_empty():
        return _empty_match_frame(), case_frame.head(0)

    if case_frame.is_empty():
        rows = []
        for record in truth_frame.to_dicts():
            rows.append(
                {
                    "truth_id": record["truth_id"],
                    "ticker": record["ticker_effective"],
                    "match_key": record["match_key"],
                    "inclusion_date": record["inclusion_date"],
                    "window_start": record["window_start_effective"],
                    "window_end": record["window_end_effective"],
                    "event_label": record.get("event_label"),
                    "source": record.get("source"),
                    "matched": False,
                    "matched_case_count": 0,
                    "best_event_id": None,
                    "best_event_type": None,
                    "best_event_start_date": None,
                    "best_event_end_date": None,
                    "best_event_strength": None,
                    "lead_days_from_start": None,
                    "lead_days_from_end": None,
                    "best_event_day_count": None,
                    "best_price_return_during_event": None,
                    "notes": record.get("notes"),
                }
            )
        return pl.from_dicts(rows), case_frame

    allowed_types = set(config.include_event_types)
    filtered_cases = case_frame.filter(pl.col("event_type").is_in(sorted(allowed_types))) if allowed_types else case_frame

    match_rows: list[dict[str, Any]] = []
    matched_event_ids: set[str] = set()

    for record in truth_frame.to_dicts():
        match_key = record["match_key"]
        window_start = record["window_start_effective"]
        window_end = record["window_end_effective"]
        inclusion_date = record["inclusion_date"]
        candidates = filtered_cases.filter(
            (pl.col("instrument_key") == match_key) | (pl.col("ticker") == match_key)
        ).filter((pl.col("start_date") <= window_end) & (pl.col("end_date") >= window_start))

        row: dict[str, Any] = {
            "truth_id": record["truth_id"],
            "ticker": record["ticker_effective"],
            "match_key": match_key,
            "inclusion_date": inclusion_date,
            "window_start": window_start,
            "window_end": window_end,
            "event_label": record.get("event_label"),
            "source": record.get("source"),
            "matched": candidates.height > 0,
            "matched_case_count": candidates.height,
            "best_event_id": None,
            "best_event_type": None,
            "best_event_start_date": None,
            "best_event_end_date": None,
            "best_event_strength": None,
            "lead_days_from_start": None,
            "lead_days_from_end": None,
            "best_event_day_count": None,
            "best_price_return_during_event": None,
            "notes": record.get("notes"),
        }
        if candidates.height > 0:
            ranked = sorted(
                candidates.to_dicts(),
                key=lambda item: (
                    -_priority(item.get("event_type")),
                    abs((inclusion_date - item["end_date"]).days),
                    -(float(item.get("peak_event_strength") or 0.0)),
                ),
            )
            best = ranked[0]
            row.update(
                {
                    "best_event_id": best.get("event_id"),
                    "best_event_type": best.get("event_type"),
                    "best_event_start_date": best.get("start_date"),
                    "best_event_end_date": best.get("end_date"),
                    "best_event_strength": best.get("peak_event_strength"),
                    "lead_days_from_start": (inclusion_date - best["start_date"]).days if best.get("start_date") else None,
                    "lead_days_from_end": (inclusion_date - best["end_date"]).days if best.get("end_date") else None,
                    "best_event_day_count": best.get("event_day_count"),
                    "best_price_return_during_event": best.get("price_return_during_event"),
                }
            )
            for matched in candidates["event_id"].to_list():
                if matched is not None:
                    matched_event_ids.add(str(matched))
        match_rows.append(row)

    matches = pl.from_dicts(match_rows) if match_rows else _empty_match_frame()
    noise_cases = filtered_cases.filter(~pl.col("event_id").is_in(sorted(matched_event_ids))) if matched_event_ids else filtered_cases
    return matches.sort(["matched", "inclusion_date"], descending=[True, False]), noise_cases.sort(
        ["peak_event_strength", "end_date"], descending=[True, True]
    )


def write_ground_truth_validation(config: GroundTruthValidationConfig) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, Any]]:
    matches, noise_cases = build_ground_truth_matches_frame(config)
    config.outputs_root.mkdir(parents=True, exist_ok=True)

    write_dataframe_with_summary(
        matches,
        data_path=config.matches_path,
        summary_path=config.outputs_root / "ground_truth_matches_summary.json",
        numeric_columns=["matched_case_count", "best_event_strength", "lead_days_from_start", "lead_days_from_end"],
        extra_summary={"config_path": str(config.config_path)},
    )
    write_dataframe_with_summary(
        noise_cases,
        data_path=config.noise_cases_path,
        summary_path=config.outputs_root / "ground_truth_noise_cases_summary.json",
        numeric_columns=["peak_event_strength", "price_return_during_event"],
        extra_summary={
            "config_path": str(config.config_path),
            "total_noise_case_count": noise_cases.height,
            "preview_limit": config.max_noise_cases,
        },
    )

    matched = matches.filter(pl.col("matched")) if not matches.is_empty() else matches
    payload: dict[str, Any] = {
        "config_path": str(config.config_path),
        "event_config_path": str(config.event_config.config_path),
        "ground_truth_csv": str(config.ground_truth_csv),
        "ground_truth_count": matches.height,
        "matched_truth_count": matched.height,
        "hit_rate": (matched.height / matches.height) if matches.height else 0.0,
        "unmatched_truth_count": matches.height - matched.height,
        "mean_lead_days_from_start": matched["lead_days_from_start"].mean() if matched.height else None,
        "mean_lead_days_from_end": matched["lead_days_from_end"].mean() if matched.height else None,
        "median_lead_days_from_end": matched["lead_days_from_end"].median() if matched.height else None,
        "matched_event_type_counts": (
            matched.group_by("best_event_type").agg(pl.len().alias("count")).sort("count", descending=True).to_dicts()
            if matched.height
            else []
        ),
        "noise_case_count": noise_cases.height,
        "noise_case_ratio_proxy": (noise_cases.height / (noise_cases.height + matched.height)) if (noise_cases.height + matched.height) else 0.0,
        "matches_preview": _preview_rows(matches),
        "noise_cases_preview": _preview_rows(noise_cases.head(min(config.max_noise_cases, 5))),
    }
    config.summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return matches, noise_cases, payload
