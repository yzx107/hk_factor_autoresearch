+++
card_id = "rc_20260329_structural_activity_proxy_2026"
name = "Structural Activity Proxy 2026"
owner = "codex"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["TickID", "Time", "Price", "Volume"]
hypothesis = "High intraday activity concentration may proxy for short-horizon attention and carry over into later intraday or next-day moves."
mechanism = "Unusually concentrated price-volume activity may capture temporary information arrival or inventory pressure without relying on blocked field semantics."
info_boundary = "Uses only structural trade fields already admitted by the upstream verified boundary."
failure_modes = ["Signal is only a size or liquidity proxy.", "Activity spikes are event pollution and do not persist.", "Cross-sectional effect vanishes after normalization."]
expected_risks = ["Attention proxy overlap.", "Event contamination.", "High-turnover decay."]

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

Study a safe structural activity proxy before moving to caveated microstructure
signals.

## Mechanism

The idea uses only verified structural trade fields.

## Holding Horizon

Thirty minutes to one day.

## Required Fields

`TickID`, `Time`, `Price`, `Volume`

## Info Boundary

No `TradeDir`, `BrokerNo`, queue, or vendor-code semantics.

## Failure Modes

The effect may collapse after normalization or event controls.

## Expected Risks

Main risks are liquidity/style overlap and event contamination.
