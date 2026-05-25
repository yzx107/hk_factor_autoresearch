"""Build a layer response board across latest factor experiments."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.compare_factors import read_experiment_log
from harness.run_layered_pre_eval import (
    DEFAULT_LAYER_PATH,
    build_layered_pre_eval_summary,
)
from harness.run_pre_eval import _load_factor_output, _load_run_summary

RUN_ROOT = ROOT / "runs"
DEFAULT_MIN_ABS_RANK_IC = 0.05
DEFAULT_MIN_NMI = 0.03
DEFAULT_DISPERSION_THRESHOLD = 0.08
PRIMARY_LAYER_COLUMN = "primary_tradability_layer"
SOUTHBOUND_LAYER_COLUMN = "southbound_bucket"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a layer response board for latest factor experiments.")
    parser.add_argument("--labels-path", required=True, help="Parquet file with forward labels.")
    parser.add_argument("--layer-path", default=str(DEFAULT_LAYER_PATH), help="Universe layer parquet path.")
    parser.add_argument("--factors", nargs="*", default=[], help="Optional factor subset. Defaults to all latest factors.")
    parser.add_argument("--min-instruments", type=int, default=20, help="Minimum instruments for non-diagnostic layer.")
    parser.add_argument("--min-dates", type=int, default=3, help="Minimum labeled dates for non-diagnostic layer.")
    parser.add_argument("--min-abs-rank-ic", type=float, default=DEFAULT_MIN_ABS_RANK_IC)
    parser.add_argument("--min-nmi", type=float, default=DEFAULT_MIN_NMI)
    parser.add_argument("--dispersion-threshold", type=float, default=DEFAULT_DISPERSION_THRESHOLD)
    parser.add_argument("--mi-permutation-count", type=int, default=25, help="Permutation count for board diagnostics.")
    parser.add_argument("--notes", default="", help="Short board note.")
    return parser.parse_args()


def _has_materialized_output(entry: dict[str, str]) -> bool:
    run_dir = Path(entry["run_dir"])
    return (run_dir / "data_run_summary.json").exists() and (run_dir / "factor_output.parquet").exists()


def latest_materialized_entries(
    entries: list[dict[str, str]],
    *,
    factors: list[str] | None = None,
) -> list[dict[str, str]]:
    selected = set(factors or [])
    latest: dict[str, dict[str, str]] = {}
    for entry in entries:
        factor_name = entry["factor_name"]
        if selected and factor_name not in selected:
            continue
        if _has_materialized_output(entry):
            latest[factor_name] = entry
    if selected:
        missing = sorted(selected - set(latest))
        if missing:
            raise ValueError(f"No materialized latest experiment for factors: {', '.join(missing)}")
    return [latest[name] for name in sorted(latest)]


def add_southbound_bucket(layers_df: pl.DataFrame) -> pl.DataFrame:
    frame = layers_df
    if "southbound_eligible_known" not in frame.columns:
        frame = frame.with_columns(pl.lit(False).alias("southbound_eligible_known"))
    if "southbound_eligible" not in frame.columns:
        frame = frame.with_columns(pl.lit(False).alias("southbound_eligible"))
    return frame.with_columns(
        pl.when(pl.col("southbound_eligible_known") & pl.col("southbound_eligible"))
        .then(pl.lit("southbound_eligible"))
        .when(pl.col("southbound_eligible_known"))
        .then(pl.lit("southbound_not_eligible"))
        .otherwise(pl.lit("southbound_unknown"))
        .alias(SOUTHBOUND_LAYER_COLUMN)
    )


def _metric(metrics: dict[str, Any], key: str) -> float | None:
    value = metrics.get(key)
    return None if value is None else float(value)


def compact_layer_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for layer in summary.get("layers", []):
        metrics = layer.get("aggregate_metrics", {})
        rows.append(
            {
                "layer_value": layer["layer_value"],
                "diagnostic_only": bool(layer["diagnostic_only"]),
                "instrument_count": int(layer["instrument_count"]),
                "labeled_date_count": int(layer["labeled_date_count"]),
                "joined_rows": int(layer["joined_rows"]),
                "rank_ic": _metric(metrics, "rank_ic"),
                "abs_rank_ic": _metric(metrics, "abs_rank_ic"),
                "nmi": _metric(metrics, "nmi"),
                "top_bottom_spread": _metric(metrics, "top_bottom_spread"),
            }
        )
    return rows


def _signal_rows(
    rows: list[dict[str, Any]],
    *,
    min_abs_rank_ic: float,
    min_nmi: float,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for row in rows:
        if row["diagnostic_only"]:
            continue
        abs_rank_ic = row.get("abs_rank_ic")
        nmi = row.get("nmi")
        if (abs_rank_ic is not None and abs_rank_ic >= min_abs_rank_ic) or (nmi is not None and nmi >= min_nmi):
            signals.append(row)
    return signals


def _strongest_and_weakest(rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    scored = [row for row in rows if not row["diagnostic_only"] and row.get("abs_rank_ic") is not None]
    if not scored:
        return None, None
    return (
        max(scored, key=lambda row: float(row["abs_rank_ic"])),
        min(scored, key=lambda row: float(row["abs_rank_ic"])),
    )


def classify_layer_response(
    rows: list[dict[str, Any]],
    *,
    min_abs_rank_ic: float = DEFAULT_MIN_ABS_RANK_IC,
    min_nmi: float = DEFAULT_MIN_NMI,
    dispersion_threshold: float = DEFAULT_DISPERSION_THRESHOLD,
) -> dict[str, Any]:
    signals = _signal_rows(rows, min_abs_rank_ic=min_abs_rank_ic, min_nmi=min_nmi)
    strongest, weakest = _strongest_and_weakest(rows)
    dispersion = None
    if strongest is not None and weakest is not None:
        dispersion = float(strongest["abs_rank_ic"]) - float(weakest["abs_rank_ic"])
    strongest_value = "" if strongest is None else str(strongest["layer_value"])
    weakest_value = "" if weakest is None else str(weakest["layer_value"])

    signal_values = {str(row["layer_value"]) for row in signals}
    if not signals:
        classification = "no_layer_signal"
        reason = "no non-diagnostic layer clears the signal thresholds"
    elif len(signals) >= 2 and dispersion is not None and dispersion >= dispersion_threshold:
        if strongest_value == "small_illiquid_special":
            classification = "small_illiquid_dominant_risk"
            reason = "signal clears multiple layers but is dominated by small_illiquid_special"
        elif strongest_value == "new_or_recent_listing":
            classification = "new_listing_dominant_watch"
            reason = "signal clears multiple layers but is dominated by new_or_recent_listing"
        elif strongest_value == "large_liquid_core":
            classification = "large_liquid_dominant"
            reason = "signal clears multiple layers but is dominated by large_liquid_core"
        elif strongest_value == "mid_liquid_tradable":
            classification = "mid_liquid_dominant"
            reason = "signal clears multiple layers but is dominated by mid_liquid_tradable"
        else:
            classification = "unstable_across_layers"
            reason = "layer dispersion is above threshold"
    elif len(signals) >= 3:
        classification = "broad_candidate"
        reason = "signal clears thresholds in at least three layers"
    elif signal_values == {"large_liquid_core"}:
        classification = "large_liquid_candidate"
        reason = "signal is concentrated in large_liquid_core"
    elif signal_values == {"mid_liquid_tradable"}:
        classification = "mid_liquid_candidate"
        reason = "signal is concentrated in mid_liquid_tradable"
    elif signal_values == {"new_or_recent_listing"}:
        classification = "new_listing_only_watch"
        reason = "signal is concentrated in new_or_recent_listing"
    elif signal_values == {"small_illiquid_special"}:
        classification = "small_illiquid_only_risk"
        reason = "signal is concentrated in small_illiquid_special"
    else:
        classification = "selective_layer_candidate"
        reason = "signal clears thresholds in a limited layer subset"

    return {
        "classification": classification,
        "classification_reason": reason,
        "signal_layer_count": len(signals),
        "signal_layers": sorted(signal_values),
        "strongest_layer": strongest_value,
        "weakest_layer": weakest_value,
        "max_abs_rank_ic": None if strongest is None else strongest.get("abs_rank_ic"),
        "min_abs_rank_ic": None if weakest is None else weakest.get("abs_rank_ic"),
        "layer_dispersion": dispersion,
    }


def build_factor_board_row(
    entry: dict[str, str],
    *,
    labels_df: pl.DataFrame,
    layers_df: pl.DataFrame,
    min_instruments: int,
    min_dates: int,
    min_abs_rank_ic: float,
    min_nmi: float,
    dispersion_threshold: float,
    mi_permutation_count: int,
) -> dict[str, Any]:
    run_summary = _load_run_summary(entry)
    factor_df = _load_factor_output(entry)
    score_column = str(run_summary["score_column"])
    primary_summary = build_layered_pre_eval_summary(
        factor_df,
        score_column=score_column,
        labels_df=labels_df,
        layers_df=layers_df,
        layer_column=PRIMARY_LAYER_COLUMN,
        min_instruments=min_instruments,
        min_dates=min_dates,
        mi_permutation_count=mi_permutation_count,
    )
    southbound_layers = add_southbound_bucket(layers_df)
    southbound_summary = build_layered_pre_eval_summary(
        factor_df,
        score_column=score_column,
        labels_df=labels_df,
        layers_df=southbound_layers,
        layer_column=SOUTHBOUND_LAYER_COLUMN,
        min_instruments=min_instruments,
        min_dates=min_dates,
        mi_permutation_count=mi_permutation_count,
    )
    primary_rows = compact_layer_rows(primary_summary)
    southbound_rows = compact_layer_rows(southbound_summary)
    classification = classify_layer_response(
        primary_rows,
        min_abs_rank_ic=min_abs_rank_ic,
        min_nmi=min_nmi,
        dispersion_threshold=dispersion_threshold,
    )
    return {
        "factor_name": entry["factor_name"],
        "experiment_id": entry["experiment_id"],
        "run_dir": entry["run_dir"],
        "score_column": score_column,
        "target_instrument_universe": str(run_summary.get("target_instrument_universe", "")),
        "source_instrument_universe": str(run_summary.get("source_instrument_universe", "")),
        "universe_filter_version": str(run_summary.get("universe_filter_version", "")),
        "primary_layer_rows": primary_rows,
        "southbound_layer_rows": southbound_rows,
        "unlayered_factor_rows": int(primary_summary["unlayered_factor_rows"]),
        **classification,
    }


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _layer_metric(rows: list[dict[str, Any]], layer_value: str, key: str = "abs_rank_ic") -> float | None:
    for row in rows:
        if row["layer_value"] == layer_value:
            return row.get(key)
    return None


def write_markdown_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Layered Factor Board",
        "",
        f"- board_id: `{payload['board_id']}`",
        f"- created_at: `{payload['created_at']}`",
        f"- factor_count: `{payload['factor_count']}`",
        f"- success_count: `{payload['success_count']}`",
        f"- failed_count: `{payload['failed_count']}`",
        f"- labels_path: `{payload['labels_path']}`",
        f"- layer_path: `{payload['layer_path']}`",
        "",
        "## Classification Counts",
        "",
    ]
    for name, count in sorted(payload["classification_counts"].items()):
        lines.append(f"- `{name}`: {count}")
    lines.extend(
        [
            "",
            "## Factor Board",
            "",
            "| factor | class | strongest | weakest | large | mid | new | small | southbound | not_eligible | unknown |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload["factors"]:
        primary = row["primary_layer_rows"]
        southbound = row["southbound_layer_rows"]
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['factor_name']}`",
                    f"`{row['classification']}`",
                    row["strongest_layer"],
                    row["weakest_layer"],
                    _fmt(_layer_metric(primary, "large_liquid_core")),
                    _fmt(_layer_metric(primary, "mid_liquid_tradable")),
                    _fmt(_layer_metric(primary, "new_or_recent_listing")),
                    _fmt(_layer_metric(primary, "small_illiquid_special")),
                    _fmt(_layer_metric(southbound, "southbound_eligible")),
                    _fmt(_layer_metric(southbound, "southbound_not_eligible")),
                    _fmt(_layer_metric(southbound, "southbound_unknown")),
                ]
            )
            + " |"
        )
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for item in payload["failures"]:
            lines.append(f"- `{item['factor_name']}`: {item['error']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_layered_factor_board(
    *,
    labels_path: Path,
    layer_path: Path = DEFAULT_LAYER_PATH,
    factors: list[str] | None = None,
    min_instruments: int = 20,
    min_dates: int = 3,
    min_abs_rank_ic: float = DEFAULT_MIN_ABS_RANK_IC,
    min_nmi: float = DEFAULT_MIN_NMI,
    dispersion_threshold: float = DEFAULT_DISPERSION_THRESHOLD,
    mi_permutation_count: int = 25,
    notes: str = "",
) -> tuple[str, dict[str, Any], Path]:
    labels_df = pl.read_parquet(labels_path)
    layers_df = pl.read_parquet(layer_path)
    entries = latest_materialized_entries(read_experiment_log(), factors=factors)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    board_id = f"layer_board_{stamp}"
    run_dir = RUN_ROOT / board_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "layered_factor_board.json"
    report_path = run_dir / "layered_factor_board.md"

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for entry in entries:
        try:
            rows.append(
                build_factor_board_row(
                    entry,
                    labels_df=labels_df,
                    layers_df=layers_df,
                    min_instruments=min_instruments,
                    min_dates=min_dates,
                    min_abs_rank_ic=min_abs_rank_ic,
                    min_nmi=min_nmi,
                    dispersion_threshold=dispersion_threshold,
                    mi_permutation_count=mi_permutation_count,
                )
            )
        except Exception as exc:  # keep batch board useful when one old artifact is stale
            failures.append({"factor_name": entry["factor_name"], "experiment_id": entry["experiment_id"], "error": str(exc)})

    rows.sort(key=lambda row: (row["classification"], row["factor_name"]))
    classification_counts = dict(Counter(row["classification"] for row in rows))
    payload = {
        "board_id": board_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "labels_path": str(labels_path),
        "layer_path": str(layer_path),
        "factor_count": len(entries),
        "success_count": len(rows),
        "failed_count": len(failures),
        "policy": {
            "min_instruments": min_instruments,
            "min_dates": min_dates,
            "min_abs_rank_ic": min_abs_rank_ic,
            "min_nmi": min_nmi,
            "dispersion_threshold": dispersion_threshold,
            "mi_permutation_count": mi_permutation_count,
        },
        "classification_counts": classification_counts,
        "factors": rows,
        "failures": failures,
        "notes": notes,
    }
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    write_markdown_report(payload, report_path)
    return board_id, payload, summary_path


def main() -> int:
    args = parse_args()
    board_id, payload, summary_path = build_layered_factor_board(
        labels_path=Path(args.labels_path),
        layer_path=Path(args.layer_path),
        factors=args.factors or None,
        min_instruments=args.min_instruments,
        min_dates=args.min_dates,
        min_abs_rank_ic=args.min_abs_rank_ic,
        min_nmi=args.min_nmi,
        dispersion_threshold=args.dispersion_threshold,
        mi_permutation_count=args.mi_permutation_count,
        notes=args.notes,
    )
    print(
        f"{board_id} factors={payload['factor_count']} success={payload['success_count']} "
        f"failed={payload['failed_count']} summary={summary_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
