"""Machine-readable factor profile helpers.

This layer synthesizes a stable factor identity from the research card,
module metadata, and family registry without requiring every factor module
to learn a separate schema.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from harness.instrument_universe import (
    DEFAULT_SOURCE_INSTRUMENT_UNIVERSE,
    DEFAULT_TARGET_INSTRUMENT_UNIVERSE,
    UNIVERSE_FILTER_VERSION,
)


DEFAULT_LABEL_DEFINITION = "forward_return_1d_close_like"


@dataclass(frozen=True)
class FactorProfile:
    factor_name: str
    factor_id: str
    family_name: str
    mechanism_hypothesis: str
    target_universe_scope: str
    source_universe_scope: str
    required_data_lane: str
    required_year_grade: str
    time_grade_requirement: str
    contains_caveat_fields: bool
    supports_default_lane: bool
    supports_extension_lane: bool
    label_definition: str
    evaluation_horizons: list[str]
    known_failure_modes: list[str]
    baseline_comparators: list[str]
    requires_cross_security_mapping: bool
    contains_cross_security_source: bool
    universe_filter_version: str
    research_card_path: str
    module_name: str
    family_registry_path: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _module_name(module: Any) -> str:
    return str(getattr(module, "__name__", "")).rsplit(".", 1)[-1]


def _required_data_lane(module: Any) -> str:
    if hasattr(module, "DAILY_AGG_TABLE") or hasattr(module, "DAILY_AGG_TABLES"):
        return "daily_agg"
    if hasattr(module, "compute_signal_from_loader"):
        return "verified_raw"
    return "verified_raw"


def _contains_caveat_fields(card: dict[str, Any]) -> bool:
    if str(card.get("universe", "")) == "phase_a_caveat_lane":
        return True
    semantics = card.get("semantics", {})
    caveat_fields = {"TradeDir", "BrokerNo", "OrderType", "Type", "OrderSideVendor"}
    return any(field in caveat_fields and semantics.get(field, "unused") != "unused" for field in caveat_fields)


def build_factor_profile(
    *,
    factor_name: str,
    card: dict[str, Any],
    module: Any,
    family_profile: dict[str, Any],
    research_card_path: str,
    target_instrument_universe: str = DEFAULT_TARGET_INSTRUMENT_UNIVERSE,
    source_instrument_universe: str = DEFAULT_SOURCE_INSTRUMENT_UNIVERSE,
    contains_cross_security_source: bool = False,
    universe_filter_version: str = UNIVERSE_FILTER_VERSION,
    label_definition: str = DEFAULT_LABEL_DEFINITION,
    family_registry_path: str = "",
) -> FactorProfile:
    factor_id = str(getattr(module, "FACTOR_ID", factor_name))
    family_name = str(
        family_profile.get("family_name")
        or getattr(module, "FACTOR_FAMILY", "")
        or card.get("factor_family", "")
    )
    mechanism = str(getattr(module, "MECHANISM", card.get("mechanism", "")))
    year_grade = ",".join(str(year) for year in card.get("years", []))
    time_grade_requirement = str(card.get("timing", {}).get("mode", "coarse_only"))
    evaluation_horizons = [
        str(card.get("holding_horizon", "")),
        str(card.get("horizon_scope", "")),
    ]
    baseline_comparators = [str(item) for item in card.get("baseline_refs", [])]
    known_failure_modes = [str(item) for item in card.get("failure_modes", [])]
    supports_default_lane = (
        target_instrument_universe == DEFAULT_TARGET_INSTRUMENT_UNIVERSE
        and source_instrument_universe == DEFAULT_SOURCE_INSTRUMENT_UNIVERSE
        and not contains_cross_security_source
    )
    supports_extension_lane = bool(contains_cross_security_source or source_instrument_universe != DEFAULT_SOURCE_INSTRUMENT_UNIVERSE)

    profile = FactorProfile(
        factor_name=factor_name,
        factor_id=factor_id,
        family_name=family_name,
        mechanism_hypothesis=mechanism,
        target_universe_scope=target_instrument_universe,
        source_universe_scope=source_instrument_universe,
        required_data_lane=_required_data_lane(module),
        required_year_grade=year_grade,
        time_grade_requirement=time_grade_requirement,
        contains_caveat_fields=_contains_caveat_fields(card),
        supports_default_lane=supports_default_lane,
        supports_extension_lane=supports_extension_lane,
        label_definition=label_definition,
        evaluation_horizons=evaluation_horizons,
        known_failure_modes=known_failure_modes,
        baseline_comparators=baseline_comparators,
        requires_cross_security_mapping=bool(contains_cross_security_source),
        contains_cross_security_source=bool(contains_cross_security_source),
        universe_filter_version=universe_filter_version,
        research_card_path=research_card_path,
        module_name=_module_name(module),
        family_registry_path=family_registry_path,
    )
    return profile

