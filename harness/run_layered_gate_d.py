"""Run Gate D sample-out tradability checks for layered follow-up candidates."""

from __future__ import annotations

import argparse
from collections import Counter
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

from backtest_engine.minimal_lane import run_minimal_backtest
from harness.run_layered_pre_eval_batch import add_southbound_bucket

RUN_ROOT = ROOT / "runs"
DEFAULT_FOLLOWUP_QUEUE = ROOT / "registry" / "layered_followup_queue.tsv"
DEFAULT_GATE_D_LOG = ROOT / "registry" / "layered_gate_d_log.tsv"
DEFAULT_LABEL_COLUMN = "forward_return_1d_close_like"
PRIMARY_LAYER_COLUMN = "primary_tradability_layer"
SOUTHBOUND_LAYER_COLUMN = "southbound_bucket"

GATE_D_LOG_HEADER = [
    "gate_d_id",
    "created_at",
    "followup_batch_id",
    "gate_c_id",
    "factor_name",
    "followup_lane",
    "gate_d_decision",
    "direction_hint",
    "target_primary_layers_json",
    "target_southbound_buckets_json",
    "sample_out_cost_adjusted_spread_return",
    "sample_out_hit_rate",
    "sample_out_turnover_proxy",
    "sample_out_stability_proxy",
    "sample_out_evaluated_dates",
    "full_cost_adjusted_spread_return",
    "full_turnover_proxy",
    "summary_path",
    "notes",
]

DECISION_ORDER = [
    "advance_paper_trade_watch",
    "research_only_source_gap",
    "research_only_capacity_risk",
    "reject_gate_d",
    "needs_more_sample",
]


def parse_args() -> argparse.Namespace:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    parser = argparse.ArgumentParser(description="Run Gate D sample-out checks for layered follow-ups.")
    parser.add_argument("--gate-c-summary", required=True, help="Path to layered_gate_c_summary.json.")
    parser.add_argument("--followup-queue", default=str(DEFAULT_FOLLOWUP_QUEUE), help="Layered follow-up TSV.")
    parser.add_argument("--gate-d-log", default=str(DEFAULT_GATE_D_LOG), help="Append-only Gate D TSV.")
    parser.add_argument(
        "--doc-path",
        default=str(ROOT / "docs" / f"layered_gate_d_summary_{month}.md"),
        help="Tracked Gate D summary markdown path.",
    )
    parser.add_argument("--followup-batch-id", default="", help="Optional follow-up batch filter. Defaults latest.")
    parser.add_argument("--label-column", default=DEFAULT_LABEL_COLUMN)
    parser.add_argument("--top-fraction", type=float, default=0.1)
    parser.add_argument("--cost-bps", type=float, default=25.0)
    parser.add_argument("--sample-out-fraction", type=float, default=0.33)
    parser.add_argument("--min-sample-out-dates", type=int, default=8)
    parser.add_argument("--min-cost-adjusted-spread", type=float, default=0.0)
    parser.add_argument("--min-hit-rate", type=float, default=0.52)
    parser.add_argument("--min-stability", type=float, default=0.55)
    parser.add_argument("--max-turnover-proxy", type=float, default=0.85)
    parser.add_argument("--notes", default="", help="Short Gate D note.")
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


def _parse_json_list(value: str) -> list[str]:
    if not value:
        return []
    payload = json.loads(value)
    if not isinstance(payload, list):
        raise ValueError(f"Expected JSON list, got {value!r}")
    return [str(item) for item in payload]


def _normalize_frame(frame: pl.DataFrame) -> pl.DataFrame:
    if "date" in frame.columns:
        frame = frame.with_columns(pl.col("date").cast(pl.Utf8))
    if "instrument_key" in frame.columns:
        frame = frame.with_columns(pl.col("instrument_key").cast(pl.Utf8))
    return frame


def _latest_followup_batch(rows: list[dict[str, str]]) -> str:
    if not rows:
        raise ValueError("Follow-up queue has no rows.")
    return max(rows, key=lambda row: row.get("created_at", "")).get("followup_batch_id", "")


def select_followup_rows(
    rows: list[dict[str, str]],
    *,
    gate_c_id: str,
    followup_batch_id: str = "",
) -> list[dict[str, Any]]:
    resolved_batch_id = followup_batch_id or _latest_followup_batch(rows)
    selected = [
        row
        for row in rows
        if row.get("followup_batch_id") == resolved_batch_id and row.get("gate_c_id") == gate_c_id
    ]
    if not selected:
        raise ValueError(f"No follow-up rows for batch `{resolved_batch_id}` and Gate C `{gate_c_id}`.")
    result: list[dict[str, Any]] = []
    for row in selected:
        result.append(
            {
                **row,
                "target_primary_layers": _parse_json_list(row.get("target_primary_layers_json", "")),
                "target_southbound_buckets": _parse_json_list(row.get("target_southbound_buckets_json", "")),
            }
        )
    return sorted(result, key=lambda row: str(row["factor_name"]))


def _split_dates(frame: pl.DataFrame, sample_out_fraction: float) -> tuple[list[str], list[str]]:
    dates = sorted(str(value) for value in frame["date"].unique().to_list()) if "date" in frame.columns else []
    if not dates:
        return [], []
    sample_count = max(1, int(len(dates) * sample_out_fraction))
    sample_count = min(sample_count, len(dates))
    return dates[:-sample_count], dates[-sample_count:]


def _score_frame(frame: pl.DataFrame, *, score_column: str, direction_hint: str) -> tuple[pl.DataFrame, str]:
    if direction_hint == "inverse_candidate":
        score = "__gate_d_score"
        return frame.with_columns((pl.col(score_column) * -1.0).alias(score)), score
    return frame, score_column


def _target_frame(
    factor_df: pl.DataFrame,
    layers_df: pl.DataFrame,
    *,
    target_primary_layers: list[str],
    target_southbound_buckets: list[str],
) -> pl.DataFrame:
    layer_cols = ["instrument_key", PRIMARY_LAYER_COLUMN, SOUTHBOUND_LAYER_COLUMN]
    layer_keys = add_southbound_bucket(layers_df).select(layer_cols).unique(subset=["instrument_key"])
    frame = factor_df.join(layer_keys, on="instrument_key", how="inner")
    if target_primary_layers:
        frame = frame.filter(pl.col(PRIMARY_LAYER_COLUMN).is_in(target_primary_layers))
    if target_southbound_buckets:
        frame = frame.filter(pl.col(SOUTHBOUND_LAYER_COLUMN).is_in(target_southbound_buckets))
    return frame


def _compact_result(result: Any) -> dict[str, Any]:
    payload = result.as_dict()
    payload.pop("per_date", None)
    return payload


def _run_target_backtest(
    frame: pl.DataFrame,
    labels_df: pl.DataFrame,
    *,
    factor_name: str,
    score_column: str,
    label_column: str,
    top_fraction: float,
    cost_bps: float,
) -> dict[str, Any]:
    result = run_minimal_backtest(
        frame,
        labels_df,
        factor_name=factor_name,
        score_column=score_column,
        label_column=label_column,
        top_fraction=top_fraction,
        cost_bps=cost_bps,
    )
    return _compact_result(result)


def _passes(result: dict[str, Any], policy: dict[str, Any]) -> bool:
    if int(result.get("evaluated_dates") or 0) < int(policy["min_sample_out_dates"]):
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


def _gate_d_decision(
    *,
    followup: dict[str, Any],
    sample_out_result: dict[str, Any],
    sample_out_passed: bool,
    policy: dict[str, Any],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if int(sample_out_result.get("evaluated_dates") or 0) < int(policy["min_sample_out_dates"]):
        reasons.append("sample-out evidence has too few evaluated dates")
        return "needs_more_sample", reasons
    if not sample_out_passed:
        reasons.append("sample-out cost, hit-rate, turnover, or stability stress failed")
        return "reject_gate_d", reasons
    primary_layers = set(followup["target_primary_layers"])
    southbound_buckets = set(followup["target_southbound_buckets"])
    if followup["followup_lane"] == "southbound_split_retest" and not southbound_buckets:
        reasons.append("no Southbound bucket survived the prior split gate")
        return "reject_gate_d", reasons
    if southbound_buckets == {"southbound_unknown"}:
        reasons.append("sample-out passed only in fail-closed Southbound unknown flow")
        if "small_illiquid_special" in primary_layers:
            reasons.append("target also includes small-illiquid capacity risk")
        return "research_only_source_gap", reasons
    if "small_illiquid_special" in primary_layers:
        reasons.append("sample-out passed only inside small-illiquid or mixed small-illiquid target")
        return "research_only_capacity_risk", reasons
    reasons.append("sample-out cost, turnover, hit-rate, and stability checks passed")
    return "advance_paper_trade_watch", reasons


def evaluate_gate_d_candidate(
    followup: dict[str, Any],
    gate_c_factor: dict[str, Any],
    *,
    labels_df: pl.DataFrame,
    layers_df: pl.DataFrame,
    policy: dict[str, Any],
) -> dict[str, Any]:
    factor_name = str(followup["factor_name"])
    factor_df = _normalize_frame(pl.read_parquet(Path(gate_c_factor["source_run_dir"]) / "factor_output.parquet"))
    frame, score_column = _score_frame(
        factor_df,
        score_column=str(gate_c_factor["score_column"]),
        direction_hint=str(followup["direction_hint"]),
    )
    target = _target_frame(
        frame,
        layers_df,
        target_primary_layers=followup["target_primary_layers"],
        target_southbound_buckets=followup["target_southbound_buckets"],
    )
    train_dates, sample_out_dates = _split_dates(target, float(policy["sample_out_fraction"]))
    train_frame = target.filter(pl.col("date").is_in(train_dates)) if train_dates else target.head(0)
    sample_out_frame = target.filter(pl.col("date").is_in(sample_out_dates)) if sample_out_dates else target.head(0)

    full_result = _run_target_backtest(
        target,
        labels_df,
        factor_name=factor_name,
        score_column=score_column,
        label_column=str(policy["label_column"]),
        top_fraction=float(policy["top_fraction"]),
        cost_bps=float(policy["cost_bps"]),
    )
    train_result = _run_target_backtest(
        train_frame,
        labels_df,
        factor_name=factor_name,
        score_column=score_column,
        label_column=str(policy["label_column"]),
        top_fraction=float(policy["top_fraction"]),
        cost_bps=float(policy["cost_bps"]),
    )
    sample_out_result = _run_target_backtest(
        sample_out_frame,
        labels_df,
        factor_name=factor_name,
        score_column=score_column,
        label_column=str(policy["label_column"]),
        top_fraction=float(policy["top_fraction"]),
        cost_bps=float(policy["cost_bps"]),
    )
    sample_out_passed = _passes(sample_out_result, policy)
    decision, reasons = _gate_d_decision(
        followup=followup,
        sample_out_result=sample_out_result,
        sample_out_passed=sample_out_passed,
        policy=policy,
    )
    return {
        "followup_id": str(followup["followup_id"]),
        "factor_name": factor_name,
        "followup_lane": str(followup["followup_lane"]),
        "gate_c_decision": str(followup["gate_c_decision"]),
        "direction_hint": str(followup["direction_hint"]),
        "target_primary_layers": followup["target_primary_layers"],
        "target_southbound_buckets": followup["target_southbound_buckets"],
        "target_rows": target.height,
        "target_date_count": len(train_dates) + len(sample_out_dates),
        "train_dates": train_dates,
        "sample_out_dates": sample_out_dates,
        "sample_out_passed": sample_out_passed,
        "gate_d_decision": decision,
        "gate_d_reasons": reasons,
        "full_backtest": full_result,
        "train_backtest": train_result,
        "sample_out_backtest": sample_out_result,
    }


def _ensure_tsv(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\t".join(GATE_D_LOG_HEADER) + "\n", encoding="utf-8")


def append_gate_d_log(
    *,
    gate_d_id: str,
    created_at: str,
    followup_batch_id: str,
    gate_c_id: str,
    rows: list[dict[str, Any]],
    summary_path: Path,
    path: Path = DEFAULT_GATE_D_LOG,
    notes: str = "",
) -> None:
    _ensure_tsv(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        for row in rows:
            sample_out = row["sample_out_backtest"]
            full = row["full_backtest"]
            writer.writerow(
                [
                    gate_d_id,
                    created_at,
                    followup_batch_id,
                    gate_c_id,
                    row["factor_name"],
                    row["followup_lane"],
                    row["gate_d_decision"],
                    row["direction_hint"],
                    json.dumps(row["target_primary_layers"], ensure_ascii=False),
                    json.dumps(row["target_southbound_buckets"], ensure_ascii=False),
                    sample_out.get("cost_adjusted_spread_return"),
                    sample_out.get("hit_rate"),
                    sample_out.get("turnover_proxy"),
                    sample_out.get("stability_proxy"),
                    sample_out.get("evaluated_dates"),
                    full.get("cost_adjusted_spread_return"),
                    full.get("turnover_proxy"),
                    str(summary_path),
                    notes,
                ]
            )


def _fmt(value: Any, digits: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _decision_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row["gate_d_decision"] for row in rows)
    return {name: counts[name] for name in DECISION_ORDER if counts[name]}


def render_gate_d_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Layered Gate D",
        "",
        "Gate D is a research tradability screen. It is not a production approval.",
        "",
        "## Source",
        "",
        f"- gate_d_id: `{payload['gate_d_id']}`",
        f"- gate_c_id: `{payload['gate_c_id']}`",
        f"- followup_batch_id: `{payload['followup_batch_id']}`",
        f"- factor_count: `{payload['factor_count']}`",
        f"- cost_bps: `{payload['policy']['cost_bps']}`",
        f"- sample_out_fraction: `{payload['policy']['sample_out_fraction']}`",
        f"- min_sample_out_dates: `{payload['policy']['min_sample_out_dates']}`",
        "",
        "## Decision Counts",
        "",
    ]
    for name, count in payload["decision_counts"].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(
        [
            "",
            "## Gate D Board",
            "",
            "| factor | decision | lane | target | sample-out cost-adj | hit | turnover | stability | dates |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload["factors"]:
        sample = row["sample_out_backtest"]
        layers = ",".join(row["target_primary_layers"]) or "*"
        buckets = ",".join(row["target_southbound_buckets"]) or "*"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['factor_name']}`",
                    f"`{row['gate_d_decision']}`",
                    f"`{row['followup_lane']}`",
                    f"`{layers}` / `{buckets}`",
                    _fmt(sample.get("cost_adjusted_spread_return")),
                    _fmt(sample.get("hit_rate")),
                    _fmt(sample.get("turnover_proxy")),
                    _fmt(sample.get("stability_proxy")),
                    str(sample.get("evaluated_dates")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Interpretation", ""])
    lines.append("- `advance_paper_trade_watch` requires sample-out cost, hit-rate, turnover, and stability to pass.")
    lines.append("- `research_only_capacity_risk` passed sample-out but is small-illiquid constrained.")
    lines.append("- `research_only_source_gap` passed only in fail-closed Southbound unknown flow.")
    lines.append("- `reject_gate_d` means do not spend new factor-mining budget on that route now.")
    return "\n".join(lines) + "\n"


def build_layered_gate_d_summary(
    *,
    gate_c_summary_path: Path,
    followup_queue_path: Path = DEFAULT_FOLLOWUP_QUEUE,
    gate_d_log_path: Path = DEFAULT_GATE_D_LOG,
    doc_path: Path | None = None,
    run_root: Path = RUN_ROOT,
    followup_batch_id: str = "",
    label_column: str = DEFAULT_LABEL_COLUMN,
    top_fraction: float = 0.1,
    cost_bps: float = 25.0,
    sample_out_fraction: float = 0.33,
    min_sample_out_dates: int = 8,
    min_cost_adjusted_spread: float = 0.0,
    min_hit_rate: float = 0.52,
    min_stability: float = 0.55,
    max_turnover_proxy: float = 0.85,
    notes: str = "",
) -> tuple[str, dict[str, Any], Path]:
    gate_c = _load_json(gate_c_summary_path)
    queue_rows = _read_tsv(followup_queue_path)
    followups = select_followup_rows(
        queue_rows,
        gate_c_id=str(gate_c["gate_c_id"]),
        followup_batch_id=followup_batch_id,
    )
    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    gate_d_id = f"layered_gate_d_{stamp}_{gate_c['gate_c_id']}"
    run_dir = run_root / gate_d_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "layered_gate_d_summary.json"
    report_path = run_dir / "layered_gate_d_report.md"
    policy = {
        "label_column": label_column,
        "top_fraction": top_fraction,
        "cost_bps": cost_bps,
        "sample_out_fraction": sample_out_fraction,
        "min_sample_out_dates": min_sample_out_dates,
        "min_cost_adjusted_spread": min_cost_adjusted_spread,
        "min_hit_rate": min_hit_rate,
        "min_stability": min_stability,
        "max_turnover_proxy": max_turnover_proxy,
    }
    labels_df = _normalize_frame(pl.read_parquet(Path(gate_c["labels_path"])))
    layers_df = _normalize_frame(pl.read_parquet(Path(gate_c["layer_path"])))
    factor_by_name = {str(row["factor_name"]): row for row in gate_c.get("factors", [])}
    rows = [
        evaluate_gate_d_candidate(
            row,
            factor_by_name[str(row["factor_name"])],
            labels_df=labels_df,
            layers_df=layers_df,
            policy=policy,
        )
        for row in followups
    ]
    rows.sort(key=lambda row: (DECISION_ORDER.index(row["gate_d_decision"]), row["factor_name"]))
    payload = {
        "gate_d_id": gate_d_id,
        "created_at": created_at,
        "gate_c_id": str(gate_c["gate_c_id"]),
        "followup_batch_id": str(followups[0]["followup_batch_id"]),
        "gate_c_summary_path": str(gate_c_summary_path),
        "followup_queue_path": str(followup_queue_path),
        "factor_count": len(rows),
        "decision_counts": _decision_counts(rows),
        "policy": policy,
        "factors": rows,
        "notes": notes,
    }
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    report = render_gate_d_report(payload)
    report_path.write_text(report, encoding="utf-8")
    if doc_path is not None:
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(report, encoding="utf-8")
    append_gate_d_log(
        gate_d_id=gate_d_id,
        created_at=created_at,
        followup_batch_id=str(followups[0]["followup_batch_id"]),
        gate_c_id=str(gate_c["gate_c_id"]),
        rows=rows,
        summary_path=summary_path,
        path=gate_d_log_path,
        notes=notes,
    )
    return gate_d_id, payload, summary_path


def main() -> int:
    args = parse_args()
    gate_d_id, payload, summary_path = build_layered_gate_d_summary(
        gate_c_summary_path=Path(args.gate_c_summary),
        followup_queue_path=Path(args.followup_queue),
        gate_d_log_path=Path(args.gate_d_log),
        doc_path=Path(args.doc_path),
        followup_batch_id=args.followup_batch_id,
        label_column=args.label_column,
        top_fraction=args.top_fraction,
        cost_bps=args.cost_bps,
        sample_out_fraction=args.sample_out_fraction,
        min_sample_out_dates=args.min_sample_out_dates,
        min_cost_adjusted_spread=args.min_cost_adjusted_spread,
        min_hit_rate=args.min_hit_rate,
        min_stability=args.min_stability,
        max_turnover_proxy=args.max_turnover_proxy,
        notes=args.notes,
    )
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"{gate_d_id} factors={payload['factor_count']} decisions={payload['decision_counts']} summary={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
