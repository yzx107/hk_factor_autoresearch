"""Run layer-aware diagnostics for an existing factor output."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from diagnostics.regime_slices import build_regime_slice_frame
from evaluation.pre_eval import LABEL_NAME, build_pre_eval_summary
from harness.compare_factors import read_experiment_log
from harness.run_pre_eval import _find_experiment, _load_factor_output, _load_run_summary

RUN_ROOT = ROOT / "runs"
DEFAULT_LAYER_PATH = ROOT / "cache" / "universe_layers" / "year=2026" / "universe_layers_2026.parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run layer-aware pre-eval diagnostics.")
    parser.add_argument("--factor", required=True, help="Factor name to diagnose.")
    parser.add_argument("--experiment", default="", help="Optional explicit experiment id.")
    parser.add_argument("--labels-path", required=True, help="Parquet file with forward labels.")
    parser.add_argument("--layer-path", default=str(DEFAULT_LAYER_PATH), help="Universe layer parquet path.")
    parser.add_argument("--layer-column", default="primary_tradability_layer", help="Layer column to slice by.")
    parser.add_argument("--min-instruments", type=int, default=20, help="Minimum instruments for non-diagnostic layer.")
    parser.add_argument("--min-dates", type=int, default=3, help="Minimum labeled dates for non-diagnostic layer.")
    parser.add_argument("--notes", default="", help="Short run note.")
    return parser.parse_args()


def _records(frame: pl.DataFrame) -> list[dict[str, Any]]:
    records = frame.to_dicts()
    for record in records:
        for key, value in list(record.items()):
            if hasattr(value, "isoformat"):
                record[key] = value.isoformat()
    return records


def _require_unique_layer_keys(layers: pl.DataFrame) -> None:
    duplicate_count = layers.filter(pl.col("instrument_key").is_duplicated()).height
    if duplicate_count:
        raise ValueError(f"Layer frame has duplicate instrument_key rows: {duplicate_count}")


def _layer_join_frame(factor_df: pl.DataFrame, layers_df: pl.DataFrame, layer_column: str) -> pl.DataFrame:
    if layer_column not in layers_df.columns:
        raise ValueError(f"Missing layer column `{layer_column}`.")
    if "instrument_key" not in layers_df.columns:
        raise ValueError("Layer frame must include `instrument_key`.")
    _require_unique_layer_keys(layers_df)
    return factor_df.join(
        layers_df.select(["instrument_key", layer_column, "layer_version"]),
        on="instrument_key",
        how="left",
    ).with_columns(pl.col(layer_column).fill_null("unlayered"))


def build_layered_pre_eval_summary(
    factor_df: pl.DataFrame,
    *,
    score_column: str,
    labels_df: pl.DataFrame,
    layers_df: pl.DataFrame,
    layer_column: str = "primary_tradability_layer",
    min_instruments: int = 20,
    min_dates: int = 3,
    label_column: str = LABEL_NAME,
    mi_permutation_count: int = 100,
) -> dict[str, Any]:
    if score_column not in factor_df.columns:
        raise ValueError(f"Missing score column `{score_column}` in factor output.")
    if min_instruments < 1 or min_dates < 1:
        raise ValueError("min_instruments and min_dates must be positive.")

    joined_factor = _layer_join_frame(factor_df, layers_df, layer_column)
    factor_dates = sorted({str(value) for value in factor_df["date"].to_list()})
    date_annotations = build_regime_slice_frame(factor_dates)
    layer_values = sorted(str(value) for value in joined_factor[layer_column].unique().to_list())
    summaries: list[dict[str, Any]] = []

    for layer_value in layer_values:
        subset = joined_factor.filter(pl.col(layer_column) == layer_value).drop(["layer_version"])
        if subset.is_empty():
            continue
        layer_summary = build_pre_eval_summary(
            subset,
            score_column=score_column,
            labels_df=labels_df,
            date_annotations=date_annotations,
            label_column=label_column,
            mi_permutation_count=mi_permutation_count,
        )
        instrument_count = subset["instrument_key"].n_unique()
        labeled_date_count = int(layer_summary["labeled_date_count"])
        diagnostic_only = instrument_count < min_instruments or labeled_date_count < min_dates
        summaries.append(
            {
                "layer_value": layer_value,
                "diagnostic_only": diagnostic_only,
                "diagnostic_reason": (
                    "below_minimum_coverage"
                    if diagnostic_only
                    else "coverage_ok"
                ),
                "instrument_count": instrument_count,
                "factor_row_count": subset.height,
                "labeled_date_count": labeled_date_count,
                "joined_rows": layer_summary["joined_rows"],
                "aggregate_metrics": layer_summary["aggregate_metrics"],
                "per_date": layer_summary["per_date"],
            }
        )

    unlayered_rows = joined_factor.filter(pl.col(layer_column) == "unlayered").height
    layer_versions = sorted(
        str(value)
        for value in joined_factor["layer_version"].drop_nulls().unique().to_list()
    )
    return {
        "layer_column": layer_column,
        "layer_versions": layer_versions,
        "min_instruments": min_instruments,
        "min_dates": min_dates,
        "factor_date_count": len(factor_dates),
        "factor_dates": factor_dates,
        "factor_rows": factor_df.height,
        "unlayered_factor_rows": unlayered_rows,
        "layer_count": len(summaries),
        "layers": summaries,
        "layer_preview": _records(
            joined_factor.select(["date", "instrument_key", score_column, layer_column]).head(10)
        ),
    }


def run_layered_pre_eval_for_factor(
    *,
    factor_name: str,
    experiment_id: str = "",
    labels_path: Path,
    layer_path: Path = DEFAULT_LAYER_PATH,
    layer_column: str = "primary_tradability_layer",
    min_instruments: int = 20,
    min_dates: int = 3,
    notes: str = "",
) -> tuple[str, dict[str, Any], Path]:
    entry = _find_experiment(read_experiment_log(), factor_name, experiment_id)
    run_summary = _load_run_summary(entry)
    factor_df = _load_factor_output(entry)
    labels_df = pl.read_parquet(labels_path)
    layers_df = pl.read_parquet(layer_path)
    score_column = str(run_summary["score_column"])
    summary = build_layered_pre_eval_summary(
        factor_df,
        score_column=score_column,
        labels_df=labels_df,
        layers_df=layers_df,
        layer_column=layer_column,
        min_instruments=min_instruments,
        min_dates=min_dates,
    )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    layered_pre_eval_id = f"layered_pre_{stamp}_{entry['experiment_id']}"
    run_dir = RUN_ROOT / layered_pre_eval_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "layered_pre_eval_summary.json"
    payload = {
        "layered_pre_eval_id": layered_pre_eval_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": entry["experiment_id"],
        "factor_name": factor_name,
        "score_column": score_column,
        "labels_path": str(labels_path),
        "layer_path": str(layer_path),
        "target_instrument_universe": str(run_summary.get("target_instrument_universe", "")),
        "source_instrument_universe": str(run_summary.get("source_instrument_universe", "")),
        "universe_filter_version": str(run_summary.get("universe_filter_version", "")),
        "notes": notes,
        **summary,
    }
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return layered_pre_eval_id, payload, summary_path


def main() -> int:
    args = parse_args()
    layered_pre_eval_id, payload, summary_path = run_layered_pre_eval_for_factor(
        factor_name=args.factor,
        experiment_id=args.experiment,
        labels_path=Path(args.labels_path),
        layer_path=Path(args.layer_path),
        layer_column=args.layer_column,
        min_instruments=args.min_instruments,
        min_dates=args.min_dates,
        notes=args.notes,
    )
    print(
        f"{layered_pre_eval_id} factor={payload['factor_name']} "
        f"layers={payload['layer_count']} unlayered_rows={payload['unlayered_factor_rows']} "
        f"summary={summary_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
