"""Fixed comparison harness for factor run artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPERIMENT_LOG = ROOT / "registry" / "experiment_log.tsv"
COMPARISON_LOG = ROOT / "registry" / "comparison_log.tsv"
RUN_ROOT = ROOT / "runs"


def read_experiment_log(path: Path = EXPERIMENT_LOG) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def ensure_comparison_log(path: Path = COMPARISON_LOG) -> None:
    if path.exists():
        return
    path.write_text(
        "comparison_id\tcreated_at\tleft_experiment_id\tright_experiment_id\t"
        "left_factor\tright_factor\tcommon_dates\tcommon_rows\tsummary_path\tnotes\n",
        encoding="utf-8",
    )


def _has_materialized_output(entry: dict[str, str]) -> bool:
    return (Path(entry["run_dir"]) / "data_run_summary.json").exists()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two factor runs under a fixed harness.")
    parser.add_argument("--left-factor", required=True, help="Factor name for the left side.")
    parser.add_argument("--right-factor", required=True, help="Factor name for the right side.")
    parser.add_argument("--left-experiment", default="", help="Optional explicit left experiment id.")
    parser.add_argument("--right-experiment", default="", help="Optional explicit right experiment id.")
    parser.add_argument("--top-n", type=int, default=20, help="Top bucket size for overlap diagnostics.")
    parser.add_argument("--notes", default="", help="Short comparison note.")
    return parser.parse_args()


def _latest_experiment(entries: list[dict[str, str]], factor_name: str) -> dict[str, str]:
    for entry in reversed(entries):
        if entry["factor_name"] == factor_name and _has_materialized_output(entry):
            return entry
    raise ValueError(f"No experiment found for factor `{factor_name}`.")


def _find_experiment(entries: list[dict[str, str]], experiment_id: str) -> dict[str, str]:
    for entry in entries:
        if entry["experiment_id"] == experiment_id:
            return entry
    raise ValueError(f"Experiment `{experiment_id}` not found.")


def _resolve_experiment(entries: list[dict[str, str]], factor_name: str, experiment_id: str) -> dict[str, str]:
    if experiment_id:
        entry = _find_experiment(entries, experiment_id)
        if entry["factor_name"] != factor_name:
            raise ValueError(
                f"Experiment `{experiment_id}` belongs to `{entry['factor_name']}`, not `{factor_name}`."
            )
        return entry
    return _latest_experiment(entries, factor_name)


def _load_run_summary(entry: dict[str, str]) -> dict[str, Any]:
    path = Path(entry["run_dir"]) / "data_run_summary.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing run summary for experiment `{entry['experiment_id']}`.")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_factor_output(entry: dict[str, str]) -> pl.DataFrame:
    path = Path(entry["run_dir"]) / "factor_output.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing factor output for experiment `{entry['experiment_id']}`.")
    return pl.read_parquet(path)


def _top_overlap(
    left: pl.DataFrame,
    right: pl.DataFrame,
    *,
    left_score: str,
    right_score: str,
    top_n: int,
) -> list[dict[str, Any]]:
    left_top = left.sort(["date", left_score], descending=[False, True]).group_by("date").head(top_n)
    right_top = right.sort(["date", right_score], descending=[False, True]).group_by("date").head(top_n)
    overlap = (
        left_top.select(["date", "instrument_key"])
        .join(right_top.select(["date", "instrument_key"]), on=["date", "instrument_key"], how="inner")
        .group_by("date")
        .agg(pl.len().alias("top_overlap_count"))
        .sort("date")
    )
    return [
        {"date": str(row["date"]), "top_overlap_count": int(row["top_overlap_count"])}
        for row in overlap.to_dicts()
    ]


def build_comparison_summary(
    left_entry: dict[str, str],
    right_entry: dict[str, str],
    *,
    top_n: int,
) -> dict[str, Any]:
    left_summary = _load_run_summary(left_entry)
    right_summary = _load_run_summary(right_entry)
    left_score = left_summary["score_column"]
    right_score = right_summary["score_column"]

    left_df = _load_factor_output(left_entry)
    right_df = _load_factor_output(right_entry)

    joined = left_df.select(["date", "instrument_key", left_score]).join(
        right_df.select(["date", "instrument_key", right_score]),
        on=["date", "instrument_key"],
        how="inner",
    )

    per_date = (
        joined.group_by("date")
        .agg(
            [
                pl.len().alias("common_rows"),
                pl.corr(left_score, right_score).alias("pearson_corr"),
            ]
        )
        .sort("date")
    )

    comparison = {
        "left": {
            "experiment_id": left_entry["experiment_id"],
            "factor_name": left_entry["factor_name"],
            "score_column": left_score,
        },
        "right": {
            "experiment_id": right_entry["experiment_id"],
            "factor_name": right_entry["factor_name"],
            "score_column": right_score,
        },
        "common_dates": [str(row["date"]) for row in per_date.to_dicts()],
        "common_rows": int(joined.height),
        "per_date": [
            {
                "date": str(row["date"]),
                "common_rows": int(row["common_rows"]),
                "pearson_corr": None if row["pearson_corr"] is None else float(row["pearson_corr"]),
            }
            for row in per_date.to_dicts()
        ],
        "top_overlap": _top_overlap(
            left_df,
            right_df,
            left_score=left_score,
            right_score=right_score,
            top_n=top_n,
        ),
    }
    return comparison


def append_comparison_log(
    *,
    comparison_id: str,
    created_at: str,
    left_entry: dict[str, str],
    right_entry: dict[str, str],
    common_dates: list[str],
    common_rows: int,
    summary_path: Path,
    notes: str,
    path: Path = COMPARISON_LOG,
) -> None:
    ensure_comparison_log(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                comparison_id,
                created_at,
                left_entry["experiment_id"],
                right_entry["experiment_id"],
                left_entry["factor_name"],
                right_entry["factor_name"],
                ",".join(common_dates),
                common_rows,
                str(summary_path),
                notes,
            ]
        )


def run_factor_comparison(
    *,
    left_factor: str,
    right_factor: str,
    left_experiment: str = "",
    right_experiment: str = "",
    top_n: int = 20,
    notes: str = "",
) -> tuple[str, dict[str, Any], Path]:
    entries = read_experiment_log()
    left_entry = _resolve_experiment(entries, left_factor, left_experiment)
    right_entry = _resolve_experiment(entries, right_factor, right_experiment)
    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    comparison_id = f"cmp_{stamp}_{left_factor}__{right_factor}"
    run_dir = RUN_ROOT / comparison_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "comparison_summary.json"

    comparison = build_comparison_summary(left_entry, right_entry, top_n=top_n)
    payload = {
        "comparison_id": comparison_id,
        "created_at": created_at,
        "notes": notes,
        **comparison,
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    append_comparison_log(
        comparison_id=comparison_id,
        created_at=created_at,
        left_entry=left_entry,
        right_entry=right_entry,
        common_dates=comparison["common_dates"],
        common_rows=comparison["common_rows"],
        summary_path=summary_path,
        notes=notes,
    )
    return comparison_id, payload, summary_path


def main() -> int:
    args = parse_args()
    comparison_id, payload, _ = run_factor_comparison(
        left_factor=args.left_factor,
        right_factor=args.right_factor,
        left_experiment=args.left_experiment,
        right_experiment=args.right_experiment,
        top_n=args.top_n,
        notes=args.notes,
    )

    print(
        f"{comparison_id} left={payload['left']['factor_name']} right={payload['right']['factor_name']} "
        f"common_rows={payload['common_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
