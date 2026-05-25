# Layered Gate D

Gate D is a research tradability screen. It is not a production approval.

## Source

- gate_d_id: `layered_gate_d_20260525T153536Z_layered_gate_c_20260525T153513Z_layer_board_20260524T172034Z`
- gate_c_id: `layered_gate_c_20260525T153513Z_layer_board_20260524T172034Z`
- followup_batch_id: `layered_followup_20260525T153531Z_layered_gate_c_20260525T153513Z_layer_board_20260524T172034Z`
- factor_count: `6`
- cost_bps: `25.0`
- sample_out_fraction: `0.33`
- min_sample_out_dates: `8`

## Decision Counts

- `research_only_capacity_risk`: 4
- `reject_gate_d`: 2

## Gate D Board

| factor | decision | lane | target | sample-out cost-adj | hit | turnover | stability | dates |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `avg_trade_notional_bias` | `research_only_capacity_risk` | `southbound_split_retest` | `mid_liquid_tradable,small_illiquid_special` / `southbound_not_eligible` | 0.007680 | 0.687500 | 0.670431 | 0.687500 | 16 |
| `avg_trade_notional_bias_change` | `research_only_capacity_risk` | `layer_explicit_rewrite` | `small_illiquid_special` / `southbound_not_eligible` | 0.006574 | 0.687500 | 0.763593 | 0.687500 | 16 |
| `order_notional_vs_trade_notional_gap_change` | `research_only_capacity_risk` | `layer_explicit_rewrite` | `small_illiquid_special` / `southbound_not_eligible` | 0.008205 | 0.625000 | 0.753356 | 0.625000 | 16 |
| `order_trade_notional_ratio` | `research_only_capacity_risk` | `layer_explicit_rewrite` | `small_illiquid_special` / `southbound_not_eligible` | 0.019755 | 0.750000 | 0.821692 | 0.750000 | 16 |
| `order_trade_event_ratio` | `reject_gate_d` | `layer_explicit_rewrite` | `large_liquid_core` / `*` | -0.002126 | 0.562500 | 0.561046 | 0.562500 | 16 |
| `order_unique_trade_participation_gap` | `reject_gate_d` | `southbound_split_retest` | `large_liquid_core,mid_liquid_tradable,small_illiquid_special` / `*` | 0.007100 | 0.750000 | 0.696370 | 0.750000 | 16 |

## Interpretation

- `advance_paper_trade_watch` requires sample-out cost, hit-rate, turnover, and stability to pass.
- `research_only_capacity_risk` passed sample-out but is small-illiquid constrained.
- `research_only_source_gap` passed only in fail-closed Southbound unknown flow.
- `reject_gate_d` means do not spend new factor-mining budget on that route now.
