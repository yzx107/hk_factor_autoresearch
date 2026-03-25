+++
card_id = "rc_20260326_queue_precision_2025"
name = "Queue Precision 2025"
owner = "codex"
status = "draft"
years = ["2025"]
universe = "phase_a_core"
holding_horizon = "seconds"
research_modules = ["queue_position_or_depletion", "precise_order_to_trade_lag"]
required_fields = ["SeqNum", "OrderId", "Time", "Level", "VolumePre"]
hypothesis = "Queue depletion and precise lag in 2025 predict immediate returns."
mechanism = "Infer strict queue order and precise latency from 2025 order records."
info_boundary = "Attempts to use blocked queue and precise timing semantics."
failure_modes = ["Timing anchor is not available in 2025."]
expected_risks = ["Hard admissibility violation.", "Queue semantics not verified."]

[timing]
mode = "fine_ok"
uses_precise_lag = true
uses_strict_ordering = true
uses_queue_semantics = true

[semantics]
TradeDir = "unused"
BrokerNo = "unused"
OrderType = "unused"
Level = "queue_semantics"
VolumePre = "queue_semantics"
Type = "unused"
Ext = "unused"
+++

## Hypothesis

This card intentionally violates the 2025 timing boundary.

## Mechanism

It assumes queue order and fine lag that are not admissible.

## Holding Horizon

Seconds.

## Required Fields

`SeqNum`, `OrderId`, `Time`, `Level`, `VolumePre`

## Info Boundary

This is an invalid example for smoke testing.

## Failure Modes

The anchor is not present in 2025.

## Expected Risks

Hard timing and semantic failure.
