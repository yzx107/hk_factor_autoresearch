# Program

## Immutable Layer 0

These surfaces are frozen until explicit change control:
- `data_contracts/`
- `backtest_engine/`
- `evaluation/`
- `gatekeeper/`
- `configs/baseline_phase_a.toml`
- `registry/` schemas

Phase A boundary inherited from upstream `Hshare_Lab_v2`:
- `2025 = coarse_only`
- `2026 = fine_ok`, still field-semantic constrained
- `TradeDir`: `2025 = stable_code_structure_only`
- `TradeDir`: `2026 = candidate_directional_signal_only`
- `BrokerNo`: both years = `reference_lookup_only`
- `Level`, `VolumePre`, and queue semantics are blocked
- `Type`, `Ext`, and `OrderType` are caveat-only vendor codes, never default
  truth
- this repo consumes upstream verified and admissibility outputs read-only

## Agent May Change

- add or edit `research_cards/`
- add or edit `factor_defs/`, `transforms/`, and `combos/`
- add derived run configs under `configs/` without changing the frozen baseline
- append experiment rows and lineage entries

## Agent May Not Change

- anything inside `/Users/yxin/AI_Workstation/Hshare_Lab_v2`
- data contracts to fit a factor
- evaluator, metrics, or cost rules to rescue a weak result
- gate policy to waive blocked semantics
- experiment history by deleting failed attempts

## Promotion Discipline

1. Write a research card before implementation.
2. Run Gate A before any backtest claim.
3. `allow_with_caveat` stays manual-review gated.
4. Failed experiments remain in the registry.
5. Renaming the same idea does not reset lineage.
