# Universe Rules

Phase A uses a conservative consumer universe, not a new upstream data contract.

Default universe:
- `phase_a_core` = rows and securities that can be studied from upstream
  `verified_orders` and `verified_trades` admit-now structural columns plus a
  declared year scope

Rules:
- every card must declare `years` and `universe`
- factor cards may not define universe membership from `TradeDir`, `BrokerNo`,
  `Level`, `VolumePre`, `Type`, `Ext`, or linkage sidecars kept out of verified
  v1
- factor code may filter on transparent structural fields only after the card
  says so
- this repo does not change corporate-action, liquidity, or tradability
  definitions owned by upstream or fixed evaluator layers
- any future narrower trading universe must be added as a named config, not
  inferred ad hoc in factor code
