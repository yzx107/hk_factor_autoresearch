"""Frozen backtest interface for Phase A."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "baseline_phase_a.toml"


@dataclass(frozen=True)
class BaselineConfig:
    version: str
    years: tuple[str, ...]
    universe: str
    cost_model_version: str
    backtest_window: str
    evaluation_profile: str


def load_baseline_config(path: Path = DEFAULT_CONFIG_PATH) -> BaselineConfig:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return BaselineConfig(
        version=raw["version"],
        years=tuple(raw["years"]),
        universe=raw["universe"],
        cost_model_version=raw["cost_model_version"],
        backtest_window=raw["backtest_window"],
        evaluation_profile=raw["evaluation_profile"],
    )


@dataclass(frozen=True)
class FactorSubmission:
    factor_name: str
    research_card: str
    years: tuple[str, ...]
    timing_mode: str
    required_fields: tuple[str, ...]


class FixedBacktestEngine:
    """Factor code plugs into this interface; evaluator rules stay fixed."""

    def __init__(self, config: BaselineConfig | None = None) -> None:
        self.config = config or load_baseline_config()

    def validate_submission(self, submission: FactorSubmission) -> list[str]:
        errors: list[str] = []
        if not set(submission.years).issubset(set(self.config.years)):
            errors.append("Submission years fall outside the frozen baseline.")
        if submission.timing_mode not in {"coarse_only", "fine_ok"}:
            errors.append("Submission timing_mode is not recognized by the baseline.")
        return errors

    def run(self, submission: FactorSubmission) -> dict[str, str]:
        errors = self.validate_submission(submission)
        if errors:
            raise ValueError("; ".join(errors))
        raise NotImplementedError(
            "Phase A ships a fixed interface only. "
            "Backtest logic is intentionally not implemented here."
        )
