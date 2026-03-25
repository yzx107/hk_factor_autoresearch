# Research Card Template

Use TOML front matter. Gate A reads only the front matter.

```toml
+++
card_id = "rc_YYYYMMDD_slug"
name = "Short factor name"
owner = "human_or_agent"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "5m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["Time", "Price", "Volume"]
hypothesis = "State the ex ante hypothesis."
mechanism = "State the market mechanism, not a post-hoc story."
info_boundary = "State exactly what upstream fields and caveats are used."
failure_modes = ["List structural ways this idea can fail."]
expected_risks = ["List style, liquidity, event, and semantic risks."]

[timing]
mode = "coarse_only"
uses_precise_lag = false
uses_strict_ordering = false
uses_queue_semantics = false

[semantics]
TradeDir = "unused"
BrokerNo = "unused"
OrderType = "unused"
Level = "unused"
VolumePre = "unused"
Type = "unused"
Ext = "unused"
+++
```

## Hypothesis

Write the short ex ante claim.

## Mechanism

Explain why the effect could exist in Hong Kong equities.

## Holding Horizon

Restate the intended holding period and why it matches the signal.

## Required Fields

List only raw upstream fields needed for this card.

## Info Boundary

State what is vendor-defined, caveated, or blocked.

## Failure Modes

List how the signal can break, leak, or collapse.

## Expected Risks

List turnover, event pollution, liquidity, style, and semantic risks.
