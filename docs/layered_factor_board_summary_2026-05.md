# Layered Factor Board Summary 2026-05

This summary converts the current layered factor board into research decisions. It is not a production promotion list.

## Source

- board_id: `layer_board_20260524T172034Z`
- layered_board_path: `runs/layer_board_20260524T172034Z/layered_factor_board.json`
- triage_id: `layered_triage_20260524T173138Z_layer_board_20260524T172034Z`
- factor_count: `18`
- southbound_split_threshold_abs_rank_ic: `0.04`

## Decision Counts

- `promote_broad_candidate`: 6
- `research_new_listing_family`: 8
- `risk_only_small_illiquid`: 4

## Decision Board

| factor | decision | secondary | lane | class | strongest | max_abs_ic | dispersion | sb_gap |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: |
| `avg_trade_notional_bias` | `promote_broad_candidate` |  | `large_southbound_research` | `broad_candidate` | small_illiquid_special | 0.0536 | 0.0307 | 0.0331 |
| `avg_trade_notional_bias_change` | `promote_broad_candidate` |  | `large_southbound_research` | `broad_candidate` | new_or_recent_listing | 0.0876 | 0.0705 | 0.0074 |
| `order_notional_vs_trade_notional_gap_change` | `promote_broad_candidate` |  | `large_southbound_research` | `broad_candidate` | large_liquid_core | 0.0735 | 0.0530 | 0.0063 |
| `order_trade_event_ratio` | `promote_broad_candidate` |  | `large_southbound_research` | `broad_candidate` | new_or_recent_listing | 0.0721 | 0.0165 | 0.0111 |
| `order_trade_notional_ratio` | `promote_broad_candidate` |  | `large_southbound_research` | `broad_candidate` | new_or_recent_listing | 0.1150 | 0.0795 | 0.0313 |
| `order_unique_trade_participation_gap` | `promote_broad_candidate` |  | `large_southbound_research` | `broad_candidate` | new_or_recent_listing | 0.0821 | 0.0318 | 0.0095 |
| `order_lifecycle_churn` | `research_new_listing_family` | `needs_southbound_split` | `new_listing_research` | `new_listing_dominant_watch` | new_or_recent_listing | 0.1648 | 0.1276 | 0.0469 |
| `order_lifecycle_churn_change` | `research_new_listing_family` | `needs_southbound_split` | `new_listing_research` | `new_listing_dominant_watch` | new_or_recent_listing | 0.1720 | 0.1614 | 0.0447 |
| `order_notional_vs_trade_notional_gap` | `research_new_listing_family` |  | `new_listing_research` | `new_listing_dominant_watch` | new_or_recent_listing | 0.1505 | 0.1140 | 0.0296 |
| `order_trade_event_ratio_change` | `research_new_listing_family` |  | `new_listing_research` | `new_listing_dominant_watch` | new_or_recent_listing | 0.1874 | 0.1563 | 0.0041 |
| `order_trade_notional_ratio_change` | `research_new_listing_family` |  | `new_listing_research` | `new_listing_dominant_watch` | new_or_recent_listing | 0.1324 | 0.1062 | 0.0038 |
| `order_unique_trade_participation_gap_change` | `research_new_listing_family` |  | `new_listing_research` | `new_listing_dominant_watch` | new_or_recent_listing | 0.1994 | 0.1673 | 0.0024 |
| `structural_activity_change` | `research_new_listing_family` | `needs_southbound_split` | `new_listing_research` | `new_listing_dominant_watch` | new_or_recent_listing | 0.2257 | 0.2114 | 0.0527 |
| `structural_activity_proxy` | `research_new_listing_family` | `needs_southbound_split` | `new_listing_research` | `new_listing_dominant_watch` | new_or_recent_listing | 0.1528 | 0.1103 | 0.0560 |
| `close_vwap_churn_interaction` | `risk_only_small_illiquid` | `needs_southbound_split` | `small_illiquid_risk` | `small_illiquid_dominant_risk` | small_illiquid_special | 0.2700 | 0.2391 | 0.1160 |
| `close_vwap_churn_interaction_change` | `risk_only_small_illiquid` | `needs_southbound_split` | `small_illiquid_risk` | `small_illiquid_dominant_risk` | small_illiquid_special | 0.1423 | 0.0903 | 0.0547 |
| `close_vwap_gap_intensity` | `risk_only_small_illiquid` | `needs_southbound_split` | `small_illiquid_risk` | `small_illiquid_dominant_risk` | small_illiquid_special | 0.2695 | 0.2522 | 0.1128 |
| `close_vwap_gap_intensity_change` | `risk_only_small_illiquid` | `needs_southbound_split` | `small_illiquid_risk` | `small_illiquid_dominant_risk` | small_illiquid_special | 0.1412 | 0.0925 | 0.0548 |

## Next Factor Spec Lanes

- `new_listing_research` count=`8`: Listing-age, seasoning, first-year liquidity, and order-lifecycle variants. Factors: `order_lifecycle_churn`, `order_lifecycle_churn_change`, `order_notional_vs_trade_notional_gap`, `order_trade_event_ratio_change`, `order_trade_notional_ratio_change`, `order_unique_trade_participation_gap_change`, `structural_activity_change`, `structural_activity_proxy`.
- `small_illiquid_risk` count=`4`: Risk-only close pressure, churn, capacity, and slippage diagnostics. Factors: `close_vwap_churn_interaction`, `close_vwap_churn_interaction_change`, `close_vwap_gap_intensity`, `close_vwap_gap_intensity_change`.
- `large_southbound_research` count=`6`: Large-liquid and Stock Connect split variants with cost and sample-out gates. Factors: `avg_trade_notional_bias`, `avg_trade_notional_bias_change`, `order_notional_vs_trade_notional_gap_change`, `order_trade_event_ratio`, `order_trade_notional_ratio`, `order_unique_trade_participation_gap`.

## Guardrails

- `risk_only_small_illiquid` is not promotable without explicit capacity and slippage stress.
- `research_new_listing_family` stays separate from mature-listing selection.
- `needs_southbound_split` must be resolved before broad promotion.
