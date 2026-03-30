"""Run a safe Phase A factor on upstream verified partitions."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib
import inspect
import json
from pathlib import Path
import sys

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.diagnostics import build_signal_diagnostics
from gatekeeper.gate_a_data import load_research_card
from harness.daily_agg import (
    build_daily_agg_cache_loader,
    load_daily_agg_lazy,
    missing_daily_agg_dates,
    missing_named_daily_agg_dates,
)
from harness.run_phase_a import build_record, append_experiment_log, append_lineage
from harness.verified_reader import load_verified_lazy, previous_available_dates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a verified-layer factor on one or more dates.")
    parser.add_argument("--card", required=True, help="Research card path.")
    parser.add_argument("--factor", required=True, help="Factor module name under factor_defs/ .")
    parser.add_argument("--dates", nargs="+", required=True, help="Trading dates like 2026-03-13.")
    parser.add_argument("--owner", default="agent", help="Experiment owner.")
    parser.add_argument("--notes", default="", help="Short run note.")
    parser.add_argument("--parent", default="", help="Optional parent experiment id.")
    parser.add_argument(
        "--allow-with-caveat",
        action="store_true",
        help="Allow materialization when Gate A returns allow_with_caveat.",
    )
    return parser.parse_args()


def _load_factor_module(factor_name: str):
    return importlib.import_module(f"factor_defs.{factor_name}")


def _required_columns(card: dict[str, object]) -> list[str]:
    fields = [str(field) for field in card["required_fields"]]
    required = ["date", "source_file"] + fields
    return list(dict.fromkeys(required))


def _compute_context_dates(
    *,
    table_name: str,
    requested_dates: list[str],
    lookback_steps: int,
) -> tuple[list[str], dict[str, str]]:
    if lookback_steps <= 0:
        return requested_dates, {}
    previous_map = previous_available_dates(table_name, requested_dates, step=lookback_steps)
    context_dates = sorted(set(requested_dates) | set(previous_map.values()))
    return context_dates, previous_map


def _build_partition_loader(table_name: str):
    def _load(dates: list[str], columns: list[str]) -> pl.LazyFrame:
        return load_verified_lazy(table_name, dates, columns)

    return _load


def _joined_table_name(table_names: list[str]) -> str:
    return "+".join(sorted(dict.fromkeys(table_names)))


def _factor_kwargs(compute_signal, *, target_dates: list[str], previous_date_map: dict[str, str]) -> dict[str, object]:
    params = inspect.signature(compute_signal).parameters
    kwargs: dict[str, object] = {}
    if "target_dates" in params:
        kwargs["target_dates"] = target_dates
    if "previous_date_map" in params:
        kwargs["previous_date_map"] = previous_date_map
    return kwargs


def run_verified_factor_experiment(
    *,
    card_path: Path,
    factor_name: str,
    dates: list[str],
    owner: str,
    notes: str,
    parent_experiment_id: str = "",
    allow_with_caveat: bool = False,
) -> tuple[object, dict[str, object] | None]:
    card = load_research_card(card_path)

    record, artifact = build_record(
        card_path=card_path,
        factor_name=factor_name,
        owner=owner,
        notes=notes,
        parent_experiment_id=parent_experiment_id,
    )
    append_experiment_log(record)
    append_lineage(record, artifact)

    if record.gate_a_decision == "fail":
        return record, None
    if record.gate_a_decision == "allow_with_caveat" and not allow_with_caveat:
        return record, None

    module = _load_factor_module(factor_name)
    table_name = getattr(module, "INPUT_TABLE")
    score_column = getattr(module, "OUTPUT_COLUMN")
    lookback_steps = int(getattr(module, "LOOKBACK_STEPS", 0))
    required_columns = _required_columns(card)
    load_dates, previous_date_map = _compute_context_dates(
        table_name=table_name,
        requested_dates=dates,
        lookback_steps=lookback_steps,
    )
    signal_lazy: pl.LazyFrame
    source_mode = "verified_raw"
    source_table_name = table_name
    loaded_columns = required_columns
    input_columns_by_table: dict[str, list[str]] = {}
    daily_table_name = getattr(module, "DAILY_AGG_TABLE", "")
    daily_table_map = dict(getattr(module, "DAILY_AGG_TABLES", {}))
    if daily_table_map and hasattr(module, "compute_signal_from_cache_loader"):
        missing_cache = missing_named_daily_agg_dates(daily_table_map, load_dates)
        if not missing_cache:
            source_mode = "daily_agg_multi"
            source_table_name = _joined_table_name(list(daily_table_map))
            input_columns_by_table = {name: list(columns) for name, columns in daily_table_map.items()}
            signal_lazy = module.compute_signal_from_cache_loader(
                cache_loader=build_daily_agg_cache_loader(daily_table_map),
                **_factor_kwargs(
                    module.compute_signal_from_cache_loader,
                    target_dates=dates,
                    previous_date_map=previous_date_map,
                ),
            )
        else:
            missing_text = ", ".join(
                f"{name}[{','.join(table_dates)}]"
                for name, table_dates in sorted(missing_cache.items())
            )
            raise FileNotFoundError(f"Missing daily agg cache partitions for `{factor_name}`: {missing_text}")
    elif daily_table_name and hasattr(module, "compute_signal_from_daily"):
        daily_columns = list(getattr(module, "DAILY_SOURCE_COLUMNS", []))
        missing_cache = missing_daily_agg_dates(daily_table_name, load_dates)
        if not missing_cache:
            source_mode = "daily_agg"
            source_table_name = daily_table_name
            loaded_columns = daily_columns
            input_columns_by_table = {daily_table_name: daily_columns}
            daily_frame = load_daily_agg_lazy(daily_table_name, load_dates, daily_columns)
            signal_lazy = module.compute_signal_from_daily(
                daily_frame,
                **_factor_kwargs(module.compute_signal_from_daily, target_dates=dates, previous_date_map=previous_date_map),
            )
        elif hasattr(module, "compute_signal_from_loader"):
            signal_lazy = module.compute_signal_from_loader(
                table_loader=_build_partition_loader(table_name),
                target_dates=dates,
                previous_date_map=previous_date_map,
            )
        else:
            lazy_frame = load_verified_lazy(table_name, load_dates, required_columns)
            signal_lazy = module.compute_signal(
                lazy_frame,
                **_factor_kwargs(module.compute_signal, target_dates=dates, previous_date_map=previous_date_map),
            )
    elif hasattr(module, "compute_signal_from_loader"):
        signal_lazy = module.compute_signal_from_loader(
            table_loader=_build_partition_loader(table_name),
            target_dates=dates,
            previous_date_map=previous_date_map,
        )
    else:
        lazy_frame = load_verified_lazy(table_name, load_dates, required_columns)
        signal_lazy = module.compute_signal(
            lazy_frame,
            **_factor_kwargs(module.compute_signal, target_dates=dates, previous_date_map=previous_date_map),
        )
    signal_df = signal_lazy.collect()
    diagnostics = build_signal_diagnostics(signal_df, score_column=score_column)

    run_dir = Path(record.run_dir)
    signal_path = run_dir / "factor_output.parquet"
    preview_path = run_dir / "preview.json"
    summary_path = run_dir / "data_run_summary.json"
    diagnostics_path = run_dir / "diagnostics_summary.json"

    signal_df.write_parquet(signal_path)
    preview_rows = signal_df.head(10).to_dicts()
    preview_path.write_text(json.dumps(preview_rows, indent=2, default=str), encoding="utf-8")
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2, default=str), encoding="utf-8")
    summary = {
        "experiment_id": record.experiment_id,
        "factor_name": factor_name,
        "table_name": source_table_name,
        "upstream_table_name": table_name,
        "data_source_mode": source_mode,
        "score_column": score_column,
        "dates": dates,
        "loaded_dates": load_dates,
        "card_required_fields": required_columns,
        "input_columns": loaded_columns,
        "input_columns_by_table": input_columns_by_table,
        "output_rows": signal_df.height,
        "output_columns": signal_df.columns,
        "artifacts": {
            "factor_output": str(signal_path),
            "preview": str(preview_path),
            "diagnostics_summary": str(diagnostics_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return record, summary


def main() -> int:
    args = parse_args()
    record, summary = run_verified_factor_experiment(
        card_path=ROOT / args.card,
        factor_name=args.factor,
        dates=args.dates,
        owner=args.owner,
        notes=args.notes,
        parent_experiment_id=args.parent,
        allow_with_caveat=args.allow_with_caveat,
    )

    if record.gate_a_decision == "fail":
        print(f"{record.experiment_id} decision=fail status=discard factor={args.factor}")
        return 1
    if record.gate_a_decision == "allow_with_caveat" and not args.allow_with_caveat:
        print(
            f"{record.experiment_id} decision=allow_with_caveat status=manual_review "
            f"factor={args.factor} data_run=skipped"
        )
        return 0

    print(
        f"{record.experiment_id} decision={record.gate_a_decision} "
        f"status={record.status} factor={args.factor} output_rows={summary['output_rows'] if summary else 0}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
