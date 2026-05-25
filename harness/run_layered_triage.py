"""Convert a layered factor board into research decisions."""

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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUN_ROOT = ROOT / "runs"
DEFAULT_DECISION_LOG = ROOT / "registry" / "layered_factor_decisions.tsv"
DEFAULT_SPLIT_THRESHOLD = 0.04

SMALL_ILLIQUID_CLASSES = {
    "small_illiquid_dominant_risk",
    "small_illiquid_only_risk",
}
NEW_LISTING_CLASSES = {
    "new_listing_dominant_watch",
    "new_listing_only_watch",
}
PROMOTE_CLASSES = {
    "broad_candidate",
    "large_liquid_candidate",
    "large_liquid_dominant",
}
RERUN_CLASSES = {
    "mid_liquid_candidate",
    "mid_liquid_dominant",
    "selective_layer_candidate",
    "unstable_across_layers",
}

DECISION_ORDER = [
    "needs_southbound_split",
    "promote_broad_candidate",
    "research_new_listing_family",
    "risk_only_small_illiquid",
    "rerun_with_cost_stress",
    "discard_or_hold",
]

DECISION_LOG_HEADER = [
    "triage_id",
    "created_at",
    "board_id",
    "factor_name",
    "classification",
    "strongest_layer",
    "primary_decision",
    "secondary_decisions_json",
    "research_lane",
    "next_action",
    "needs_southbound_split",
    "southbound_abs_rank_ic",
    "southbound_unknown_abs_rank_ic",
    "southbound_abs_rank_ic_gap",
    "max_abs_rank_ic",
    "layer_dispersion",
    "run_dir",
    "notes",
]


def parse_args() -> argparse.Namespace:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    parser = argparse.ArgumentParser(description="Run layer-aware triage over a layered factor board.")
    parser.add_argument("--layered-board", required=True, help="Path to layered_factor_board.json.")
    parser.add_argument("--decision-log", default=str(DEFAULT_DECISION_LOG), help="Tracked decision TSV path.")
    parser.add_argument(
        "--doc-path",
        default=str(ROOT / "docs" / f"layered_factor_board_summary_{month}.md"),
        help="Tracked monthly summary markdown path.",
    )
    parser.add_argument("--southbound-split-threshold", type=float, default=DEFAULT_SPLIT_THRESHOLD)
    parser.add_argument("--notes", default="", help="Short triage note.")
    parser.add_argument("--json", action="store_true", help="Emit JSON payload.")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing layered board JSON: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _as_float(value: object) -> float | None:
    if value in ("", None):
        return None
    return float(value)


def _layer_metric(rows: list[dict[str, Any]], layer_value: str, key: str = "abs_rank_ic") -> float | None:
    for row in rows:
        if row.get("layer_value") == layer_value:
            return _as_float(row.get(key))
    return None


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return fsum(values) / len(values)


def _base_decision(classification: str) -> str:
    if classification in SMALL_ILLIQUID_CLASSES:
        return "risk_only_small_illiquid"
    if classification in NEW_LISTING_CLASSES:
        return "research_new_listing_family"
    if classification in PROMOTE_CLASSES:
        return "promote_broad_candidate"
    if classification in RERUN_CLASSES:
        return "rerun_with_cost_stress"
    return "discard_or_hold"


def _southbound_split(row: dict[str, Any], threshold: float) -> dict[str, Any]:
    rows = list(row.get("southbound_layer_rows") or [])
    eligible = _layer_metric(rows, "southbound_eligible")
    unknown = _layer_metric(rows, "southbound_unknown")
    not_eligible = _layer_metric(rows, "southbound_not_eligible")
    comparisons = [
        (name, value, abs(eligible - value))
        for name, value in [
            ("southbound_not_eligible", not_eligible),
            ("southbound_unknown", unknown),
        ]
        if eligible is not None and value is not None
    ]
    comparison_layer = ""
    comparison_value = None
    gap = None
    if comparisons:
        comparison_layer, comparison_value, gap = max(comparisons, key=lambda item: item[2])
    return {
        "southbound_abs_rank_ic": eligible,
        "southbound_unknown_abs_rank_ic": unknown,
        "southbound_not_eligible_abs_rank_ic": not_eligible,
        "southbound_comparison_layer": comparison_layer,
        "southbound_comparison_abs_rank_ic": comparison_value,
        "southbound_abs_rank_ic_gap": gap,
        "needs_southbound_split": bool(gap is not None and gap >= threshold),
    }


def derive_layered_decision(
    row: dict[str, Any],
    *,
    southbound_split_threshold: float = DEFAULT_SPLIT_THRESHOLD,
) -> dict[str, Any]:
    classification = str(row.get("classification", ""))
    base = _base_decision(classification)
    southbound = _southbound_split(row, southbound_split_threshold)
    secondary: list[str] = []
    primary = base

    if southbound["needs_southbound_split"]:
        if base in {"promote_broad_candidate", "rerun_with_cost_stress"}:
            primary = "needs_southbound_split"
            secondary.append(base)
        elif base != "discard_or_hold":
            secondary.append("needs_southbound_split")

    lane, next_action = _lane_and_action(primary, base, row, secondary)
    decision = {
        "factor_name": str(row["factor_name"]),
        "classification": classification,
        "classification_reason": str(row.get("classification_reason", "")),
        "strongest_layer": str(row.get("strongest_layer", "")),
        "weakest_layer": str(row.get("weakest_layer", "")),
        "signal_layers": list(row.get("signal_layers") or []),
        "primary_decision": primary,
        "secondary_decisions": secondary,
        "research_lane": lane,
        "next_action": next_action,
        "max_abs_rank_ic": _as_float(row.get("max_abs_rank_ic")),
        "layer_dispersion": _as_float(row.get("layer_dispersion")),
        "run_dir": str(row.get("run_dir", "")),
        **southbound,
    }
    return decision


def _lane_and_action(
    primary: str,
    base: str,
    row: dict[str, Any],
    secondary: list[str],
) -> tuple[str, str]:
    if primary == "risk_only_small_illiquid":
        return (
            "small_illiquid_risk",
            "Keep out of promotion; use only as capacity, turnover, and slippage stress evidence.",
        )
    if primary == "research_new_listing_family":
        return (
            "new_listing_research",
            "Build listing-age and seasoning variants, then evaluate separately from mature listings.",
        )
    if primary == "needs_southbound_split":
        return (
            "large_southbound_research",
            "Split southbound_eligible versus not-eligible or unknown before any Gate C promotion.",
        )
    if primary == "promote_broad_candidate":
        lane = "large_southbound_research" if "large_liquid_core" in row.get("signal_layers", []) else "broad_retest"
        return lane, "Promote to controlled Gate C research with cost, capacity, and sample-out checks."
    if primary == "rerun_with_cost_stress":
        return (
            "layer_stability_retest",
            "Rerun with stricter cost and capacity stress before creating a new factor family spec.",
        )
    if base == "promote_broad_candidate" and "needs_southbound_split" in secondary:
        return (
            "large_southbound_research",
            "Promote only after the southbound split remains robust.",
        )
    return "hold_or_discard", "Hold until layer evidence or coverage improves."


def _ensure_tsv(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\t".join(DECISION_LOG_HEADER) + "\n", encoding="utf-8")


def append_decision_log(
    *,
    triage_id: str,
    created_at: str,
    board_id: str,
    decisions: list[dict[str, Any]],
    path: Path = DEFAULT_DECISION_LOG,
    notes: str = "",
) -> None:
    _ensure_tsv(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        for row in decisions:
            writer.writerow(
                [
                    triage_id,
                    created_at,
                    board_id,
                    row["factor_name"],
                    row["classification"],
                    row["strongest_layer"],
                    row["primary_decision"],
                    json.dumps(row["secondary_decisions"], ensure_ascii=False),
                    row["research_lane"],
                    row["next_action"],
                    row["needs_southbound_split"],
                    row["southbound_abs_rank_ic"],
                    row["southbound_unknown_abs_rank_ic"],
                    row["southbound_abs_rank_ic_gap"],
                    row["max_abs_rank_ic"],
                    row["layer_dispersion"],
                    row["run_dir"],
                    notes,
                ]
            )


def build_factor_spec_lanes(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lane_rows = [
        {
            "lane": "new_listing_research",
            "decision_filter": ["research_new_listing_family"],
            "factor_count": 0,
            "factor_names": [],
            "spec_direction": "Listing-age, seasoning, first-year liquidity, and order-lifecycle variants.",
        },
        {
            "lane": "small_illiquid_risk",
            "decision_filter": ["risk_only_small_illiquid"],
            "factor_count": 0,
            "factor_names": [],
            "spec_direction": "Risk-only close pressure, churn, capacity, and slippage diagnostics.",
        },
        {
            "lane": "large_southbound_research",
            "decision_filter": ["needs_southbound_split", "promote_broad_candidate"],
            "factor_count": 0,
            "factor_names": [],
            "spec_direction": "Large-liquid and Stock Connect split variants with cost and sample-out gates.",
        },
    ]
    for lane in lane_rows:
        filters = set(lane["decision_filter"])
        names = [
            row["factor_name"]
            for row in decisions
            if row["primary_decision"] in filters
        ]
        lane["factor_count"] = len(names)
        lane["factor_names"] = sorted(names)
    return lane_rows


def _decision_counts(decisions: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row["primary_decision"] for row in decisions)
    return {name: counts[name] for name in DECISION_ORDER if counts[name]}


def _render_run_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Layered Factor Triage",
        "",
        f"- triage_id: `{payload['triage_id']}`",
        f"- board_id: `{payload['board_id']}`",
        f"- factor_count: `{payload['factor_count']}`",
        "",
        "## Decision Counts",
        "",
    ]
    for name, count in payload["decision_counts"].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(["", "## Decisions", ""])
    for row in payload["decisions"]:
        lines.append(
            "- "
            f"`{row['factor_name']}` decision=`{row['primary_decision']}` "
            f"lane=`{row['research_lane']}` class=`{row['classification']}` "
            f"strongest=`{row['strongest_layer']}`"
        )
    return "\n".join(lines) + "\n"


def render_monthly_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# Layered Factor Board Summary 2026-05",
        "",
        "This summary converts the current layered factor board into research decisions. "
        "It is not a production promotion list.",
        "",
        "## Source",
        "",
        f"- board_id: `{payload['board_id']}`",
        f"- layered_board_path: `{payload['layered_board_path']}`",
        f"- triage_id: `{payload['triage_id']}`",
        f"- factor_count: `{payload['factor_count']}`",
        f"- southbound_split_threshold_abs_rank_ic: `{payload['policy']['southbound_split_threshold']}`",
        "",
        "## Decision Counts",
        "",
    ]
    for name, count in payload["decision_counts"].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(
        [
            "",
            "## Decision Board",
            "",
            "| factor | decision | secondary | lane | class | strongest | max_abs_ic | dispersion | sb_compare | sb_gap |",
            "| --- | --- | --- | --- | --- | --- | ---: | ---: | --- | ---: |",
        ]
    )
    for row in payload["decisions"]:
        secondary = ", ".join(f"`{item}`" for item in row["secondary_decisions"])
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['factor_name']}`",
                    f"`{row['primary_decision']}`",
                    secondary,
                    f"`{row['research_lane']}`",
                    f"`{row['classification']}`",
                    row["strongest_layer"],
                    _fmt(row["max_abs_rank_ic"]),
                    _fmt(row["layer_dispersion"]),
                    row["southbound_comparison_layer"],
                    _fmt(row["southbound_abs_rank_ic_gap"]),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Next Factor Spec Lanes", ""])
    for lane in payload["factor_spec_lanes"]:
        names = ", ".join(f"`{name}`" for name in lane["factor_names"]) or "none"
        lines.append(f"- `{lane['lane']}` count=`{lane['factor_count']}`: {lane['spec_direction']} Factors: {names}.")
    lines.extend(["", "## Guardrails", ""])
    lines.append("- `risk_only_small_illiquid` is not promotable without explicit capacity and slippage stress.")
    lines.append("- `research_new_listing_family` stays separate from mature-listing selection.")
    lines.append("- `needs_southbound_split` must be resolved before broad promotion.")
    return "\n".join(lines) + "\n"


def build_layered_triage_summary(
    *,
    layered_board_path: Path,
    decision_log_path: Path = DEFAULT_DECISION_LOG,
    doc_path: Path | None = None,
    run_root: Path = RUN_ROOT,
    southbound_split_threshold: float = DEFAULT_SPLIT_THRESHOLD,
    notes: str = "",
) -> tuple[str, dict[str, Any], Path]:
    board = _load_json(layered_board_path)
    board_id = str(board["board_id"])
    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    triage_id = f"layered_triage_{stamp}_{board_id}"
    run_dir = run_root / triage_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "layered_triage_summary.json"
    report_path = run_dir / "layered_triage_report.md"

    decisions = [
        derive_layered_decision(row, southbound_split_threshold=southbound_split_threshold)
        for row in board.get("factors", [])
    ]
    decisions.sort(key=lambda row: (DECISION_ORDER.index(row["primary_decision"]), row["factor_name"]))
    lane_rows = build_factor_spec_lanes(decisions)
    payload = {
        "triage_id": triage_id,
        "created_at": created_at,
        "board_id": board_id,
        "layered_board_path": str(layered_board_path),
        "factor_count": len(decisions),
        "decision_counts": _decision_counts(decisions),
        "classification_counts": board.get("classification_counts", {}),
        "policy": {
            "southbound_split_threshold": southbound_split_threshold,
            "decision_order": DECISION_ORDER,
        },
        "factor_spec_lanes": lane_rows,
        "mean_max_abs_rank_ic": _mean([row["max_abs_rank_ic"] for row in decisions if row["max_abs_rank_ic"] is not None]),
        "decisions": decisions,
        "notes": notes,
    }
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    report_path.write_text(_render_run_report(payload), encoding="utf-8")
    append_decision_log(
        triage_id=triage_id,
        created_at=created_at,
        board_id=board_id,
        decisions=decisions,
        path=decision_log_path,
        notes=notes,
    )
    if doc_path is not None:
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(render_monthly_summary(payload), encoding="utf-8")
    return triage_id, payload, summary_path


def main() -> int:
    args = parse_args()
    triage_id, payload, summary_path = build_layered_triage_summary(
        layered_board_path=Path(args.layered_board),
        decision_log_path=Path(args.decision_log),
        doc_path=Path(args.doc_path),
        southbound_split_threshold=args.southbound_split_threshold,
        notes=args.notes,
    )
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(
            f"{triage_id} factors={payload['factor_count']} "
            f"decisions={payload['decision_counts']} summary={summary_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
