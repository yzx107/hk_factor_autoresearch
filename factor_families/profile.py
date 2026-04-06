"""Machine-readable factor family profile helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
FAMILY_DIR = ROOT / "factor_families"
REGISTRY_PATH = ROOT / "registry" / "factor_families.tsv"
REQUIRED_FAMILY_KEYS = {
    "family_id",
    "family_name",
    "mechanism_hypothesis",
    "allowed_input_lane",
    "common_variants",
    "current_best_variants",
    "known_failure_patterns",
    "redundancy_pattern",
    "regime_sensitivity",
    "extension_lane_eligibility",
    "whether_to_expand_further",
}


@dataclass(frozen=True)
class FamilyProfile:
    family_id: str
    family_name: str
    mechanism_hypothesis: str
    allowed_input_lane: str
    common_variants: list[str]
    current_best_variants: list[str]
    known_failure_patterns: list[str]
    redundancy_pattern: str
    regime_sensitivity: list[str]
    extension_lane_eligibility: str
    whether_to_expand_further: str
    baseline_refs: list[str]
    approved_factor_ids: list[str]
    rejected_factor_ids: list[str]
    core_observables: list[str]
    forbidden_semantic_assumptions: list[str]
    status: str
    notes: str
    family_yaml_path: str
    family_registry_path: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_family_yaml(family_id: str, *, family_dir: Path = FAMILY_DIR) -> dict[str, Any]:
    path = family_dir / f"{family_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Missing family yaml: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Family yaml `{path}` must decode to a mapping.")
    data["family_yaml_path"] = str(path)
    return data


def _split_csv(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value)
    return [item.strip() for item in text.split(",") if item.strip()]


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return _split_csv(value)


def build_family_profile(
    family_id: str,
    *,
    family_yaml: dict[str, Any] | None = None,
    family_registry_path: Path = REGISTRY_PATH,
) -> FamilyProfile:
    data = dict(family_yaml or load_family_yaml(family_id))
    family_name = str(data.get("family_name", family_id))
    mechanism = str(data.get("mechanism_hypothesis", data.get("mechanism", "")))
    approved_factor_ids = _as_list(data.get("approved_factor_ids"))
    common_variants = _as_list(data.get("common_variants", data.get("current_members", approved_factor_ids)))
    current_best_variant = data.get("current_best_variant")
    current_best_variants = _as_list(data.get("current_best_variants"))
    if not current_best_variants and current_best_variant:
        current_best_variants = _as_list(current_best_variant)
    known_failure_patterns = _as_list(data.get("known_failure_patterns", data.get("known_failure_modes", [])))
    baseline_refs = _as_list(data.get("baseline_refs", []))
    redundancy_pattern = str(data.get("redundancy_pattern", "not_recorded"))
    regime_sensitivity = _as_list(data.get("regime_sensitivity", data.get("expected_regime", "unknown")))
    status = str(data.get("status", "unknown"))
    notes = str(data.get("notes", ""))

    return FamilyProfile(
        family_id=family_id,
        family_name=family_name,
        mechanism_hypothesis=mechanism,
        allowed_input_lane=str(data.get("allowed_input_lane", "phase_a_core")),
        common_variants=common_variants,
        current_best_variants=current_best_variants,
        known_failure_patterns=known_failure_patterns,
        redundancy_pattern=redundancy_pattern,
        regime_sensitivity=regime_sensitivity,
        extension_lane_eligibility=str(data.get("extension_lane_eligibility", "default_lane_only")),
        whether_to_expand_further=str(data.get("whether_to_expand_further", "monitor")),
        baseline_refs=baseline_refs,
        approved_factor_ids=approved_factor_ids,
        rejected_factor_ids=_as_list(data.get("rejected_factor_ids", [])),
        core_observables=_as_list(data.get("core_observables", [])),
        forbidden_semantic_assumptions=_as_list(data.get("forbidden_semantic_assumptions", [])),
        status=status,
        notes=notes,
        family_yaml_path=str(data.get("family_yaml_path", family_dir_path(family_id))),
        family_registry_path=str(family_registry_path),
    )


def family_dir_path(family_id: str) -> str:
    return str(FAMILY_DIR / f"{family_id}.yaml")
