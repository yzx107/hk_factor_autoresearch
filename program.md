# Program

## Harness Law

This repo follows the `autoresearch` harness law:
- the experiment object may change
- the evaluation harness may not drift during ordinary research

In practice:
- humans evolve `program.md`
- agents work only inside the narrow mutable surface
- all experiments run through the same harness and append-only registry

## Immutable Layer 0

These surfaces are frozen until explicit change control:
- `data_contracts/`
- `backtest_engine/`
- `evaluation/`
- `gatekeeper/`
- `configs/baseline_phase_a.toml`
- `harness/`
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

Default narrow mutable surface for one experiment:
- one research card
- one factor definition or one small transform/combo change
- no harness edits in the same experiment branch

## Agent May Not Change

- anything inside `/Users/yxin/AI_Workstation/Hshare_Lab_v2`
- data contracts to fit a factor
- evaluator, metrics, or cost rules to rescue a weak result
- gate policy to waive blocked semantics
- experiment history by deleting failed attempts

## Promotion Discipline

1. Write a research card before implementation.
2. Run Gate A before any backtest claim.
3. Run the fixed pre-eval harness before ranking candidates.
4. `allow_with_caveat` stays manual-review gated.
5. Failed experiments remain in the registry.
6. Renaming the same idea does not reset lineage.

## Autoresearch Loop

1. Human updates `program.md` when the research policy changes.
2. Agent proposes one bounded experiment via a research card.
3. Agent edits only the narrow mutable surface for that experiment.
4. Agent runs the Phase A harness.
5. Agent runs the fixed pre-eval on any materialized factor output.
Pre-eval is allowed to use fixed non-linear metrics such as normalized mutual
information, but only under frozen binning and label rules.
6. Agent rebuilds comparison and scoreboard artifacts on the same frozen rules.
7. Agent runs the fixed autoresearch cycle over the configured inventory.
8. Harness records `pass`, `allow_with_caveat`, or `fail`.
9. `fail` means discard the candidate revision.
10. `allow_with_caveat` means manual review, not auto-promotion.
11. `pass` means the idea may proceed to the next controlled stage.

## Token Discipline

To reduce token burn:
- read only `program.md`, the baseline config, the active card, and the last few
  registry rows before acting
- prefer card front matter and compact machine-readable output over long prose
- send long command output to `runs/` artifacts instead of pasting it back into
  chat
- use the harness runner's compact summary as the default status report
