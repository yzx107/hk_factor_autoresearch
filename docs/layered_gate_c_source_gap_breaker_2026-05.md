# Layered Gate C

- gate_c_id: `layered_gate_c_20260525T153513Z_layer_board_20260524T172034Z`
- board_id: `layer_board_20260524T172034Z`
- source_triage_id: `layered_gate_c_ext_20260524T175806Z_layer_board_20260524T172034Z`
- factor_count: `6`
- cost_bps: `15.0`

## Decision Counts

- `needs_southbound_split`: 2
- `needs_layer_split`: 4

## Gate C Board

| factor | decision | cost_adj | hit | turnover | stability | primary_pass | southbound_pass | time_pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `avg_trade_notional_bias` | `needs_southbound_split` / `inverse_candidate` | 0.005295 | 0.7059 | 0.5949 | 0.7059 | 2 | 1 | 2 |
| `order_unique_trade_participation_gap` | `needs_southbound_split` / `as_is_candidate` | 0.005457 | 0.6275 | 0.7158 | 0.6275 | 3 | 0 | 2 |
| `avg_trade_notional_bias_change` | `needs_layer_split` / `inverse_candidate` | 0.003905 | 0.6863 | 0.7155 | 0.6863 | 1 | 1 | 2 |
| `order_notional_vs_trade_notional_gap_change` | `needs_layer_split` / `as_is_candidate` | 0.002958 | 0.6275 | 0.7049 | 0.6275 | 1 | 1 | 2 |
| `order_trade_event_ratio` | `needs_layer_split` / `as_is_candidate` | 0.003869 | 0.6275 | 0.7277 | 0.6275 | 1 | 0 | 2 |
| `order_trade_notional_ratio` | `needs_layer_split` / `as_is_candidate` | 0.004197 | 0.6667 | 0.7549 | 0.6667 | 1 | 1 | 2 |

## Interpretation

- `advance_gate_d_watch` still means research watchlist, not production approval.
- Direction is selected by cost-adjusted spread across as-is versus inverse candidates.
- `hold_cost_capacity` failed the full-sample cost, turnover, hit-rate, or stability stress.
- `hold_time_instability` failed or lacked enough early/late time-slice evidence.
- `needs_layer_split` passed the base stress but not enough primary tradability buckets.
- `needs_southbound_split` means Stock Connect buckets diverged under cost stress.
