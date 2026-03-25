+++
card_id = "rc_20260326_brokerno_direct_alpha"
name = "BrokerNo Direct Alpha"
owner = "codex"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["matched_edge_session_profile"]
required_fields = ["Time", "Price", "Volume", "BrokerNo"]
hypothesis = "Specific broker seats predict next-period returns."
mechanism = "Use BrokerNo as direct alpha input."
info_boundary = "Attempts to turn BrokerNo into direct broker alpha."
failure_modes = ["Identity ambiguity invalidates the signal."]
expected_risks = ["Semantic overclaim.", "Lookup coverage gaps.", "Vendor export mismatch."]

[timing]
mode = "coarse_only"
uses_precise_lag = false
uses_strict_ordering = false
uses_queue_semantics = false

[semantics]
TradeDir = "unused"
BrokerNo = "direct_alpha"
OrderType = "unused"
Level = "unused"
VolumePre = "unused"
Type = "unused"
Ext = "unused"
+++

## Hypothesis

This card intentionally violates the broker boundary.

## Mechanism

It treats BrokerNo as if official identity were already confirmed.

## Holding Horizon

Thirty minutes to one day.

## Required Fields

`BrokerNo`, `Time`, `Price`, `Volume`

## Info Boundary

This is an invalid example for smoke testing.

## Failure Modes

The field meaning is not verified.

## Expected Risks

Direct broker alpha is outside current admissibility.
