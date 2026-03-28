+++
card_id = "rc_20260329_close_vwap_gap_intensity_2026"
name = "Close VWAP Gap Intensity 2026"
owner = "codex"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["matched_edge_session_profile"]
required_fields = ["date", "source_file", "Time", "row_num_in_file", "Price", "Volume"]
hypothesis = "An end-of-day close-like print that sits materially above or below same-day VWAP may proxy for unresolved pressure that can carry into the next session."
mechanism = "A persistent intraday gap between the last observed trade and volume-weighted average price can reflect imbalance or urgency without relying on blocked queue or side semantics."
info_boundary = "Uses only verified trade fields, file-derived instrument grouping, last observed trade price by Time plus row_num_in_file, and same-day VWAP."
failure_modes = ["The signal is only a noisy closing print artifact.", "Gap intensity is dominated by event-driven names.", "Any edge vanishes once sign is normalized or re-centered."]
expected_risks = ["Close auction contamination.", "Large-cap concentration.", "Short-horizon reversal noise."]

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

Study whether a same-day close-to-VWAP gap carries short-horizon information.

## Mechanism

The idea compares the last observed trade price with same-day VWAP and scales it
by trade activity.

## Holding Horizon

Thirty minutes to one day.

## Required Fields

`date`, `source_file`, `Time`, `row_num_in_file`, `Price`, `Volume`

## Info Boundary

No `TradeDir`, `BrokerNo`, queue, or vendor-code semantics.

## Failure Modes

The signal can collapse into noisy close prints or event contamination.

## Expected Risks

Main risks are close-print noise, event concentration, and reversal.
