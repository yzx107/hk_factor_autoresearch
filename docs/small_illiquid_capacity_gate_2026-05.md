# Small Illiquid Capacity Gate

Gate E tests whether Gate D research-only small/liquidity traces survive explicit capacity and slippage stress.

## Source

- capacity_gate_id: `small_illiquid_capacity_20260525T160853Z_layered_gate_d_20260525T153536Z_layered_gate_c_20260525T153513Z_layer_board_20260524T172034Z`
- gate_d_id: `layered_gate_d_20260525T153536Z_layered_gate_c_20260525T153513Z_layer_board_20260524T172034Z`
- factor_count: `4`
- pass_stress_bps: `50.0`
- pass_participation_rate: `0.01`
- min_gross_capacity_hkd: `5000000.0`

## Decision Counts

- `research_only_micro_capacity`: 4

## Capacity Board

| factor | decision | 50bps adj | 100bps adj | p25 cap @1% | median cap @1% | top contrib | selected turnover med |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `avg_trade_notional_bias` | `research_only_micro_capacity` | 0.006004 | 0.002652 | 25 | 72 | 0.023513 | 96,118 |
| `avg_trade_notional_bias_change` | `research_only_micro_capacity` | 0.004665 | 0.000847 | 14 | 42 | 0.063456 | 13,594 |
| `order_notional_vs_trade_notional_gap_change` | `research_only_micro_capacity` | 0.006322 | 0.002555 | 14 | 42 | 0.064177 | 11,344 |
| `order_trade_notional_ratio` | `research_only_micro_capacity` | 0.017700 | 0.013592 | 7 | 28 | 0.070589 | 9,518 |

## Interpretation

- `paper_trade_micro_watch` requires positive 50bps stress, acceptable concentration, and p25 gross capacity above the micro threshold at 1% participation.
- `research_only_micro_capacity` means the signal remains positive under stress but cannot support the configured micro capital threshold robustly.
- `reject_capacity` or `reject_concentration` should not move to paper trading.
