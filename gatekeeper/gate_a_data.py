"""Minimal Gate A validator for Phase A research cards."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any
import tomllib

ROOT = Path(__file__).resolve().parents[1]

YEAR_GRADES = {
    "2025": "coarse_only",
    "2026": "fine_ok",
}

SAFE_FIELDS = {
    "date",
    "table_name",
    "source_file",
    "ingest_ts",
    "row_num_in_file",
    "SeqNum",
    "OrderId",
    "Time",
    "Price",
    "Volume",
    "TickID",
}

FIELD_ALIASES = {
    "Dir": "TradeDir",
    "TradeDir": "TradeDir",
}

BLOCKED_FIELDS = {
    "Level": "Level is blocked in Phase A; queue and depth semantics are not verified.",
    "VolumePre": "VolumePre is blocked in Phase A; pre-modify quantity semantics are not verified.",
    "BidOrderID": "BidOrderID stays outside the default verified boundary in Phase A.",
    "AskOrderID": "AskOrderID stays outside the default verified boundary in Phase A.",
    "BidVolume": "BidVolume stays outside the default verified boundary in Phase A.",
    "AskVolume": "AskVolume stays outside the default verified boundary in Phase A.",
}

CAVEAT_FIELDS = {
    "OrderType": "OrderType remains a vendor event code and is not default-admitted.",
    "Type": "Type remains a vendor trade code and is not default-admitted.",
    "Ext": "Ext remains a vendor extension code and is not default-admitted.",
}

KNOWN_FIELDS = SAFE_FIELDS | set(BLOCKED_FIELDS) | set(CAVEAT_FIELDS) | {"TradeDir", "BrokerNo"}

MODULE_MATRIX = {
    "order_trade_coverage_profile": {"2025": "allowed", "2026": "allowed"},
    "matched_edge_session_profile": {"2025": "allowed", "2026": "allowed"},
    "order_trade_consistency_same_second": {"2025": "allowed_with_caveat", "2026": "allowed"},
    "order_lifecycle_shape_by_event_count": {"2025": "allowed", "2026": "allowed"},
    "trade_dir_weak_consistency_check": {"2025": "allowed_with_caveat", "2026": "allowed"},
    "trade_dir_candidate_signal_profile": {"2025": "blocked", "2026": "allowed_with_caveat"},
    "broker_weak_consistency_check": {"2025": "allowed_with_caveat", "2026": "allowed"},
    "ordertype_weak_consistency_check": {"2025": "allowed_with_caveat", "2026": "allowed_with_caveat"},
    "coarse_lag_bucket": {"2025": "allowed_with_caveat", "2026": "allowed"},
    "post_trade_drift_coarse_window": {"2025": "allowed_with_caveat", "2026": "allowed"},
    "waiting_time_distribution": {"2025": "blocked", "2026": "allowed"},
    "precise_order_to_trade_lag": {"2025": "blocked", "2026": "allowed"},
    "strict_ordering_sensitive_causality": {"2025": "blocked", "2026": "allowed_with_caveat"},
    "queue_position_or_depletion": {"2025": "blocked", "2026": "blocked"},
    "execution_realism_or_fill_simulation": {"2025": "blocked", "2026": "allowed_with_caveat"},
    "latency_like_metrics": {"2025": "blocked", "2026": "allowed_with_caveat"},
    "signed_flow_directional_factor": {"2025": "blocked", "2026": "blocked"},
}

REQUIRED_TOP_LEVEL_KEYS = {
    "card_id",
    "name",
    "owner",
    "status",
    "years",
    "universe",
    "holding_horizon",
    "research_modules",
    "required_fields",
    "hypothesis",
    "mechanism",
    "info_boundary",
    "failure_modes",
    "expected_risks",
    "timing",
    "semantics",
}

REQUIRED_TIMING_KEYS = {"mode", "uses_precise_lag", "uses_strict_ordering", "uses_queue_semantics"}
REQUIRED_SEMANTIC_KEYS = {"TradeDir", "BrokerNo", "OrderType", "Level", "VolumePre", "Type", "Ext"}


@dataclass(frozen=True)
class GateResult:
    path: str
    decision: str
    reasons: tuple[str, ...]
    manual_review_required: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "decision": self.decision,
            "reasons": list(self.reasons),
            "manual_review_required": self.manual_review_required,
        }


def _canonical_field(field_name: str) -> str:
    return FIELD_ALIASES.get(field_name, field_name)


def _load_card(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "+++":
        raise ValueError("Research card must start with TOML front matter delimited by +++.")

    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "+++":
            end_index = index
            break

    if end_index is None:
        raise ValueError("Closing +++ front matter delimiter not found.")

    front_matter = "\n".join(lines[1:end_index])
    return tomllib.loads(front_matter)


def _validate_card_shape(card: dict[str, Any], errors: list[str]) -> None:
    missing_top = sorted(REQUIRED_TOP_LEVEL_KEYS - set(card))
    if missing_top:
        errors.append(f"Missing required front-matter keys: {', '.join(missing_top)}.")
        return

    timing = card["timing"]
    semantics = card["semantics"]

    missing_timing = sorted(REQUIRED_TIMING_KEYS - set(timing))
    if missing_timing:
        errors.append(f"Missing timing keys: {', '.join(missing_timing)}.")

    missing_semantics = sorted(REQUIRED_SEMANTIC_KEYS - set(semantics))
    if missing_semantics:
        errors.append(f"Missing semantics keys: {', '.join(missing_semantics)}.")

    if not isinstance(card["years"], list) or not card["years"]:
        errors.append("`years` must be a non-empty list.")
    if not isinstance(card["research_modules"], list) or not card["research_modules"]:
        errors.append("`research_modules` must be a non-empty list.")
    if not isinstance(card["required_fields"], list) or not card["required_fields"]:
        errors.append("`required_fields` must be a non-empty list.")
    if not isinstance(card["failure_modes"], list) or not card["failure_modes"]:
        errors.append("`failure_modes` must be a non-empty list.")
    if not isinstance(card["expected_risks"], list) or not card["expected_risks"]:
        errors.append("`expected_risks` must be a non-empty list.")
    if card.get("universe") != "phase_a_core":
        errors.append("Phase A currently supports only the named universe `phase_a_core`.")


def _check_year_and_timing(card: dict[str, Any], errors: list[str], caveats: list[str]) -> list[str]:
    years = [str(year) for year in card["years"]]
    unknown_years = sorted(set(years) - set(YEAR_GRADES))
    if unknown_years:
        errors.append(f"Unsupported years: {', '.join(unknown_years)}.")
        return years

    timing = card["timing"]
    mode = timing["mode"]
    if mode not in {"coarse_only", "fine_ok"}:
        errors.append("`timing.mode` must be `coarse_only` or `fine_ok`.")

    if "2025" in years and mode != "coarse_only":
        errors.append("2025 cards must declare `timing.mode = coarse_only`.")
    if "2025" in years and timing["uses_precise_lag"]:
        errors.append("2025 is coarse_only and cannot use precise lag.")
    if "2025" in years and timing["uses_strict_ordering"]:
        errors.append("2025 cannot use strict ordering semantics.")
    if timing["uses_queue_semantics"]:
        errors.append("Queue semantics are blocked for both 2025 and 2026.")

    if "2026" in years and timing["uses_precise_lag"]:
        caveats.append("2026 precise lag work remains manual-review gated by field semantics.")
    if "2026" in years and timing["uses_strict_ordering"]:
        caveats.append("2026 strict ordering work remains caveated and cannot rely on queue semantics.")

    return years


def _check_modules(card: dict[str, Any], years: list[str], errors: list[str], caveats: list[str]) -> None:
    for module in card["research_modules"]:
        if module not in MODULE_MATRIX:
            errors.append(f"Unknown research module `{module}`. Add policy before using it.")
            continue
        for year in years:
            status = MODULE_MATRIX[module][year]
            if status == "blocked":
                errors.append(f"Module `{module}` is blocked for {year}.")
            elif status == "allowed_with_caveat":
                caveats.append(f"Module `{module}` is allowed_with_caveat for {year}.")


def _check_fields(card: dict[str, Any], years: list[str], errors: list[str], caveats: list[str]) -> None:
    fields = [_canonical_field(str(field)) for field in card["required_fields"]]
    semantics = card["semantics"]

    unknown_fields = sorted(set(fields) - KNOWN_FIELDS)
    if unknown_fields:
        errors.append(f"Unknown fields in `required_fields`: {', '.join(unknown_fields)}.")

    for field in fields:
        if field in BLOCKED_FIELDS:
            errors.append(BLOCKED_FIELDS[field])
        elif field in CAVEAT_FIELDS:
            caveats.append(CAVEAT_FIELDS[field])

    trade_dir_semantics = semantics["TradeDir"]
    uses_trade_dir = "TradeDir" in fields or trade_dir_semantics != "unused"
    if uses_trade_dir:
        if trade_dir_semantics == "unused":
            errors.append("TradeDir is listed but `semantics.TradeDir` is `unused`.")
        if trade_dir_semantics in {"confirmed_signed_side", "signed_flow_truth", "aggressor_truth"}:
            errors.append("TradeDir cannot be treated as confirmed signed-side or aggressor truth.")
        if "2025" in years:
            if trade_dir_semantics != "stable_code_structure_only":
                errors.append("2025 TradeDir use is limited to `stable_code_structure_only`.")
            else:
                caveats.append("2025 TradeDir use is limited to stable code structure checks.")
        if "2026" in years:
            if trade_dir_semantics == "candidate_directional_signal":
                caveats.append(
                    "2026 TradeDir may be used only as a candidate directional signal under manual review."
                )
            elif trade_dir_semantics == "stable_code_structure_only":
                caveats.append("TradeDir remains vendor-defined and manually reviewed.")
            elif trade_dir_semantics != "unused":
                errors.append("2026 TradeDir use cannot exceed `candidate_directional_signal_only`.")

    broker_semantics = semantics["BrokerNo"]
    uses_broker = "BrokerNo" in fields or broker_semantics != "unused"
    if uses_broker:
        if broker_semantics == "unused":
            errors.append("BrokerNo is listed but `semantics.BrokerNo` is `unused`.")
        elif broker_semantics == "reference_lookup_only":
            caveats.append("BrokerNo is lookup-only and cannot drive direct alpha claims.")
        else:
            errors.append("BrokerNo is limited to `reference_lookup_only` in both 2025 and 2026.")

    order_type_semantics = semantics["OrderType"]
    if "OrderType" in fields or order_type_semantics != "unused":
        if order_type_semantics == "weak_event_code_only":
            caveats.append("OrderType remains a vendor code and needs manual review.")
        elif order_type_semantics != "unused":
            errors.append("OrderType cannot be promoted beyond weak vendor event-code usage.")

    for field_name in ("Type", "Ext"):
        semantic_value = semantics[field_name]
        if field_name in fields or semantic_value != "unused":
            if semantic_value == "vendor_code_descriptive_only":
                caveats.append(f"{field_name} remains vendor-defined and descriptive only.")
            elif semantic_value != "unused":
                errors.append(f"{field_name} cannot be promoted beyond vendor-code descriptive usage.")

    for blocked_semantic_field in ("Level", "VolumePre"):
        if semantics[blocked_semantic_field] != "unused":
            errors.append(f"{blocked_semantic_field} semantics are blocked in Phase A.")


def evaluate_card(path: Path) -> GateResult:
    errors: list[str] = []
    caveats: list[str] = []

    try:
        card = _load_card(path)
    except Exception as exc:
        return GateResult(
            path=str(path),
            decision="fail",
            reasons=(str(exc),),
            manual_review_required=False,
        )

    _validate_card_shape(card, errors)
    if not errors:
        years = _check_year_and_timing(card, errors, caveats)
        _check_modules(card, years, errors, caveats)
        _check_fields(card, years, errors, caveats)

    if errors:
        return GateResult(
            path=str(path),
            decision="fail",
            reasons=tuple(errors + caveats),
            manual_review_required=False,
        )
    if caveats:
        return GateResult(
            path=str(path),
            decision="allow_with_caveat",
            reasons=tuple(caveats),
            manual_review_required=True,
        )
    return GateResult(
        path=str(path),
        decision="pass",
        reasons=("No Phase A data-admissibility issue found.",),
        manual_review_required=False,
    )


def evaluate_many(paths: list[Path]) -> list[GateResult]:
    return [evaluate_card(path) for path in paths]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase A Gate A data checks on research cards.")
    parser.add_argument("cards", nargs="+", help="Research card markdown files with TOML front matter.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    paths = [Path(card) for card in args.cards]
    results = evaluate_many(paths)

    if args.json:
        print(json.dumps([result.as_dict() for result in results], indent=2))
    else:
        for result in results:
            print(result.path)
            print(f"  decision: {result.decision}")
            for reason in result.reasons:
                print(f"  - {reason}")

    return 0 if all(result.decision != "fail" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
