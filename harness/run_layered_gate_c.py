"""Run layer-aware Gate C stress checks for promoted broad candidates."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from math import fsum
from pathlib import Path
import sys
from typing import Any

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest_engine.minimal_lane import run_minimal_backtest
from harness.run_layered_pre_eval_batch import add_southbound_bucket

RUN_ROOT = ROOT / "runs"
DEFAULT_DECISION_LOG = ROOT / "registry" / "layered_factor_decisions.tsv"
DEFAULT_GATE_C_LOG = ROOT / "registry" / "layered_gate_c_log.tsv"
DEFAULT_LABEL_COLUMN = "forward_return_1d_close_like"
PRIMARY_LAYER_COLUMN = "primary_tradability_layer"
SOUTHBOUND_LAYER_COLUMN = "southbound_bucket"

GATE_C_LOG_HEADER = [
    "gate_c_id",
    "created_at",
    "triage_id",
    "board_id",
    "factor_name",
    "gate_c_decision",
    "direction_hint",
    "base_cost_adjusted_spread_return",
    "base_hit_rate",
    "base_turnover_proxy",
    "base_stability_proxy",
    "primary_pass_layer_count",
    "southbound_pass_bucket_count",
    "time_pass_slice_count",
    "summary_path",
    "notes",
]

DECISION_ORDER = [
    "advance_gate_d_watch",
    "needs_southbound_split",
    "needs_layer_split",
    "hold_time_instability",
    "hold_cost_capacity",
]


def parse_args() -> argparse.Namespace:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    parser = argparse.ArgumentParser(description="Run layer-aware Gate C stress checks.")
    parser.add_argument("--layered-board", required=True, help="Source layered_factor_board.json.")
    parser.add_argument("--decision-log", default=str(DEFAULT_DECISION_LOG), help="Layered decision TSV.")
    parser.add_argument("--gate-log", default=str(DEFAULT_GATE_C_LOG), help="Append-only Gate C TSV.")
    parser.add_argument(
        "--doc-path",
        default=str(ROOT / "docs" / f"layered_gate_c_summary_{month}.md"),
        help="Tracked Gate C summary markdown path.",
    )
    parser.add_argument("--triage-id", default="", help="Optional triage_id filter. Defaults to latest in TSV.")
    parser.add_argument("--factors", nargs="*", default=[], help="Optional factor subset.")
    parser.add_argument("--label-column", default=DEFAULT_LABEL_COLUMN)
    parser.add_argument("--top-fraction", type=float, default=0.1)
    parser.add_argument("--cost-bps", type=float, default=15.0)
    parser.add_argument("--no-inverse", action="store_true", help="Disable inverse-direction stress selection.")
    parser.add_argument("--min-evaluated-dates", type=int, default=3)
    parser.add_argument("--min-cost-adjusted-spread", type=float, default=0.0)
    parser.add_argument("--min-hit-rate", type=float, default=0.52)
    parser.add_argument("--min-stability", type=float, default=0.55)
    parser.add_argument("--max-turnover-proxy", type=float, default=0.9)
    parser.add_argument("--min-primary-pass-layers", type=int, default=2)
    parser.add_argument("--notes", default="", help="Short Gate C note.")
    parser.add_argument("--json", action="store_true", help="Emit JSON payload.")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSON artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing TSV artifact: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _latest_triage_id(rows: list[dict[str, str]]) -> str:
    if not rows:
        raise ValueError("Decision log has no rows.")
    ordered = sorted(rows, key=lambda row: row.get("created_at", ""))
    return str(ordered[-1]["triage_id"])


def select_gate_c_candidates(
    decision_rows: list[dict[str, str]],
    *,
    triage_id: str = "",
    factors: list[str] | None = None,
) -> list[dict[str, str]]:
    selected_factors = set(factors or [])
    resolved_triage_id = triage_id or _latest_triage_id(decision_rows)
    rows = [
        row
        for row in decision_rows
        if row.get("triage_id") == resolved_triage_id
        and row.get("primary_decision") == "promote_broad_candidate"
        and (not selected_factors or row.get("factor_name") in selected_factors)
    ]
    missing = selected_factors - {str(row.get("factor_name")) for row in rows}
    if missing:
        raise ValueError(f"No promoted Gate C candidate rows for factors: {', '.join(sorted(missing))}")
    if not rows:
        raise ValueError("No promote_broad_candidate rows available for Gate C.")
    return sorted(rows, key=lambda row: str(row["factor_name"]))


def _normalize_frame(frame: pl.DataFrame) -> pl.DataFrame:
    if "date" in frame.columns:
        frame = frame.with_columns(pl.col("date").cast(pl.Utf8))
    if "instrument_key" in frame.columns:
        frame = frame.with_columns(pl.col("instrument_key").cast(pl.Utf8))
    return frame


def _compact_backtest(result: Any) -> dict[str, Any]:
    payload = result.as_dict()
    payload.pop("per_date", None)
    return payload


def _metric_for_direction(result: dict[str, Any]) -> float:
    value = result.get("cost_adjusted_spread_return")
    if value is None:
        return float("-inf")
    return float(value)


def _passes_backtest(result: dict[str, Any], policy: dict[str, Any]) -> bool:
    if int(result.get("evaluated_dates") or 0) < int(policy["min_evaluated_dates"]):
        return False
    cost_adjusted = result.get("cost_adjusted_spread_return")
    hit_rate = result.get("hit_rate")
    turnover = result.get("turnover_proxy")
    stability = result.get("stability_proxy")
    return (
        cost_adjusted is not None
        and float(cost_adjusted) > float(policy["min_cost_adjusted_spread"])
        and hit_rate is not None
        and float(hit_rate) >= float(policy["min_hit_rate"])
        and turnover is not None
        and float(turnover) <= float(policy["max_turnover_proxy"])
        and stability is not None
        and float(stability) >= float(policy["min_stability"])
    )


def _run_backtest(
    factor_df: pl.DataFrame,
    labels_df: pl.DataFrame,
    *,
    factor_name: str,
    score_column: str,
    direction: int = 1,
    label_column: str,
    top_fraction: float,
    cost_bps: float,
) -> dict[str, Any]:
    resolved_score_column = score_column
    frame = factor_df
    if direction not in {-1, 1}:
        raise ValueError("direction must be -1 or 1.")
    if direction == -1:
        resolved_score_column = "__gate_c_inverse_score"
        frame = factor_df.with_columns((pl.col(score_column) * -1.0).alias(resolved_score_column))
    result = run_minimal_backtest(
        frame,
        labels_df,
        factor_name=factor_name,
        score_column=resolved_score_column,
        label_column=label_column,
        top_fraction=top_fraction,
        cost_bps=cost_bps,
    )
    payload = _compact_backtest(result)
    payload["direction_hint"] = "inverse_candidate" if direction == -1 else "as_is_candidate"
    return payload


def _choose_base_direction(
    factor_df: pl.DataFrame,
    labels_df: pl.DataFrame,
    *,
    factor_name: str,
    score_column: str,
    label_column: str,
    top_fraction: float,
    cost_bps: float,
    allow_inverse: bool,
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    as_is = _run_backtest(
        factor_df,
        labels_df,
        factor_name=factor_name,
        score_column=score_column,
        direction=1,
        label_column=label_column,
        top_fraction=top_fraction,
        cost_bps=cost_bps,
    )
    if not allow_inverse:
        return 1, as_is, {"as_is_candidate": as_is}
    inverse = _run_backtest(
        factor_df,
        labels_df,
        factor_name=factor_name,
        score_column=score_column,
        direction=-1,
        label_column=label_column,
        top_fraction=top_fraction,
        cost_bps=cost_bps,
    )
    diagnostics = {"as_is_candidate": as_is, "inverse_candidate": inverse}
    if _metric_for_direction(inverse) > _metric_for_direction(as_is):
        return -1, inverse, diagnostics
    return 1, as_is, diagnostics


def _layer_subsets(
    factor_df: pl.DataFrame,
    layers_df: pl.DataFrame,
    *,
    layer_column: str,
) -> list[tuple[str, pl.DataFrame]]:
    joined = factor_df.join(
        layers_df.select(["instrument_key", layer_column]).unique(subset=["instrument_key"]),
        on="instrument_key",
        how="inner",
    ).drop_nulls([layer_column])
    values = sorted(str(value) for value in joined[layer_column].unique().to_list())
    return [(value, joined.filter(pl.col(layer_column) == value).drop(layer_column)) for value in values]


def _time_slices(factor_df: pl.DataFrame) -> list[tuple[str, pl.DataFrame]]:
    dates = sorted(str(value) for value in factor_df["date"].unique().to_list())
    if len(dates) < 2:
        return [("all_dates", factor_df)]
    mid = max(1, len(dates) // 2)
    return [
        ("early_half", factor_df.filter(pl.col("date").is_in(dates[:mid]))),
        ("late_half", factor_df.filter(pl.col("date").is_in(dates[mid:]))),
    ]


def _evaluate_subsets(
    subsets: list[tuple[str, pl.DataFrame]],
    labels_df: pl.DataFrame,
    *,
    factor_name: str,
    score_column: str,
    direction: int,
    label_column: str,
    top_fraction: float,
    cost_bps: float,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, frame in subsets:
        result = _run_backtest(
            frame,
            labels_df,
            factor_name=factor_name,
            score_column=score_column,
            direction=direction,
            label_column=label_column,
            top_fraction=top_fraction,
            cost_bps=cost_bps,
        )
        rows.append({"slice_value": name, "passed": _passes_backtest(result, policy), "result": result})
    return rows


def _decide_gate_c(
    *,
    base_passed: bool,
    primary_rows: list[dict[str, Any]],
    southbound_rows: list[dict[str, Any]],
    time_rows: list[dict[str, Any]],
    policy: dict[str, Any],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    primary_passes = [row for row in primary_rows if row["passed"] and row["slice_value"] not in {"unknown", "unlayered"}]
    southbound_named = [row for row in southbound_rows if row["slice_value"] in {"southbound_eligible", "southbound_unknown"}]
    southbound_named_passes = [row for row in southbound_named if row["passed"]]
    time_passes = [row for row in time_rows if row["passed"]]

    if not base_passed:
        reasons.append("base cost-adjusted backtest failed")
        return "hold_cost_capacity", reasons
    if len(time_passes) < len(time_rows):
        insufficient = [
            row["slice_value"]
            for row in time_rows
            if int(row["result"].get("evaluated_dates") or 0) < int(policy["min_evaluated_dates"])
        ]
        if insufficient:
            reasons.append(f"early/late time-slice evidence is insufficient: {','.join(insufficient)}")
        else:
            reasons.append("early/late time-slice stress failed")
        return "hold_time_instability", reasons
    if len(primary_passes) < int(policy["min_primary_pass_layers"]):
        reasons.append("not enough primary tradability layers passed")
        return "needs_layer_split", reasons
    if len(southbound_named) >= 2 and len(southbound_named_passes) < 2:
        reasons.append("southbound eligible and unknown buckets failed to both pass cost stress")
        return "needs_southbound_split", reasons
    return "advance_gate_d_watch", ["passed cost, layer, southbound, and time stress checks"]


def evaluate_gate_c_candidate(
    decision_row: dict[str, str],
    *,
    labels_df: pl.DataFrame,
    layers_df: pl.DataFrame,
    label_column: str,
    top_fraction: float,
    cost_bps: float,
    allow_inverse: bool,
    policy: dict[str, Any],
) -> dict[str, Any]:
    factor_name = str(decision_row["factor_name"])
    run_dir = Path(decision_row["run_dir"])
    run_summary = _load_json(run_dir / "data_run_summary.json")
    factor_df = _normalize_frame(pl.read_parquet(run_dir / "factor_output.parquet"))
    score_column = str(run_summary["score_column"])

    direction, base_result, direction_diagnostics = _choose_base_direction(
        factor_df,
        labels_df,
        factor_name=factor_name,
        score_column=score_column,
        label_column=label_column,
        top_fraction=top_fraction,
        cost_bps=cost_bps,
        allow_inverse=allow_inverse,
    )
    primary_rows = _evaluate_subsets(
        _layer_subsets(factor_df, layers_df, layer_column=PRIMARY_LAYER_COLUMN),
        labels_df,
        factor_name=factor_name,
        score_column=score_column,
        direction=direction,
        label_column=label_column,
        top_fraction=top_fraction,
        cost_bps=cost_bps,
        policy=policy,
    )
    southbound_rows = _evaluate_subsets(
        _layer_subsets(factor_df, add_southbound_bucket(layers_df), layer_column=SOUTHBOUND_LAYER_COLUMN),
        labels_df,
        factor_name=factor_name,
        score_column=score_column,
        direction=direction,
        label_column=label_column,
        top_fraction=top_fraction,
        cost_bps=cost_bps,
        policy=policy,
    )
    time_rows = _evaluate_subsets(
        _time_slices(factor_df),
        labels_df,
        factor_name=factor_name,
        score_column=score_column,
        direction=direction,
        label_column=label_column,
        top_fraction=top_fraction,
        cost_bps=cost_bps,
        policy=policy,
    )
    base_passed = _passes_backtest(base_result, policy)
    decision, reasons = _decide_gate_c(
        base_passed=base_passed,
        primary_rows=primary_rows,
        southbound_rows=southbound_rows,
        time_rows=time_rows,
        policy=policy,
    )
    return {
        "factor_name": factor_name,
        "source_triage_id": str(decision_row["triage_id"]),
        "source_run_dir": str(run_dir),
        "score_column": score_column,
        "direction_hint": base_result["direction_hint"],
        "gate_c_decision": decision,
        "gate_c_reasons": reasons,
        "base_passed": base_passed,
        "base_backtest": base_result,
        "direction_diagnostics": direction_diagnostics,
        "primary_layer_backtests": primary_rows,
        "southbound_backtests": southbound_rows,
        "time_slice_backtests": time_rows,
        "primary_pass_layer_count": sum(1 for row in primary_rows if row["passed"]),
        "southbound_pass_bucket_count": sum(1 for row in southbound_rows if row["passed"]),
        "time_pass_slice_count": sum(1 for row in time_rows if row["passed"]),
    }


def _ensure_tsv(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\t".join(GATE_C_LOG_HEADER) + "\n", encoding="utf-8")


def append_gate_c_log(
    *,
    gate_c_id: str,
    created_at: str,
    triage_id: str,
    board_id: str,
    rows: list[dict[str, Any]],
    summary_path: Path,
    path: Path,
    notes: str,
) -> None:
    _ensure_tsv(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        for row in rows:
            base = row["base_backtest"]
            writer.writerow(
                [
                    gate_c_id,
                    created_at,
                    triage_id,
                    board_id,
                    row["factor_name"],
                    row["gate_c_decision"],
                    row["direction_hint"],
                    base.get("cost_adjusted_spread_return"),
                    base.get("hit_rate"),
                    base.get("turnover_proxy"),
                    base.get("stability_proxy"),
                    row["primary_pass_layer_count"],
                    row["southbound_pass_bucket_count"],
                    row["time_pass_slice_count"],
                    str(summary_path),
                    notes,
                ]
            )


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return fsum(values) / len(values)


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Layered Gate C",
        "",
        f"- gate_c_id: `{payload['gate_c_id']}`",
        f"- board_id: `{payload['board_id']}`",
        f"- source_triage_id: `{payload['source_triage_id']}`",
        f"- factor_count: `{payload['factor_count']}`",
        f"- cost_bps: `{payload['policy']['cost_bps']}`",
        "",
        "## Decision Counts",
        "",
    ]
    for name, count in payload["decision_counts"].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(
        [
            "",
            "## Gate C Board",
            "",
            "| factor | decision | cost_adj | hit | turnover | stability | primary_pass | southbound_pass | time_pass |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload["factors"]:
        base = row["base_backtest"]
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['factor_name']}`",
                    f"`{row['gate_c_decision']}` / `{row['direction_hint']}`",
                    _fmt(base.get("cost_adjusted_spread_return"), 6),
                    _fmt(base.get("hit_rate")),
                    _fmt(base.get("turnover_proxy")),
                    _fmt(base.get("stability_proxy")),
                    str(row["primary_pass_layer_count"]),
                    str(row["southbound_pass_bucket_count"]),
                    str(row["time_pass_slice_count"]),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Interpretation", ""])
    lines.append("- `advance_gate_d_watch` still means research watchlist, not production approval.")
    lines.append("- Direction is selected by cost-adjusted spread across as-is versus inverse candidates.")
    lines.append("- `hold_cost_capacity` failed the full-sample cost, turnover, hit-rate, or stability stress.")
    lines.append("- `hold_time_instability` failed or lacked enough early/late time-slice evidence.")
    lines.append("- `needs_layer_split` passed the base stress but not enough primary tradability buckets.")
    lines.append("- `needs_southbound_split` means Stock Connect buckets diverged under cost stress.")
    return "\n".join(lines) + "\n"


def build_layered_gate_c_summary(
    *,
    layered_board_path: Path,
    decision_log_path: Path = DEFAULT_DECISION_LOG,
    gate_log_path: Path = DEFAULT_GATE_C_LOG,
    doc_path: Path | None = None,
    run_root: Path = RUN_ROOT,
    triage_id: str = "",
    factors: list[str] | None = None,
    label_column: str = DEFAULT_LABEL_COLUMN,
    top_fraction: float = 0.1,
    cost_bps: float = 15.0,
    allow_inverse: bool = True,
    min_evaluated_dates: int = 3,
    min_cost_adjusted_spread: float = 0.0,
    min_hit_rate: float = 0.52,
    min_stability: float = 0.55,
    max_turnover_proxy: float = 0.9,
    min_primary_pass_layers: int = 2,
    notes: str = "",
) -> tuple[str, dict[str, Any], Path]:
    board = _load_json(layered_board_path)
    decision_rows = _read_tsv(decision_log_path)
    candidates = select_gate_c_candidates(decision_rows, triage_id=triage_id, factors=factors)
    source_triage_id = str(candidates[0]["triage_id"])
    labels_df = _normalize_frame(pl.read_parquet(Path(board["labels_path"])))
    layers_df = _normalize_frame(pl.read_parquet(Path(board["layer_path"])))
    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    gate_c_id = f"layered_gate_c_{stamp}_{board['board_id']}"
    run_dir = run_root / gate_c_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "layered_gate_c_summary.json"
    report_path = run_dir / "layered_gate_c_report.md"
    policy = {
        "label_column": label_column,
        "top_fraction": top_fraction,
        "cost_bps": cost_bps,
        "allow_inverse": allow_inverse,
        "min_evaluated_dates": min_evaluated_dates,
        "min_cost_adjusted_spread": min_cost_adjusted_spread,
        "min_hit_rate": min_hit_rate,
        "min_stability": min_stability,
        "max_turnover_proxy": max_turnover_proxy,
        "min_primary_pass_layers": min_primary_pass_layers,
    }
    rows = [
        evaluate_gate_c_candidate(
            row,
            labels_df=labels_df,
            layers_df=layers_df,
            label_column=label_column,
            top_fraction=top_fraction,
            cost_bps=cost_bps,
            allow_inverse=allow_inverse,
            policy=policy,
        )
        for row in candidates
    ]
    rows.sort(key=lambda row: (DECISION_ORDER.index(row["gate_c_decision"]), row["factor_name"]))
    counts = Counter(row["gate_c_decision"] for row in rows)
    payload = {
        "gate_c_id": gate_c_id,
        "created_at": created_at,
        "board_id": str(board["board_id"]),
        "source_triage_id": source_triage_id,
        "layered_board_path": str(layered_board_path),
        "decision_log_path": str(decision_log_path),
        "labels_path": str(board["labels_path"]),
        "layer_path": str(board["layer_path"]),
        "factor_count": len(rows),
        "decision_counts": {name: counts[name] for name in DECISION_ORDER if counts[name]},
        "policy": policy,
        "mean_base_cost_adjusted_spread": _mean(
            [
                float(row["base_backtest"]["cost_adjusted_spread_return"])
                for row in rows
                if row["base_backtest"].get("cost_adjusted_spread_return") is not None
            ]
        ),
        "factors": rows,
        "notes": notes,
    }
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    report = _render_report(payload)
    report_path.write_text(report, encoding="utf-8")
    if doc_path is not None:
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(report, encoding="utf-8")
    append_gate_c_log(
        gate_c_id=gate_c_id,
        created_at=created_at,
        triage_id=source_triage_id,
        board_id=str(board["board_id"]),
        rows=rows,
        summary_path=summary_path,
        path=gate_log_path,
        notes=notes,
    )
    return gate_c_id, payload, summary_path


def main() -> int:
    args = parse_args()
    gate_c_id, payload, summary_path = build_layered_gate_c_summary(
        layered_board_path=Path(args.layered_board),
        decision_log_path=Path(args.decision_log),
        gate_log_path=Path(args.gate_log),
        doc_path=Path(args.doc_path),
        triage_id=args.triage_id,
        factors=args.factors or None,
        label_column=args.label_column,
        top_fraction=args.top_fraction,
        cost_bps=args.cost_bps,
        allow_inverse=not args.no_inverse,
        min_evaluated_dates=args.min_evaluated_dates,
        min_cost_adjusted_spread=args.min_cost_adjusted_spread,
        min_hit_rate=args.min_hit_rate,
        min_stability=args.min_stability,
        max_turnover_proxy=args.max_turnover_proxy,
        min_primary_pass_layers=args.min_primary_pass_layers,
        notes=args.notes,
    )
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"{gate_c_id} factors={payload['factor_count']} decisions={payload['decision_counts']} summary={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
