"""Machine-readable factor family profile helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
FAMILY_DIR = ROOT / "factor_families"
REGISTRY_PATH = ROOT / "registry" / "factor_families.tsv"


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
    regime_sensitivity: str
    extension_lane_eligibility: bool
    whether_to_expand_further: bool
    baseline_refs: list[str]
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


def build_family_profile(
    family_id: str,
    *,
    family_yaml: dict[str, Any] | None = None,
    family_registry_path: Path = REGISTRY_PATH,
) -> FamilyProfile:
    data = dict(family_yaml or load_family_yaml(family_id))
    family_name = str(data.get("family_name", family_id))
    mechanism = str(data.get("mechanism_hypothesis", data.get("mechanism", "")))
    common_variants = _split_csv(data.get("current_members", data.get("approved_factor_ids", [])))
    current_best_variant = data.get("current_best_variant")
    current_best_variants = _split_csv(current_best_variant) if current_best_variant else []
    known_failure_patterns = [str(item) for item in data.get("known_failure_modes", [])]
    baseline_refs = [str(item) for item in data.get("baseline_refs", [])]
    redundancy_pattern = (
        f"baseline_overlap_with={','.join(baseline_refs)}" if baseline_refs else "unknown"
    )
    regime_sensitivity = str(data.get("expected_regime", "unknown"))
    status = str(data.get("status", "unknown"))
    notes = str(data.get("notes", ""))

    return FamilyProfile(
        family_id=family_id,
        family_name=family_name,
        mechanism_hypothesis=mechanism,
        allowed_input_lane="phase_a_core_only",
        common_variants=common_variants,
        current_best_variants=current_best_variants,
        known_failure_patterns=known_failure_patterns,
        redundancy_pattern=redundancy_pattern,
        regime_sensitivity=regime_sensitivity,
        extension_lane_eligibility=bool(data.get("extension_lane_eligibility", False)),
        whether_to_expand_further=bool(data.get("whether_to_expand_further", False)),
        baseline_refs=baseline_refs,
        status=status,
        notes=notes,
        family_yaml_path=str(data.get("family_yaml_path", family_dir_path(family_id))),
        family_registry_path=str(family_registry_path),
    )


def family_dir_path(family_id: str) -> str:
    return str(FAMILY_DIR / f"{family_id}.yaml")

