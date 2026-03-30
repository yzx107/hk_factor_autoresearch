"""Generate repetitive Gate A factor candidates from structured specs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SPECS_ROOT = ROOT / "factor_specs"
FACTOR_DEFS_ROOT = ROOT / "factor_defs"
CARDS_ROOT = ROOT / "research_cards" / "examples"

SUPPORT_MODULES = {
    "order_trade_interaction": {
        "module": "factor_defs.order_trade_interaction_support",
        "tables_symbol": "DAILY_AGG_TABLES",
        "loader_symbol": "build_interaction_daily_from_cache_loader",
        "input_tables": ["verified_trades", "verified_orders"],
        "input_table": "verified_trades",
    }
}


@dataclass(frozen=True)
class PrototypeSpec:
    slug: str
    display_name: str
    mechanism: str
    hypothesis: str
    why_incremental: str
    expected_regime: str
    expected_winning_regimes: tuple[str, ...]
    expected_failure_regimes: tuple[str, ...]
    baseline_refs: tuple[str, ...]
    observable_proxies: tuple[str, ...]
    required_fields: tuple[str, ...]
    input_dependencies: tuple[str, ...]
    failure_modes: tuple[str, ...]
    expected_risks: tuple[str, ...]
    level_expression: str


@dataclass(frozen=True)
class BatchSpec:
    version: str
    family: str
    support: str
    owner: str
    universe: str
    years: tuple[str, ...]
    holding_horizon: str
    horizon_scope: str
    promotion_target: str
    research_modules: tuple[str, ...]
    forbidden_semantic_assumptions: tuple[str, ...]
    prototypes: tuple[PrototypeSpec, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Gate A factor candidates from factor_specs TOML.")
    parser.add_argument("--spec", required=True, help="Path under factor_specs/ or absolute path.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    return parser.parse_args()


def _resolve_spec_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / value if value.startswith("factor_specs/") else SPECS_ROOT / value


def load_batch_spec(path: Path) -> BatchSpec:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    prototypes = tuple(
        PrototypeSpec(
            slug=str(item["slug"]),
            display_name=str(item["display_name"]),
            mechanism=str(item["mechanism"]),
            hypothesis=str(item["hypothesis"]),
            why_incremental=str(item["why_incremental"]),
            expected_regime=str(item["expected_regime"]),
            expected_winning_regimes=tuple(str(value) for value in item["expected_winning_regimes"]),
            expected_failure_regimes=tuple(str(value) for value in item["expected_failure_regimes"]),
            baseline_refs=tuple(str(value) for value in item["baseline_refs"]),
            observable_proxies=tuple(str(value) for value in item["observable_proxies"]),
            required_fields=tuple(str(value) for value in item["required_fields"]),
            input_dependencies=tuple(str(value) for value in item["input_dependencies"]),
            failure_modes=tuple(str(value) for value in item["failure_modes"]),
            expected_risks=tuple(str(value) for value in item["expected_risks"]),
            level_expression=str(item["level_expression"]),
        )
        for item in raw["prototypes"]
    )
    return BatchSpec(
        version=str(raw["version"]),
        family=str(raw["family"]),
        support=str(raw["support"]),
        owner=str(raw["owner"]),
        universe=str(raw["universe"]),
        years=tuple(str(value) for value in raw["years"]),
        holding_horizon=str(raw["holding_horizon"]),
        horizon_scope=str(raw["horizon_scope"]),
        promotion_target=str(raw["promotion_target"]),
        research_modules=tuple(str(value) for value in raw["research_modules"]),
        forbidden_semantic_assumptions=tuple(str(value) for value in raw["forbidden_semantic_assumptions"]),
        prototypes=prototypes,
    )


def _python_list(values: tuple[str, ...] | list[str]) -> str:
    return "[" + ", ".join(repr(value) for value in values) + "]"


def _render_level_module(spec: BatchSpec, prototype: PrototypeSpec) -> str:
    support = SUPPORT_MODULES[spec.support]
    factor_name = prototype.slug
    factor_id = f"{factor_name}_v1"
    output_column = f"{factor_name}_score"
    return f'''"""Auto-generated Gate A factor from factor_specs."""

from __future__ import annotations

import polars as pl

from factor_defs.change_support import build_change_signal
from {support["module"]} import {support["tables_symbol"]}, {support["loader_symbol"]}

FACTOR_ID = "{factor_id}"
FACTOR_FAMILY = "{spec.family}"
MECHANISM = {prototype.mechanism!r}
INPUT_DEPENDENCIES = {_python_list(prototype.input_dependencies)}
RESEARCH_UNIT = "date_x_instrument_key"
HORIZON_SCOPE = "{spec.horizon_scope}"
VERSION = "v1"
TRANSFORM_CHAIN = ["level", "one_day_difference"]
EXPECTED_REGIME = {prototype.expected_regime!r}
FORBIDDEN_SEMANTIC_ASSUMPTIONS = {_python_list(spec.forbidden_semantic_assumptions)}

INPUT_TABLE = "{support["input_table"]}"
INPUT_TABLES = {_python_list(support["input_tables"])}
OUTPUT_COLUMN = "{output_column}"
SUPPORTED_TRANSFORMS = ["level", "one_day_difference"]
LOOKBACK_STEPS = 1


def _level_frame(daily: pl.LazyFrame) -> pl.LazyFrame:
    return daily.with_columns(
        ({prototype.level_expression}).alias("{prototype.slug}_level")
    )


def compute_signal(
    daily: pl.LazyFrame,
    *,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
    transform: str = "level",
) -> pl.LazyFrame:
    if transform == "level":
        return (
            _level_frame(daily)
            .with_columns(pl.col("{prototype.slug}_level").alias(OUTPUT_COLUMN))
            .sort(["date", OUTPUT_COLUMN], descending=[False, True])
        )
    if transform == "one_day_difference":
        return build_change_signal(
            _level_frame(daily),
            base_score_column="{prototype.slug}_level",
            output_column=OUTPUT_COLUMN,
            target_dates=target_dates,
            previous_date_map=previous_date_map,
        )
    raise ValueError(f"Unsupported transform `{{transform}}` for {factor_id}.")


def compute_signal_from_cache_loader(
    *,
    cache_loader,
    target_dates: list[str] | None = None,
    previous_date_map: dict[str, str] | None = None,
    transform: str = "level",
) -> pl.LazyFrame:
    target_dates = list(target_dates or [])
    previous_date_map = dict(previous_date_map or {{}})
    context_dates = (
        target_dates
        if transform == "level"
        else sorted(set(target_dates) | set(previous_date_map.values()))
    )
    daily = {support["loader_symbol"]}(cache_loader=cache_loader, dates=context_dates)
    return compute_signal(
        daily,
        target_dates=target_dates,
        previous_date_map=previous_date_map,
        transform=transform,
    )
'''


def _render_card(spec: BatchSpec, prototype: PrototypeSpec) -> str:
    slug = prototype.slug
    display_name = prototype.display_name
    card_id = f"rc_20260330_{slug}_2026"
    title = f"{display_name}（{slug.replace('_', ' ').title()} 2026）"
    hypothesis = prototype.hypothesis
    mechanism = prototype.mechanism
    why_incremental = (
        prototype.why_incremental
        + " 这个 prototype 默认同时支持 `level` 和 `one_day_difference` 两种 transform。"
    )
    baseline_refs = list(prototype.baseline_refs)
    required_fields = _python_list(prototype.required_fields)
    observable_proxies = _python_list(prototype.observable_proxies)
    baseline_refs_text = _python_list(tuple(baseline_refs))
    research_modules = _python_list(spec.research_modules)
    years = _python_list(spec.years)
    failure_modes = _python_list(prototype.failure_modes)
    expected_risks = _python_list(prototype.expected_risks)
    semantics = """[semantics]
TradeDir = "unused"
BrokerNo = "unused"
OrderType = "unused"
Level = "unused"
VolumePre = "unused"
Type = "unused"
Ext = "unused"
"""
    winning = "、".join(prototype.expected_winning_regimes)
    failing = "、".join(prototype.expected_failure_regimes)
    forbidden = "、".join(spec.forbidden_semantic_assumptions)
    return f'''+++
card_id = "{card_id}"
name = "{title}"
owner = "{spec.owner}"
status = "draft"
factor_family = "{spec.family}"
years = {years}
universe = "{spec.universe}"
holding_horizon = "{spec.holding_horizon}"
research_modules = {research_modules}
required_fields = {required_fields}
horizon_scope = "{spec.horizon_scope}"
hypothesis = {hypothesis!r}
mechanism = {mechanism!r}
info_boundary = "只使用 verified_trades_daily 与 verified_orders_daily 的安全 daily agg；不使用任何 caveat-only 字段。"
observable_proxies = {observable_proxies}
baseline_refs = {baseline_refs_text}
promotion_target = "{spec.promotion_target}"
failure_modes = {failure_modes}
expected_risks = {expected_risks}

[timing]
mode = "coarse_only"
uses_precise_lag = false
uses_strict_ordering = false
uses_queue_semantics = false

{semantics}+++

## Hypothesis

{hypothesis}

## Mechanism

{mechanism}

## Observable Proxies

{", ".join(prototype.observable_proxies)}

## Holding Horizon

{spec.holding_horizon}

## Required Fields

{", ".join(prototype.required_fields)}

## Info Boundary

只使用 `phase_a_core` 的日级安全缓存，不使用任何 caveat-only 字段。

## Failure Modes

{" ".join(prototype.failure_modes)}

## Expected Winning Regimes

{winning}

## Expected Failure Regimes

{failing}

## Why Incremental vs Baselines

{why_incremental}

## Forbidden Semantic Assumptions

{forbidden}

## Promotion Target

{spec.promotion_target}

## Transform Variants

这个 prototype 统一使用同一张 research card，但允许在 harness 配置里声明：
- `transform = "level"`
- `transform = "one_day_difference"`

## Expected Risks

{" ".join(prototype.expected_risks)}
'''


def _write_text(path: Path, text: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file without --overwrite: {path}")
    path.write_text(text, encoding="utf-8")


def generate_from_spec(spec: BatchSpec, *, overwrite: bool = False) -> list[Path]:
    generated: list[Path] = []
    for prototype in spec.prototypes:
        level_module = FACTOR_DEFS_ROOT / f"{prototype.slug}.py"
        level_card = CARDS_ROOT / f"{prototype.slug}_2026.md"

        _write_text(level_module, _render_level_module(spec, prototype), overwrite)
        _write_text(level_card, _render_card(spec, prototype), overwrite)
        generated.extend([level_module, level_card])
    return generated


def main() -> int:
    args = parse_args()
    spec_path = _resolve_spec_path(args.spec)
    batch = load_batch_spec(spec_path)
    generated = generate_from_spec(batch, overwrite=args.overwrite)
    for path in generated:
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
