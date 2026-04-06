# Project Memory

## Current State

- Repository path: `/Users/yxin/AI_Workstation/hk_factor_autoresearch`
- Default branch/worktree state has been cleaned up to a single main worktree.
- Current branch is expected to be `main` unless a task explicitly creates a feature branch.
- Upstream `Hshare_Lab_v2` now explicitly treats instrument universe classification as a sidecar boundary, not as verified default fact truth.

## Recent Completed Work

- Phase 1 information-theory support is already merged into `main`.
- `pre-eval` now includes canonical mutual information outputs:
  - `aggregate_metrics.mi`
  - `aggregate_metrics.nmi`
  - `aggregate_metrics.rank_ic`
  - `aggregate_metrics.top_bottom_spread`
  - `aggregate_metrics.nmi_ic_gap`
  - `aggregate_metrics.mi_p_value`
  - `aggregate_metrics.mi_excess_over_null`
  - `aggregate_metrics.mi_significant_date_ratio`
- Per-date canonical fields are:
  - `per_date[*].mi`
  - `per_date[*].nmi`
  - `per_date[*].mi_p_value`
  - `per_date[*].mi_significant`
  - `per_date[*].nmi_ic_gap`
- Legacy aliases remain for compatibility:
  - `mean_mutual_info`
  - `mean_normalized_mutual_info`
  - `per_date[*].mutual_info`
  - `per_date[*].normalized_mutual_info`

## Regime Slicing Scope

- Current entropy diagnostics mean turnover distribution entropy only.
- `regime_slices.entropy_quantile` is based on `market_turnover_entropy`.
- This is descriptive regime labeling for research diagnostics, not a production predictive regime model.

## Explicitly Out Of Scope So Far

- No gate framework rewrite has been done.
- No hard filter based on NMI or entropy diagnostics has been added.
- No heavyweight new dependency was introduced for information-theory work.

## Current Transfer Entropy Scope

- Transfer entropy now exists as a separate exploratory utility:
  - `evaluation/transfer_entropy.py`
  - `harness/find_lead_factors.py`
- It is not part of the fixed Phase 1 pre-eval contract.
- It is not part of the default Gate B decision policy.
- Do not conflate it with `market_turnover_entropy` or `entropy_quantile`.

## Recommended Next Phase

- Improve Gate B / scoreboard consumers around the new MI reliability fields before tightening thresholds further.
- Treat transfer entropy as a separate Phase 2 track, not as an extension of the current Phase 1 pre-eval.

## Notes For New Codex Sessions

- Start by reading this file, then `README.md`, `harness/README.md`, and `gates/promotion_policy.md`.
- If the task talks about “stocks”, “equity universe”, or cross-sectional factor coverage, also read:
  - `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/instrument_universe_classification_boundary_2026-04-06.md`
- If continuing information-theory work, preserve the current boundary:
  - keep Shannon-entropy slicing wording narrow
  - state clearly that transfer entropy is exploratory and separate from fixed pre-eval
  - avoid folding TE into existing entropy diagnostics unless explicitly requested
- If writing or reviewing research cards, preserve the new universe wording boundary:
  - `phase_a_core` is a field-safety surface, not proof of a pure equity universe
  - research cards in this repo now require `instrument_universe = "stock_research_candidate"`
  - `stock_research_candidate` is a conservative stock research lane, not a fully verified common-equity set
