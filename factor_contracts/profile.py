"""Machine-readable factor profile helpers.

This layer synthesizes a stable factor identity from the research card,
module metadata, and family profile without requiring every factor module
to learn a second wave of schema constants.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from gatekeeper.gate_a_data import YEAR_GRADES
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
    family_id: str
    family_name: str
    mechanism_hypothesis: str
    target_universe_scope: str
    source_universe_scope: str
    contains_cross_security_source: bool
    universe_filter_version: str
    required_data_lane: str
    required_year_grade: list[str]
    time_grade_requirement: str
    contains_caveat_fields: bool
    supports_default_lane: bool
    supports_extension_lane: bool
    label_definition: str
    evaluation_horizons: list[str]
    known_failure_modes: list[str]
    baseline_comparators: list[str]
    requires_cross_security_mapping: bool
    forbidden_semantic_assumptions: list[str]
    input_dependencies: list[str]
    transform_chain: list[str]
    expected_regime: list[str]
    promotion_target: str
    family_allowed_input_lane: str
    family_common_variants: list[str]
    family_current_best_variants: list[str]
    family_redundancy_pattern: str
    family_regime_sensitivity: list[str]
    family_expand_direction: str
    research_card_path: str
    module_name: str
    family_registry_path: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _module_name(module: Any) -> str:
    return str(getattr(module, "__name__", "")).rsplit(".", 1)[-1]


def _contains_caveat_fields(card: dict[str, Any]) -> bool:
    if str(card.get("universe", "")) == "phase_a_caveat_lane":
        return True
    semantics = card.get("semantics", {})
    caveat_fields = {"TradeDir", "BrokerNo", "OrderType", "Type", "Ext"}
    return any(semantics.get(field, "unused") != "unused" for field in caveat_fields)


def _dedup(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _split_csv(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    text = str(value)
    return [item.strip() for item in text.split(",") if item.strip()]


def _required_data_lane(module: Any) -> str:
    if hasattr(module, "DAILY_AGG_TABLE") or hasattr(module, "DAILY_AGG_TABLES"):
        return "daily_agg"
    return "verified_raw"


def _supports_extension_lane(family_profile: dict[str, Any], source_instrument_universe: str) -> bool:
    eligibility = str(family_profile.get("extension_lane_eligibility", "default_lane_only"))
    return eligibility not in {"default_lane_only", "not_allowed", "blocked"} or source_instrument_universe != DEFAULT_SOURCE_INSTRUMENT_UNIVERSE


def _expected_regime(module: Any) -> list[str]:
    value = getattr(module, "EXPECTED_REGIMES", None)
    if value:
        return _split_csv(value)
    return _split_csv(getattr(module, "EXPECTED_REGIME", ""))


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
    family_id = str(getattr(module, "FACTOR_FAMILY", "") or card.get("factor_family", ""))
    family_name = str(
        family_profile.get("family_name")
        or family_id
        or card.get("factor_family", "")
    )
    mechanism = str(getattr(module, "MECHANISM", card.get("mechanism", "")))
    year_grade = [
        YEAR_GRADES[str(year)]
        for year in card.get("years", [])
        if str(year) in YEAR_GRADES
    ]
    time_grade_requirement = str(card.get("timing", {}).get("mode", "coarse_only"))
    evaluation_horizons = _dedup(
        [
            str(card.get("holding_horizon", "")),
            str(card.get("horizon_scope", "")),
            str(getattr(module, "HORIZON_SCOPE", "")),
        ]
    )
    baseline_comparators = _dedup(
        [str(item) for item in card.get("baseline_refs", [])]
        + _split_csv(family_profile.get("baseline_refs", []))
    )
    known_failure_modes = _dedup(
        [str(item) for item in card.get("failure_modes", [])]
        + _split_csv(family_profile.get("known_failure_patterns", []))
    )
    requires_cross_security_mapping = bool(
        contains_cross_security_source
        or source_instrument_universe != DEFAULT_SOURCE_INSTRUMENT_UNIVERSE
        or card.get("requires_cross_security_mapping", False)
    )
    supports_default_lane = (
        target_instrument_universe == DEFAULT_TARGET_INSTRUMENT_UNIVERSE
        and source_instrument_universe == DEFAULT_SOURCE_INSTRUMENT_UNIVERSE
        and not requires_cross_security_mapping
    )
    supports_extension_lane = _supports_extension_lane(family_profile, source_instrument_universe)

    profile = FactorProfile(
        factor_name=factor_name,
        factor_id=factor_id,
        family_id=family_id,
        family_name=family_name,
        mechanism_hypothesis=mechanism,
        target_universe_scope=target_instrument_universe,
        source_universe_scope=source_instrument_universe,
        contains_cross_security_source=bool(contains_cross_security_source),
        universe_filter_version=universe_filter_version,
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
        requires_cross_security_mapping=requires_cross_security_mapping,
        forbidden_semantic_assumptions=_split_csv(getattr(module, "FORBIDDEN_SEMANTIC_ASSUMPTIONS", [])),
        input_dependencies=_split_csv(getattr(module, "INPUT_DEPENDENCIES", [])),
        transform_chain=_split_csv(getattr(module, "TRANSFORM_CHAIN", [])),
        expected_regime=_expected_regime(module),
        promotion_target=str(card.get("promotion_target", "")),
        family_allowed_input_lane=str(family_profile.get("allowed_input_lane", "")),
        family_common_variants=_split_csv(family_profile.get("common_variants", [])),
        family_current_best_variants=_split_csv(family_profile.get("current_best_variants", [])),
        family_redundancy_pattern=str(family_profile.get("redundancy_pattern", "")),
        family_regime_sensitivity=_split_csv(family_profile.get("regime_sensitivity", [])),
        family_expand_direction=str(family_profile.get("whether_to_expand_further", "")),
        research_card_path=research_card_path,
        module_name=_module_name(module),
        family_registry_path=family_registry_path,
    )
    return profile
