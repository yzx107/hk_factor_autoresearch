"""Route layered Gate C outcomes into explicit follow-up research queues."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUN_ROOT = ROOT / "runs"
DEFAULT_QUEUE_LOG = ROOT / "registry" / "layered_followup_queue.tsv"

FOLLOWUP_LOG_HEADER = [
    "followup_batch_id",
    "followup_id",
    "created_at",
    "gate_c_id",
    "board_id",
    "source_triage_id",
    "factor_name",
    "gate_c_decision",
    "direction_hint",
    "followup_lane",
    "target_primary_layers_json",
    "target_southbound_buckets_json",
    "action",
    "rationale",
    "base_cost_adjusted_spread_return",
    "primary_pass_layers_json",
    "southbound_pass_buckets_json",
    "primary_strongest_layer",
    "southbound_strongest_bucket",
    "notes",
]

LANE_ORDER = [
    "southbound_split_retest",
    "layer_explicit_rewrite",
    "gate_d_watch_candidate",
    "time_stability_retest",
    "hold_or_discard",
    "manual_review",
]


def parse_args() -> argparse.Namespace:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    parser = argparse.ArgumentParser(description="Route layered Gate C outcomes into follow-up queues.")
    parser.add_argument("--gate-c-summary", required=True, help="Path to layered_gate_c_summary.json.")
    parser.add_argument("--queue-log", default=str(DEFAULT_QUEUE_LOG), help="Tracked follow-up TSV path.")
    parser.add_argument(
        "--doc-path",
        default=str(ROOT / "docs" / f"layered_gate_c_followup_plan_{month}.md"),
        help="Tracked follow-up plan markdown path.",
    )
    parser.add_argument("--notes", default="", help="Short follow-up note.")
    parser.add_argument("--json", action="store_true", help="Emit JSON payload.")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing Gate C summary JSON: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _metric(row: dict[str, Any], key: str) -> float | None:
    value = row.get("result", {}).get(key)
    if value in ("", None):
        return None
    return float(value)


def _passed_slices(rows: list[dict[str, Any]], *, exclude: set[str] | None = None) -> list[str]:
    blocked = exclude or set()
    return [
        str(row.get("slice_value"))
        for row in rows
        if row.get("passed") is True and str(row.get("slice_value")) not in blocked
    ]


def _strongest_slice(rows: list[dict[str, Any]]) -> str:
    scored = [(row, _metric(row, "cost_adjusted_spread_return")) for row in rows]
    valid = [(row, score) for row, score in scored if score is not None]
    if not valid:
        return ""
    row, _ = max(valid, key=lambda item: float(item[1]))
    return str(row.get("slice_value", ""))


def _base_cost(row: dict[str, Any]) -> float | None:
    value = row.get("base_backtest", {}).get("cost_adjusted_spread_return")
    if value in ("", None):
        return None
    return float(value)


def derive_followup(row: dict[str, Any]) -> dict[str, Any]:
    primary_rows = list(row.get("primary_layer_backtests") or [])
    southbound_rows = list(row.get("southbound_backtests") or [])
    primary_passes = _passed_slices(primary_rows, exclude={"unknown", "unlayered"})
    southbound_passes = _passed_slices(southbound_rows)
    primary_pass_rows = [
        row
        for row in primary_rows
        if row.get("passed") is True and str(row.get("slice_value")) not in {"unknown", "unlayered"}
    ]
    southbound_pass_rows = [row for row in southbound_rows if row.get("passed") is True]
    primary_strongest = _strongest_slice(primary_pass_rows or primary_rows)
    southbound_strongest = _strongest_slice(southbound_pass_rows or southbound_rows)
    decision = str(row.get("gate_c_decision", ""))

    target_primary_layers = primary_passes
    target_southbound_buckets = southbound_passes
    if decision == "needs_southbound_split":
        lane = "southbound_split_retest"
        action = (
            "split_passing_southbound_bucket_then_retest"
            if southbound_passes
            else "retest_southbound_buckets_before_promotion"
        )
        rationale = "Stock Connect buckets did not both pass Gate C stress."
    elif decision == "needs_layer_split":
        lane = "layer_explicit_rewrite"
        action = "rewrite_factor_as_layer_explicit_spec"
        rationale = "Base stress passed, but too few primary tradability layers passed."
        if not target_primary_layers and primary_strongest:
            target_primary_layers = [primary_strongest]
    elif decision == "advance_gate_d_watch":
        lane = "gate_d_watch_candidate"
        action = "prepare_sample_out_gate_d"
        rationale = "Gate C broad stress passed; still research-watch only."
    elif decision == "hold_time_instability":
        lane = "time_stability_retest"
        action = "rerun_with_more_dates_or_hold"
        rationale = "Early/late time-slice stress failed or had insufficient evidence."
    elif decision == "hold_cost_capacity":
        lane = "hold_or_discard"
        action = "hold_until_cost_capacity_improves"
        rationale = "Base cost, turnover, hit-rate, or stability stress failed."
    else:
        lane = "manual_review"
        action = "manual_review_gate_c_outcome"
        rationale = "Gate C decision is not mapped by the follow-up router."

    return {
        "factor_name": str(row["factor_name"]),
        "gate_c_decision": decision,
        "direction_hint": str(row.get("direction_hint", "")),
        "followup_lane": lane,
        "target_primary_layers": target_primary_layers,
        "target_southbound_buckets": target_southbound_buckets,
        "action": action,
        "rationale": rationale,
        "base_cost_adjusted_spread_return": _base_cost(row),
        "primary_pass_layers": primary_passes,
        "southbound_pass_buckets": southbound_passes,
        "primary_strongest_layer": primary_strongest,
        "southbound_strongest_bucket": southbound_strongest,
        "gate_c_reasons": list(row.get("gate_c_reasons") or []),
    }


def _ensure_tsv(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\t".join(FOLLOWUP_LOG_HEADER) + "\n", encoding="utf-8")


def _list_json(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def append_followup_log(
    *,
    followup_batch_id: str,
    created_at: str,
    gate_c: dict[str, Any],
    rows: list[dict[str, Any]],
    path: Path = DEFAULT_QUEUE_LOG,
    notes: str = "",
) -> None:
    _ensure_tsv(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        for row in rows:
            writer.writerow(
                [
                    followup_batch_id,
                    row["followup_id"],
                    created_at,
                    gate_c["gate_c_id"],
                    gate_c.get("board_id", ""),
                    gate_c.get("source_triage_id", ""),
                    row["factor_name"],
                    row["gate_c_decision"],
                    row["direction_hint"],
                    row["followup_lane"],
                    _list_json(row["target_primary_layers"]),
                    _list_json(row["target_southbound_buckets"]),
                    row["action"],
                    row["rationale"],
                    row["base_cost_adjusted_spread_return"],
                    _list_json(row["primary_pass_layers"]),
                    _list_json(row["southbound_pass_buckets"]),
                    row["primary_strongest_layer"],
                    row["southbound_strongest_bucket"],
                    notes,
                ]
            )


def _fmt(value: Any, digits: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _lane_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row["followup_lane"] for row in rows)
    return {name: counts[name] for name in LANE_ORDER if counts[name]}


def render_followup_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Layered Gate C Follow-up Plan",
        "",
        "This plan converts Gate C stress outcomes into research tasks. It is not a promotion list.",
        "",
        "## Source",
        "",
        f"- followup_batch_id: `{payload['followup_batch_id']}`",
        f"- gate_c_id: `{payload['gate_c_id']}`",
        f"- board_id: `{payload['board_id']}`",
        f"- source_triage_id: `{payload['source_triage_id']}`",
        f"- factor_count: `{payload['factor_count']}`",
        f"- gate_c_summary_path: `{payload['gate_c_summary_path']}`",
        "",
        "## Lane Counts",
        "",
    ]
    for lane, count in payload["lane_counts"].items():
        lines.append(f"- `{lane}`: {count}")
    lines.extend(
        [
            "",
            "## Queue",
            "",
            "| factor | Gate C decision | lane | target layers | target buckets | action | base cost-adj |",
            "| --- | --- | --- | --- | --- | --- | ---: |",
        ]
    )
    for row in payload["followups"]:
        layers = ", ".join(f"`{value}`" for value in row["target_primary_layers"]) or ""
        buckets = ", ".join(f"`{value}`" for value in row["target_southbound_buckets"]) or ""
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['factor_name']}`",
                    f"`{row['gate_c_decision']}` / `{row['direction_hint']}`",
                    f"`{row['followup_lane']}`",
                    layers,
                    buckets,
                    f"`{row['action']}`",
                    _fmt(row["base_cost_adjusted_spread_return"]),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Guardrails", ""])
    lines.append("- `southbound_split_retest` must separate eligible, not-eligible, and unknown flow before promotion.")
    lines.append("- `layer_explicit_rewrite` should become a layer-scoped factor spec, not a broad all-candidate factor.")
    lines.append("- Small-illiquid targets remain capacity and slippage constrained until a later cost gate proves otherwise.")
    return "\n".join(lines) + "\n"


def build_layered_gate_c_followups(
    *,
    gate_c_summary_path: Path,
    queue_log_path: Path = DEFAULT_QUEUE_LOG,
    doc_path: Path | None = None,
    run_root: Path = RUN_ROOT,
    notes: str = "",
) -> tuple[str, dict[str, Any], Path]:
    gate_c = _load_json(gate_c_summary_path)
    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    followup_batch_id = f"layered_followup_{stamp}_{gate_c['gate_c_id']}"
    run_dir = run_root / followup_batch_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "layered_gate_c_followup_summary.json"
    report_path = run_dir / "layered_gate_c_followup_report.md"

    followups = [derive_followup(row) for row in gate_c.get("factors", [])]
    followups.sort(key=lambda row: (LANE_ORDER.index(row["followup_lane"]), row["factor_name"]))
    for index, row in enumerate(followups, start=1):
        row["followup_id"] = f"{followup_batch_id}_{index:03d}"

    payload = {
        "followup_batch_id": followup_batch_id,
        "created_at": created_at,
        "gate_c_id": str(gate_c["gate_c_id"]),
        "board_id": str(gate_c.get("board_id", "")),
        "source_triage_id": str(gate_c.get("source_triage_id", "")),
        "gate_c_summary_path": str(gate_c_summary_path),
        "factor_count": len(followups),
        "lane_counts": _lane_counts(followups),
        "followups": followups,
        "notes": notes,
    }
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    report = render_followup_report(payload)
    report_path.write_text(report, encoding="utf-8")
    if doc_path is not None:
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(report, encoding="utf-8")
    append_followup_log(
        followup_batch_id=followup_batch_id,
        created_at=created_at,
        gate_c=gate_c,
        rows=followups,
        path=queue_log_path,
        notes=notes,
    )
    return followup_batch_id, payload, summary_path


def main() -> int:
    args = parse_args()
    followup_batch_id, payload, summary_path = build_layered_gate_c_followups(
        gate_c_summary_path=Path(args.gate_c_summary),
        queue_log_path=Path(args.queue_log),
        doc_path=Path(args.doc_path),
        notes=args.notes,
    )
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(
            f"{followup_batch_id} factors={payload['factor_count']} "
            f"lanes={payload['lane_counts']} summary={summary_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
