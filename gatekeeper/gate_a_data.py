"""Minimal Gate A validator for Phase A research cards."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any
import tomllib

from harness.instrument_universe import (
    DEFAULT_SOURCE_INSTRUMENT_UNIVERSE,
    DEFAULT_TARGET_INSTRUMENT_UNIVERSE,
    UNIVERSE_FILTER_VERSION,
)

ROOT = Path(__file__).resolve().parents[1]

YEAR_GRADES = {
    "2025": "coarse_only",
    "2026": "fine_ok",
}

SUPPORTED_UNIVERSES = {
    "phase_a_core",
    "phase_a_caveat_lane",
}

SUPPORTED_TARGET_INSTRUMENT_UNIVERSES = {
    "stock_research_candidate",
}

SUPPORTED_SOURCE_INSTRUMENT_UNIVERSES = {
    "target_only",
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
    "OrderType": "OrderType is caveat-only: stable vendor event code under manual review.",
    "Type": "Type is caveat-only: vendor public-trade-type bucket under manual review.",
    "OrderSideVendor": "OrderSideVendor is caveat-only: derived from Ext.bit0 under manual review.",
}

KNOWN_FIELDS = SAFE_FIELDS | set(BLOCKED_FIELDS) | set(CAVEAT_FIELDS) | {"TradeDir", "BrokerNo", "Ext"}

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
    "target_instrument_universe",
    "source_instrument_universe",
    "contains_cross_security_source",
    "universe_filter_version",
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
    return _normalize_card(tomllib.loads(front_matter))


def _normalize_card(card: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(card)
    if "target_instrument_universe" not in normalized and "instrument_universe" in normalized:
        normalized["target_instrument_universe"] = normalized["instrument_universe"]
    return normalized


def load_research_card(path: Path) -> dict[str, Any]:
    return _load_card(path)


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
    if card.get("universe") not in SUPPORTED_UNIVERSES:
        allowed = ", ".join(sorted(SUPPORTED_UNIVERSES))
        errors.append(f"Phase A currently supports only named universes: {allowed}.")
    legacy_target = card.get("instrument_universe")
    target_instrument_universe = card.get("target_instrument_universe")
    if (
        legacy_target is not None
        and target_instrument_universe is not None
        and legacy_target != target_instrument_universe
    ):
        errors.append(
            "Legacy `instrument_universe` and `target_instrument_universe` disagree. "
            "Keep only one target-universe declaration or make them identical."
        )
    if target_instrument_universe not in SUPPORTED_TARGET_INSTRUMENT_UNIVERSES:
        allowed = ", ".join(sorted(SUPPORTED_TARGET_INSTRUMENT_UNIVERSES))
        errors.append(
            "This repo only supports stock-factor research cards with "
            f"`target_instrument_universe` in: {allowed}."
        )
    if card.get("source_instrument_universe") not in SUPPORTED_SOURCE_INSTRUMENT_UNIVERSES:
        allowed = ", ".join(sorted(SUPPORTED_SOURCE_INSTRUMENT_UNIVERSES))
        errors.append(
            "Default stock-factor runs only support "
            f"`source_instrument_universe` in: {allowed}. "
            "Cross-security non-equity sources must live in an explicit future extension lane, "
            "not the default factor scoreboard path."
        )
    contains_cross_security_source = card.get("contains_cross_security_source")
    if not isinstance(contains_cross_security_source, bool):
        errors.append("`contains_cross_security_source` must be a boolean.")
    elif contains_cross_security_source:
        errors.append(
            "Default Phase A stock-factor cards must not set `contains_cross_security_source = true`."
        )
    if card.get("universe_filter_version") != UNIVERSE_FILTER_VERSION:
        errors.append(
            f"Default universe filter version must be `{UNIVERSE_FILTER_VERSION}`."
        )


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
    universe = str(card["universe"])
    uses_caveat_lane = False

    unknown_fields = sorted(set(fields) - KNOWN_FIELDS)
    if unknown_fields:
        errors.append(f"Unknown fields in `required_fields`: {', '.join(unknown_fields)}.")

    for field in fields:
        if field in BLOCKED_FIELDS:
            errors.append(BLOCKED_FIELDS[field])
        elif field in CAVEAT_FIELDS:
            caveats.append(CAVEAT_FIELDS[field])
            uses_caveat_lane = True

    trade_dir_semantics = semantics["TradeDir"]
    uses_trade_dir = "TradeDir" in fields or trade_dir_semantics != "unused"
    if uses_trade_dir:
        uses_caveat_lane = True
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
            if trade_dir_semantics in {"candidate_directional_signal", "vendor_aggressor_proxy_only"}:
                caveats.append(
                    "2026 TradeDir is caveat-only: vendor-derived aggressor proxy under manual review, not signed-side truth."
                )
            elif trade_dir_semantics == "stable_code_structure_only":
                caveats.append("TradeDir remains vendor-defined and manually reviewed.")
            elif trade_dir_semantics != "unused":
                errors.append("2026 TradeDir use cannot exceed `vendor_aggressor_proxy_only`.")

    broker_semantics = semantics["BrokerNo"]
    uses_broker = "BrokerNo" in fields or broker_semantics != "unused"
    if uses_broker:
        uses_caveat_lane = True
        if broker_semantics == "unused":
            errors.append("BrokerNo is listed but `semantics.BrokerNo` is `unused`.")
        elif broker_semantics == "reference_lookup_only":
            caveats.append("BrokerNo remains reference-only and cannot drive direct alpha claims.")
        else:
            errors.append("BrokerNo is limited to `reference_lookup_only` in both 2025 and 2026.")

    order_type_semantics = semantics["OrderType"]
    if "OrderType" in fields or order_type_semantics != "unused":
        uses_caveat_lane = True
        if order_type_semantics in {"weak_event_code_only", "stable_vendor_event_code_only"}:
            caveats.append("OrderType is caveat-only: stable vendor event code, not official event semantics.")
        elif order_type_semantics != "unused":
            errors.append("OrderType cannot be promoted beyond weak vendor event-code usage.")

    type_semantics = semantics["Type"]
    if "Type" in fields or type_semantics != "unused":
        uses_caveat_lane = True
        if type_semantics in {"vendor_code_descriptive_only", "vendor_public_trade_type_bucket_only"}:
            caveats.append("Type is caveat-only: vendor public-trade-type bucket, not official raw TrdType.")
        elif type_semantics != "unused":
            errors.append("Type cannot be promoted beyond vendor public-trade-type bucket usage.")

    if "Ext" in fields:
        errors.append("Full Ext stays outside Phase A caveat lane; use `OrderSideVendor` derived from `Ext.bit0` instead.")

    ext_semantics = semantics["Ext"]
    uses_order_side_vendor = "OrderSideVendor" in fields
    if uses_order_side_vendor:
        uses_caveat_lane = True
        if ext_semantics != "bit0_order_side_proxy_only":
            errors.append(
                "OrderSideVendor requires `semantics.Ext = bit0_order_side_proxy_only`."
            )
        else:
            caveats.append(
                "OrderSideVendor is caveat-only: derived from Ext.bit0 as a vendor order-side proxy."
            )
    elif ext_semantics != "unused":
        errors.append(
            "Ext cannot be used directly in Phase A; only `OrderSideVendor` derived from `Ext.bit0` may enter the caveat lane."
        )

    for blocked_semantic_field in ("Level", "VolumePre"):
        if semantics[blocked_semantic_field] != "unused":
            errors.append(f"{blocked_semantic_field} semantics are blocked in Phase A.")

    if uses_caveat_lane and universe != "phase_a_caveat_lane":
        errors.append(
            "Caveat-only fields require `universe = phase_a_caveat_lane`."
        )


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
