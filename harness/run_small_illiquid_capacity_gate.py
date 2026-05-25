"""Run Gate E capacity and slippage checks for small-illiquid candidates."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
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

from harness.daily_agg import load_daily_agg_lazy, missing_daily_agg_dates
from harness.run_layered_gate_d import (
    _load_json,
    _normalize_frame,
    _score_frame,
    _target_frame,
)

RUN_ROOT = ROOT / "runs"
DEFAULT_CAPACITY_LOG = ROOT / "registry" / "small_illiquid_capacity_gate_log.tsv"
DEFAULT_LABEL_COLUMN = "forward_return_1d_close_like"

CAPACITY_LOG_HEADER = [
    "capacity_gate_id",
    "created_at",
    "gate_d_id",
    "factor_name",
    "capacity_decision",
    "direction_hint",
    "target_primary_layers_json",
    "target_southbound_buckets_json",
    "sample_out_cost_adjusted_50bps",
    "sample_out_cost_adjusted_100bps",
    "capacity_p25_hkd_at_1pct",
    "capacity_median_hkd_at_1pct",
    "top_abs_contribution_share",
    "selected_turnover_median_hkd",
    "missing_turnover_ratio",
    "summary_path",
    "notes",
]

DECISION_ORDER = [
    "paper_trade_micro_watch",
    "research_only_micro_capacity",
    "reject_concentration",
    "reject_capacity",
    "needs_liquidity_data",
]


def parse_args() -> argparse.Namespace:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    parser = argparse.ArgumentParser(description="Run Gate E capacity/slippage checks.")
    parser.add_argument("--gate-d-summary", required=True, help="Path to layered_gate_d_summary.json.")
    parser.add_argument("--capacity-log", default=str(DEFAULT_CAPACITY_LOG), help="Append-only capacity TSV.")
    parser.add_argument(
        "--doc-path",
        default=str(ROOT / "docs" / f"small_illiquid_capacity_gate_{month}.md"),
        help="Tracked capacity gate markdown path.",
    )
    parser.add_argument("--factors", nargs="*", default=[], help="Optional factor subset.")
    parser.add_argument("--label-column", default=DEFAULT_LABEL_COLUMN)
    parser.add_argument("--top-fraction", type=float, default=0.1)
    parser.add_argument("--stress-bps", nargs="*", type=float, default=[25.0, 50.0, 100.0])
    parser.add_argument("--participation-rates", nargs="*", type=float, default=[0.01, 0.03, 0.05])
    parser.add_argument("--pass-stress-bps", type=float, default=50.0)
    parser.add_argument("--pass-participation-rate", type=float, default=0.01)
    parser.add_argument("--min-gross-capacity-hkd", type=float, default=5_000_000.0)
    parser.add_argument("--max-concentration-share", type=float, default=0.35)
    parser.add_argument("--max-missing-turnover-ratio", type=float, default=0.05)
    parser.add_argument("--notes", default="", help="Short capacity gate note.")
    parser.add_argument("--json", action="store_true", help="Emit JSON payload.")
    return parser.parse_args()


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return fsum(values) / len(values)


def _quantile(values: list[float], q: float) -> float | None:
    clean = sorted(value for value in values if value is not None)
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    position = (len(clean) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(clean) - 1)
    weight = position - lower
    return clean[lower] * (1.0 - weight) + clean[upper] * weight


def _json_key(value: float) -> str:
    return f"{value:g}"


def _select_capacity_candidates(gate_d: dict[str, Any], factors: list[str] | None = None) -> list[dict[str, Any]]:
    selected = set(factors or [])
    rows = [
        row
        for row in gate_d.get("factors", [])
        if row.get("gate_d_decision") == "research_only_capacity_risk"
        and (not selected or row.get("factor_name") in selected)
    ]
    missing = selected - {str(row.get("factor_name")) for row in rows}
    if missing:
        raise ValueError(f"No Gate D capacity-risk rows for factors: {', '.join(sorted(missing))}")
    if not rows:
        raise ValueError("No research_only_capacity_risk rows available for Gate E.")
    return sorted(rows, key=lambda row: str(row["factor_name"]))


def _load_liquidity(dates: list[str]) -> pl.DataFrame:
    missing = missing_daily_agg_dates("verified_trades_daily", dates)
    if missing:
        raise FileNotFoundError(f"Missing verified_trades_daily partitions: {', '.join(missing)}")
    return _normalize_frame(
        load_daily_agg_lazy(
            "verified_trades_daily",
            dates,
            ["date", "instrument_key", "turnover"],
        ).collect()
    )


def _selected_daily_rows(
    frame: pl.DataFrame,
    labels_df: pl.DataFrame,
    liquidity_df: pl.DataFrame,
    *,
    score_column: str,
    label_column: str,
    top_fraction: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    joined = (
        frame.select(["date", "instrument_key", score_column])
        .join(labels_df.select(["date", "instrument_key", label_column]), on=["date", "instrument_key"], how="inner")
        .join(liquidity_df.select(["date", "instrument_key", "turnover"]), on=["date", "instrument_key"], how="left")
        .drop_nulls([score_column, label_column])
        .sort(["date", score_column], descending=[False, True])
    )
    per_date: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    prev_selected: set[str] | None = None
    for date_key, date_frame in joined.group_by("date", maintain_order=True):
        date_value = str(date_key[0] if isinstance(date_key, tuple) else date_key)
        ordered = date_frame.sort(score_column, descending=True)
        row_count = ordered.height
        bucket_size = max(1, int(row_count * top_fraction))
        long_bucket = ordered.head(bucket_size)
        short_bucket = ordered.tail(bucket_size).sort(score_column)
        long_return = _mean([float(value) for value in long_bucket[label_column].to_list()])
        short_return = _mean([float(value) for value in short_bucket[label_column].to_list()])
        spread = None if long_return is None or short_return is None else long_return - short_return
        long_keys = set(long_bucket["instrument_key"].to_list())
        short_keys = set(short_bucket["instrument_key"].to_list())
        selected_keys = long_keys | short_keys
        if prev_selected is None:
            turnover_proxy = 0.0
        else:
            union = selected_keys | prev_selected
            turnover_proxy = 0.0 if not union else 1.0 - (len(selected_keys & prev_selected) / len(union))
        prev_selected = selected_keys

        selected_count = len(long_keys) + len(short_keys)
        missing_turnover = 0
        valid_turnovers: list[float] = []
        for side, bucket, sign in [("long", long_bucket, 1.0), ("short", short_bucket, -1.0)]:
            for item in bucket.to_dicts():
                turnover = item.get("turnover")
                turnover_value = None if turnover is None else float(turnover)
                if turnover_value is None or turnover_value <= 0.0:
                    missing_turnover += 1
                else:
                    valid_turnovers.append(turnover_value)
                selected_rows.append(
                    {
                        "date": date_value,
                        "instrument_key": str(item["instrument_key"]),
                        "side": side,
                        "side_return": float(item[label_column]) * sign,
                        "turnover_hkd": turnover_value,
                        "bucket_size": bucket_size,
                    }
                )
        per_date.append(
            {
                "date": date_value,
                "row_count": row_count,
                "bucket_size": bucket_size,
                "selected_count": selected_count,
                "spread_return": spread,
                "turnover_proxy": turnover_proxy,
                "missing_turnover_count": missing_turnover,
                "missing_turnover_ratio": 0.0 if selected_count == 0 else missing_turnover / selected_count,
                "min_selected_turnover_hkd": min(valid_turnovers) if valid_turnovers else None,
                "median_selected_turnover_hkd": _quantile(valid_turnovers, 0.5),
            }
        )
    return per_date, selected_rows


def _capacity_by_participation(
    per_date: list[dict[str, Any]],
    participation_rates: list[float],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for rate in participation_rates:
        values = [
            2.0 * float(row["bucket_size"]) * float(row["min_selected_turnover_hkd"]) * rate
            for row in per_date
            if row.get("min_selected_turnover_hkd") is not None
        ]
        result[_json_key(rate)] = {
            "min_gross_capacity_hkd": _quantile(values, 0.0),
            "p25_gross_capacity_hkd": _quantile(values, 0.25),
            "median_gross_capacity_hkd": _quantile(values, 0.5),
            "mean_gross_capacity_hkd": _mean(values),
        }
    return result


def _stress_returns(per_date: list[dict[str, Any]], stress_bps: list[float]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for bps in stress_bps:
        adjusted = [
            float(row["spread_return"]) - ((bps / 10_000.0) * float(row["turnover_proxy"]))
            for row in per_date
            if row.get("spread_return") is not None and row.get("turnover_proxy") is not None
        ]
        result[_json_key(bps)] = {
            "cost_adjusted_spread_return": _mean(adjusted),
            "hit_rate": None if not adjusted else sum(1 for value in adjusted if value > 0.0) / len(adjusted),
        }
    return result


def _concentration(selected_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_instrument: dict[str, float] = defaultdict(float)
    for row in selected_rows:
        contribution = float(row["side_return"]) / float(row["bucket_size"])
        by_instrument[str(row["instrument_key"])] += abs(contribution)
    total = fsum(by_instrument.values())
    if total <= 0.0 or not by_instrument:
        return {"top_instrument_key": "", "top_abs_contribution_share": None}
    top_key, top_value = max(by_instrument.items(), key=lambda item: item[1])
    return {"top_instrument_key": top_key, "top_abs_contribution_share": top_value / total}


def _selected_turnover_summary(selected_rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["turnover_hkd"]) for row in selected_rows if row.get("turnover_hkd") is not None]
    return {
        "selected_turnover_p10_hkd": _quantile(values, 0.10),
        "selected_turnover_median_hkd": _quantile(values, 0.50),
        "selected_turnover_p90_hkd": _quantile(values, 0.90),
    }


def _capacity_decision(metrics: dict[str, Any], policy: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    missing_ratio = metrics["missing_turnover_ratio"]
    if missing_ratio > float(policy["max_missing_turnover_ratio"]):
        reasons.append("selected liquidity coverage is insufficient")
        return "needs_liquidity_data", reasons
    pass_bps_key = _json_key(float(policy["pass_stress_bps"]))
    pass_rate_key = _json_key(float(policy["pass_participation_rate"]))
    stressed = metrics["stress_results"][pass_bps_key]["cost_adjusted_spread_return"]
    if stressed is None or float(stressed) <= 0.0:
        reasons.append(f"{pass_bps_key}bps stressed spread is not positive")
        return "reject_capacity", reasons
    concentration = metrics["concentration"]["top_abs_contribution_share"]
    if concentration is not None and concentration > float(policy["max_concentration_share"]):
        reasons.append("return contribution is too concentrated")
        return "reject_concentration", reasons
    capacity = metrics["capacity_by_participation"][pass_rate_key]["p25_gross_capacity_hkd"]
    if capacity is not None and capacity >= float(policy["min_gross_capacity_hkd"]):
        reasons.append("capacity, slippage, and concentration checks passed for micro watch")
        return "paper_trade_micro_watch", reasons
    reasons.append("stressed spread is positive, but robust capacity is below the micro threshold")
    return "research_only_micro_capacity", reasons


def evaluate_capacity_candidate(
    gate_d_row: dict[str, Any],
    gate_c_factor: dict[str, Any],
    *,
    labels_df: pl.DataFrame,
    layers_df: pl.DataFrame,
    liquidity_df: pl.DataFrame,
    policy: dict[str, Any],
) -> dict[str, Any]:
    factor_name = str(gate_d_row["factor_name"])
    factor_df = _normalize_frame(pl.read_parquet(Path(gate_c_factor["source_run_dir"]) / "factor_output.parquet"))
    frame, score_column = _score_frame(
        factor_df,
        score_column=str(gate_c_factor["score_column"]),
        direction_hint=str(gate_d_row["direction_hint"]),
    )
    target = _target_frame(
        frame,
        layers_df,
        target_primary_layers=list(gate_d_row["target_primary_layers"]),
        target_southbound_buckets=list(gate_d_row["target_southbound_buckets"]),
    )
    sample_dates = [str(date) for date in gate_d_row.get("sample_out_dates", [])]
    sample_frame = target.filter(pl.col("date").is_in(sample_dates)) if sample_dates else target.head(0)
    per_date, selected_rows = _selected_daily_rows(
        sample_frame,
        labels_df,
        liquidity_df,
        score_column=score_column,
        label_column=str(policy["label_column"]),
        top_fraction=float(policy["top_fraction"]),
    )
    spread_values = [float(row["spread_return"]) for row in per_date if row.get("spread_return") is not None]
    turnover_values = [float(row["turnover_proxy"]) for row in per_date if row.get("turnover_proxy") is not None]
    selected_counts = [float(row["selected_count"]) for row in per_date]
    missing_ratios = [float(row["missing_turnover_ratio"]) for row in per_date]
    metrics = {
        "sample_out_dates": sample_dates,
        "evaluated_dates": len(per_date),
        "mean_spread_return": _mean(spread_values),
        "turnover_proxy": _mean(turnover_values),
        "median_selected_count": _quantile(selected_counts, 0.5),
        "median_bucket_size": _quantile([float(row["bucket_size"]) for row in per_date], 0.5),
        "missing_turnover_ratio": _mean(missing_ratios) or 0.0,
        "max_missing_turnover_ratio": max(missing_ratios) if missing_ratios else 0.0,
        "stress_results": _stress_returns(per_date, list(policy["stress_bps"])),
        "capacity_by_participation": _capacity_by_participation(per_date, list(policy["participation_rates"])),
        "concentration": _concentration(selected_rows),
        "turnover_distribution": _selected_turnover_summary(selected_rows),
    }
    decision, reasons = _capacity_decision(metrics, policy)
    return {
        "factor_name": factor_name,
        "followup_id": str(gate_d_row["followup_id"]),
        "direction_hint": str(gate_d_row["direction_hint"]),
        "target_primary_layers": list(gate_d_row["target_primary_layers"]),
        "target_southbound_buckets": list(gate_d_row["target_southbound_buckets"]),
        "gate_d_decision": str(gate_d_row["gate_d_decision"]),
        "capacity_decision": decision,
        "capacity_reasons": reasons,
        "metrics": metrics,
    }


def _ensure_tsv(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\t".join(CAPACITY_LOG_HEADER) + "\n", encoding="utf-8")


def append_capacity_log(
    *,
    capacity_gate_id: str,
    created_at: str,
    gate_d_id: str,
    rows: list[dict[str, Any]],
    summary_path: Path,
    path: Path = DEFAULT_CAPACITY_LOG,
    notes: str = "",
) -> None:
    _ensure_tsv(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        for row in rows:
            metrics = row["metrics"]
            capacity = metrics["capacity_by_participation"].get("0.01", {})
            stress = metrics["stress_results"]
            writer.writerow(
                [
                    capacity_gate_id,
                    created_at,
                    gate_d_id,
                    row["factor_name"],
                    row["capacity_decision"],
                    row["direction_hint"],
                    json.dumps(row["target_primary_layers"], ensure_ascii=False),
                    json.dumps(row["target_southbound_buckets"], ensure_ascii=False),
                    stress.get("50", {}).get("cost_adjusted_spread_return"),
                    stress.get("100", {}).get("cost_adjusted_spread_return"),
                    capacity.get("p25_gross_capacity_hkd"),
                    capacity.get("median_gross_capacity_hkd"),
                    metrics["concentration"].get("top_abs_contribution_share"),
                    metrics["turnover_distribution"].get("selected_turnover_median_hkd"),
                    metrics["missing_turnover_ratio"],
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


def _money(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):,.0f}"


def _decision_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row["capacity_decision"] for row in rows)
    return {name: counts[name] for name in DECISION_ORDER if counts[name]}


def render_capacity_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Small Illiquid Capacity Gate",
        "",
        "Gate E tests whether Gate D research-only small/liquidity traces survive explicit capacity and slippage stress.",
        "",
        "## Source",
        "",
        f"- capacity_gate_id: `{payload['capacity_gate_id']}`",
        f"- gate_d_id: `{payload['gate_d_id']}`",
        f"- factor_count: `{payload['factor_count']}`",
        f"- pass_stress_bps: `{payload['policy']['pass_stress_bps']}`",
        f"- pass_participation_rate: `{payload['policy']['pass_participation_rate']}`",
        f"- min_gross_capacity_hkd: `{payload['policy']['min_gross_capacity_hkd']}`",
        "",
        "## Decision Counts",
        "",
    ]
    for decision, count in payload["decision_counts"].items():
        lines.append(f"- `{decision}`: {count}")
    lines.extend(
        [
            "",
            "## Capacity Board",
            "",
            "| factor | decision | 50bps adj | 100bps adj | p25 cap @1% | median cap @1% | top contrib | selected turnover med |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload["factors"]:
        metrics = row["metrics"]
        cap = metrics["capacity_by_participation"]["0.01"]
        stress = metrics["stress_results"]
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['factor_name']}`",
                    f"`{row['capacity_decision']}`",
                    _fmt(stress.get("50", {}).get("cost_adjusted_spread_return")),
                    _fmt(stress.get("100", {}).get("cost_adjusted_spread_return")),
                    _money(cap.get("p25_gross_capacity_hkd")),
                    _money(cap.get("median_gross_capacity_hkd")),
                    _fmt(metrics["concentration"].get("top_abs_contribution_share")),
                    _money(metrics["turnover_distribution"].get("selected_turnover_median_hkd")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Interpretation", ""])
    lines.append("- `paper_trade_micro_watch` requires positive 50bps stress, acceptable concentration, and p25 gross capacity above the micro threshold at 1% participation.")
    lines.append("- `research_only_micro_capacity` means the signal remains positive under stress but cannot support the configured micro capital threshold robustly.")
    lines.append("- `reject_capacity` or `reject_concentration` should not move to paper trading.")
    return "\n".join(lines) + "\n"


def build_capacity_gate_summary(
    *,
    gate_d_summary_path: Path,
    capacity_log_path: Path = DEFAULT_CAPACITY_LOG,
    doc_path: Path | None = None,
    run_root: Path = RUN_ROOT,
    factors: list[str] | None = None,
    label_column: str = DEFAULT_LABEL_COLUMN,
    top_fraction: float = 0.1,
    stress_bps: list[float] | None = None,
    participation_rates: list[float] | None = None,
    pass_stress_bps: float = 50.0,
    pass_participation_rate: float = 0.01,
    min_gross_capacity_hkd: float = 5_000_000.0,
    max_concentration_share: float = 0.35,
    max_missing_turnover_ratio: float = 0.05,
    notes: str = "",
    liquidity_df: pl.DataFrame | None = None,
) -> tuple[str, dict[str, Any], Path]:
    gate_d = _load_json(gate_d_summary_path)
    gate_c = _load_json(Path(gate_d["gate_c_summary_path"]))
    rows = _select_capacity_candidates(gate_d, factors=factors)
    sample_dates = sorted({str(date) for row in rows for date in row.get("sample_out_dates", [])})
    liquidity = liquidity_df if liquidity_df is not None else _load_liquidity(sample_dates)
    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    capacity_gate_id = f"small_illiquid_capacity_{stamp}_{gate_d['gate_d_id']}"
    run_dir = run_root / capacity_gate_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "small_illiquid_capacity_summary.json"
    report_path = run_dir / "small_illiquid_capacity_report.md"
    policy = {
        "label_column": label_column,
        "top_fraction": top_fraction,
        "stress_bps": list(stress_bps or [25.0, 50.0, 100.0]),
        "participation_rates": list(participation_rates or [0.01, 0.03, 0.05]),
        "pass_stress_bps": pass_stress_bps,
        "pass_participation_rate": pass_participation_rate,
        "min_gross_capacity_hkd": min_gross_capacity_hkd,
        "max_concentration_share": max_concentration_share,
        "max_missing_turnover_ratio": max_missing_turnover_ratio,
    }
    labels_df = _normalize_frame(pl.read_parquet(Path(gate_c["labels_path"])))
    layers_df = _normalize_frame(pl.read_parquet(Path(gate_c["layer_path"])))
    factor_by_name = {str(row["factor_name"]): row for row in gate_c.get("factors", [])}
    evaluated = [
        evaluate_capacity_candidate(
            row,
            factor_by_name[str(row["factor_name"])],
            labels_df=labels_df,
            layers_df=layers_df,
            liquidity_df=liquidity,
            policy=policy,
        )
        for row in rows
    ]
    evaluated.sort(key=lambda row: (DECISION_ORDER.index(row["capacity_decision"]), row["factor_name"]))
    payload = {
        "capacity_gate_id": capacity_gate_id,
        "created_at": created_at,
        "gate_d_id": str(gate_d["gate_d_id"]),
        "gate_d_summary_path": str(gate_d_summary_path),
        "gate_c_id": str(gate_c["gate_c_id"]),
        "sample_out_dates": sample_dates,
        "factor_count": len(evaluated),
        "decision_counts": _decision_counts(evaluated),
        "policy": policy,
        "factors": evaluated,
        "notes": notes,
    }
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    report = render_capacity_report(payload)
    report_path.write_text(report, encoding="utf-8")
    if doc_path is not None:
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(report, encoding="utf-8")
    append_capacity_log(
        capacity_gate_id=capacity_gate_id,
        created_at=created_at,
        gate_d_id=str(gate_d["gate_d_id"]),
        rows=evaluated,
        summary_path=summary_path,
        path=capacity_log_path,
        notes=notes,
    )
    return capacity_gate_id, payload, summary_path


def main() -> int:
    args = parse_args()
    capacity_gate_id, payload, summary_path = build_capacity_gate_summary(
        gate_d_summary_path=Path(args.gate_d_summary),
        capacity_log_path=Path(args.capacity_log),
        doc_path=Path(args.doc_path),
        factors=args.factors or None,
        label_column=args.label_column,
        top_fraction=args.top_fraction,
        stress_bps=args.stress_bps,
        participation_rates=args.participation_rates,
        pass_stress_bps=args.pass_stress_bps,
        pass_participation_rate=args.pass_participation_rate,
        min_gross_capacity_hkd=args.min_gross_capacity_hkd,
        max_concentration_share=args.max_concentration_share,
        max_missing_turnover_ratio=args.max_missing_turnover_ratio,
        notes=args.notes,
    )
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(
            f"{capacity_gate_id} factors={payload['factor_count']} "
            f"decisions={payload['decision_counts']} summary={summary_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
