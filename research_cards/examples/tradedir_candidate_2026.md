+++
card_id = "rc_20260326_tradedir_candidate_2026"
name = "TradeDir Candidate Contrast 2026"
owner = "codex"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "5m_to_30m"
research_modules = ["trade_dir_candidate_signal_profile"]
required_fields = ["TickID", "Time", "Price", "Volume", "TradeDir"]
hypothesis = "A caveated TradeDir contrast may carry weak short-horizon directional information in 2026."
mechanism = "Vendor direction codes may correlate with short-horizon flow imbalance, but they are not signed-side truth."
info_boundary = "Uses upstream admissibility outputs. TradeDir is treated only as a candidate directional signal under manual review."
failure_modes = ["Contrast disappears after costs.", "Signal is only event pollution.", "Vendor direction semantics drift."]
expected_risks = ["Manual review required.", "Not signed-flow truth.", "May be a vendor export artifact."]

[timing]
mode = "fine_ok"
uses_precise_lag = false
uses_strict_ordering = false
uses_queue_semantics = false

[semantics]
TradeDir = "candidate_directional_signal"
BrokerNo = "unused"
OrderType = "unused"
Level = "unused"
VolumePre = "unused"
Type = "unused"
Ext = "unused"
+++

## Hypothesis

Study whether the 2026 TradeDir contrast has weak predictive value after a
short hold.

## Mechanism

Treat the code as a vendor-defined candidate direction proxy only.

## Holding Horizon

Five to thirty minutes.

## Required Fields

`TickID`, `Time`, `Price`, `Volume`, `TradeDir`

## Info Boundary

No signed-side truth claim. No queue or latency semantics.

## Failure Modes

The observed contrast may be non-causal or may vanish after frictions.

## Expected Risks

Strong vendor-semantic caveat.
