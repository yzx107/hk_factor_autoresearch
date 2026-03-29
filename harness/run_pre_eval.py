"""Run the fixed forward-return pre-eval harness for a factor experiment."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.pre_eval import (
    LABEL_NAME,
    build_close_like_frame,
    build_forward_return_labels,
    build_pre_eval_summary,
)
from harness.compare_factors import read_experiment_log
from harness.daily_agg import load_daily_agg_lazy, missing_daily_agg_dates
from harness.verified_reader import load_verified_lazy, next_available_dates

PRE_EVAL_LOG = ROOT / "registry" / "pre_eval_log.tsv"
RUN_ROOT = ROOT / "runs"


def ensure_pre_eval_log(path: Path = PRE_EVAL_LOG) -> None:
    if path.exists():
        return
    path.write_text(
        "pre_eval_id\tcreated_at\texperiment_id\tfactor_name\tscore_column\t"
        "label_name\tevaluated_dates\tjoined_rows\tmean_rank_ic\tmean_abs_rank_ic\t"
        "mean_top_bottom_spread\tsummary_path\tnotes\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run fixed pre-eval for a factor experiment.")
    parser.add_argument("--factor", required=True, help="Factor name to pre-evaluate.")
    parser.add_argument("--experiment", default="", help="Optional explicit experiment id.")
    parser.add_argument(
        "--labels-path",
        default="",
        help="Optional parquet file with prebuilt labels to avoid re-reading verified trades.",
    )
    parser.add_argument("--notes", default="", help="Short pre-eval note.")
    return parser.parse_args()


def _find_experiment(entries: list[dict[str, str]], factor_name: str, experiment_id: str) -> dict[str, str]:
    if experiment_id:
        for entry in entries:
            if entry["experiment_id"] == experiment_id:
                if entry["factor_name"] != factor_name:
                    raise ValueError(
                        f"Experiment `{experiment_id}` belongs to `{entry['factor_name']}`, not `{factor_name}`."
                    )
                return entry
        raise ValueError(f"Experiment `{experiment_id}` not found.")

    for entry in reversed(entries):
        if entry["factor_name"] == factor_name and (Path(entry["run_dir"]) / "data_run_summary.json").exists():
            return entry
    raise ValueError(f"No experiment found for factor `{factor_name}`.")


def _load_run_summary(entry: dict[str, str]) -> dict[str, object]:
    path = Path(entry["run_dir"]) / "data_run_summary.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing data run summary for experiment `{entry['experiment_id']}`.")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_factor_output(entry: dict[str, str]) -> pl.DataFrame:
    path = Path(entry["run_dir"]) / "factor_output.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing factor output for experiment `{entry['experiment_id']}`.")
    return pl.read_parquet(path)


def _append_pre_eval_log(
    *,
    pre_eval_id: str,
    created_at: str,
    experiment_id: str,
    factor_name: str,
    score_column: str,
    summary: dict[str, object],
    summary_path: Path,
    notes: str,
    path: Path = PRE_EVAL_LOG,
) -> None:
    ensure_pre_eval_log(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                pre_eval_id,
                created_at,
                experiment_id,
                factor_name,
                score_column,
                summary["label_name"],
                ",".join(str(date) for date in summary["labeled_dates"]),
                summary["joined_rows"],
                summary["mean_rank_ic"],
                summary["mean_abs_rank_ic"],
                summary["mean_top_bottom_spread"],
                str(summary_path),
                notes,
            ]
        )


def run_pre_eval_for_factor(
    *,
    factor_name: str,
    experiment_id: str = "",
    labels_path: Path | None = None,
    notes: str = "",
) -> tuple[str, dict[str, object], Path]:
    entries = read_experiment_log()
    entry = _find_experiment(entries, factor_name, experiment_id)
    run_summary = _load_run_summary(entry)
    score_column = str(run_summary["score_column"])
    factor_df = _load_factor_output(entry)
    factor_dates = sorted(
        {value.isoformat() if hasattr(value, "isoformat") else str(value) for value in factor_df["date"]}
    )

    if labels_path:
        labels_df = pl.read_parquet(labels_path)
    else:
        next_map = next_available_dates("verified_trades", factor_dates, step=1)
        label_dates = sorted(set(factor_dates) | set(next_map.values()))
        if not missing_daily_agg_dates("verified_trades_daily", label_dates):
            close_like = (
                load_daily_agg_lazy(
                    "verified_trades_daily",
                    label_dates,
                    ["date", "instrument_key", "close_like_price"],
                )
                .collect()
                .sort(["date", "instrument_key"])
            )
        else:
            trades = load_verified_lazy(
                "verified_trades",
                label_dates,
                ["date", "source_file", "Time", "Price", "row_num_in_file"],
            )
            close_like = build_close_like_frame(trades)
        labels_df = build_forward_return_labels(close_like, next_date_map=next_map, label_name=LABEL_NAME)
    summary = build_pre_eval_summary(factor_df, score_column=score_column, labels_df=labels_df, label_column=LABEL_NAME)

    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pre_eval_id = f"pre_{stamp}_{entry['experiment_id']}"
    run_dir = RUN_ROOT / pre_eval_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "pre_eval_summary.json"
    label_preview_path = run_dir / "label_preview.json"

    payload = {
        "pre_eval_id": pre_eval_id,
        "created_at": created_at,
        "experiment_id": entry["experiment_id"],
        "factor_name": entry["factor_name"],
        "score_column": score_column,
        "notes": notes,
        "labels_path": str(labels_path) if labels_path else "",
        **summary,
    }
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    label_preview_path.write_text(
        json.dumps(labels_df.head(10).to_dicts(), indent=2, default=str),
        encoding="utf-8",
    )
    _append_pre_eval_log(
        pre_eval_id=pre_eval_id,
        created_at=created_at,
        experiment_id=entry["experiment_id"],
        factor_name=entry["factor_name"],
        score_column=score_column,
        summary=summary,
        summary_path=summary_path,
        notes=notes,
    )
    return pre_eval_id, payload, summary_path


def main() -> int:
    args = parse_args()
    pre_eval_id, payload, _ = run_pre_eval_for_factor(
        factor_name=args.factor,
        experiment_id=args.experiment,
        labels_path=Path(args.labels_path) if args.labels_path else None,
        notes=args.notes,
    )

    print(
        f"{pre_eval_id} factor={payload['factor_name']} "
        f"evaluated_dates={payload['labeled_date_count']} "
        f"joined_rows={payload['joined_rows']} "
        f"mean_abs_rank_ic={payload['mean_abs_rank_ic']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
