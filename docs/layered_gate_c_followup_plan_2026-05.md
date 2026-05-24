# Layered Gate C Follow-up Plan

This plan converts Gate C stress outcomes into research tasks. It is not a promotion list.

## Source

- followup_batch_id: `layered_followup_20260524T181428Z_layered_gate_c_20260524T180031Z_layer_board_20260524T172034Z`
- gate_c_id: `layered_gate_c_20260524T180031Z_layer_board_20260524T172034Z`
- board_id: `layer_board_20260524T172034Z`
- source_triage_id: `layered_gate_c_ext_20260524T175806Z_layer_board_20260524T172034Z`
- factor_count: `6`
- gate_c_summary_path: `runs/layered_gate_c_20260524T180031Z_layer_board_20260524T172034Z/layered_gate_c_summary.json`

## Lane Counts

- `southbound_split_retest`: 2
- `layer_explicit_rewrite`: 4

## Queue

| factor | Gate C decision | lane | target layers | target buckets | action | base cost-adj |
| --- | --- | --- | --- | --- | --- | ---: |
| `avg_trade_notional_bias` | `needs_southbound_split` / `inverse_candidate` | `southbound_split_retest` | `mid_liquid_tradable`, `small_illiquid_special` | `southbound_unknown` | `split_unknown_from_eligible_then_retest` | 0.005295 |
| `order_unique_trade_participation_gap` | `needs_southbound_split` / `as_is_candidate` | `southbound_split_retest` | `large_liquid_core`, `mid_liquid_tradable`, `small_illiquid_special` |  | `retest_southbound_buckets_before_promotion` | 0.005457 |
| `avg_trade_notional_bias_change` | `needs_layer_split` / `inverse_candidate` | `layer_explicit_rewrite` | `small_illiquid_special` | `southbound_unknown` | `rewrite_factor_as_layer_explicit_spec` | 0.003905 |
| `order_notional_vs_trade_notional_gap_change` | `needs_layer_split` / `as_is_candidate` | `layer_explicit_rewrite` | `small_illiquid_special` | `southbound_unknown` | `rewrite_factor_as_layer_explicit_spec` | 0.002958 |
| `order_trade_event_ratio` | `needs_layer_split` / `as_is_candidate` | `layer_explicit_rewrite` | `large_liquid_core` |  | `rewrite_factor_as_layer_explicit_spec` | 0.003869 |
| `order_trade_notional_ratio` | `needs_layer_split` / `as_is_candidate` | `layer_explicit_rewrite` | `small_illiquid_special` | `southbound_unknown` | `rewrite_factor_as_layer_explicit_spec` | 0.004197 |

## Guardrails

- `southbound_split_retest` must separate `southbound_eligible` from fail-closed unknown flow before promotion.
- `layer_explicit_rewrite` should become a layer-scoped factor spec, not a broad all-candidate factor.
- Small-illiquid targets remain capacity and slippage constrained until a later cost gate proves otherwise.
