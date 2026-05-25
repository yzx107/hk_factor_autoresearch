# Source Gap Breaker Summary

This run tests whether the Southbound source gap was the reason Gate D could not
produce a tradable candidate.

## Source Contract

- Source: `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/References/normalized/hkex_southbound_seed.csv`
- Contract: complete Southbound eligible list, where absence means
  `southbound_not_eligible`.
- As-of date: `2026-05-22`
- Seed rows: `633`

## Layer Coverage

After rebuilding `cache/universe_layers/year=2026/universe_layers_2026.parquet`:

- `southbound_eligible`: 601
- `southbound_not_eligible`: 2092
- `southbound_unknown`: 0
- `southbound_eligible_unknown`: 0

The previous source gap is therefore closed for the current 2026 candidate
universe under this complete-list contract.

## Gate Results

- Gate C: 2 `needs_southbound_split`, 4 `needs_layer_split`, 0 broad advances.
- Follow-up queue: 2 `southbound_split_retest`, 4 `layer_explicit_rewrite`.
- Gate D: 4 `research_only_capacity_risk`, 2 `reject_gate_d`,
  0 `advance_paper_trade_watch`.
- Layered triage now compares `southbound_eligible` against known
  `southbound_not_eligible` as well as fail-closed `southbound_unknown`.
- Gate E capacity/slippage: 4 `research_only_micro_capacity`,
  0 `paper_trade_micro_watch`.

## Interpretation

The source gap was real, but closing it does not produce a tradable result.
Positive sample-out traces move from fail-closed `southbound_unknown` to known
`southbound_not_eligible`, mostly inside `small_illiquid_special` targets. This
is capacity and slippage constrained research evidence, not a paper-trade
candidate.

Do not mine broad all-candidate variants from this batch. The next useful work
is either a dedicated small-illiquid capacity/slippage harness, or a new factor
family focused on eligible and large-liquid flow where Gate D can actually
advance.

## Gate E Capacity Result

Gate E confirms the small-illiquid traces remain positive after 50bps and
100bps stress, but fail robust capacity. At 1% participation, p25 equal-weight
gross capacity is only HKD 7 to HKD 25 across the four surviving candidates.
That is not a tradable paper-watch result; it is micro-capacity research only.
