+++
card_id = "rc_20260329_avg_trade_notional_bias_2026"
name = "Average Trade Notional Bias 2026"
owner = "codex"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["date", "source_file", "Price", "Volume"]
hypothesis = "Instruments with unusually large average trade notional may proxy for concentrated participation and temporary information pressure."
mechanism = "Average notional per print separates concentrated block-like activity from fragmented small-ticket trading without relying on blocked semantics."
info_boundary = "Uses only verified structural trade fields plus a file-derived instrument key extracted from source_file."
failure_modes = ["Signal is only a price-level proxy.", "Effect is dominated by illiquid names.", "Single event bursts do not generalize."]
expected_risks = ["Cross-sectional price bias.", "Liquidity overlap.", "Event contamination."]

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

## Hypothesis

Large average trade notional may signal concentrated demand for immediacy or
attention.

## Mechanism

The factor stays inside verified structural trades and avoids any directional or
broker semantics.

## Holding Horizon

Thirty minutes to one day.

## Required Fields

`date`, `source_file`, `Price`, `Volume`

## Info Boundary

Instrument grouping is derived from `source_file` filename only.

## Failure Modes

Price level and liquidity can dominate the raw cross section.

## Expected Risks

The factor can overlap with size, liquidity, and event-driven bursts.
