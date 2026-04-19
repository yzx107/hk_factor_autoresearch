"""Load upstream semantic artifacts and derive conservative factor gating."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UPSTREAM_REPO_ROOT = Path(
    os.environ.get("HK_SEMANTIC_UPSTREAM_ROOT", "/Users/yxin/AI_Workstation/Hshare_Lab_v2")
)
DEFAULT_SEMANTIC_DQA_ROOT = Path(
    os.environ.get("HK_SEMANTIC_DQA_ROOT", str(DEFAULT_UPSTREAM_REPO_ROOT / "data" / "dqa"))
)
SEMANTIC_GATE_LOG = ROOT / "registry" / "semantic_gate_log.tsv"

STATUS_ALLOW = "semantic_allowed"
STATUS_CAVEAT = "semantic_allow_with_caveat"
STATUS_BLOCKED = "semantic_blocked"
STATUS_MANUAL_REVIEW = "semantic_requires_manual_review"
STATUS_SESSION_SPLIT = "semantic_requires_session_split"
STATUS_UNRESOLVED = "semantic_unresolved_mapping"
STATUS_NOT_LOADED = "semantic_not_loaded"

STATUS_PRIORITY = {
    STATUS_BLOCKED: 6,
    STATUS_MANUAL_REVIEW: 5,
    STATUS_SESSION_SPLIT: 4,
    STATUS_UNRESOLVED: 3,
    STATUS_NOT_LOADED: 2,
    STATUS_CAVEAT: 1,
    STATUS_ALLOW: 0,
}

KNOWN_MODULES = {
    "order_lifecycle_shape_by_event_count",
    "execution_realism_or_fill_simulation",
    "strict_ordering_sensitive_causality",
    "trade_dir_weak_consistency_check",
    "signed_flow",
    "aggressor_side_inference",
    "ordertype_weak_consistency_check",
    "event_semantics_inference",
    "matched_edge_session_profile",
    "cross_session_unaware_research",
}

TEXT_HEURISTIC_MAP = {
    "directional_proxy": ["signed_flow", "aggressor_side_inference"],
    "trade_dir": ["signed_flow", "aggressor_side_inference"],
    "signed_flow": ["signed_flow"],
    "aggressor": ["aggressor_side_inference"],
    "lifecycle": ["order_lifecycle_shape_by_event_count"],
    "session": ["matched_edge_session_profile"],
}


@dataclass(frozen=True)
class SemanticArtifacts:
    source_root: Path
    loaded_years: list[str]
    missing_years: list[str]
    yearly_summary: pl.DataFrame
    bridge: pl.DataFrame

    @property
    def source_loaded(self) -> bool:
        return self.bridge.height > 0 or self.yearly_summary.height > 0


def _split_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def infer_row_years(row: dict[str, Any]) -> list[str]:
    dates = list(row.get("evaluated_dates") or row.get("dates") or [])
    years: list[str] = []
    for item in dates:
        text = str(item)
        if len(text) >= 4 and text[:4].isdigit() and text[:4] not in years:
            years.append(text[:4])
    if not years:
        required_year_grade = _split_list(row.get("required_year_grade"))
        years.extend([year for year in required_year_grade if len(year) == 4 and year.isdigit()])
    return years or ["2026"]


def _empty_frame(columns: list[str]) -> pl.DataFrame:
    return pl.DataFrame(schema={column: pl.String for column in columns})


def load_semantic_artifacts(
    years: list[str],
    *,
    semantic_dqa_root: Path | None = None,
) -> SemanticArtifacts:
    root = semantic_dqa_root or DEFAULT_SEMANTIC_DQA_ROOT
    summary_frames: list[pl.DataFrame] = []
    bridge_frames: list[pl.DataFrame] = []
    loaded_years: list[str] = []
    missing_years: list[str] = []
    for year in years:
        year_dir = root / "semantic" / f"year={year}"
        summary_path = year_dir / "semantic_yearly_summary.parquet"
        bridge_path = year_dir / "semantic_admissibility_bridge.parquet"
        year_loaded = False
        if summary_path.exists():
            summary_frames.append(pl.read_parquet(summary_path))
            year_loaded = True
        if bridge_path.exists():
            bridge_frames.append(pl.read_parquet(bridge_path))
            year_loaded = True
        if year_loaded:
            loaded_years.append(year)
        else:
            missing_years.append(year)
    yearly_summary = pl.concat(summary_frames, how="diagonal_relaxed") if summary_frames else _empty_frame([
        "year",
        "semantic_area",
        "status",
        "confidence",
        "blocking_level",
        "summary",
        "admissibility_impact",
    ])
    bridge = pl.concat(bridge_frames, how="diagonal_relaxed") if bridge_frames else _empty_frame([
        "year",
        "semantic_area",
        "research_module",
        "semantic_status",
        "blocking_level",
        "admissibility_impact",
        "final_research_status",
        "reason",
        "notes",
    ])
    return SemanticArtifacts(
        source_root=root,
        loaded_years=loaded_years,
        missing_years=missing_years,
        yearly_summary=yearly_summary,
        bridge=bridge,
    )


def infer_research_modules(
    row: dict[str, Any],
    *,
    factor_profile: dict[str, Any] | None = None,
    family_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    factor_profile = factor_profile or {}
    family_profile = family_profile or {}
    explicit_modules: list[str] = []
    for key in (
        "semantic_required_modules",
        "semantic_blocked_modules",
        "semantic_modules",
    ):
        explicit_modules.extend(_split_list(factor_profile.get(key)))
        explicit_modules.extend(_split_list(family_profile.get(key)))
    explicit_modules = [module for module in explicit_modules if module in KNOWN_MODULES]
    if explicit_modules:
        return {
            "modules": sorted(dict.fromkeys(explicit_modules)),
            "mapping_source": "explicit_metadata",
            "unresolved": False,
            "reason": "metadata-provided semantic modules",
        }

    forbidden = []
    forbidden.extend(_split_list(row.get("forbidden_semantic_assumptions")))
    forbidden.extend(_split_list(factor_profile.get("forbidden_semantic_assumptions")))
    forbidden.extend(_split_list(family_profile.get("forbidden_semantic_assumptions")))
    forbidden_modules = [item for item in forbidden if item in KNOWN_MODULES]
    if forbidden_modules:
        return {
            "modules": sorted(dict.fromkeys(forbidden_modules)),
            "mapping_source": "forbidden_semantic_assumptions",
            "unresolved": False,
            "reason": "mapped from forbidden semantic assumptions",
        }

    text_parts = [
        str(row.get("factor_name", "")),
        str(row.get("module_name", "")),
        str(row.get("factor_family", "")),
        str(row.get("family_name", "")),
        str(row.get("mechanism", "")),
        str(factor_profile.get("mechanism_hypothesis", "")),
        str(family_profile.get("mechanism_hypothesis", "")),
    ]
    joined = " ".join(text_parts).lower()
    heuristic_modules: list[str] = []
    for token, modules in TEXT_HEURISTIC_MAP.items():
        if token in joined:
            heuristic_modules.extend(modules)
    if heuristic_modules:
        return {
            "modules": sorted(dict.fromkeys(heuristic_modules)),
            "mapping_source": "text_heuristic",
            "unresolved": False,
            "reason": "mapped from factor/family text heuristics",
        }

    return {
        "modules": [],
        "mapping_source": "unresolved",
        "unresolved": True,
        "reason": "no stable semantic module mapping found",
    }


def _normalize_bridge_status(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text in {"allow", STATUS_ALLOW}:
        return STATUS_ALLOW
    if text == "allow_with_caveat":
        return STATUS_CAVEAT
    if text == "block":
        return STATUS_BLOCKED
    if text == "requires_manual_review":
        return STATUS_MANUAL_REVIEW
    if text == "requires_session_split":
        return STATUS_SESSION_SPLIT
    if text in STATUS_PRIORITY:
        return text
    return None


def _select_worst_status(statuses: list[str]) -> str:
    if not statuses:
        return STATUS_UNRESOLVED
    return max(statuses, key=lambda item: STATUS_PRIORITY.get(item, -1))


def evaluate_semantic_gate(
    row: dict[str, Any],
    *,
    factor_profile: dict[str, Any] | None = None,
    family_profile: dict[str, Any] | None = None,
    semantic_dqa_root: Path | None = None,
) -> dict[str, Any]:
    years = infer_row_years(row)
    artifacts = load_semantic_artifacts(years, semantic_dqa_root=semantic_dqa_root)
    mapping = infer_research_modules(row, factor_profile=factor_profile, family_profile=family_profile)
    base_payload = {
        "semantic_gate_source_loaded": artifacts.source_loaded,
        "semantic_gate_source_root": str(artifacts.source_root),
        "semantic_gate_loaded_years": list(artifacts.loaded_years),
        "semantic_gate_missing_years": list(artifacts.missing_years),
        "semantic_gate_mapping_source": mapping["mapping_source"],
        "semantic_gate_modules": list(mapping["modules"]),
        "semantic_gate_unresolved_mapping": bool(mapping["unresolved"]),
    }
    if not artifacts.source_loaded:
        return base_payload | {
            "semantic_gate_status": STATUS_NOT_LOADED,
            "semantic_gate_reason": f"semantic artifacts not found under {artifacts.source_root}",
            "semantic_gate_matched_modules": [],
            "semantic_supported_modules": [],
            "semantic_blocked_modules": [],
            "semantic_blocking_areas": [],
            "semantic_requires_manual_review": True,
            "semantic_requires_session_split": False,
            "semantic_gate_bridge_matches": 0,
        }
    if mapping["unresolved"]:
        return base_payload | {
            "semantic_gate_status": STATUS_UNRESOLVED,
            "semantic_gate_reason": mapping["reason"],
            "semantic_gate_matched_modules": [],
            "semantic_supported_modules": [],
            "semantic_blocked_modules": [],
            "semantic_blocking_areas": [],
            "semantic_requires_manual_review": True,
            "semantic_requires_session_split": False,
            "semantic_gate_bridge_matches": 0,
        }

    bridge = artifacts.bridge
    if "research_module" not in bridge.columns:
        return base_payload | {
            "semantic_gate_status": STATUS_NOT_LOADED,
            "semantic_gate_reason": "semantic bridge artifact is missing research_module column",
            "semantic_gate_matched_modules": [],
            "semantic_supported_modules": [],
            "semantic_blocked_modules": [],
            "semantic_blocking_areas": [],
            "semantic_requires_manual_review": True,
            "semantic_requires_session_split": False,
            "semantic_gate_bridge_matches": 0,
        }

    matched = bridge.filter(pl.col("research_module").cast(pl.Utf8).is_in(mapping["modules"]))
    if matched.height == 0:
        return base_payload | {
            "semantic_gate_status": STATUS_UNRESOLVED,
            "semantic_gate_reason": "no upstream semantic bridge rows matched the inferred modules",
            "semantic_gate_matched_modules": [],
            "semantic_supported_modules": [],
            "semantic_blocked_modules": [],
            "semantic_blocking_areas": [],
            "semantic_requires_manual_review": True,
            "semantic_requires_session_split": False,
            "semantic_gate_bridge_matches": 0,
        }

    statuses = []
    for item in matched.to_dicts():
        normalized = _normalize_bridge_status(item.get("final_research_status"))
        if normalized is None:
            normalized = _normalize_bridge_status(item.get("admissibility_impact"))
        if normalized is not None:
            statuses.append(normalized)
    final_status = _select_worst_status(statuses)
    matched_rows = matched.to_dicts()
    blocking_areas = sorted({str(item.get("semantic_area", "")) for item in matched_rows if str(item.get("semantic_area", ""))})
    blocked_modules = sorted({str(item.get("research_module", "")) for item in matched_rows if _normalize_bridge_status(item.get("final_research_status")) == STATUS_BLOCKED or _normalize_bridge_status(item.get("admissibility_impact")) == STATUS_BLOCKED})
    supported_modules = sorted({str(item.get("research_module", "")) for item in matched_rows if str(item.get("research_module", "")) and str(item.get("research_module", "")) not in blocked_modules})
    reasons = [str(item.get("reason", "")).strip() for item in matched_rows if str(item.get("reason", "")).strip()]
    return base_payload | {
        "semantic_gate_status": final_status,
        "semantic_gate_reason": reasons[0] if reasons else mapping["reason"],
        "semantic_gate_matched_modules": sorted({str(item.get("research_module", "")) for item in matched_rows if str(item.get("research_module", ""))}),
        "semantic_supported_modules": supported_modules,
        "semantic_blocked_modules": blocked_modules,
        "semantic_blocking_areas": blocking_areas,
        "semantic_requires_manual_review": final_status in {STATUS_MANUAL_REVIEW, STATUS_UNRESOLVED, STATUS_NOT_LOADED},
        "semantic_requires_session_split": final_status == STATUS_SESSION_SPLIT,
        "semantic_gate_bridge_matches": matched.height,
    }


def _ensure_log(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "scoreboard_id\tcreated_at\tfactor_name\tfamily_name\tsemantic_gate_status\tsemantic_gate_source_loaded\tsemantic_gate_mapping_source\tsemantic_gate_modules_json\tsemantic_supported_modules_json\tsemantic_blocked_modules_json\tsemantic_blocking_areas_json\tsemantic_gate_reason\tnotes\n",
        encoding="utf-8",
    )


def append_semantic_gate_log(
    *,
    scoreboard_id: str,
    factor_name: str,
    family_name: str,
    gate_payload: dict[str, Any],
    notes: str,
    path: Path | None = None,
) -> None:
    path = path or SEMANTIC_GATE_LOG
    _ensure_log(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                scoreboard_id,
                datetime.now(timezone.utc).isoformat(),
                factor_name,
                family_name,
                gate_payload.get("semantic_gate_status", ""),
                gate_payload.get("semantic_gate_source_loaded", False),
                gate_payload.get("semantic_gate_mapping_source", ""),
                json.dumps(gate_payload.get("semantic_gate_modules", []), ensure_ascii=False),
                json.dumps(gate_payload.get("semantic_supported_modules", []), ensure_ascii=False),
                json.dumps(gate_payload.get("semantic_blocked_modules", []), ensure_ascii=False),
                json.dumps(gate_payload.get("semantic_blocking_areas", []), ensure_ascii=False),
                gate_payload.get("semantic_gate_reason", ""),
                notes,
            ]
        )
