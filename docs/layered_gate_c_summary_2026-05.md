# Layered Gate C

- gate_c_id: `layered_gate_c_20260524T174138Z_layer_board_20260524T172034Z`
- board_id: `layer_board_20260524T172034Z`
- source_triage_id: `layered_triage_20260524T173138Z_layer_board_20260524T172034Z`
- factor_count: `6`
- cost_bps: `15.0`

## Decision Counts

- `hold_time_instability`: 5
- `hold_cost_capacity`: 1

## Gate C Board

| factor | decision | cost_adj | hit | turnover | stability | primary_pass | southbound_pass | time_pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `avg_trade_notional_bias` | `hold_time_instability` / `inverse_candidate` | 0.001953 | 0.6667 | 0.4653 | 0.6667 | 2 | 1 | 0 |
| `avg_trade_notional_bias_change` | `hold_time_instability` / `inverse_candidate` | 0.001605 | 0.6667 | 0.5676 | 0.6667 | 1 | 1 | 0 |
| `order_trade_event_ratio` | `hold_time_instability` / `inverse_candidate` | 0.005793 | 1.0000 | 0.5600 | 1.0000 | 2 | 2 | 0 |
| `order_trade_notional_ratio` | `hold_time_instability` / `inverse_candidate` | 0.004487 | 0.6667 | 0.5679 | 0.6667 | 2 | 0 | 0 |
| `order_unique_trade_participation_gap` | `hold_time_instability` / `inverse_candidate` | 0.007262 | 1.0000 | 0.5522 | 1.0000 | 2 | 2 | 0 |
| `order_notional_vs_trade_notional_gap_change` | `hold_cost_capacity` / `inverse_candidate` | 0.000269 | 0.3333 | 0.5638 | 0.6667 | 2 | 1 | 0 |

## Interpretation

- `advance_gate_d_watch` still means research watchlist, not production approval.
- Direction is selected by cost-adjusted spread across as-is versus inverse candidates.
- `hold_cost_capacity` failed the full-sample cost, turnover, hit-rate, or stability stress.
- `hold_time_instability` failed or lacked enough early/late time-slice evidence.
- `needs_layer_split` passed the base stress but not enough primary tradability buckets.
- `needs_southbound_split` means Stock Connect buckets diverged under cost stress.
