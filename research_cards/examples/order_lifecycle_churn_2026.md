+++
card_id = "rc_20260329_order_lifecycle_churn_2026"
name = "Order Lifecycle Churn 2026"
owner = "codex"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["order_lifecycle_shape_by_event_count"]
required_fields = ["date", "source_file", "OrderId", "Price", "Volume"]
hypothesis = "Instruments with higher order-event churn per unique order may proxy for contested liquidity and short-horizon positioning pressure."
mechanism = "Repeated structural updates around the same project-level OrderId can indicate more intense order-book negotiation without assuming unverified event semantics."
info_boundary = "Uses only verified structural order fields plus a file-derived instrument key extracted from source_file. It relies on project-level OrderId lifecycle shape, not official native identity claims."
failure_modes = ["Lifecycle churn is only a liquidity proxy.", "The signal is dominated by a few active ETFs or large caps.", "Project-level OrderId structure is insufficiently distinct cross-sectionally."]
expected_risks = ["Liquidity overlap.", "Turnover overlap.", "ETF concentration."]

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

High order lifecycle churn may reflect stronger competition for liquidity.

## Mechanism

The factor uses event counts per project-level `OrderId`, not event-type labels.

## Holding Horizon

Thirty minutes to one day.

## Required Fields

`date`, `source_file`, `OrderId`, `Price`, `Volume`

## Info Boundary

No `OrderType`, `TradeDir`, `BrokerNo`, queue, or vendor-code semantics.

## Failure Modes

The effect can collapse into a plain activity or liquidity exposure.

## Expected Risks

Main risks are overlap with turnover-heavy names and ETF concentration.
